import threading
import traceback
from collections import deque

from flask import Flask, request
from ai import understand
from quotation import (
    calculate_curtain_quote,
    calculate_multi_line_quotation,
    QuotationInput,
    LineQuoteLabel,
)
from search import search_fabric
from whatsapp import send_message
from images import download_image
from vision import extract_code
from quotation import load_config
from decimal import Decimal

app = Flask(__name__)

quote_config = load_config("config.json")
VERIFY_TOKEN = "fabricbot123"


def _line_label(item):
    """Readable label for a line item dict, e.g. 'MBR / Balcony / Sheer'."""
    parts = [item.get("room"), item.get("window"), item.get("curtain_type")]
    parts = [p for p in parts if p]
    return " / ".join(parts) if parts else "your quotation"


def _format_label(label: LineQuoteLabel):
    parts = [label.room, label.window, label.curtain_type]
    parts = [p for p in parts if p]
    return " / ".join(parts) if parts else "Quotation"

# -----------------------------------------------------------------
# Dedupe: WhatsApp resends the same message if it doesn't get a fast
# 200 back. We ack immediately now (see below), so this is a safety
# net for retries that were already in flight before that took effect.
# In-memory only -> resets on restart, which is fine at this scale.
# -----------------------------------------------------------------
_seen_ids = set()
_seen_order = deque(maxlen=2000)
_dedupe_lock = threading.Lock()


def _already_processed(message_id):
    with _dedupe_lock:
        if message_id in _seen_ids:
            return True
        _seen_ids.add(message_id)
        _seen_order.append(message_id)
        if len(_seen_order) == _seen_order.maxlen:
            oldest = _seen_order.popleft()
            _seen_ids.discard(oldest)
        return False


@app.route("/")
def home():
    return "FabricBot is running!"


@app.route("/webhook", methods=["POST", "GET"])
def webhook():
    if request.method == "GET":
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if token == VERIFY_TOKEN:
            return challenge, 200

        return "Verification failed", 403

    data = request.json
    print("========== WEBHOOK ==========")
    print(data)

    try:
        value = data["entry"][0]["changes"][0]["value"]

        if "messages" not in value:
            return "OK", 200

        message_data = value["messages"][0]
        message_id = message_data.get("id")

        if message_id and _already_processed(message_id):
            print(f"Duplicate delivery ignored: {message_id}")
            return "OK", 200

    except Exception:
        traceback.print_exc()
        return "ERROR", 500

    # Ack WhatsApp immediately. Everything slow (OCR, Gemini, the
    # WhatsApp send call) happens after this, in the background, so
    # Meta's own webhook timeout never has a chance to fire and
    # trigger a duplicate delivery.
    threading.Thread(target=process_message, args=(data,), daemon=True).start()
    return "OK", 200


