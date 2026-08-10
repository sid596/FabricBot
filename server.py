from flask import Flask, request
from ai import understand
from search import search_fabric
from whatsapp import send_message
from images import download_image
from vision import extract_code
from quotation import load_config
app = Flask(__name__)
from database import (
    init_db,
    get_conversation,
    save_conversation,
)
from conversation import update_conversation
from quotation_flow import handle_quotation


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

        state = get_conversation(phone)

        print(state)
        
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
        result = understand(message, state)
        print(result)
        state = update_conversation(state, result)
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

            flow = handle_quotation(
                state,
                quote_config,
            )

            reply = flow.reply

            if flow.completed:
                state.completed = True
                
            
        else:   
            reply = "Sorry, I didn't understand your request."
        save_conversation(phone, state)
        send_message(phone, reply)
        return "OK", 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return "ERROR", 500