from flask import Flask, request
from ai import understand
from search import search_fabric
from whatsapp import send_message
from images import download_image
app = Flask(__name__)

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
        message_type = message_data["type"]

        print(f"Phone: {phone}")
        print(f"Message Type: {message_type}")

        # -----------------------------
        # TEXT MESSAGE
        # -----------------------------
        if message_type == "text":

            message = message_data["text"]["body"]

            print(message)

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

            else:
                reply = "Sorry, I didn't understand your request."

            send_message(phone, reply)

        # -----------------------------
        # IMAGE MESSAGE
        # -----------------------------
        elif message_type == "image":

            image_id = message_data["image"]["id"]

            print(f"Image ID: {image_id}")

            image_path = download_image(image_id)

            print(f"Saved image to {image_path}")

            send_message(
                phone,
                "📷 Image received successfully!"
            )

            # We'll download the image and process it here next.

        else:

            print("Unsupported message type.")

        return "OK", 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return "ERROR", 500