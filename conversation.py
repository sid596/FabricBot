from dataclasses import dataclass, field, asdict
from typing import Optional
import json


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

    awaiting: list[str] = field(default_factory=list)

    completed: bool = False

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

            awaiting=obj.get("awaiting", []),

            completed=obj.get("completed", False),

        )