"""
src/schemas.py
Shared data contract for Procurement Desk.

Owner: Member 4 (Project Integration)
Depends on: standard library only.

Every other module imports its data structures from this file.
Do NOT import from policy_engine, message_parser, security_checker,
decision_engine or utils here, because that would create circular imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Allowed vocabulary (from the Phase 1 analysis)
# ---------------------------------------------------------------------------

# The only action -> reason combinations that may appear in a label.
VALID_COMBINATIONS: dict[str, frozenset[str]] = {
    "ACCEPT": frozenset({"ACCEPTABLE_PRICE"}),
    "COUNTER": frozenset({"COUNTER_OFFER"}),
    "REJECT": frozenset({"ABOVE_WALKAWAY", "BLACKLISTED_SUPPLIER"}),
    "ESCALATE": frozenset({
        "MISSING_INFO",
        "PROMPT_INJECTION",
        "BANNED_TERM",
        "OVER_APPROVAL_LIMIT",
    }),
}

VALID_RAW_STATUSES = frozenset({"OK", "NO_PRICE"})
VALID_PERIODS = frozenset({"month", "year"})
VALID_UNIT_TOKENS = frozenset({"unit", "dozen", "pack", "ream"})


@dataclass(frozen=True)
class Decision:
    """One procurement decision. Example label: ACCEPT:ACCEPTABLE_PRICE:"""

    action: str
    reason: str
    counter_price: Optional[int] = None

    def __post_init__(self) -> None:
        # Reject unknown actions and action-reason pairs outside the allowed set.
        if self.action not in VALID_COMBINATIONS:
            raise ValueError(f"Unknown action: {self.action!r}")
        if self.reason not in VALID_COMBINATIONS[self.action]:
            raise ValueError(
                f"Invalid reason {self.reason!r} for action {self.action!r}"
            )
        # Only COUNTER carries a price, and that price must be a positive integer.
        if self.action == "COUNTER":
            if self.counter_price is None:
                raise ValueError("COUNTER decisions must include a counter_price")
            if not isinstance(self.counter_price, int) or self.counter_price <= 0:
                raise ValueError("counter_price must be a positive integer")
        elif self.counter_price is not None:
            raise ValueError(
                f"{self.action} decisions must not include a counter_price"
            )

    def to_label(self) -> str:
        """Return the submission label, e.g. 'COUNTER:COUNTER_OFFER:1234'."""
        price = "" if self.counter_price is None else str(self.counter_price)
        return f"{self.action}:{self.reason}:{price}"


@dataclass(frozen=True)
class ThreadRecord:
    """One row of threads.csv, converted into a typed object."""

    thread_id: str
    date: str                       # ISO text, parsed later by policy_engine
    supplier: str
    category: str
    quantity: int
    round: int
    our_last_counter: Optional[float]
    raw_message: str


@dataclass(frozen=True)
class ThreadText:
    """The supplier_message split into the parts the rules need.

    earlier_supplier and earlier_acme are LISTS, one entry per message,
    in thread order. They are never plain strings.
    """

    latest: str                      # latest supplier message only
    earlier_supplier: list[str]      # earlier supplier messages (previous-quote discounts)
    earlier_acme: list[str]          # Acme's own earlier messages (never an offer)
    full: str                        # whole thread (prompt-injection checks)

    def __post_init__(self) -> None:
        # Guard against the common mistake of passing a single string,
        # which would be silently iterated character by character later on.
        if not isinstance(self.earlier_supplier, list):
            raise TypeError("earlier_supplier must be a list of strings")
        if not isinstance(self.earlier_acme, list):
            raise TypeError("earlier_acme must be a list of strings")
        if not all(isinstance(m, str) for m in self.earlier_supplier):
            raise TypeError("every item in earlier_supplier must be a string")
        if not all(isinstance(m, str) for m in self.earlier_acme):
            raise TypeError("every item in earlier_acme must be a string")


@dataclass(frozen=True)
class RawOffer:
    """A price offer as extracted from text, before normalization."""

    status: str                       # "OK" or "NO_PRICE"
    amount: Optional[float] = None
    currency: Optional[str] = None    # e.g. "INR", "USD", "EUR", "GBP"
    gst_inclusive: bool = False
    period: Optional[str] = None      # "month", "year", or None
    unit_token: Optional[str] = None  # "unit", "dozen", "pack", "ream", or None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.status not in VALID_RAW_STATUSES:
            raise ValueError(f"Invalid RawOffer status: {self.status!r}")
        if self.period is not None and self.period not in VALID_PERIODS:
            raise ValueError(f"Invalid period: {self.period!r}")
        if self.unit_token is not None and self.unit_token not in VALID_UNIT_TOKENS:
            raise ValueError(f"Invalid unit_token: {self.unit_token!r}")


@dataclass(frozen=True)
class Params:
    """All policy values that apply to one thread (category + supplier + date)."""

    category: str
    supplier: str
    as_of: str                        # the thread date used for amendment lookup
    unit_text: str                    # the unit wording from the category page
    gst_rate: float                   # e.g. 0.18 for 18 percent
    target: float
    walkaway: float
    rounds: int                       # R, the maximum number of rounds
    beta: float                       # concession exponent
    approval_limit: Optional[float]
    billing_period: Optional[str]     # policy-level billing default, if any (to confirm)
    units_per_token: dict[str, float] = field(default_factory=dict)
    fx_rates: dict[str, float] = field(default_factory=dict)
    supplier_status: str = "APPROVED"     # APPROVED, PROBATION or BLACKLISTED
    walkaway_source: str = "category"     # "category" or "supplier_contract_cap"
    applied_amendments: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class NormalizedOffer:
    """A price converted into a per-unit, pre-GST, INR figure."""

    ok: bool
    price: Optional[float] = None
    missing_reason: Optional[str] = None
    steps: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.ok and self.price is None:
            raise ValueError("A successful NormalizedOffer must include a price")
        if not self.ok and not self.missing_reason:
            raise ValueError("A failed NormalizedOffer must include a missing_reason")


@dataclass(frozen=True)
class DecisionResult:
    """The output of the decision engine for one thread."""

    decision: Decision
    price: Optional[float] = None     # normalized offer price, if any
    limit: Optional[float] = None     # concession limit L(r) used for the comparison
    trace: list[str] = field(default_factory=list)  # human-readable audit trail
