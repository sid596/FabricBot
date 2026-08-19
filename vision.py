from google import genai
from dotenv import load_dotenv
import os

from pydantic import BaseModel
from typing import Optional

from ai import LineItem

class ImageResult(BaseModel):
    code: str


class VisualExtraction(BaseModel):
    content_type: str  # "product_code" | "quotation_table" | "unknown"
    code: Optional[str] = None
    line_items: Optional[list[LineItem]] = None

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


def extract_visual_content(image_path):
    """
    Auto-detecting vision call used for every incoming WhatsApp photo.
    Decides whether the image is a printed product tag (existing
    behaviour) or a handwritten quotation requirements note, and
    extracts accordingly -- no caption or mode selection needed from
    the salesperson.
    """

    prompt = """
You are a vision assistant for a curtain and furnishings business.
Every image sent to you is one of two things:

1. A product tag or label with a printed fabric product code.

2. A handwritten note a salesperson jotted down while taking curtain
   requirements from a customer -- rooms, windows, curtain types
   (main/sheer), dimensions, and fabric names, in shorthand.

Decide which one this image is, then extract accordingly.

-----------------------
IF IT IS A PRODUCT TAG
-----------------------

content_type = "product_code"
code = the product code (letters, numbers, hyphens only)
line_items = null

-----------------------
IF IT IS A HANDWRITTEN REQUIREMENTS NOTE
-----------------------

content_type = "quotation_table"
code = null
line_items = one entry per room + window + curtain_type combination
written in the note.

For each line item extract, if present:
room, window, curtain_type, fabric, fabric_price, height, width,
track, curtain_style, order_type.

Apply the same shorthand rules a human reading the note would use:
- A shared value (fabric, track) written once but meant for several
  rows applies to all of those rows -- copy it onto each one.
- "Main + Sheer" or similar for one room/window means two separate
  line items sharing the same room/window/dimensions/fabric.
- If a room clearly has curtains already and only needs a track/rod,
  set order_type = "track_only" and leave fabric fields null.

Return null for anything not written down or not legible. Do not
guess a dimension or fabric name you cannot actually read -- an
illegible value should be null, never invented.

-----------------------
IF NEITHER
-----------------------

content_type = "unknown"
code = null
line_items = null

-----------------------
OUTPUT
-----------------------

Return ONLY valid JSON matching the schema. No explanation.
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
            "response_schema": VisualExtraction,
        },
    )

    return response.parsed.model_dump()