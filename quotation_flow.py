from dataclasses import dataclass
from decimal import Decimal

from conversation import (
    next_question,
)

from quotation import (
    calculate_curtain_quote,
    QuotationInput,
)

from search import search_fabric


@dataclass
class FlowResult:
    reply: str
    completed: bool = False


def handle_quotation(
    state,
    quote_config,
):
    # Step 1: Ask for missing information
    question = next_question(state)

    if question is not None:
        return FlowResult(reply=question)
    q = state.quotation
    # Step 2: Resolve fabric
    order_type = q.order_type or "full"

    fabric = None

    if order_type != "track_only":

        if q.fabric is not None:

            print("===== QUOTATION STATE =====")
            print(q)

            print("Stored fabric:", q.fabric)

            matches = search_fabric(q.fabric)

            print("Matches:", matches)

            if not matches:
                return FlowResult(
                    reply="Sorry, I couldn't find that fabric."
                )


            
            fabric = matches[0]

        elif q.fabric_price is not None:

            fabric = {
                "price": q.fabric_price,
                "width": "48",
            }

        else:

            return FlowResult(
                reply="Please provide the fabric name or fabric price."
        )


    # Step 3: Calculate quotation

    quote = calculate_curtain_quote(
        QuotationInput(
            fabric_width_inches=Decimal(
                "0"
                if order_type == "track_only"
                else fabric["width"]
            ),

            track_type=q.track or "MTrack Premium",
            curtain_style=(
                ""
                if order_type == "track_only"
                else (
                    q.curtain_style or "Pleated"                
                    )
            ),

            height_inches=Decimal(q.height),

            width_inches=Decimal(q.width),

            fabric_price_per_meter=Decimal(
                "0"
                if order_type == "track_only"
                else fabric["price"]
            ),

            order_type=order_type,
        ),
        quote_config,
    )

    reply = (
    "🪟 *Curtain Quotation*\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"

    "📐 *Window Details*\n"
    f"• Height: {quote.window_height_inches:.0f}\"\n"
    f"• Width: {quote.window_width_inches:.0f}\"\n\n"

    "🧵 *Fabric Details*\n"
    f"• Fabric Price: ₹{quote.fabric_price_per_meter:.0f}/m\n"
    f"• Fabric Width: {quote.fabric_width_inches:.0f}\"\n"
    f"• Curtain Style: {quote.curtain_style}\n"
    f"• Fullness: {quote.fullness:.1f}×\n\n"

    "📏 *Fabric Calculation*\n"
    f"• Panels Required: {quote.number_of_panels}\n"
    f"• Cut Length / Panel: {quote.raw_meters_per_panel:.2f} m\n"
    f"• Total Fabric Used: {quote.total_fabric_meters:.2f} m\n\n"

    "🛤 *Track Details*\n"
    f"• Track: {quote.track_type}\n"
    f"• Track Length: {quote.track_length_feet:.1f} ft\n\n"

    "💰 *Cost Breakdown*\n"
    f"• Fabric: ₹{quote.total_fabric_cost}\n"
    f"• Track: ₹{quote.total_track_cost}\n"
    f"• Stitching: ₹{quote.total_stitching_cost}\n"
    f"• Fitting: ₹{quote.fitting_charges}\n"
    f"• GST: ₹{quote.gst_total}\n\n"

    "━━━━━━━━━━━━━━━━━━━━\n"

    f"💵 *Grand Total: ₹{quote.grand_total}*"
)

    return FlowResult(
        reply=reply,
        completed=True,
    )