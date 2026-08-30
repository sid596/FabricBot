"""Pricing package: product-type pricing calculators.

pricing/shared.py   -- utilities and types used by every product type
pricing/curtains.py -- curtain pricing (fabric panels, stitching, track, fitting)
pricing/blinds.py   -- blind pricing (Roller, Roman, Zebra, Venetian, PVC)

This file re-exports the public API from those submodules so callers
can do `from pricing import calculate_curtain_quote` (or
`import pricing; pricing.calculate_blind_quote(...)`) without needing
to know which submodule a given name lives in. quotation.py re-exports
these same names for backward compatibility with older
`from quotation import X` call sites.
"""

from __future__ import annotations

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