def build_reply(result, quote_config):
    """Given ai.py's parsed result, build the WhatsApp reply text.
    Pulled out of process_message() so it can be unit tested without
    needing a live webhook or a live Gemini call."""

    if result["intent"] == "price_lookup":
        matches = search_fabric(result["fabric"])
        print("Matches:", matches)
        if not matches:
            return "Sorry, I couldn't find that fabric."
        reply = ""
        for fabric in matches:
            reply += (
                f"Album: {fabric['album']}\n"
                f"Quality: {fabric['quality']}\n"
                f"Price: ₹{fabric['price']}/m\n"
                f"Width: {fabric['width']} inches\n\n"
            )
        return reply

    elif result["intent"] == "quotation":
        line_items = result.get("line_items") or []

        if not line_items:
            return "Please describe what you'd like a quotation for."

        # Pass 1: every line item needs dimensions before we do
        # anything else -- ask for all of them at once rather
        # than one room at a time.
        missing = [
            f"Missing height/width for {_line_label(item)}."
            for item in line_items
            if item.get("height") is None or item.get("width") is None
        ]

        if missing:
            return "\n".join(missing)

        resolved = []  # list of (LineQuoteLabel, QuotationInput)

        for item in line_items:
            label_text = _line_label(item)
            order_type = item.get("order_type") or "full"
            fabric = None

            if order_type != "track_only":
                if item.get("fabric") is not None:
                    matches = search_fabric(item["fabric"])
                    if not matches:
                        missing.append(
                            f"Sorry, I couldn't find fabric "
                            f"'{item['fabric']}' for {label_text}."
                        )
                        continue
                    fabric = matches[0]
                elif item.get("fabric_price") is not None:
                    DEFAULT_FABRIC_WIDTH = "48"
                    fabric = {
                        "price": item["fabric_price"],
                        "width": DEFAULT_FABRIC_WIDTH,
                    }
                else:
                    missing.append(
                        f"Please provide the fabric name or "
                        f"fabric price for {label_text}."
                    )
                    continue

            label = LineQuoteLabel(
                room=item.get("room"),
                window=item.get("window"),
                curtain_type=item.get("curtain_type"),
            )
            quotation_input = QuotationInput(
                fabric_width_inches=Decimal(
                    "0" if order_type == "track_only" else fabric["width"]
                ),
                track_type=item.get("track") or "MTrack Premium",
                curtain_style=(
                    ""
                    if order_type == "track_only"
                    else (item.get("curtain_style") or "Pleated")
                ),
                height_inches=Decimal(item["height"]),
                width_inches=Decimal(item["width"]),
                fabric_price_per_meter=Decimal(
                    "0" if order_type == "track_only" else str(fabric["price"])
                ),
                order_type=order_type,
            )
            resolved.append((label, quotation_input))

        if missing:
            return "\n".join(missing)

        multi = calculate_multi_line_quotation(resolved, quote_config)

        if len(multi.line_results) == 1:
            r = multi.line_results[0]
            return (
                f"Quotation\n\n"
                f"Fabric: ₹{r.total_fabric_cost}\n"
                f"Track: ₹{r.total_track_cost}\n"
                f"Stitching: ₹{r.total_stitching_cost}\n"
                f"Fitting: ₹{r.fitting_charges}\n"
                f"GST: ₹{r.gst_total}\n\n"
                f"Grand Total: ₹{r.grand_total}"
            )

        parts = []
        for label, line_result in zip(multi.line_labels, multi.line_results):
            parts.append(
                f"{_format_label(label)}\n"
                f"  Fabric: ₹{line_result.total_fabric_cost}\n"
                f"  Track: ₹{line_result.total_track_cost}\n"
                f"  Stitching: ₹{line_result.total_stitching_cost}\n"
                f"  Fitting: ₹{line_result.fitting_charges}\n"
                f"  GST: ₹{line_result.gst_total}\n"
                f"  Line Total: ₹{line_result.grand_total}"
            )
        parts.append(
            "— — —\n"
            f"Total Fabric: ₹{multi.total_fabric_cost}\n"
            f"Total Track: ₹{multi.total_track_cost}\n"
            f"Total Stitching: ₹{multi.total_stitching_cost}\n"
            f"Total Fitting: ₹{multi.total_fitting_charges}\n"
            f"Total GST: ₹{multi.total_gst}\n\n"
            f"Grand Total: ₹{multi.grand_total}"
        )
        return "Quotation\n\n" + "\n\n".join(parts)

    else:
        return "Sorry, I didn't understand your request."


def process_message(data):
    try:
        value = data["entry"][0]["changes"][0]["value"]
        message_data = value["messages"][0]

        phone = message_data["from"]
        message_type = message_data["type"]

        print(f"Phone: {phone}")
        print(f"Message Type: {message_type}")

        # -----------------------------
        # TEXT MESSAGE
        # -----------------------------
        if message_type == "text":
            message = message_data["text"]["body"]

        # -----------------------------
        # IMAGE MESSAGE
        # -----------------------------
        elif message_type == "image":
            image_id = message_data["image"]["id"]
            print(f"Image ID: {image_id}")

            image_path = download_image(image_id)
            result = extract_code(image_path)
            app.logger.info(result)

            message = result["code"]
            print(message)

        # -----------------------------
        # UNSUPPORTED MESSAGE TYPE
        # -----------------------------
        else:
            print("Unsupported message type.")
            send_message(
                phone,
                "Sorry, I currently only support text messages and photos of "
                "product codes.",
            )
            return

        result = understand(message)
        print(result)

        reply = build_reply(result, quote_config)
        send_message(phone, reply)

    except Exception:
        traceback.print_exc()