from google import genai
from dotenv import load_dotenv
import os
import json
from pydantic import BaseModel
load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

class Intent(BaseModel):
    intent: str
    fabric: str


def understand(message):

    prompt = f"""
You are an AI assistant for a curtain business.

Determine the user's intent and the fabric they are referring to.

If they ask for a price, search, find, give, the intent is "price_lookup". if they ask for quotation then intent is "quotation"
if the ask is just one word wihtout price keyword its most liekly fabric name and provide price for the same

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