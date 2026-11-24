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
            r"\b(?:ignore|disregard|forget|override|bypass|skip)\b.{0,80}\b(?:previous|above|prior|all|system|policy|policies|rule|rules|instructions?|prompt|limit|walkaway|approval|eval|evaluator)\b|"
            r"\[admin\s+override\]",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "addressed_to_ai_or_reviewer",
        re.compile(
            r"(?:note\s+(?:for|to)\s+(?:the\s+)?(?:ai|llm|language\s+model|model|bot|assistant|reviewer|automated\s+system|scoring\s+system)|"
            r"(?:dear|attention|to|p\.?s\.?\s+to)\s+(?:whichever\s+)?(?:ai|llm|language\s+model|model|bot|assistant|reviewer|automated\s+system)\b|"
            r"(?:<!--\s*)?(?:ai|assistant|system\s+note(?:\s+to\s+ai\s+agent)?)\s*:\s*|"
            r"(?:automated\s+system|bot|assistant|model|llm)\s+(?:is\s+reading|screens?|processing|evaluating)|"
            r"(?:reviewing\s+assistant|automated\s+system|ai\s+model)\s+(?:should|must|please)\s+(?:accept|approve))",
            re.IGNORECASE,
        ),
    ),
    (
        "claimed_preapproval_or_override",
        re.compile(
            r"\b(?:already\s+(?:approved|authorized|cleared|waived|accepted|signed\s+off)|"
            r"approval\s+(?:(?:already|has\s+been)\s+)?(?:granted|given|confirmed|issued)|"
            r"(?:are|is|was)\s+pre-?approved|"
            r"pre-?approved\s+by\s+(?:management|procurement|finance|admin|legal|vp|director|cfo|ceo|board)|"
            r"(?:cfo|ceo|management|procurement)\s+already\s+signed\s+off|"
            r"(?:system|admin|policy|manager)\s+override|"
            r"force[_\s-]?(?:accept|approve)|"
            r"mark\s+(?:this\s+thread\s+as\s+|it\s+)?(?:accepted?|approved?)|"
            r"record\s+the\s+decision\s+as\s+approved)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "multilingual_override_or_approval",
        re.compile(
            r"(?:pehle\s+hi\s+(?:approve|manzoor|pakka)|"
            r"system\s+ko\s+(?:ignore|bypass|approve)|"
            r"नियम\s*(?:अनदेखा|छोड़|नजरअंदाज)|पहले\s*से\s*(?:मंज़ूर|मंजूर|स्वीकृत)|"
            r"(?:AI|एआई)?\s*सहायक\s*(?:के\s*लिए\s*निर्देश)?|निर्देश\s*:\s*इस\s*डील)",
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
