from google import genai
from dotenv import load_dotenv
import os
import json
from pydantic import BaseModel
load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

from typing import Optional

class Intent(BaseModel):
    intent: str

    fabric: Optional[str] = None

    width: Optional[int] = None
    height: Optional[int] = None

    track: Optional[str] = None
    curtain_style: Optional[str] = None

    discount: Optional[float] = None


def understand(message):

    prompt = f"""
You are an AI assistant for a curtain furnishing business.

Extract information from the user's message.

Return ONLY JSON.

Fields:

intent
fabric
width
height
track
curtain_style
discount

Rules:

- If the user wants a quotation, intent = "quotation"
- If the user wants fabric price, intent = "price_lookup"
- If they only write a fabric name like "Luna", assume they want a price lookup.
- Width and height are in inches unless stated otherwise.
- If any field isn't mentioned, return null.
- Do not guess values.

User:
{message}
"""

    response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config={
        "response_mime_type": "application/json",
        "response_schema": Intent,
    }
)
    # print("TEXT:")
    # print(response.text)

    # print("PARSED:")
    # print(response.parsed)

    return response.parsed.model_dump()
if __name__ == "__main__":

    tests = [
        "Luna",
        "Price of Luna",
        "Quote Luna 71 x 65",
        "Quote Luna 84 x 140 premium track",
        "Quote Luna 71 x 65 with 15% discount",
    ]

    for t in tests:
        print(f"\nINPUT: {t}")
        print(understand(t))