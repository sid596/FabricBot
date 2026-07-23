from flask import Flask, request
from ai import understand
from search import search_fabric
from whatsapp import send_message

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
        print("Meta sent token:", token)
        print("Our token:", VERIFY_TOKEN)
        if token == VERIFY_TOKEN:
            return challenge, 200

        return "Verification failed", 403

        
    
    data = request.json

    value = data["entry"][0]["changes"][0]["value"]

    if "messages" not in value:
        return "OK", 200

    message_data = value["messages"][0]

    phone = message_data["from"]
    message = message_data["text"]["body"]

    print(phone)
    print(message)

    result = understand(message)

    print(result)
    reply = ""
    if result["intent"] == "price_lookup":

        matches = search_fabric(result["fabric"])


        for fabric in matches:
            reply += (
                f"Album: {fabric['album']}\n"
                f"Quality: {fabric['quality']}\n"
                f"Price: ₹{fabric['price']}/m\n"
                f"Width: {fabric['width']} inches\n\n"
            )
        print(reply)
    

    send_message(phone, reply)

   
    return "OK", 200

if __name__ == "__main__":
    app.run(debug=True)