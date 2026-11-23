"""
src/message_parser.py
Owner: Member 2 (Message Parser)
Depends on: src.schemas

Splits a thread into its parts and extracts the latest supplier offer
as a RawOffer. Contains no policy logic.

Phase 3 status: STUB. Bodies raise NotImplementedError until Phase 4.
"""

from __future__ import annotations

from typing import Optional

from src.schemas import RawOffer, ThreadText

_PHASE4_MSG = "Phase 4: to be implemented by Member 2 (Message Parser)."


def split_thread(raw_message: str) -> ThreadText:
    """Split the raw thread into its four parts.

    Returns a ThreadText where:
      - latest is the latest supplier message only (str)
      - earlier_supplier is a list[str] of earlier supplier messages, in order
      - earlier_acme is a list[str] of Acme's own earlier messages, in order
      - full is the whole thread (str)
    The two earlier_* fields must be lists, never a single string.
    """
    raise NotImplementedError(_PHASE4_MSG)


def parse_amount(text: str) -> Optional[float]:
    """Parse a numeric amount from text (lakh, k notation, words). Return None if absent."""
    raise NotImplementedError(_PHASE4_MSG)


def extract_offer(text: ThreadText, quantity: int) -> RawOffer:
    """Extract the latest supplier offer from a ThreadText. Returns a RawOffer."""
    raise NotImplementedError(_PHASE4_MSG)
