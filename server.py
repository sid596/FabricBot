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
from whatsapp import send_message, send_typing_indicator
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

        # Pass 1: every line item needs dimensions before we do
        # anything else -- ask for all of them at once rather
        # than one room at a time.
        def _needs_dimensions(item):
            order_type = item.get("order_type") or "full"
            if order_type == "track_only":
                return item.get("width") is None
            return item.get("height") is None or item.get("width") is None

        missing = [
            (
                f"Missing width for {_line_label(item)}."
                if (item.get("order_type") or "full") == "track_only"
                else f"Missing height/width for {_line_label(item)}."
            )
            for item in line_items
            if _needs_dimensions(item)
        ]

        if missing:
            return "\n".join(missing)

        resolved = []  # list of (LineQuoteLabel, QuotationInput)
        assumed_defaults = []  # notices for silently-assumed values

        fabric_discount_percent = result.get("fabric_discount_percent") or 0
        track_discount_percent = result.get("track_discount_percent") or 0
        stitching_discount_percent = result.get("stitching_discount_percent") or 0

        for item in line_items:
            label_text = _line_label(item)
            order_type = item.get("order_type") or "full"
            fabric = None

            if order_type != "track_only":
                has_fabric = item.get("fabric") is not None
                has_price = item.get("fabric_price") is not None

                if has_fabric and has_price:
                    # Negotiated rate: look the fabric up for its real
                    # width (needed for meter calculations), but use
                    # the given price instead of the catalogue price,
                    # since it may differ from what's on file.
                    matches = search_fabric(item["fabric"])
                    if not matches:
                        missing.append(
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
                        missing.append(
                            f"Sorry, I couldn't find fabric "
                            f"'{item['fabric']}' for {label_text}."
                        )
                        continue
                    fabric = matches[0]
                elif has_price:
                    # No fabric name to look up -- width has to be
                    # assumed. This is the one case where we can't
                    # know the real width.
                    DEFAULT_FABRIC_WIDTH = "48"
                    fabric = {
                        "price": item["fabric_price"],
                        "width": DEFAULT_FABRIC_WIDTH,
                    }
                else:
                    # Nothing given at all -- assume a default price
                    # and width rather than blocking the quote. This
                    # is the one place we invent a number instead of
                    # asking; make sure the reply is explicit about it
                    # so nobody mistakes it for a real quoted fabric.
                    DEFAULT_FABRIC_PRICE = "590"
                    DEFAULT_FABRIC_WIDTH = "48"
                    fabric = {
                        "price": DEFAULT_FABRIC_PRICE,
                        "width": DEFAULT_FABRIC_WIDTH,
                    }
                    assumed_defaults.append(
                        f"Assumed default fabric price (₹{DEFAULT_FABRIC_PRICE}/m) "
                        f"for {label_text} -- no fabric or price was given."
                    )

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
                height_inches=Decimal(
                    item["height"] if item.get("height") is not None else 0
                ),
                width_inches=Decimal(item["width"]),
                fabric_price_per_meter=Decimal(
                    "0" if order_type == "track_only" else str(fabric["price"])
                ),
                order_type=order_type,
                fabric_discount_percent=Decimal(str(fabric_discount_percent)),
                track_discount_percent=Decimal(str(track_discount_percent)),
                stitching_discount_percent=Decimal(str(stitching_discount_percent)),
            )
            resolved.append((label, quotation_input))

        if missing:
            return "\n".join(missing)

        multi = calculate_multi_line_quotation(resolved, quote_config)
        defaults_note = (
            ("\n\n" + "\n".join(assumed_defaults)) if assumed_defaults else ""
        )

        # Build detailed summary for each line
        line_summaries = []
        for i, (original_item, label, line_result) in enumerate(zip(line_items, multi.line_labels, multi.line_results)):
            summary = f"*{_format_label(label)}*\n"
            
            # Check if this is a blind or curtain by looking for blind_type
            if original_item.get("blind_type"):
                # BLIND QUOTATION
                # Note: Blind quotation calculation not yet integrated in server.py
                # Currently showing the parsed blind info alongside the calculation
                blind_type = original_item.get("blind_type", "N/A").title()
                with_pelmet = original_item.get("with_pelmet")
                pelmet_text = ""
                if with_pelmet is not None:
                    pelmet_text = f" {'(With Pelmet)' if with_pelmet else '(No Pelmet)'}"
                
                summary += (
                    f"  Type: {blind_type} Blind{pelmet_text}\n"
                    f"  Dimensions: {original_item.get('height', '?')}\" × {original_item.get('width', '?')}\" \n"
                )
                
                # Add fabric details if fabric is specified (for roman blinds)
                if original_item.get("fabric"):
                    summary += f"  Fabric: {original_item.get('fabric')}\n"
                    if original_item.get("fabric_price"):
                        summary += f"  Fabric Price: ₹{original_item.get('fabric_price'):,.0f}/m\n"
                
                # Note: Blind mechanism cost calculation pending
                summary += (
                    f"  Mechanism Cost: [Pending blind calculation integration]\n"
                    f"  Fitting Charges: ₹{line_result.fitting_charges:,.0f}\n"
                    f"  GST (18%): ₹{line_result.gst_total:,.0f}\n"
                    f"  Line Total: ₹{line_result.grand_total:,.0f}"
                )
            else:
                # CURTAIN QUOTATION
                curtain_style = original_item.get("curtain_style") or "Pleated"
                order_type = original_item.get("order_type", "full")
                
                # Build curtain summary with all details
                summary += f"  Style: {curtain_style}\n"
                
                if order_type != "track_only":
                    # Include fabric details
                    panels = line_result.number_of_panels
                    meters_per_panel = line_result.meters_per_panel
                    total_meters = line_result.total_fabric_meters
                    fabric_price = line_result.fabric_price_per_meter
                    
                    summary += (
                        f"  Panels: {panels} × {meters_per_panel:.1f}m = {total_meters:.1f}m\n"
                        f"  Fabric Price Taken: ₹{fabric_price:,.0f}/m\n"
                        f"  Fabric Cost: ₹{line_result.total_fabric_cost:,.0f}\n"
                    )
                
                if order_type != "curtains_only":
                    # Include track details
                    track_type = original_item.get("track") or "MTrack Premium"
                    track_length = line_result.track_length_feet
                    
                    summary += (
                        f"  Track: {track_type}, {track_length:.1f}ft\n"
                        f"  Track Cost: ₹{line_result.total_track_cost:,.0f}\n"
                    )
                
                if order_type != "track_only":
                    summary += f"  Stitching Cost: ₹{line_result.total_stitching_cost:,.0f}\n"
                
                summary += (
                    f"  Fitting Charges: ₹{line_result.fitting_charges:,.0f}\n"
                    f"  GST (18%): ₹{line_result.gst_total:,.0f}\n"
                    f"  Line Total: ₹{line_result.grand_total:,.0f}"
                )
            
            line_summaries.append(summary)
        
        # Single line quotation
        if len(multi.line_results) == 1:
            return f"*QUOTATION*\n\n{line_summaries[0]}{defaults_note}"
        
        # Multi-line quotation
        parts = line_summaries
        parts.append(
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"*SUMMARY*\n"
            f"Total Fabric Cost: ₹{multi.total_fabric_cost:,.0f}\n"
            f"Total Track Cost: ₹{multi.total_track_cost:,.0f}\n"
            f"Total Stitching Cost: ₹{multi.total_stitching_cost:,.0f}\n"
            f"Total Fitting: ₹{multi.total_fitting_charges:,.0f}\n"
            f"Total GST (18%): ₹{multi.total_gst:,.0f}\n\n"
            f"*GRAND TOTAL: ₹{multi.grand_total:,.0f}*"
        )
        return "*QUOTATION*\n\n" + "\n\n".join(parts) + defaults_note

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