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
from vision import extract_code, extract_visual_content
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

def _default_fabric(item, calculation):
    """Return configured fallback fabric values for a quotation line item."""
    curtain_type = (item.get("curtain_type") or "").casefold()

    price_key = (
        "default_sheer_fabric_price_per_meter"
        if "sheer" in curtain_type
        else "default_main_fabric_price_per_meter"
    )

    return {
        "price": calculation[price_key],
        "width": calculation["default_fabric_width_inches"],
    }

def _resolve_fabric(item, calculation, label_text):
    """Resolve catalogue data or return safe configured defaults."""
    has_fabric = item.get("fabric") is not None
    has_price = item.get("fabric_price") is not None

    if has_fabric and has_price:
        matches = search_fabric(item["fabric"])
        width = (
            matches[0]["width"]
            if matches
            else calculation["default_fabric_width_inches"]
        )
        note = None if matches else (
            f"Used the default fabric width for {label_text} because "
            f"'{item['fabric']}' was not found."
        )
        return {"price": item["fabric_price"], "width": width}, note

    if has_fabric:
        matches = search_fabric(item["fabric"])
        if matches:
            return matches[0], None

        fabric = _default_fabric(item, calculation)
        return fabric, (
            f"Used the default fabric price for {label_text} because "
            f"'{item['fabric']}' was not found."
        )

    if has_price:
        return {
            "price": item["fabric_price"],
            "width": calculation["default_fabric_width_inches"],
        }, None

    fabric = _default_fabric(item, calculation)
    return fabric, (
        f"Used the default fabric price (₹{fabric['price']}/m) for "
        f"{label_text} — no fabric or price was given."
    )


def _resolve_line_item(item, calculation, discounts):
    """Convert one extracted line item into calculator input."""
    label = LineQuoteLabel(
        room=item.get("room"),
        window=item.get("window"),
        curtain_type=item.get("curtain_type"),
    )

    label_text = _line_label(item)
    order_type = item.get("order_type") or "full"
    note = None

    if order_type == "track_only":
        fabric = {"price": 0, "width": 0}
    else:
        fabric, note = _resolve_fabric(item, calculation, label_text)

    quotation_input = QuotationInput(
        fabric_width_inches=Decimal(str(fabric["width"])),
        track_type=item.get("track") or calculation["default_track"],
        curtain_style=(
            ""
            if order_type == "track_only"
            else item.get("curtain_style") or calculation["default_style"]
        ),
        height_inches=Decimal(str(item["height"])),
        width_inches=Decimal(str(item["width"])),
        fabric_price_per_meter=Decimal(str(fabric["price"])),
        order_type=order_type,
        fabric_discount_percent=Decimal(str(discounts["fabric"])),
        track_discount_percent=Decimal(str(discounts["track"])),
        stitching_discount_percent=Decimal(str(discounts["stitching"])),
    )

    return label, quotation_input, note


def _format_quote_section(label, quote, show_line_total):
    """Format one physical track as a polished WhatsApp quotation section."""
    title = _format_label(label)

    sections = [
        (
            f"🪟 *{title}*\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📐 *Window Details*\n"
            f"• Height: {quote.window_height_inches:.0f}\"\n"
            f"• Width: {quote.window_width_inches:.0f}\""
        )
    ]

    if quote.number_of_panels:
        sections.append(
            "🧵 *Fabric Details*\n"
            f"• Fabric Price: ₹{quote.fabric_price_per_meter:.0f}/m\n"
            f"• Fabric Width: {quote.fabric_width_inches:.0f}\"\n"
            f"• Curtain Style: {quote.curtain_style}\n"
            f"• Fullness: {quote.fullness:.1f}×"
        )

        sections.append(
            "📏 *Fabric Calculation*\n"
            f"• Panels Required: {quote.number_of_panels}\n"
            f"• Cut Length / Panel: {quote.raw_meters_per_panel:.2f} m\n"
            f"• Total Fabric Used: {quote.total_fabric_meters:.2f} m"
        )

    if quote.track_length_feet:
        sections.append(
            "🛤 *Track Details*\n"
            f"• Track: {quote.track_type}\n"
            f"• Track Length: {quote.track_length_feet:.1f} ft"
        )

    sections.append(
        "💰 *Cost Breakdown*\n"
        f"• Fabric: ₹{quote.total_fabric_cost}\n"
        f"• Track: ₹{quote.total_track_cost}\n"
        f"• Stitching: ₹{quote.total_stitching_cost}\n"
        f"• Fitting: ₹{quote.fitting_charges}\n"
        f"• GST: ₹{quote.gst_total}"
    )

    if show_line_total:
        sections.append(f"💵 *Line Total: ₹{quote.grand_total}*")

    return "\n\n".join(sections)


