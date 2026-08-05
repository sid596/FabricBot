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
from database import init_db, get_or_create_conversation

init_db()
quote_config = load_config("config.json")
VERIFY_TOKEN = "fabricbot123"

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

    try:
        data = request.json
        print("========== WEBHOOK ==========")
        print(data)

        value = data["entry"][0]["changes"][0]["value"]

        if "messages" not in value:
            return "OK", 200

        message_data = value["messages"][0]

        phone = message_data["from"]
        conversation = get_or_create_conversation(phone)
        print(conversation)
        message_type = message_data["type"]

        print(f"Phone: {phone}")
        print(f"Message Type: {message_type}")

        # -----------------------------
        # TEXT MESSAGE
        # -----------------------------
        if message_type == "text":

            message = message_data["text"]["body"]


         # IMAGE MESSAGE
        elif message_type == "image":

            image_id = message_data["image"]["id"]

            print(f"Image ID: {image_id}")

            image_path = download_image(image_id)

            result = extract_code(image_path)

            app.logger.info(result)

            message = result["code"]
            print(message)
        else:
            print("Unsupported message type.")
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
            # Check required dimensions
            if result["height"] is None or result["width"] is None:
                reply = "Please provide the window height and width."
            else:
                # -----------------------------
                # Resolve fabric
                # -----------------------------
                fabric = None
                if result["fabric"] is not None:
                    matches = search_fabric(result["fabric"])
                    if not matches:
                        reply = "Sorry, I couldn't find that fabric."
                    else:
                        fabric = matches[0]
                elif result["fabric_price"] is not None:
                    # Temporary default width until AI extracts it
                    DEFAULT_FABRIC_WIDTH = "48"
                    fabric = {
                        "price": result["fabric_price"],
                        "width": DEFAULT_FABRIC_WIDTH,
                    }
                else:
                    reply = "Please provide the fabric name or the fabric price."
                # -----------------------------
                # Calculate quotation
                # -----------------------------
                if fabric is not None:
                    width = int(fabric["width"])
                    quote = calculate_curtain_quote(
                        QuotationInput(
                            curtain_type=(
                                "Main 54"
                                if width == 54
                                else "Main 48"
                            ),
                            track_type=result["track"] or "MTrack Premium",
                            curtain_style=result["curtain_style"] or "Pleated",
                            height_inches=Decimal(result["height"]),
                            width_inches=Decimal(result["width"]),
                            fabric_price_per_meter=Decimal(fabric["price"]),
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
        return "OK", 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return "ERROR", 500