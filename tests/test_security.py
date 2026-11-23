"""Tests for src/security_checker.py. Owner: Member 3 (Security and Decision Engine)."""

import pytest

from src import security_checker

EXPECTED_FUNCTIONS = ["is_blacklisted", "detect_prompt_injection"]


def test_module_exposes_agreed_interface():
    """Confirms every agreed function name exists and is callable."""
    for name in EXPECTED_FUNCTIONS:
        assert callable(getattr(security_checker, name, None)), f"missing {name}"


@pytest.mark.skip(reason="Phase 4: Member 3 writes real security tests here")
def test_security_behaviour_placeholder():
    pass
