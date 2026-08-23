import os
import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")


def send_message(phone, message):

    url = f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {
            "body": message
        }
    }

    response = requests.post(url, headers=headers, json=data)

    print(response.status_code)
    print(response.text)



def send_typing_indicator(message_id):
    """
    Shows WhatsApp's native 'typing...' bubble on the customer's device,
    and marks the message as read. Lasts up to 25 seconds or until we
    actually reply, whichever comes first.
    """
    url = f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
        "typing_indicator": {
            "type": "text"
        }
    }

    response = requests.post(url, headers=headers, json=data)

    print(response.status_code)
    print(response.text)


if __name__ == "__main__":
    send_message(
        "918147500872",
        "Hello from FabricBot 🚀"
    )