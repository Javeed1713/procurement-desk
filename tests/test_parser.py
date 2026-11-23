"""Tests for src/message_parser.py. Owner: Member 2 (Message Parser)."""

import pytest

from src import message_parser

EXPECTED_FUNCTIONS = ["split_thread", "parse_amount", "extract_offer"]


def test_module_exposes_agreed_interface():
    """Confirms every agreed function name exists and is callable."""
    for name in EXPECTED_FUNCTIONS:
        assert callable(getattr(message_parser, name, None)), f"missing {name}"


@pytest.mark.skip(reason="Phase 4: Member 2 writes real parser tests here")
def test_parser_behaviour_placeholder():
    pass
