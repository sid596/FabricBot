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
)
REQUIRED_FIELDS = (

    "width",

    "height",

)

@dataclass
class QuotationState:

    fabric: Optional[str] = None
    fabric_price: Optional[float] = None

    width: Optional[int] = None
    height: Optional[int] = None

    track: Optional[str] = None
    curtain_style: Optional[str] = None

    order_type: str = "full"

    confirmed: bool = False

@dataclass
class ConversationState:

    active_task: Optional[str] = None

    quotation: Optional[QuotationState] = None

    last_intent: Optional[str] = None

    completed: bool = False

    last_reply: Optional[str] = None

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
        )

def start_new_quotation(state: ConversationState) -> ConversationState:
    state.active_task = "quotation"
    state.quotation = QuotationState()
    state.completed = False

    return state

def reset_conversation(state: ConversationState) -> ConversationState:

    state.active_task = None
    state.quotation = None
    state.completed = False
    state.last_intent = None
    state.last_reply = None

    return state

def merge_quotation(
    state: ConversationState,
    result: dict,
) -> ConversationState:
    if state.quotation is None:
        state.quotation = QuotationState()

    q = state.quotation

    for field in QUOTE_FIELDS:
        value = result.get(field)
        if value is not None:
            setattr(q, field, value)

    return state

def find_missing_fields(state: ConversationState) -> list[str]:

    if state.quotation is None:
        return list(REQUIRED_FIELDS)
    
    q = state.quotation

    missing = []

    if q.order_type != "track_only":

        if q.fabric is None and q.fabric_price is None:
            missing.append("fabric")

    for field in REQUIRED_FIELDS:
        if getattr(q, field) is None:
            missing.append(field)

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

    if intent == "quotation":

        if not has_active_quotation(state):
            start_new_quotation(state)

        merge_quotation(state, result)

    return state

def is_quote_complete(state: ConversationState) -> bool:
    return len(find_missing_fields(state)) == 0