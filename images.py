import os
import requests
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")

def download_image(image_id):
    """
    Downloads an image sent on WhatsApp.
    Returns the local file path.
    """

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }

    # Step 1: Get temporary download URL
    response = requests.get(
        f"https://graph.facebook.com/v23.0/{image_id}",
        headers=headers
    )

    response.raise_for_status()

    image_url = response.json()["url"]

    # Step 2: Download image
    image = requests.get(
        image_url,
        headers=headers
    )

    image.raise_for_status()

    os.makedirs("temp", exist_ok=True)

    file_path = f"temp/{image_id}.jpg"

    with open(file_path, "wb") as f:
        f.write(image.content)

    return file_path