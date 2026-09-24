from decimal import Decimal
from quotation import (
    load_config,
    calculate_curtain_quote,
    QuotationInput,
)

config = load_config("config.json")

tests = [
    {
        "name": "Full Order - 48 inch fabric",
        "input": QuotationInput(
            fabric_width_inches=Decimal("48"),
            track_type="MTrack Premium",
            curtain_style="Pleated",
            height_inches=Decimal("84"),
            width_inches=Decimal("96"),
            fabric_price_per_meter=Decimal("590"),
            order_type="full",
        ),
    },
    {
        "name": "Curtains Only",
        "input": QuotationInput(
            fabric_width_inches=Decimal("48"),
            track_type="",
            curtain_style="Pleated",
            height_inches=Decimal("84"),
            width_inches=Decimal("96"),
            fabric_price_per_meter=Decimal("590"),
            order_type="curtains_only",
        ),
    },
    {
        "name": "Track Only",
        "input": QuotationInput(
            fabric_width_inches=Decimal("0"),
            track_type="MTrack Premium",
            curtain_style="",
            height_inches=Decimal("84"),
            width_inches=Decimal("96"),
            fabric_price_per_meter=Decimal("0"),
            order_type="track_only",
        ),
    },
    {
        "name": "52 inch fabric",
        "input": QuotationInput(
            fabric_width_inches=Decimal("52"),
            track_type="MTrack Premium",
            curtain_style="Pleated",
            height_inches=Decimal("84"),
            width_inches=Decimal("96"),
            fabric_price_per_meter=Decimal("590"),
            order_type="full",
        ),
    },
    {
        "name": "54 inch fabric",
        "input": QuotationInput(
            fabric_width_inches=Decimal("54"),
            track_type="MTrack Premium",
            curtain_style="Pleated",
            height_inches=Decimal("84"),
            width_inches=Decimal("96"),
            fabric_price_per_meter=Decimal("590"),
            order_type="full",
        ),
    },
    {
        "name": "108 inch fabric",
        "input": QuotationInput(
            fabric_width_inches=Decimal("108"),
            track_type="MTrack Premium",
            curtain_style="Pleated",
            height_inches=Decimal("84"),
            width_inches=Decimal("96"),
            fabric_price_per_meter=Decimal("590"),
            order_type="full",
        ),
    },
]

for test in tests:
    print("=" * 70)
    print(test["name"])
    quote = calculate_curtain_quote(test["input"], config)
    # The pricing-package refactor removed the old diagnostic fields.
    # Verify the public results and the component total instead.
    assert quote.grand_total == (
        quote.total_fabric_cost + quote.total_track_cost
        + quote.total_stitching_cost + quote.fitting_charges + quote.gst_total
    )
    if test["input"].order_type == "track_only":
        assert quote.number_of_panels == 0
        assert quote.total_fabric_meters == 0
        assert quote.total_stitching_cost == 0
    else:
        assert quote.number_of_panels > 0
        assert quote.total_fabric_meters >= quote.number_of_panels * quote.meters_per_panel
    if test["input"].order_type == "curtains_only":
        assert quote.total_track_cost == 0
    print(quote)