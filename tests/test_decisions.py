"""Tests for src/decision_engine.py. Owner: Member 3 (Security and Decision Engine)."""

import pytest

from src import decision_engine

EXPECTED_FUNCTIONS = ["apply_rules", "decide"]


def test_module_exposes_agreed_interface():
    """Confirms every agreed function name exists and is callable."""
    for name in EXPECTED_FUNCTIONS:
        assert callable(getattr(decision_engine, name, None)), f"missing {name}"


@pytest.mark.skip(reason="Phase 4: Member 3 writes real decision tests here")
def test_decision_behaviour_placeholder():
    pass
