"""
src/decision_engine.py
Owner: Member 3 (Security and Decision Engine)
Depends on: src.schemas, src.policy_engine, src.message_parser,
            src.security_checker

Applies the decision sequence to one thread and returns a DecisionResult.
The exact rule order must be confirmed against decision-procedure.md
before implementation (see the Phase 4 verification step).

Phase 3 status: STUB. Bodies raise NotImplementedError until Phase 4.
"""

from __future__ import annotations

from src.policy_engine import PolicyBook
from src.schemas import DecisionResult, NormalizedOffer, Params, ThreadRecord, ThreadText

_PHASE4_MSG = "Phase 4: to be implemented by Member 3 (Decision Engine)."


def apply_rules(
    *,
    params: Params,
    norm: NormalizedOffer,
    text: ThreadText,
    quantity: int,
    round_no: int,
) -> DecisionResult:
    """Apply the ordered rules to already-parsed inputs and return a DecisionResult."""
    raise NotImplementedError(_PHASE4_MSG)


def decide(thread: ThreadRecord, book: PolicyBook) -> DecisionResult:
    """Full pipeline for one thread: parse, normalize, then apply_rules."""
    raise NotImplementedError(_PHASE4_MSG)
