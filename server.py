from flask import Flask, request
import traceback

from ai import understand
from search import search_fabric
from whatsapp import send_message
from images import download_image
from vision import extract_code
from quotation import load_config
from quotation_flow import handle_quotation
from database import (
    init_db,
    get_conversation,
    save_conversation,
)
from conversation import (
    update_conversation,
    reset_conversation,
    start_new_quotation,
    expected_field,
)

app = Flask(__name__)

init_db()
quote_config = load_config("config.json")

VERIFY_TOKEN = "fabricbot123"


def make_result(
    intent=None,
    fabric=None,
    fabric_price=None,
    width=None,
    height=None,
    track=None,
    curtain_style=None,
    discount=None,
    order_type=None,
):
    return {
        "intent": intent,
        "fabric": fabric,
        "fabric_price": fabric_price,
        "width": width,
        "height": height,
        "track": track,
        "curtain_style": curtain_style,
        "discount": discount,
        "order_type": order_type,
    }


def parse_menu_reply(message, state):
    if (
        state is None
        or state.active_task != "quotation"
        or state.quotation is None
        or state.completed
    ):
        return None

    waiting_for = expected_field(state)
    if waiting_for is None:
        return None

    text = message.strip()
    lowered = text.lower()

    if waiting_for == "order_type":
        options = {
            "1": "full",
            "2": "curtains_only",
            "3": "track_only",
            "full": "full",
            "curtains + track": "full",
            "curtains and track": "full",
            "both": "full",
            "curtains only": "curtains_only",
            "track only": "track_only",
            "tracks only": "track_only",
            "rod only": "track_only",
            "rods only": "track_only",
        }
        if lowered in options:
            return make_result(
                intent="quotation",
                order_type=options[lowered],
            )

    elif waiting_for == "curtain_style":
        options = {
            "1": "Pleated",
            "2": "Eyelet",
            "3": "Arabian",
            "4": "Ripple",
            "pleated": "Pleated",
            "eyelet": "Eyelet",
            "arabian": "Arabian",
            "ripple": "Ripple",
        }
        if lowered in options:
            return make_result(
                intent="quotation",
                curtain_style=options[lowered],
            )

    elif waiting_for == "track":
        options = {
            "1": "MTrack Premium",
            "2": "MTrack Silent",
            "3": "SS Rods",
            "4": "Golden Rod",
            "5": "Antique Rods",
            "6": "Silent Rod Gold",
            "7": "I-Track",
            "8": "Standard Track",
            "9": "Jumbo Track",
            "10": "Ripple",
            "11": "Motorised Track",
            "12": "Flat Track",
            "13": "Colored Track",
            "mtrack premium": "MTrack Premium",
            "mtrack silent": "MTrack Silent",
            "ss rod": "SS Rods",
            "ss rods": "SS Rods",
            "golden rod": "Golden Rod",
            "antique rod": "Antique Rods",
            "antique rods": "Antique Rods",
            "silent rod gold": "Silent Rod Gold",
            "i-track": "I-Track",
            "itrack": "I-Track",
            "standard track": "Standard Track",
            "jumbo track": "Jumbo Track",
            "ripple": "Ripple",
            "motorised track": "Motorised Track",
            "flat track": "Flat Track",
            "colored track": "Colored Track",
        }
        if lowered in options:
            return make_result(
                intent="quotation",
                track=options[lowered],
            )

    elif waiting_for == "discount":
        try:
            value = float(text.replace("%", "").strip())
            if value < 0 or value > 100:
                return make_result(intent="invalid_discount")
            return make_result(
                intent="quotation",
                discount=value,
            )
        except ValueError:
            return None

    return None


@app.route("/")
def home():
    return "FabricBot is running!"


