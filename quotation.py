"""Configurable curtain quotation calculator.

Usage:
    python quotation.py --curtain-type "Main 48" --track-type "MTrack Premium" \
        --style "Peated" --height 108 --width 120 --fabric-price 590
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class QuotationInput:
    fabric_width_inches: Decimal    
    track_type: str
    curtain_style: str
    height_inches: Decimal
    width_inches: Decimal
    fabric_price_per_meter: Decimal
    order_type: str = "full"


@dataclass(frozen=True)
class QuotationResult:
    fabric_width_inches: float    
    track_type: str
    curtain_style: str
    fold_margin_inches: float
    number_of_panels: int
    meters_per_panel: float
    total_fabric_meters: float
    fabric_price_per_meter: float
    total_fabric_cost: int
    stitching_rate_per_panel: int
    total_stitching_cost: int
    track_length_feet: float
    track_rate_per_foot: int
    total_track_cost: int
    fitting_sections: int
    fitting_charges: int
    grand_total: int
    gst_total: int


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


def calculate_curtain_quote(data: QuotationInput, config: dict[str, Any]) -> QuotationResult:
    calc = config["calculation"]
    tracks = config["track_rates_per_running_foot"]
    styles = config["style_rates_per_panel"]
    margin = Decimal(calc["fold_margin_inches"])
    inches_per_meter = Decimal(calc["inches_per_meter"])
    fabric_increment = Decimal(calc["fabric_rounding_increment_meters"])
    track_increment = Decimal(calc["track_length_rounding_feet"])
    money_increment = Decimal(calc["currency_rounding"])
    _positive(data.height_inches, "height")
    _positive(data.width_inches, "width")

    # -----------------------------
    # Order type flags
    # -----------------------------
    has_curtains = data.order_type in ("full", "curtains_only")
    has_track = data.order_type in ("full", "track_only")

    stitching_discount = has_curtains
    apply_track_discount = has_track and has_curtains

    if has_curtains:
        

        if data.curtain_style not in styles:
            raise ValueError(f"Unknown curtain style: {data.curtain_style}")

        _positive(data.fabric_price_per_meter, "fabric price")
        fabric_width = data.fabric_width_inches
        _positive(fabric_width, "fabric width")

        fullness = Decimal(str(calc["default_fullness"]))


        finished_coverage = fabric_width / fullness

        panels = _round_units(
            data.width_inches / finished_coverage,
            str(calc["panel_count_rounding"]),
        )

        raw_meters_per_panel = (data.height_inches + margin) / inches_per_meter
        meters_per_panel = raw_meters_per_panel

        total_fabric_meters = _round_up_to_increment(
            meters_per_panel * panels,
            fabric_increment,
        )

        fabric_cost = _money(
            total_fabric_meters * data.fabric_price_per_meter,
            money_increment,
        )

        discount = Decimal(calc["default_fabric_discount_percent"])

        fabric_cost = _money(
            Decimal(fabric_cost)
            * (Decimal(100) - discount)
            / Decimal(100),
            money_increment,
        )

        stitching_rate = Decimal(styles[data.curtain_style])

        stitching_cost = _money(
            stitching_rate * panels,
            money_increment,
        )

        if stitching_discount:
            stitching_cost = _money(
                Decimal(stitching_cost)
                * (Decimal(100) - Decimal(calc["discounts"]["stitching_percent"]))
                / Decimal(100),
                money_increment,
            )

    else:

        fabric_width = Decimal(0)
        panels = 0
        meters_per_panel = Decimal(0)
        total_fabric_meters = Decimal(0)
        stitching_rate = Decimal(0)

        fabric_cost = 0
        stitching_cost = 0

    if has_track:
        if data.track_type not in tracks:
            raise ValueError(f"Unknown track/rod type: {data.track_type}")
        raw_track_feet = data.width_inches / Decimal(12)

        track_feet = _round_up_to_increment(
            raw_track_feet,
            track_increment,
        )

        track_rate = Decimal(tracks[data.track_type])

        track_cost = _money(
            track_feet * track_rate,
            money_increment,
        )

        if apply_track_discount:
            track_cost = _money(
                Decimal(track_cost)
                * (Decimal(100) - Decimal(calc["discounts"]["track_percent"]))
                / Decimal(100),
                money_increment,
            )

        minimum_sections = int(calc["fitting"]["minimum_sections"])

        fitting_quotient = float(data.width_inches) / 60

        rounded_fitting_quotient = math.floor(fitting_quotient * 2 + 0.5) / 2

        fitting_units = max(
            minimum_sections,
            rounded_fitting_quotient,
        )

        fitting_charges = _money(
            Decimal(str(fitting_units))
            * calc["fitting"]["charge_per_unit"],
            money_increment,
        )

    else:

        track_feet = Decimal(0)
        track_rate = Decimal(0)

        track_cost = 0
        fitting_units = 0
        fitting_charges = 0


    gst = calc["gst"]

    fabric_gst = _money(
        Decimal(fabric_cost) * Decimal(gst["fabric"]) / Decimal(100),
        money_increment,
    )

    stitching_gst = _money(
        Decimal(stitching_cost) * Decimal(gst["stitching"]) / Decimal(100),
        money_increment,
    )

    track_gst = _money(
        Decimal(track_cost) * Decimal(gst["track"]) / Decimal(100),
        money_increment,
    )

    fitting_gst = _money(
        Decimal(fitting_charges) * Decimal(gst["fitting"]) / Decimal(100),
        money_increment,
    )

    gst_total = _money(
    Decimal(fabric_gst)
    + Decimal(stitching_gst)
    + Decimal(track_gst)
    + Decimal(fitting_gst),
    money_increment,
)
    return QuotationResult(
    fabric_width_inches=float(fabric_width),
    track_type=data.track_type,
    curtain_style=data.curtain_style,
    fold_margin_inches=float(margin),
    number_of_panels=panels,
    meters_per_panel=float(meters_per_panel),
    total_fabric_meters=float(total_fabric_meters),
    fabric_price_per_meter=float(data.fabric_price_per_meter),
    total_fabric_cost=fabric_cost,
    stitching_rate_per_panel=int(stitching_rate),
    total_stitching_cost=stitching_cost,
    track_length_feet=float(track_feet),
    track_rate_per_foot=int(track_rate),
    total_track_cost=track_cost,
    fitting_sections=fitting_units,
    fitting_charges=fitting_charges,
    gst_total=gst_total,
    grand_total=
        fabric_cost
        + stitching_cost
        + track_cost
        + fitting_charges
        + gst_total,
)


@dataclass(frozen=True)
class LineQuoteLabel:
    """Human-readable label for one line item, carried alongside its
    QuotationResult so the reply can say which room/window it belongs to."""
    room: str | None
    window: str | None
    curtain_type: str | None


@dataclass(frozen=True)
class MultiQuotationResult:
    line_labels: list[LineQuoteLabel]
    line_results: list[QuotationResult]
    total_fabric_cost: int
    total_track_cost: int
    total_stitching_cost: int
    total_fitting_charges: int
    total_gst: int
    grand_total: int


def calculate_multi_line_quotation(
    items: list[tuple[LineQuoteLabel, QuotationInput]],
    config: dict[str, Any],
) -> MultiQuotationResult:
    """
    Computes a quotation covering multiple rooms/windows/curtain types
    in one go. Each line item is calculated with the exact same,
    already-tested calculate_curtain_quote() logic used for a single
    static quote -- this function only adds the multi-line loop and
    aggregation on top, it does not change any per-line math.
    """
    if not items:
        raise ValueError("At least one line item is required.")

    labels = [label for label, _ in items]
    results = [calculate_curtain_quote(data, config) for _, data in items]

    return MultiQuotationResult(
        line_labels=labels,
        line_results=results,
        total_fabric_cost=sum(r.total_fabric_cost for r in results),
        total_track_cost=sum(r.total_track_cost for r in results),
        total_stitching_cost=sum(r.total_stitching_cost for r in results),
        total_fitting_charges=sum(r.fitting_charges for r in results),
        total_gst=sum(r.gst_total for r in results),
        grand_total=sum(r.grand_total for r in results),
    )


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