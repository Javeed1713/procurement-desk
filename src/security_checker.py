"""
src/security_checker.py
Owner: Member 3 (Security and Decision Engine)
Depends on: nothing inside src/

Checks supplier blacklist status and scans for prompt-injection attempts.
Banned-term detection lives in policy_engine.find_banned_terms.

Phase 3 status: STUB. Bodies raise NotImplementedError until Phase 4.
"""

from __future__ import annotations

_PHASE4_MSG = "Phase 4: to be implemented by Member 3 (Security)."


def is_blacklisted(supplier_status: str) -> bool:
    """Return True when the supplier status is BLACKLISTED."""
    raise NotImplementedError(_PHASE4_MSG)


def detect_prompt_injection(full_text: str) -> list[str]:
    """Return the injection patterns found anywhere in the full thread."""
    raise NotImplementedError(_PHASE4_MSG)
