"""
src/policy_engine.py
Owner: Member 1 (Policy Engine)
Depends on: src.schemas

Loads the playbook, resolves the policy parameters for a thread, normalizes
offers into INR per unit, calculates concession limits and counter prices,
and finds banned terms.

Phase 3 status: STUB. Bodies raise NotImplementedError until Phase 4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.schemas import NormalizedOffer, Params, RawOffer

_PHASE4_MSG = "Phase 4: to be implemented by Member 1 (Policy Engine)."


@dataclass
class PolicyBook:
    """Container for parsed playbook data.

    This is a PLACEHOLDER. Member 1 replaces these fields in Phase 4 with the
    real structures (categories, suppliers, amendments, contract overrides,
    FX table, banned terms). Other modules should only pass a PolicyBook
    around, not read its fields directly.
    """

    root: Path
    notes: list[str] = field(default_factory=list)


def load_policy(playbook_dir: str | Path) -> PolicyBook:
    """Parse the playbook folder into a PolicyBook."""
    raise NotImplementedError(_PHASE4_MSG)


def get_params(book: PolicyBook, supplier: str, category: str, on_date: str) -> Params:
    """Resolve all policy values for one supplier, category and date."""
    raise NotImplementedError(_PHASE4_MSG)


def normalize_offer(raw: RawOffer, params: Params) -> NormalizedOffer:
    """Convert a RawOffer into an INR, pre-GST, per-unit price (or a missing reason)."""
    raise NotImplementedError(_PHASE4_MSG)


def price_limit(params: Params, round_no: int) -> float:
    """Return the concession limit L(r) for the given round (unrounded)."""
    raise NotImplementedError(_PHASE4_MSG)


def counter_price(params: Params, round_no: int) -> int:
    """Return the integer counter price for the given round (half-up rounding)."""
    raise NotImplementedError(_PHASE4_MSG)


def is_final_round(params: Params, round_no: int) -> bool:
    """Return True when round_no equals params.rounds."""
    raise NotImplementedError(_PHASE4_MSG)


def exceeds_approval_limit(unit_price: float, quantity: int, params: Params) -> bool:
    """Return True when the total order value exceeds the approval limit."""
    raise NotImplementedError(_PHASE4_MSG)


def round_half_up(x: float) -> int:
    """Round to the nearest integer, with .5 always going up. Never use round()."""
    raise NotImplementedError(_PHASE4_MSG)


def find_banned_terms(latest_text: str) -> list[str]:
    """Return the banned terms found in the latest supplier message."""
    raise NotImplementedError(_PHASE4_MSG)
