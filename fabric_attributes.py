"""Structured search preferences; visual similarity is not material verification."""
from typing import Literal
from pydantic import BaseModel, Field


class FabricPreferences(BaseModel):
    description: str = ""
    colours: list[str] = Field(default_factory=list)
    textures: list[str] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)
    fabric_type: Literal["main", "sheer", "both", "upholstery"] | None = None
    # Only set for explicit fibre-content requests, not 'linen look'.
    materials: list[str] = Field(default_factory=list)


SEARCH_INSTRUCTIONS = """
Fabric discovery requests have intent fabric_search (e.g. 'show sage green linen
look curtains', 'similar floral fabrics', 'pastel sheer options'). Extract
search_preferences: description (short English visual description), colours,
textures, patterns, fabric_type and materials. No quoted numbers or prices.
Preserve the precise colour name. Sage green, teal and sea green can be related
colour suggestions but are not identical shades. Pastel describes soft/light
colours, not a single hue. 'Natural' describes a texture unless actual natural
fibre content is explicitly required. 'Cotton/linen look/feel/texture' belongs
in textures; '100% cotton', 'made of linen', 'only natural fibres' belongs in
materials. main = opaque curtain; sheer = translucent curtain; both means the
SAME fabric is suitable for main AND sheer, not separate line items. Upholstery
is separate. Unspecified usage stays null. Do not assume all curtains are main.
A request with dimensions or an explicit quotation remains quotation.
A bare named quality or a price question remains price_lookup.
For a photo caption requesting similar options, use fabric_search even if a
product label is also visible. Never infer fabric composition from a photo.
"""