def _format_grand_total(multi):
    """Format all combined costs after every line item is shown."""
    return (
        "🏁 *Quotation Total*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"• Total Fabric: ₹{multi.total_fabric_cost}\n"
        f"• Total Track: ₹{multi.total_track_cost}\n"
        f"• Total Stitching: ₹{multi.total_stitching_cost}\n"
        f"• Total Fitting: ₹{multi.total_fitting_charges}\n"
        f"• Total GST: ₹{multi.total_gst}\n\n"
        f"💵 *Grand Total: ₹{multi.grand_total}*"
    )


def _format_quotation_reply(multi, default_notes):
    """Format single-line and multiline quotations consistently."""
    show_line_total = len(multi.line_results) > 1

    sections = [
        _format_quote_section(label, quote, show_line_total)
        for label, quote in zip(multi.line_labels, multi.line_results)
    ]

    sections.append(_format_grand_total(multi))

    reply = "🪟 *Curtain Quotation*\n\n" + "\n\n".join(sections)

    if default_notes:
        reply += "\n\nℹ️ " + "\n".join(default_notes)

    return reply

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
    """Build a WhatsApp reply from structured AI output."""

    if result["intent"] == "price_lookup":
        matches = search_fabric(result["fabric"])

        if not matches:
            return "Sorry, I couldn't find that fabric."

        return "\n\n".join(
            (
                f"Album: {fabric['album']}\n"
                f"Quality: {fabric['quality']}\n"
                f"Price: ₹{fabric['price']}/m\n"
                f"Width: {fabric['width']} inches"
            )
            for fabric in matches
        )

    if result["intent"] != "quotation":
        return "Sorry, I didn't understand your request."

    line_items = result.get("line_items") or []

    if not line_items:
        return "Please describe what you'd like a quotation for."

    missing_dimensions = [
        f"Missing height/width for {_line_label(item)}."
        for item in line_items
        if item.get("height") is None or item.get("width") is None
    ]

    if missing_dimensions:
        return "\n".join(missing_dimensions)

    calculation = quote_config["calculation"]
    discounts = {
        "fabric": result.get("fabric_discount_percent") or 0,
        "track": result.get("track_discount_percent") or 0,
        "stitching": result.get("stitching_discount_percent") or 0,
    }

    resolved_items = []
    default_notes = []

    for item in line_items:
        label, quotation_input, note = _resolve_line_item(
            item,
            calculation,
            discounts,
        )
        resolved_items.append((label, quotation_input))

        if note:
            default_notes.append(note)

    multi = calculate_multi_line_quotation(resolved_items, quote_config)

    return _format_quotation_reply(multi, default_notes)

def _format_item_for_review(item):
    """One readable line per extracted row, deliberately using the same
    phrasing style (room / window: type, HxW, fabric, track) that
    ai.py's LINE ITEMS prompt already parses reliably, so this reply
    can be sent straight back in as the quotation request."""
    location = " / ".join(p for p in [item.get("room"), item.get("window")] if p)
    if not location:
        location = "Item"

    bits = []
    if item.get("curtain_type"):
        bits.append(item["curtain_type"])

    if item.get("height") is not None and item.get("width") is not None:
        bits.append(f"{item['height']}x{item['width']}")
    elif item.get("height") is not None or item.get("width") is not None:
        h = item.get("height")
        w = item.get("width")
        bits.append(
            f"{h if h is not None else '?'}x{w if w is not None else '?'} "
            f"(one dimension unclear)"
        )
    else:
        bits.append("dimensions not legible")

    if item.get("order_type") == "track_only":
        bits.append("track only")
    elif item.get("fabric"):
        bits.append(item["fabric"])
    elif item.get("fabric_price") is not None:
        bits.append(f"fabric price {item['fabric_price']}")
    else:
        bits.append("fabric not legible")

    if item.get("track"):
        bits.append(item["track"])

    return f"{location}: {', '.join(bits)}"


def build_table_review_reply(line_items):
    if not line_items:
        return (
            "I couldn't clearly read any rows from that note. Could you "
            "resend a clearer photo, or type the details instead?"
        )

    body = "\n".join(_format_item_for_review(item) for item in line_items)
    return (
        "Here's what I read from your note:\n\n"
        f"{body}\n\n"
        "If that's correct, send this exact message back to me and I'll "
        "prepare the quotation. If anything's wrong or missing, fix it "
        "before sending it back."
    )


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
            visual = extract_visual_content(image_path)
            app.logger.info(visual)
            print(visual)

            if visual["content_type"] == "product_code":
                message = visual["code"]

            elif visual["content_type"] == "quotation_table":
                reply = build_table_review_reply(visual.get("line_items") or [])
                send_message(phone, reply)
                return

            else:
                send_message(
                    phone,
                    "Sorry, I couldn't tell what that photo was. Please send "
                    "a clear photo of a product tag, or of your requirements "
                    "note.",
                )
                return

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