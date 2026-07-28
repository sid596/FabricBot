from google import genai
from dotenv import load_dotenv
import os

from pydantic import BaseModel

class ImageResult(BaseModel):
    code: str

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def extract_code(image_path):

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    prompt = """
You are an OCR assistant for a curtain and wallpaper business.

Extract the product code from this image.

Rules:
- Return ONLY the catalogue name
- Do not explain.
- Do not include extra words.
- Preserve letters, numbers and hyphens.
- If multiple codes exist, return the most prominent one.
- If no product code is visible, return exactly NOT_FOUND.
"""

    uploaded_file = client.files.upload(file=image_path)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            prompt,
            uploaded_file,
        ],
        config={
            "response_mime_type": "application/json",
            "response_schema": ImageResult,
        },
    )

    return response.parsed.model_dump()