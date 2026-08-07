from google import genai
from dotenv import load_dotenv
import os
import json
from pydantic import BaseModel
load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

from typing import Optional, types

class Intent(BaseModel):
    intent: str

    fabric: Optional[str] = None
    fabric_price: Optional[float] = None

    width: Optional[int] = None
    height: Optional[int] = None

    track: Optional[str] = None
    curtain_style: Optional[str] = None

    discount: Optional[float] = None
    order_type: Optional[str] = None

def understand(message):

    knowledge = f"""
You are Angie, an AI assistant for a curtain and furnishing business.

Your only job is to understand the user's request and extract structured information.

Return ONLY valid JSON matching the provided schema.

-----------------------
INTENTS
-----------------------

price_lookup
The user wants the price of a fabric.

Examples:
- Luna
- Price of Luna
- Rate of Luna
- How much is Luna?

quotation
The user wants a curtain quotation.

Examples:
- Quote Luna 71 x 65
- Quotation for Luna
- Need curtains for one window
- Fabric price is 590, size 71x65
- Quotation for 7 feet height and 8 feet width

-----------------------
FIELDS
-----------------------

Extract these fields if present:

- intent
- fabric
- fabric_price
- height
- width
- track
- curtain_style
- discount

Return null for any field that is not mentioned.

-----------------------
FABRICS
-----------------------

Fabric names include the fabric and the supplier(like Nuhome, JM, SNN, Rivee, etc) (but are not limited to):

For ex:
NuHome Luna
JM Luna
Treat recognized fabric names as the fabric field.

-----------------------
TRACK TYPES
-----------------------

Valid track values are:

- Standard Track
- MTrack Premium
- MTrack Silent
- Jumbo Track
- Golden Rod
- SS Rods
- Silent Rod Gold
- Antique Rods
- I-Track
- Ripple
- Motorised Track
- Flat Track
- Colored Track

Interpret synonyms as follows:

premium track
premium rail
premium rod
single track

→ MTrack Premium

silent track
quiet track
silent rod
noiseless track

→ MTrack Silent
-----------------------
CURTAIN STYLES
-----------------------

Valid curtain styles are:

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

If dimensions are written as

71 x 65
71×65
71 by 65

interpret them as

Height = 71
Width = 65

unless the user explicitly specifies otherwise.

If dimensions are written as

Height x Width

the first value is Height and the second is Width.

Convert feet to inches.

Examples:

7 feet
7 ft

→ 84

8 feet

→ 96

If no unit is specified, assume inches.

-----------------------
RULES
-----------------------

If only a fabric name is given:

intent = price_lookup

If a fabric price is given:

intent = quotation

fabric_price = value

fabric = null

If window dimensions are given:

intent = quotation

Do not invent:

- dimensions
- discounts
- track
- curtain_style
- fabric
- fabric_price
Determine order_type.

If the customer asks for curtains or a quotation without specifying otherwise,
assume:

order_type = "full"

If they explicitly say only curtains:

order_type = "curtains_only"

If they explicitly ask only for tracks or rods:

order_type = "track_only"

Otherwise return null.
If information is missing, return null.
-----------------------
BUSINESS KNOWLEDGE
-----------------------
Order types:

full
- Customer wants curtains and track.

curtains_only
- Customer wants only curtains.
- They already have tracks or explicitly say no track.

track_only
- Customer wants only tracks or rods.
-----------------------
OUTPUT
-----------------------

Return ONLY valid JSON.

"""
    # Cache
    cache = client.caches.create(
        model = "gemini-2.5-flash",
        config = genai.types.CreateCachedContentConfig(
            display_name="furnishing0calculation-rules-v1", 
            system_instruction = knowledge,
            ttl = "86400s"
        ))
    # response
    response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents = message,
    config={
        "response_mime_type": "application/json",
        "response_schema": Intent,
        "cached_content": cache.name
    }
)
    # print("TEXT:")
    # print(response.text)

    # print("PARSED:")
    # print(response.parsed)

    return response.parsed.model_dump()
if __name__ == "__main__":

    tests = [
    "Quotation Luna 71x65",
    "Quotation Luna 71x65 curtains only",
    "Quotation Luna 71x65 only track",
    "Need only MTrack Premium for 8 feet",
    "I already have tracks, quotation for Luna",
]

    for t in tests:
        print(f"\nINPUT: {t}")
        print(understand(t))