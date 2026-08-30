"""Command-line curtain quotation tool, and a backward-compatible
re-export point for the pricing/ package.

The actual pricing logic now lives in pricing/shared.py (utilities
used by every product type), pricing/curtains.py, and pricing/blinds.py
-- this file is no longer where the math lives, it's just the CLI
entry point plus re-exports, so any existing `from quotation import X`
elsewhere (test scripts, older code) keeps working without changes.

Usage:
    python quotation.py --fabric-width 54 --track-type "MTrack Premium" \
        --style "Pleated" --height 108 --width 120 --fabric-price 590
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from pricing.shared import LineQuoteLabel, load_config
from pricing.curtains import (
    QuotationInput,
    QuotationResult,
    MultiQuotationResult,
    calculate_curtain_quote,
    calculate_multi_line_quotation,
)
from pricing.blinds import (
    BLIND_TYPES,
    BlindQuotationInput,
    BlindQuotationResult,
    MultiBlindQuotationResult,
    calculate_blind_quote,
    calculate_multi_blind_quotation,
)

__all__ = [
    "LineQuoteLabel",
    "load_config",
    "QuotationInput",
    "QuotationResult",
    "MultiQuotationResult",
    "calculate_curtain_quote",
    "calculate_multi_line_quotation",
    "BLIND_TYPES",
    "BlindQuotationInput",
    "BlindQuotationResult",
    "MultiBlindQuotationResult",
    "calculate_blind_quote",
    "calculate_multi_blind_quotation",
]


def build_parser() -> argparse.ArgumentParser:
    default_config = Path(__file__).with_name("config.json")
    parser = argparse.ArgumentParser(description="Create a curtain quotation.")
    parser.add_argument("--config", default=str(default_config))
    parser.add_argument(
            "--fabric-width",
            required=True,
            type=Decimal,
        )
    parser.add_argument("--track-type", required=True)
    parser.add_argument("--style", required=True)
    parser.add_argument("--height", required=True, type=Decimal, help="In inches")
    parser.add_argument("--width", required=True, type=Decimal, help="In inches")
    parser.add_argument(
        "--fabric-price", required=True, type=Decimal, help="Price per meter"
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    quote = calculate_curtain_quote(
        QuotationInput(
            fabric_width_inches=args.fabric_width,
            track_type=args.track_type,
            curtain_style=args.style,
            height_inches=args.height,
            width_inches=args.width,
            fabric_price_per_meter=args.fabric_price,
        ),
        config,
    )
    print(json.dumps(asdict(quote), indent=2))


if __name__ == "__main__":
    main()