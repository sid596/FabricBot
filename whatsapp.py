"""WhatsApp Cloud API transport with bounded waits and visible failures."""
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()
ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v23.0")


def _post_message(data):
    response = requests.post(
        f"https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/messages",
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
        json={"messaging_product": "whatsapp", **data}, timeout=(10, 60),
    )
    response.raise_for_status()
    return response.json()


def send_message(phone, message):
    return _post_message({"to": phone, "type": "text", "text": {"body": message}})


def upload_media(content, filename, mime_type):
    response = requests.post(
        f"https://graph.facebook.com/{API_VERSION}/{PHONE_NUMBER_ID}/media",
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
        data={"messaging_product": "whatsapp", "type": mime_type},
        files={"file": (filename, content, mime_type)}, timeout=(10, 90),
    )
    response.raise_for_status()
    return response.json()["id"]


def send_document(phone, content, filename="Angie-Quotation.pdf", caption="Your quotation from Angie"):
    media_id = upload_media(content, filename, "application/pdf")
    return _post_message({"to": phone, "type": "document", "document": {
        "id": media_id, "filename": filename, "caption": caption,
    }})


def send_image(phone, image_path, caption):
    path = Path(image_path)
    media_id = upload_media(path.read_bytes(), path.name, "image/jpeg")
    return _post_message({"to": phone, "type": "image", "image": {"id": media_id, "caption": caption[:1024]}})


def send_typing_indicator(message_id):
    return _post_message({"status": "read", "message_id": message_id, "typing_indicator": {"type": "text"}})
