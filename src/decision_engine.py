"""
src/decision_engine.py
Owner: Member 3 (Security and Decision Engine)
Depends on: src.schemas, src.policy_engine, src.message_parser,
            src.security_checker

Applies the ordered decision procedure to one thread and returns a DecisionResult.
"""

from __future__ import annotations

import math

from src.message_parser import extract_offer, split_thread
from src.policy_engine import (
    PolicyBook,
    counter_price,
    exceeds_approval_limit,
    find_banned_terms,
    get_params,
    is_final_round,
    normalize_offer,
    price_limit,
    round_half_up,
)
from src.schemas import Decision, DecisionResult, NormalizedOffer, Params, ThreadRecord, ThreadText
from src.security_checker import detect_prompt_injection, is_blacklisted


def _reconstruct_full_text(text: ThreadText) -> str:
    if text.full and text.full.strip():
        return text.full
    parts: list[str] = []
    parts.extend(m for m in text.earlier_acme if m)
    parts.extend(m for m in text.earlier_supplier if m)
    if text.latest:
        parts.append(text.latest)
    return "\n".join(parts)


def _is_probation(params: Params) -> bool:
    status = (params.supplier_status or "").strip().upper()
    return status == "PROBATION" or status.startswith("PROBATION")


def _effective_limit(params: Params, round_no: int) -> float:
    if _is_probation(params):
        return float(params.target)
    return float(price_limit(params, round_no))


def _effective_counter(params: Params, round_no: int, limit_val: float) -> int:
    if _is_probation(params):
        return int(round_half_up(limit_val))
    return int(counter_price(params, round_no))


def apply_rules(
    *,
    params: Params,
    norm: NormalizedOffer,
    text: ThreadText,
    quantity: int,
    round_no: int,
) -> DecisionResult:
    """Apply the ordered rules to already-parsed inputs and return a DecisionResult."""
    trace: list[str] = []
    offer_price = norm.price if norm.ok else None

    # 1. Missing information
    if not norm.ok or norm.price is None or not math.isfinite(norm.price) or norm.price <= 0:
        detail = norm.missing_reason or "missing_or_invalid_price"
        trace.append(f"1_missing_info:{detail}")
        return DecisionResult(
            decision=Decision(action="ESCALATE", reason="MISSING_INFO", counter_price=None),
            price=offer_price,
            limit=None,
            trace=trace,
        )

    # 2. Blacklisted supplier
    if is_blacklisted(params.supplier_status):
        trace.append("2_blacklisted_supplier")
        return DecisionResult(
            decision=Decision(action="REJECT", reason="BLACKLISTED_SUPPLIER", counter_price=None),
            price=offer_price,
            limit=None,
            trace=trace,
        )

    # 3. Prompt injection anywhere in the thread
    injections = detect_prompt_injection(_reconstruct_full_text(text))
    if injections:
        trace.append(f"3_prompt_injection:{','.join(injections)}")
        return DecisionResult(
            decision=Decision(action="ESCALATE", reason="PROMPT_INJECTION", counter_price=None),
            price=offer_price,
            limit=None,
            trace=trace,
        )

    # 4. Banned contractual terms in latest supplier message
    banned = find_banned_terms(text.latest)
    if banned:
        trace.append(f"4_banned_term:{len(banned)}_matched")
        return DecisionResult(
            decision=Decision(action="ESCALATE", reason="BANNED_TERM", counter_price=None),
            price=offer_price,
            limit=None,
            trace=trace,
        )

    # 5. Price comparison against concession limit L(r) (or target for PROBATION)
    limit_val = _effective_limit(params, round_no)
    trace.append(f"5_price_check:price={offer_price},limit={limit_val},round={round_no}")

    if offer_price > limit_val:
        if is_final_round(params, round_no):
            trace.append("5b_above_walkaway_final_round")
            return DecisionResult(
                decision=Decision(action="REJECT", reason="ABOVE_WALKAWAY", counter_price=None),
                price=offer_price,
                limit=limit_val,
                trace=trace,
            )
        c_price = _effective_counter(params, round_no, limit_val)
        trace.append(f"5c_counter_offer:counter={c_price}")
        return DecisionResult(
            decision=Decision(action="COUNTER", reason="COUNTER_OFFER", counter_price=c_price),
            price=offer_price,
            limit=limit_val,
            trace=trace,
        )

    # 6. Approval limit check (only after price is acceptable)
    if exceeds_approval_limit(offer_price, quantity, params):
        trace.append(f"6_over_approval_limit:qty={quantity}")
        return DecisionResult(
            decision=Decision(action="ESCALATE", reason="OVER_APPROVAL_LIMIT", counter_price=None),
            price=offer_price,
            limit=limit_val,
            trace=trace,
        )

    trace.append("6_acceptable_price")
    return DecisionResult(
        decision=Decision(action="ACCEPT", reason="ACCEPTABLE_PRICE", counter_price=None),
        price=offer_price,
        limit=limit_val,
        trace=trace,
    )


def decide(thread: ThreadRecord, book: PolicyBook) -> DecisionResult:
    """Full pipeline for one thread: split, resolve policy, extract, normalize, apply rules."""
    thread_text = split_thread(thread.raw_message)
    params = get_params(book, thread.supplier, thread.category, thread.date)
    raw_offer = extract_offer(thread_text, thread.quantity)
    norm = normalize_offer(raw_offer, params)
    return apply_rules(
        params=params,
        norm=norm,
        text=thread_text,
        quantity=thread.quantity,
        round_no=thread.round,
    )
