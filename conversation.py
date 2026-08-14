from dataclasses import dataclass, asdict
from typing import Optional
import json

QUOTE_FIELDS = (
    "fabric",
    "fabric_price",
    "width",
    "height",
    "track",
    "curtain_style",
    "order_type",
    "discount",
)

QUESTION_MAP = {
    "dimensions": "What are the window dimensions? (Height x Width, e.g. 84x60 or 7ft x 5ft)",
    "order_type": (
        "What would you like to quote?\n"
        "1. Curtains + Track\n"
        "2. Curtains Only\n"
        "3. Track Only"
    ),
    "fabric": "Which fabric would you like to use?",
    "curtain_style": (
        "Which curtain style would you like?\n"
        "1. Pleated\n"
        "2. Eyelet\n"
        "3. Arabian\n"
        "4. Ripple"
    ),
    "track": (
        "Which track/rod would you like?\n"
        "1. MTrack Premium\n"
        "2. MTrack Silent\n"
        "3. SS Rod\n"
        "4. Golden Rod\n"
        "5. Antique Rod\n"
        "6. Silent Rod Gold\n"
        "7. I-Track\n"
        "8. Standard Track\n"
        "9. Jumbo Track\n"
        "10. Ripple\n"
        "11. Motorised Track\n"
        "12. Flat Track\n"
        "13. Colored Track"
    ),
    "discount": "What discount percentage should be applied? Reply with a number like 0, 10, 15",
}


@dataclass
class QuotationState:
    fabric: Optional[str] = None
    fabric_price: Optional[float] = None

    width: Optional[int] = None
    height: Optional[int] = None

    track: Optional[str] = None
    curtain_style: Optional[str] = None

    order_type: Optional[str] = None
    discount: Optional[float] = None

    confirmed: bool = False


@dataclass
class ConversationState:
    active_task: Optional[str] = None
    quotation: Optional[QuotationState] = None
    last_intent: Optional[str] = None
    completed: bool = False
    last_reply: Optional[str] = None
    awaiting_confirmation: Optional[str] = None

    def to_json(self):
        return json.dumps(asdict(self))

    @staticmethod
    def from_json(data):
        if not data:
            return ConversationState()

        obj = json.loads(data)

        quotation = None
        if obj.get("quotation"):
            quotation = QuotationState(**obj["quotation"])

        return ConversationState(
            active_task=obj.get("active_task"),
            quotation=quotation,
            last_intent=obj.get("last_intent"),
            completed=obj.get("completed", False),
            last_reply=obj.get("last_reply"),
            awaiting_confirmation=obj.get("awaiting_confirmation"),
        )


def start_new_quotation(state: ConversationState) -> ConversationState:
    state.active_task = "quotation"
    state.quotation = QuotationState()
    state.completed = False
    state.awaiting_confirmation = None
    return state


def reset_conversation(state: ConversationState) -> ConversationState:
    state.active_task = None
    state.quotation = None
    state.completed = False
    state.last_intent = None
    state.last_reply = None
    state.awaiting_confirmation = None
    return state


def merge_quotation(
    state: ConversationState,
    result: dict,
) -> ConversationState:
    if state.quotation is None:
        state.quotation = QuotationState()

    q = state.quotation

    if result.get("fabric") is not None:
        q.fabric = result["fabric"]
        q.fabric_price = None

    if result.get("fabric_price") is not None and q.fabric is None:
        q.fabric_price = result["fabric_price"]

    for field in (
        "width",
        "height",
        "track",
        "curtain_style",
        "discount",
        "order_type",
    ):
        value = result.get(field)
        if value is not None:
            setattr(q, field, value)

    return state


def find_missing_fields(state: ConversationState) -> list[str]:
    if state.quotation is None:
        return ["dimensions"]

    q = state.quotation
    missing = []

    # 1. dimensions first
    if q.height is None or q.width is None:
        missing.append("dimensions")
        return missing

    # 2. order type next
    if q.order_type is None:
        missing.append("order_type")
        return missing

    # 3. fabric only if not track-only
    if q.order_type != "track_only":
        if q.fabric is None and q.fabric_price is None:
            missing.append("fabric")
            return missing

    # 4. curtain style only if curtains involved
    if q.order_type != "track_only":
        if q.curtain_style is None:
            missing.append("curtain_style")
            return missing

    # 5. track only if track involved
    if q.order_type != "curtains_only":
        if q.track is None:
            missing.append("track")
            return missing

    # 6. discount last
    if q.discount is None:
        missing.append("discount")
        return missing

    return missing


def has_active_quotation(state: ConversationState) -> bool:
    return (
        state.active_task == "quotation"
        and state.completed is False
        and state.quotation is not None
    )


def update_conversation(
    state: ConversationState,
    result: dict,
) -> ConversationState:
    intent = result.get("intent")
    state.last_intent = intent

    if intent == "quotation" and not has_active_quotation(state):
        start_new_quotation(state)

    if has_active_quotation(state):
        merge_quotation(state, result)

    print("===== AFTER MERGE =====")
    print(state.quotation)

    return state


def is_quote_complete(state: ConversationState) -> bool:
    return len(find_missing_fields(state)) == 0


def next_question(state: ConversationState) -> Optional[str]:
    missing = find_missing_fields(state)

    if not missing:
        return None

    return QUESTION_MAP.get(
        missing[0],
        f"Please provide {missing[0]}.",
    )


def expected_field(state: ConversationState) -> Optional[str]:
    missing = find_missing_fields(state)

    if not missing:
        return None

    return missing[0]
