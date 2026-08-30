"""Blind pricing: Roller, Roman, Zebra, Venetian, PVC. Moved out of
quotation.py unchanged during the product-type architecture split --
see pricing/curtains.py for the equivalent module for curtains, and
pricing/shared.py for utilities used by both.

Blinds are priced fundamentally differently from curtains (area x
rate, not fullness/panels), and only Roman blinds have a fabric cost
at all -- see calculate_blind_quote()'s docstring for the full rules
and open assumptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Any

from pricing.shared import LineQuoteLabel, _money, _positive

BLIND_TYPES = ("roller", "roman", "zebra", "venetian", "pvc")

# Rates confirmed directly from business rules given 2026-08-24.
ROLLER_RATE_NO_PELMET = Decimal("210")
ROLLER_RATE_WITH_PELMET = Decimal("260")
ZEBRA_RATE = Decimal("320")          # always with pelmet
VENETIAN_RATE = Decimal("400")       # always with pelmet
PVC_RATE = Decimal("195")            # always with pelmet
ROMAN_SQFT_RATE = Decimal("210")     # NOTE: a real handwritten note showed
                                      # 220/sqft for this line -- may be an
                                      # older rate, confirm which is current.

BLIND_HEIGHT_ALLOWANCE_INCHES = Decimal("6")          # roller/zebra/venetian/pvc
ROMAN_EFFECTIVE_FABRIC_WIDTH_INCHES = Decimal("46")    # 48in roll - 1in fold/side

BLIND_FITTING_PER_UNIT = Decimal("250")
BLIND_MAX_WIDTH_PER_UNIT_INCHES = Decimal("72")        # 6ft cutoff per blind unit


@dataclass(frozen=True)
class BlindQuotationInput:
    blind_type: str  # "roller" | "roman" | "zebra" | "venetian" | "pvc"
    height_inches: Decimal
    width_inches: Decimal
    with_pelmet: bool = True  # only changes the rate for "roller"
    # Roman only -- the fabric price per meter for this blind's fabric
    fabric_price_per_meter: Decimal | None = None
    fabric_discount_percent: Decimal = Decimal(0)


@dataclass(frozen=True)
class BlindQuotationResult:
    blind_type: str
    window_height_inches: float
    window_width_inches: float
    area_sqft: float
    rate_per_sqft: float
    area_cost: int
    fabric_meters: float          # 0 for every type except roman
    fabric_cost: int              # 0 for every type except roman
    number_of_blind_units: int
    fitting_charges: int
    gst_total: int
    grand_total: int


def calculate_blind_quote(
    data: BlindQuotationInput, config: dict[str, Any]
) -> BlindQuotationResult:
    """
    Blind pricing, per business rules given 2026-08-24.

    Roller / Zebra / Venetian / PVC: pure area (sqft) x rate, no
    fabric cost at all. Height gets a flat +6in allowance before the
    area is computed.

    Roman: the one blind type that DOES have a fabric cost, computed
    like curtain fabric -- BUT using a fixed 46in effective fabric
    width (48in roll minus 1in folded on each side) instead of a
    per-catalogue fabric width, and using the curtain-style fold
    margin allowance on height (confirmed against a real note to
    within ~2%, not exact -- see caller-facing docs). On top of that
    fabric cost, Roman also has its own sqft-rate charge like the
    other blind types.

    Fitting is a flat per-blind-unit charge, not the curtain fitting
    formula. A window wider than 6ft needs multiple blind units side
    by side, and fitting scales with that count (2 units = 2x fitting,
    and so on) -- this implementation assumes only fitting scales with
    unit count, not the area/fabric cost, since the total window area
    doesn't change based on how many physical units cover it. This
    is an assumption, not something explicitly confirmed.

    NOT modelled here: pelmet variants beyond roller's two rates,
    "customised variant" (undefined), and a third cost component
    (labelled "A") seen on one real Roman blind note that doesn't
    match anything in the given spec -- possibly a lining fabric,
    unconfirmed.
    """
    _positive(data.height_inches, "height")
    _positive(data.width_inches, "width")

    blind_type = data.blind_type.lower()
    if blind_type not in BLIND_TYPES:
        raise ValueError(f"Unknown blind type: {data.blind_type}")

    calc = config["calculation"]
    money_increment = Decimal(str(calc["currency_rounding"]))
    inches_per_foot = Decimal(12)

    # Fitting scales with how many blind units the width requires.
    number_of_blind_units = int(
        (data.width_inches / BLIND_MAX_WIDTH_PER_UNIT_INCHES).to_integral_value(
            rounding=ROUND_CEILING
        )
    )
    if number_of_blind_units < 1:
        number_of_blind_units = 1
    fitting_charges = int(BLIND_FITTING_PER_UNIT * number_of_blind_units)

    fabric_meters = Decimal(0)
    fabric_cost = Decimal(0)

    if blind_type == "roman":
        fold_margin = Decimal(str(calc["fold_margin_inches"]))
        adjusted_height = data.height_inches + fold_margin
        inches_per_meter = Decimal(str(calc["inches_per_meter"]))

        panels = (
            data.width_inches / ROMAN_EFFECTIVE_FABRIC_WIDTH_INCHES
        ).to_integral_value(rounding=ROUND_CEILING)
        if panels < 1:
            panels = Decimal(1)

        meters_per_panel = adjusted_height / inches_per_meter
        fabric_meters = panels * meters_per_panel

        if data.fabric_price_per_meter is None:
            raise ValueError("Roman blinds require a fabric price per meter.")

        raw_fabric_cost = fabric_meters * data.fabric_price_per_meter
        fabric_cost = _money(
            raw_fabric_cost
            * (Decimal(100) - data.fabric_discount_percent)
            / Decimal(100),
            money_increment,
        )

        rate_per_sqft = ROMAN_SQFT_RATE
        # Sqft portion uses the RAW window height -- the fold-margin
        # allowance above is specifically for the fabric-length calc.
        # Not explicitly confirmed either way; flagged as an assumption.
        height_for_area = data.height_inches

    else:
        height_for_area = data.height_inches + BLIND_HEIGHT_ALLOWANCE_INCHES
        if blind_type == "roller":
            rate_per_sqft = (
                ROLLER_RATE_WITH_PELMET if data.with_pelmet else ROLLER_RATE_NO_PELMET
            )
        elif blind_type == "zebra":
            rate_per_sqft = ZEBRA_RATE
        elif blind_type == "venetian":
            rate_per_sqft = VENETIAN_RATE
        else:  # pvc
            rate_per_sqft = PVC_RATE

    height_ft = height_for_area / inches_per_foot
    width_ft = data.width_inches / inches_per_foot
    area_sqft = height_ft * width_ft

    area_cost = _money(area_sqft * rate_per_sqft, money_increment)

    # No confirmed GST rate for blinds yet -- defaulting to fabric's
    # rate as a starting assumption. Add an explicit "blinds" key
    # under config["calculation"]["gst"] once the real rate is known.
    gst_rate = Decimal(str(calc["gst"].get("blinds", calc["gst"]["fabric"])))
    taxable_amount = Decimal(area_cost) + Decimal(fabric_cost)
    gst_total = _money(taxable_amount * gst_rate / Decimal(100), money_increment)

    grand_total = int(area_cost) + int(fabric_cost) + fitting_charges + int(gst_total)

    return BlindQuotationResult(
        blind_type=blind_type,
        window_height_inches=float(data.height_inches),
        window_width_inches=float(data.width_inches),
        area_sqft=float(area_sqft),
        rate_per_sqft=float(rate_per_sqft),
        area_cost=int(area_cost),
        fabric_meters=float(fabric_meters),
        fabric_cost=int(fabric_cost),
        number_of_blind_units=number_of_blind_units,
        fitting_charges=fitting_charges,
        gst_total=int(gst_total),
        grand_total=grand_total,
    )


@dataclass(frozen=True)
class MultiBlindQuotationResult:
    line_labels: list[LineQuoteLabel]
    line_results: list[BlindQuotationResult]
    total_area_cost: int
    total_fabric_cost: int
    total_fitting_charges: int
    total_gst: int
    grand_total: int


def calculate_multi_blind_quotation(
    items: list[tuple[LineQuoteLabel, BlindQuotationInput]],
    config: dict[str, Any],
) -> MultiBlindQuotationResult:
    if not items:
        raise ValueError("At least one line item is required.")

    labels = [label for label, _ in items]
    results = [calculate_blind_quote(data, config) for _, data in items]

    return MultiBlindQuotationResult(
        line_labels=labels,
        line_results=results,
        total_area_cost=sum(r.area_cost for r in results),
        total_fabric_cost=sum(r.fabric_cost for r in results),
        total_fitting_charges=sum(r.fitting_charges for r in results),
        total_gst=sum(r.gst_total for r in results),
        grand_total=sum(r.grand_total for r in results),
    )