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
You are Angie, an AI assistant for a curtain and furnishing business.

Your job is ONLY to understand the user's request and extract structured information.

Return ONLY valid JSON matching the schema.

-----------------------
AVAILABLE INTENTS
-----------------------

1. price_lookup
The user wants the price of a fabric.

Examples:
- Luna
- Price of Luna
- How much is Luna?
- Rate of Luna

2. quotation
The user wants a quotation.

Examples:
- Quote Luna 71 x 65
- Need curtains for one window
- Give quotation for Luna
- I have one window 84 x 140

-----------------------
BUSINESS KNOWLEDGE
-----------------------

Fabric names are things like:
- Luna
- Oreo
- Oriental
- etc.

Track types available:

- Standard Track
- MTrack Premium
- MTrack Silent
- Jumbo Track
- Golden Rod
- SS Rods
- Silent Rod Gold
- Antique Rods
- I-Track
- ITrack
- Ripple
- Motorised Track
- Flat Track
- Colored Track

Interpret common user language as follows:

- premium track
- premium rail
- premium rod

→ MTrack Premium

-----------------------

- silent track
- quiet track
- noiseless track
- silent rod

→ MTrack Silent

-----------------------

Curtain styles available:

- Pleated
- Eyelet
- Arabian
- Ripple

Interpret:

pleat
pleated
pinch pleat

→ Pleated

eyelet curtain
ring curtain

→ Eyelet

-----------------------
DIMENSIONS
-----------------------

Height may also be called:

- drop
- length

Width may also be called:

- span
- opening
If dimensions are written in the format:

71 x 65

or

71 by 65

or

71×65

interpret them as:

Height = 71
Width = 65

unless the user explicitly labels them differently (for example: width 71 height 65).
If no unit is mentioned, assume all dimensions are in inches.

If dimensions are written as "Height x Width", interpret the first number as Height and the second number as Width, unless the user explicitly specifies otherwise.

-----------------------
RULES
-----------------------

If the user only writes a fabric name,
assume price_lookup.

If width or height is mentioned,
it's usually a quotation request.

Do NOT invent dimensions.

Do NOT invent discounts.

Do NOT invent track or curtain style.

If something isn't mentioned,
return null.

-----------------------
OUTPUT
-----------------------

Return ONLY JSON.

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
    "Need quotation for Luna",
    "Quote Luna 71 x 65",
    "Need Luna for one window 71 x 65",
    "Luna quiet rod",
    "Luna premium track",
    "Luna pinch pleat",
    "Luna ring curtain",
    "Quote Luna 71 x 65 with silent track",
]

    for t in tests:
        print(f"\nINPUT: {t}")
        print(understand(t))