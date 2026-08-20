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
    assert quote.window_height_inches == float(test["input"].height_inches)
    assert quote.window_width_inches == float(test["input"].width_inches)
    assert quote.raw_meters_per_panel == quote.meters_per_panel

    expected_fullness = (
        float(config["calculation"]["default_fullness"])
        if test["input"].order_type != "track_only"
        else 0.0
    )

    assert quote.fullness == expected_fullness
    print(quote)