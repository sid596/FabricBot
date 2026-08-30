"""Shared utilities and types used across all product-type pricing
calculators (curtains, blinds, and anything added later).

Nothing product-specific belongs in this file -- if a function or
type only makes sense for one product, it belongs in that product's
own module instead.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path
from typing import Any


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file, parse_float=Decimal, parse_int=Decimal)


def _positive(value: Decimal, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")


def _round_units(value: Decimal, mode: str) -> int:
    if mode == "ceil":
        return int(value.to_integral_value(rounding=ROUND_CEILING))
    if mode == "nearest":
        return int(value.to_integral_value(rounding=ROUND_HALF_UP))
    raise ValueError("panel_count_rounding must be 'ceil' or 'nearest'.")


def _round_up_to_increment(value: Decimal, increment: Decimal) -> Decimal:
    _positive(increment, "rounding increment")
    units = (value / increment).to_integral_value(rounding=ROUND_CEILING)
    return units * increment


def _money(value: Decimal, increment: Decimal) -> int:
    rounded = _round_up_to_increment(value, increment)
    return int(rounded)


@dataclass(frozen=True)
class LineQuoteLabel:
    """Human-readable label for one line item (room/window/curtain_type),
    carried alongside its result so a reply can say which room/window
    it belongs to. Shared across product types -- a blind line item
    uses this exact same label shape as a curtain line item."""
    room: str | None
    window: str | None
    curtain_type: str | None