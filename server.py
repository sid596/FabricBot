import threading
import traceback
from collections import deque

from flask import Flask, request
from ai import understand
from quotation import calculate_curtain_quote, QuotationInput
from search import search_fabric
from whatsapp import send_message
from images import download_image
from vision import extract_code
from quotation import load_config
from decimal import Decimal

app = Flask(__name__)

quote_config = load_config("config.json")
VERIFY_TOKEN = "fabricbot123"

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

        reply = ""
        if result["intent"] == "price_lookup":
            matches = search_fabric(result["fabric"])
            print("Matches:", matches)
            if matches:
                for fabric in matches:
                    reply += (
                        f"Album: {fabric['album']}\n"
                        f"Quality: {fabric['quality']}\n"
                        f"Price: ₹{fabric['price']}/m\n"
                        f"Width: {fabric['width']} inches\n\n"
                    )
            else:
                reply = "Sorry, I couldn't find that fabric."

        elif result["intent"] == "quotation":
            if result["height"] is None or result["width"] is None:
                reply = "Please provide the window height and width."
            else:
                order_type = result["order_type"] or "full"
                fabric = None

                if order_type != "track_only":
                    if result["fabric"] is not None:
                        matches = search_fabric(result["fabric"])
                        if not matches:
                            reply = "Sorry, I couldn't find that fabric."
                        else:
                            fabric = matches[0]
                    elif result["fabric_price"] is not None:
                        DEFAULT_FABRIC_WIDTH = "48"
                        fabric = {
                            "price": result["fabric_price"],
                            "width": DEFAULT_FABRIC_WIDTH,
                        }
                    else:
                        reply = "Please provide the fabric name or the fabric price."

                if reply == "":
                    quote = calculate_curtain_quote(
                        QuotationInput(
                            fabric_width_inches=Decimal(
                                "0" if order_type == "track_only" else fabric["width"]
                            ),
                            track_type=result["track"] or "MTrack Premium",
                            curtain_style=(
                                ""
                                if order_type == "track_only"
                                else (result["curtain_style"] or "Pleated")
                            ),
                            height_inches=Decimal(result["height"]),
                            width_inches=Decimal(result["width"]),
                            fabric_price_per_meter=Decimal(
                                "0" if order_type == "track_only" else fabric["price"]
                            ),
                            order_type=order_type,
                        ),
                        quote_config,
                    )
                    reply = (
                        f"Quotation\n\n"
                        f"Fabric: ₹{quote.total_fabric_cost}\n"
                        f"Track: ₹{quote.total_track_cost}\n"
                        f"Stitching: ₹{quote.total_stitching_cost}\n"
                        f"Fitting: ₹{quote.fitting_charges}\n"
                        f"GST: ₹{quote.gst_total}\n\n"
                        f"Grand Total: ₹{quote.grand_total}"
                    )
        else:
            reply = "Sorry, I didn't understand your request."

        send_message(phone, reply)

    except Exception:
        traceback.print_exc()