import threading
import traceback
from collections import deque

from flask import Flask, request
from ai import understand
from quotation import (
    calculate_curtain_quote,
    calculate_multi_line_quotation,
    calculate_multi_blind_quotation,
    QuotationInput,
    BlindQuotationInput,
    LineQuoteLabel,
)
from search import search_fabric
from whatsapp import send_message, send_typing_indicator
from images import download_image
from vision import extract_code, extract_visual_content
from quotation import load_config
from decimal import Decimal

app = Flask(__name__)

quote_config = load_config("config.json")
VERIFY_TOKEN = "fabricbot123"


def _line_label(item):
    """Readable label for a curtain or blind line item."""
    product_type = item.get("curtain_type") or item.get("blind_type")

    parts = [
        item.get("room"),
        item.get("window"),
        product_type,
    ]
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

        if message_id:
            try:
                send_typing_indicator(message_id)
            except Exception:
                # Never let a typing-indicator failure block the actual
                # reply -- this is purely cosmetic.
                traceback.print_exc()

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
        fabric_name = result.get("fabric")
        print(f"Price lookup for fabric: {fabric_name}")
        
        if not fabric_name:
            return "Please specify which fabric you'd like the price for."
        
        matches = search_fabric(fabric_name)
        print("Matches found:", len(matches) if matches else 0)
        
        if not matches:
            return f"Sorry, I couldn't find '{fabric_name}' in our catalogue."
        
        if len(matches) == 1:
            fabric = matches[0]
            return (
                f"*{fabric_name}*\n\n"
                f"Album: {fabric.get('album', 'N/A')}\n"
                f"Quality: {fabric.get('quality', 'N/A')}\n"
                f"Price: ₹{fabric.get('price', 'N/A')}/meter\n"
                f"Width: {fabric.get('width', 'N/A')} inches"
            )
        else:
            # Multiple matches
            reply = f"Found {len(matches)} options for '{fabric_name}':\n\n"
            for i, fabric in enumerate(matches[:3], 1):
                reply += (
                    f"{i}. {fabric.get('album', 'N/A')} - {fabric.get('quality', 'N/A')}\n"
                    f"   Price: ₹{fabric.get('price', 'N/A')}/m | Width: {fabric.get('width', 'N/A')}\" \n\n"
                )
            return reply

    elif result["intent"] == "quotation":
        line_items = result.get("line_items") or []

        if not line_items:
            return "Please describe what you'd like a quotation for."

        # ---------------------------------------------------------
        # DISCOUNTS
        # ---------------------------------------------------------

        fabric_discount_percent = result.get("fabric_discount_percent") or 0
        track_discount_percent = result.get("track_discount_percent") or 0
        stitching_discount_percent = result.get("stitching_discount_percent") or 0

        # ---------------------------------------------------------
        # SEPARATE CURTAIN AND BLIND LINE ITEMS
        # ---------------------------------------------------------

        curtain_items = []
        blind_items = []

        for item in line_items:
            if item.get("blind_type"):
                blind_items.append(item)
            else:
                curtain_items.append(item)

        # ---------------------------------------------------------
        # CURTAIN LINES
        # ---------------------------------------------------------

        curtain_resolved = []
        assumed_defaults = []
        errors = []

        for item in curtain_items:
            label_text = _line_label(item)
            order_type = item.get("order_type") or "full"

            # We still need dimensions for an actual calculation.
            # Do not ask conversationally; simply report the affected
            # line(s) if the information is genuinely unavailable.
            if order_type == "track_only":
                if item.get("width") is None:
                    errors.append(
                        f"Missing width for {label_text}."
                    )
                    continue
            else:
                if item.get("height") is None or item.get("width") is None:
                    errors.append(
                        f"Missing height/width for {label_text}."
                    )
                    continue

            fabric = None

            if order_type != "track_only":
                has_fabric = item.get("fabric") is not None
                has_price = item.get("fabric_price") is not None

                if has_fabric and has_price:
                    # Negotiated rate: use the supplied price but look
                    # up the catalogue fabric width.
                    matches = search_fabric(item["fabric"])

                    if not matches:
                        errors.append(
                            f"Sorry, I couldn't find fabric "
                            f"'{item['fabric']}' for {label_text}."
                        )
                        continue

                    fabric = {
                        "price": item["fabric_price"],
                        "width": matches[0]["width"],
                    }

                elif has_fabric:
                    matches = search_fabric(item["fabric"])

                    if not matches:
                        errors.append(
                            f"Sorry, I couldn't find fabric "
                            f"'{item['fabric']}' for {label_text}."
                        )
                        continue

                    fabric = matches[0]

                elif has_price:
                    # No fabric name means catalogue width is unknown.
                    fabric = {
                        "price": item["fabric_price"],
                        "width": "48",
                    }

                else:
                    # Default curtain fabric price.
                    fabric = {
                        "price": "590",
                        "width": "48",
                    }

                    assumed_defaults.append(
                        f"Assumed default fabric price of ₹590/m "
                        f"for {label_text}."
                    )

            label = LineQuoteLabel(
                room=item.get("room"),
                window=item.get("window"),
                curtain_type=item.get("curtain_type"),
            )

            quotation_input = QuotationInput(
                fabric_width_inches=Decimal(
                    "0"
                    if order_type == "track_only"
                    else fabric["width"]
                ),
                track_type=item.get("track") or "MTrack Premium",
                curtain_style=(
                    ""
                    if order_type == "track_only"
                    else (item.get("curtain_style") or "Pleated")
                ),
                height_inches=Decimal(
                    item["height"]
                    if item.get("height") is not None
                    else 0
                ),
                width_inches=Decimal(item["width"]),
                fabric_price_per_meter=Decimal(
                    "0"
                    if order_type == "track_only"
                    else str(fabric["price"])
                ),
                order_type=order_type,
                fabric_discount_percent=Decimal(
                    str(fabric_discount_percent)
                ),
                track_discount_percent=Decimal(
                    str(track_discount_percent)
                ),
                stitching_discount_percent=Decimal(
                    str(stitching_discount_percent)
                ),
            )

            curtain_resolved.append((label, quotation_input))

        # ---------------------------------------------------------
        # BLIND LINES
        # ---------------------------------------------------------

        blind_resolved = []

        for item in blind_items:
            label_text = _line_label(item)

            # A blind type is required because each blind type has
            # different pricing.
            blind_type = item.get("blind_type")

            if not blind_type:
                errors.append(
                    f"Blind type could not be determined for {label_text}."
                )
                continue

            # Dimensions are required for blind area calculation.
            if item.get("height") is None or item.get("width") is None:
                errors.append(
                    f"Missing height/width for {label_text}."
                )
                continue

            # Only Roman blinds use fabric.
            fabric_price_per_meter = None

            if blind_type.lower() == "roman":
                if item.get("fabric_price") is not None:
                    fabric_price_per_meter = Decimal(
                        str(item["fabric_price"])
                    )

                elif item.get("fabric"):
                    matches = search_fabric(item["fabric"])

                    if not matches:
                        errors.append(
                            f"Sorry, I couldn't find fabric "
                            f"'{item['fabric']}' for {label_text}."
                        )
                        continue

                    fabric_price_per_meter = Decimal(
                        str(matches[0]["price"])
                    )

                else:
                    # Roman blinds genuinely require a fabric price
                    # because their calculator includes fabric cost.
                    errors.append(
                        f"Roman blind fabric price is required for "
                        f"{label_text}."
                    )
                    continue

            # The calculator defaults roller pelmet to True.
            # If Gemini returned null because the customer didn't
            # mention it, apply the business default here.
            with_pelmet = item.get("with_pelmet")

            if with_pelmet is None:
                with_pelmet = True

            label = LineQuoteLabel(
                room=item.get("room"),
                window=item.get("window"),
                # LineQuoteLabel has no blind_type field, so use the
                # product type here purely for display.
                curtain_type=blind_type.title(),
            )

            blind_input = BlindQuotationInput(
                blind_type=blind_type,
                height_inches=Decimal(item["height"]),
                width_inches=Decimal(item["width"]),
                with_pelmet=with_pelmet,
                fabric_price_per_meter=fabric_price_per_meter,
                fabric_discount_percent=Decimal(
                    str(fabric_discount_percent)
                ),
            )

            blind_resolved.append((label, blind_input))

        # ---------------------------------------------------------
        # RETURN EXTRACTION/CALCULATION ERRORS
        # ---------------------------------------------------------

        if errors:
            return "\n".join(errors)

        # ---------------------------------------------------------
        # CALCULATE CURTAINS
        # ---------------------------------------------------------

        curtain_multi = None

        if curtain_resolved:
            curtain_multi = calculate_multi_line_quotation(
                curtain_resolved,
                quote_config,
            )

        # ---------------------------------------------------------
        # CALCULATE BLINDS
        # ---------------------------------------------------------

        blind_multi = None

        if blind_resolved:
            blind_multi = calculate_multi_blind_quotation(
                blind_resolved,
                quote_config,
            )

        # ---------------------------------------------------------
        # BUILD RESPONSE
        # ---------------------------------------------------------

        parts = []

        # -------------------------
        # CURTAIN RESULTS
        # -------------------------

        if curtain_multi:
            for label, line_result in zip(
                curtain_multi.line_labels,
                curtain_multi.line_results,
            ):
                parts.append(
                    f"*{_format_label(label)}*\n"
                    f"  Fabric: ₹{line_result.total_fabric_cost:,.0f}\n"
                    f"  Track: ₹{line_result.total_track_cost:,.0f}\n"
                    f"  Stitching: ₹{line_result.total_stitching_cost:,.0f}\n"
                    f"  Fitting: ₹{line_result.fitting_charges:,.0f}\n"
                    f"  GST: ₹{line_result.gst_total:,.0f}\n"
                    f"  Line Total: ₹{line_result.grand_total:,.0f}"
                )

        # -------------------------
        # BLIND RESULTS
        # -------------------------

        if blind_multi:
            for label, line_result in zip(
                blind_multi.line_labels,
                blind_multi.line_results,
            ):
                parts.append(
                    f"*{_format_label(label)}*\n"
                    f"  Blind: {line_result.blind_type.title()}\n"
                    f"  Area: {line_result.area_sqft:.2f} sq ft\n"
                    f"  Rate: ₹{line_result.rate_per_sqft:,.0f}/sq ft\n"
                    f"  Blind Cost: ₹{line_result.area_cost:,.0f}\n"
                    f"  Fabric: ₹{line_result.fabric_cost:,.0f}\n"
                    f"  Fitting: ₹{line_result.fitting_charges:,.0f}\n"
                    f"  GST: ₹{line_result.gst_total:,.0f}\n"
                    f"  Line Total: ₹{line_result.grand_total:,.0f}"
                )

        # ---------------------------------------------------------
        # GRAND TOTALS
        # ---------------------------------------------------------

        total_fabric = 0
        total_track = 0
        total_stitching = 0
        total_fitting = 0
        total_gst = 0
        grand_total = 0

        if curtain_multi:
            total_fabric += curtain_multi.total_fabric_cost
            total_track += curtain_multi.total_track_cost
            total_stitching += curtain_multi.total_stitching_cost
            total_fitting += curtain_multi.total_fitting_charges
            total_gst += curtain_multi.total_gst
            grand_total += curtain_multi.grand_total

        if blind_multi:
            # Blind area cost is effectively the blind's product cost.
            total_fabric += blind_multi.total_area_cost
            total_fabric += blind_multi.total_fabric_cost
            total_fitting += blind_multi.total_fitting_charges
            total_gst += blind_multi.total_gst
            grand_total += blind_multi.grand_total

        # If there was exactly one line, keep the response compact.
        if len(line_items) == 1 and len(parts) == 1:
            return (
                "*QUOTATION*\n\n"
                f"{parts[0]}\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"*GRAND TOTAL: ₹{grand_total:,.0f}*"
            )

        # Multiple line items.
        reply = (
            "*QUOTATION*\n\n"
            + "\n\n".join(parts)
            + "\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Total Fabric / Blind Cost: ₹{total_fabric:,.0f}\n"
            f"Total Track: ₹{total_track:,.0f}\n"
            f"Total Stitching: ₹{total_stitching:,.0f}\n"
            f"Total Fitting: ₹{total_fitting:,.0f}\n"
            f"Total GST: ₹{total_gst:,.0f}\n\n"
            f"*GRAND TOTAL: ₹{grand_total:,.0f}*"
        )

        if assumed_defaults:
            reply += "\n\n" + "\n".join(assumed_defaults)

        return reply

    else:
        intent = result.get("intent", "unknown")
        print(f"WARNING: Unrecognized intent: {intent}")
        print(f"Full result: {result}")
        return (
            f"Sorry, I didn't understand that request. "
            f"Could you please:\n\n"
            f"1. Ask for a *fabric price* (e.g., 'Luna')\n"
            f"2. Request a *quotation* with dimensions (e.g., '71x65 Luna')"
        )


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
    interim_timer = None
    try:
        value = data["entry"][0]["changes"][0]["value"]
        message_data = value["messages"][0]

        phone = message_data["from"]
        message_type = message_data["type"]

        print(f"Phone: {phone}")
        print(f"Message Type: {message_type}")

        # WhatsApp's native typing bubble (triggered earlier, in the fast
        # webhook route) lasts at most ~25s. If we're still working once
        # it would have expired, THAT's when the customer needs a text
        # message telling them we're still on it -- not immediately,
        # since that falsely implies every request is a big one, and not
        # never, since the bubble disappearing with no follow-up looks
        # exactly like a crash.
        interim_timer = threading.Timer(
            25.0,
            lambda: send_message(
                phone,
                "⏳ Still working on it, I'll reply shortly.",
            ),
        )
        interim_timer.daemon = True
        interim_timer.start()

        try:
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
                        "Sorry, I couldn't tell what that photo was. Please "
                        "send a clear photo of a product tag, or of your "
                        "requirements note.",
                    )
                    return

            # -----------------------------
            # UNSUPPORTED MESSAGE TYPE
            # -----------------------------
            else:
                print("Unsupported message type.")
                send_message(
                    phone,
                    "Sorry, I currently only support text messages and "
                    "photos of product codes.",
                )
                return

            result = understand(message)
            print(f"[PARSED INTENT] {result.get('intent', 'unknown')}")
            print(f"[FULL RESULT] {result}")

            reply = build_reply(result, quote_config)
            print(f"[REPLY LENGTH] {len(reply)} characters")
            send_message(phone, reply)

        finally:
            # Whatever happened -- fast reply, slow reply, or an early
            # return above -- the countdown is no longer relevant.
            interim_timer.cancel()

    except Exception:
        traceback.print_exc()
        try:
            phone = data["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
            send_message(
                phone,
                "Sorry, something went wrong on my end while working on "
                "that. Please try again -- if it's a large quotation, "
                "try splitting it into two messages.",
            )
        except Exception:
            # If we can't even figure out who to reply to, or sending
            # itself fails, there's nothing more we can do here --
            # this is already inside the top-level error handler.
            traceback.print_exc()