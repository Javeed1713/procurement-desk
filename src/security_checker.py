"""
src/security_checker.py
Owner: Member 3 (Security and Decision Engine)
Depends on: nothing inside src/

Checks supplier blacklist status and scans for prompt-injection attempts.
Banned-term detection lives in policy_engine.find_banned_terms.
"""

from __future__ import annotations

import re
from typing import Iterable

_BLACKLIST_EXACT = {
    "BLACKLISTED",
    "BLACK_LISTED",
    "BANNED",
    "SUSPENDED_BLACKLIST",
}

_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "override_or_ignore_instructions",
        re.compile(
            r"\b(?:ignore|disregard|forget|override|bypass|skip)\b.{0,80}\b(?:previous|above|prior|all|system|policy|policies|rule|rules|instructions?|prompt|limit|walkaway|approval|eval|evaluator)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "addressed_to_ai_or_reviewer",
        re.compile(
            r"(?:note\s+for\s+(?:the\s+)?(?:ai|llm|language\s+model|model|bot|assistant|reviewer|automated\s+system|scoring\s+system)|"
            r"(?:dear|attention|to)\s+(?:ai|llm|language\s+model|model|bot|assistant|reviewer)\b)",
            re.IGNORECASE,
        ),
    ),
    (
        "claimed_preapproval_or_override",
        re.compile(
            r"\b(?:already\s+(?:approved|authorized|cleared|waived|accepted)|"
            r"approval\s+(?:has\s+been\s+)?(?:granted|given|confirmed|issued)|"
            r"pre-?approved\s+by\s+(?:management|procurement|finance|admin|legal|vp|director)|"
            r"(?:system|admin|policy|manager)\s+override|"
            r"force[_\s-]?(?:accept|approve))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "multilingual_override_or_approval",
        re.compile(
            r"(?:pehle\s+hi\s+(?:approve|manzoor|pakka)|"
            r"system\s+ko\s+(?:ignore|bypass|approve)|"
            r"नियम\s*(?:अनदेखा|छोड़|नजरअंदाज)|पहले\s*से\s*(?:मंज़ूर|मंजूर|स्वीकृत))",
            re.IGNORECASE,
        ),
    ),
]


def is_blacklisted(supplier_status: str | None) -> bool:
    """Return True when the supplier status indicates BLACKLISTED."""
    if not supplier_status:
        return False
    cleaned = supplier_status.strip().upper()
    if cleaned.startswith("BLACKLISTED"):
        return True
    normalized = re.sub(r"[\s\-]+", "_", cleaned)
    return normalized in _BLACKLIST_EXACT


def detect_prompt_injection(full_text: str | Iterable[str] | None) -> list[str]:
    """Return pattern identifiers found anywhere in the full thread."""
    if not full_text:
        return []

    if isinstance(full_text, str):
        haystack = full_text
    else:
        haystack = "\n".join(part for part in full_text if isinstance(part, str) and part)

    if not haystack.strip():
        return []

    matches: list[str] = []
    for label, pattern in _INJECTION_PATTERNS:
        if pattern.search(haystack):
            matches.append(label)
    return matches
