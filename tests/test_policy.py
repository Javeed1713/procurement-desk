"""Tests for src/policy_engine.py. Owner: Member 1 (Policy Engine)."""

import pytest

from src import policy_engine

EXPECTED_FUNCTIONS = [
    "load_policy",
    "get_params",
    "normalize_offer",
    "price_limit",
    "counter_price",
    "is_final_round",
    "exceeds_approval_limit",
    "round_half_up",
    "find_banned_terms",
]


def test_module_exposes_agreed_interface():
    """Confirms every agreed function name exists and is callable."""
    for name in EXPECTED_FUNCTIONS:
        assert callable(getattr(policy_engine, name, None)), f"missing {name}"


@pytest.mark.skip(reason="Phase 4: Member 1 writes real policy tests here")
def test_policy_behaviour_placeholder():
    pass
