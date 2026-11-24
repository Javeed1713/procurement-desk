"""Tests for src/message_parser.py. Owner: Member 2 (Message Parser)."""

import pytest

from src import message_parser

EXPECTED_FUNCTIONS = ["split_thread", "parse_amount", "extract_offer"]


def test_module_exposes_agreed_interface():
    """Confirms every agreed function name exists and is callable."""
    for name in EXPECTED_FUNCTIONS:
        assert callable(getattr(message_parser, name, None)), f"missing {name}"


def test_precedent_p01_range_upper_bound():
    """Precedent P-01: Range offers evaluate at upper bound."""
    thread = message_parser.split_thread(
        "Supplier quoted between ₹13,400 and ₹14,600 per monitor depending on final specs."
    )
    raw = message_parser.extract_offer(thread, quantity=10)
    assert raw.status == "OK"
    assert raw.amount == 14600.0


def test_precedent_p02_free_units_catering():
    """Precedent P-02: '₹300 per meal, plus 1 free meal for every 10 you pay for' -> 300 * 10 / 11."""
    thread = message_parser.split_thread(
        "We offer ₹300 per meal, plus 1 free meal for every 10 you pay for."
    )
    raw = message_parser.extract_offer(thread, quantity=50)
    assert raw.status == "OK"
    assert raw.amount == pytest.approx(300.0 * 10.0 / 11.0, rel=1e-4)


def test_precedent_p04_headsets_range():
    """Precedent P-04: Range upper bound evaluated properly."""
    thread = message_parser.split_thread(
        "For the headsets, we offer between ₹3,300 and ₹3,700 per headset."
    )
    raw = message_parser.extract_offer(thread, quantity=20)
    assert raw.status == "OK"
    assert raw.amount == 3700.0


def test_precedent_p05_free_units_courier():
    """Precedent P-05: '₹170 per shipment, plus 1 free shipment for every 5 you pay for' -> 170 * 5 / 6."""
    thread = message_parser.split_thread(
        "We offer ₹170 per shipment, plus 1 free shipment for every 5 you pay for."
    )
    raw = message_parser.extract_offer(thread, quantity=50)
    assert raw.status == "OK"
    assert raw.amount == pytest.approx(170.0 * 5.0 / 6.0, rel=1e-4)


def test_precedent_p06_subscription_period_detected():
    """Precedent P-06: Monthly period detected for CRM licenses."""
    thread = message_parser.split_thread(
        "We quote ₹1,600 per seat per month for CRM licenses."
    )
    raw = message_parser.extract_offer(thread, quantity=10)
    assert raw.status == "OK"
    assert raw.amount == 1600.0
    assert raw.period == "month"