@app.route("/webhook", methods=["POST", "GET"])
def webhook():
    phone = None

    if request.method == "GET":
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if token == VERIFY_TOKEN:
            return challenge, 200

        return "Verification failed", 403

    try:
        data = request.json
        print("========== WEBHOOK ==========")
        print(data)

        value = data["entry"][0]["changes"][0]["value"]

        if "messages" not in value:
            return "OK", 200

        message_data = value["messages"][0]
        phone = message_data["from"]
        state = get_conversation(phone)

        print("STATE FROM DB")
        print(state)

        message_type = message_data["type"]

        print(f"Phone: {phone}")
        print(f"Message Type: {message_type}")

        if message_type == "text":
            message = message_data["text"]["body"]

        elif message_type == "image":
            image_id = message_data["image"]["id"]
            print(f"Image ID: {image_id}")

            image_path = download_image(image_id)
            vision_result = extract_code(image_path)

            app.logger.info(vision_result)

            message = f"What is the price of {vision_result["code"]}?"
            print("VISION MESSAGE:", message)

        else:
            send_message(
                phone,
                "Sorry, I currently support only text and image messages."
            )
            return "OK", 200

        print("STATE BEFORE UNDERSTAND")
        print(state)

        text_lower = message.lower().strip()

        if text_lower in {"cancel", "stop", "exit"}:
            reset_conversation(state)
            save_conversation(phone, state)
            send_message(phone, "Quotation cancelled.")
            return "OK", 200

        if state.awaiting_confirmation == "new_quotation":
            choice = text_lower

            if choice in [
                "1",
                "continue",
                "continue quotation",
                "continue this quotation",
                "resume",
                "yes",
            ]:
                state.awaiting_confirmation = None
                flow = handle_quotation(state, quote_config)
                save_conversation(phone, state)
                send_message(phone, flow.reply)
                return "OK", 200

            elif choice in [
                "2",
                "new",
                "new quotation",
                "start new",
                "start a new quotation",
                "restart",
            ]:
                reset_conversation(state)
                start_new_quotation(state)
                state.awaiting_confirmation = None

                flow = handle_quotation(state, quote_config)
                save_conversation(phone, state)
                send_message(phone, flow.reply)
                return "OK", 200

            else:
                send_message(
                    phone,
                    "Please reply with:\n"
                    "1. Continue this quotation\n"
                    "2. Start a new quotation"
                )
                return "OK", 200

        result = parse_menu_reply(message, state)

        if result is None:
            result = understand(message, state)

        print("UNDERSTAND RESULT")
        print(result)

        if result["intent"] == "invalid_discount":
            send_message(
                phone,
                "Please enter a valid discount percentage between 0 and 100."
            )
            return "OK", 200

        if result["intent"] == "cancel":
            reset_conversation(state)
            save_conversation(phone, state)
            send_message(phone, "Quotation cancelled.")
            return "OK", 200

        if (
            result["intent"] == "quotation"
            and state.active_task == "quotation"
            and not state.completed
            and result.get("fabric") is None
            and result.get("fabric_price") is None
            and result.get("width") is None
            and result.get("height") is None
            and result.get("track") is None
            and result.get("curtain_style") is None
            and result.get("discount") is None
            and result.get("order_type") is None
        ):
            state.awaiting_confirmation = "new_quotation"

            reply = (
                "You already have a quotation in progress.\n\n"
                "Would you like to:\n"
                "1. Continue this quotation\n"
                "2. Start a new quotation"
            )

            save_conversation(phone, state)
            send_message(phone, reply)
            return "OK", 200

        state = update_conversation(state, result)

        if result["intent"] == "price_lookup":
            reply = ""
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
            flow = handle_quotation(state, quote_config)
            reply = flow.reply

            if flow.completed:
                state.completed = True

        else:
            reply = "Sorry, I didn't understand your request."

        save_conversation(phone, state)
        send_message(phone, reply)
        return "OK", 200

    except ValueError as e:
        print("VALUE ERROR")
        traceback.print_exc()

        if phone:
            send_message(
                phone,
                f"⚠️ Calculation error:\n{str(e)}\nPlease check the measurements/options and try again."
            )
        return "OK", 200

    except Exception as e:
        print("UNHANDLED ERROR")
        traceback.print_exc()

        if phone:
            send_message(
                phone,
                "Sorry, I ran into a technical glitch. Please try again."
            )
        return "ERROR", 500
