"""Download incoming WhatsApp media to a unique temporary file."""
import os
from pathlib import Path
import tempfile

import requests
from dotenv import load_dotenv

load_dotenv()


def download_image(image_id):
    headers = {"Authorization": f"Bearer {os.getenv('WHATSAPP_ACCESS_TOKEN')}"}
    version = os.getenv("WHATSAPP_API_VERSION", "v23.0")
    response = requests.get(f"https://graph.facebook.com/{version}/{image_id}", headers=headers, timeout=(10, 30))
    response.raise_for_status()
    image = requests.get(response.json()["url"], headers=headers, timeout=(10, 60))
    image.raise_for_status()
    with tempfile.NamedTemporaryFile(prefix="angie-photo-", suffix=".jpg", delete=False) as f:
        f.write(image.content)
        return f.name
