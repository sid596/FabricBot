import os
import requests

ACCESS_TOKEN = "EAAPDL3JnivUBRZBMiy0ArGKmUhGPhiDEAGSkkrRPHEedItZAPJwmPbBOyq8BCTLZArF06puUHDY5M67AM5RZCkHphsv80MXyiAGGyPkcrFZAbMdnKdLqzhHzJT0pVgPdPjTw2CZCjWF19ZB73mzFVOIZCs4L3WUOMO6JkiTp5ZCiOy7rEurVY40nrqNtEDsKqowZDZD"

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
