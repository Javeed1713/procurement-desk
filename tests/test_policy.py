"""Tests for src/policy_engine.py. Owner: Member 1 (Policy Engine)."""

from pathlib import Path

from src import policy_engine
from src.schemas import Params, RawOffer

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


def _make_params(**overrides) -> Params:
    base = {
        "category": "catering",
        "supplier": "arvind-office-supplies",
        "as_of": "2026-05-01",
        "unit_text": "INR excl. GST per meal",
        "gst_rate": 0.05,
        "target": 280.0,
        "walkaway": 340.0,
        "rounds": 3,
        "beta": 1.0,
        "approval_limit": 600000.0,
        "billing_period": None,
        "units_per_token": {"unit": 1, "dozen": 12},
        "fx_rates": {"INR": 1.0, "USD": 84.5, "EUR": 91.0, "GBP": 106.0},
        "supplier_status": "APPROVED",
        "walkaway_source": "category",
        "applied_amendments": [],
    }
    base.update(overrides)
    return Params(**base)


def test_module_exposes_agreed_interface():
    """Confirms every agreed function name exists and is callable."""
    for name in EXPECTED_FUNCTIONS:
        assert callable(getattr(policy_engine, name, None)), f"missing {name}"


def test_round_half_up_avoids_bankers_rounding():
    assert policy_engine.round_half_up(2.5) == 3
    assert policy_engine.round_half_up(3.5) == 4
    assert policy_engine.round_half_up(12000.5) == 12001


def test_price_limit_and_final_round():
    params = _make_params(target=280.0, walkaway=340.0, rounds=3, beta=1.0)
    assert policy_engine.price_limit(params, 1) == 280.0
    assert policy_engine.price_limit(params, 2) == 310.0
    assert policy_engine.price_limit(params, 3) == 340.0
    assert policy_engine.counter_price(params, 2) == 310
    assert policy_engine.is_final_round(params, 2) is False
    assert policy_engine.is_final_round(params, 3) is True


def test_normalize_offer_fx_gst_period_and_missing_cases():
    params = _make_params(gst_rate=0.05, billing_period="year")

    ok_norm = policy_engine.normalize_offer(
        RawOffer(status="OK", amount=100.0, currency="USD", gst_inclusive=True, period="year"),
        params,
    )
    assert ok_norm.ok is True
    assert ok_norm.price is not None
    assert abs(ok_norm.price - ((100.0 * 84.5) / 1.05)) < 1e-6

    missing_period = policy_engine.normalize_offer(
        RawOffer(status="OK", amount=1000.0, currency="INR", period=None),
        params,
    )
    assert missing_period.ok is False
    assert missing_period.missing_reason == "missing_billing_period"

    bad_currency = policy_engine.normalize_offer(
        RawOffer(status="OK", amount=100.0, currency="JPY"),
        params,
    )
    assert bad_currency.ok is False


def test_exceeds_approval_limit_boundary():
    params = _make_params(approval_limit=600000.0)
    assert policy_engine.exceeds_approval_limit(300.0, 2000, params) is False
    assert policy_engine.exceeds_approval_limit(300.01, 2000, params) is True


def test_find_banned_terms():
    assert policy_engine.find_banned_terms("Contract auto-renews every year.")
    assert policy_engine.find_banned_terms("Requires 50% advance payment.")
    assert policy_engine.find_banned_terms("Includes unlimited liability for Acme.")
    assert policy_engine.find_banned_terms("Net-30 payment, 20% advance, no exclusivity.") == []


def test_load_policy_and_get_params_on_playbook():
    playbook_path = Path("data/playbook")
    if not playbook_path.exists():
        return
    book = policy_engine.load_policy(playbook_path)
    p_catering = policy_engine.get_params(book, "arvind-office-supplies", "catering", "2026-05-01")
    assert p_catering.target == 280.0
    assert p_catering.walkaway == 340.0
    assert abs(p_catering.gst_rate - 0.05) < 1e-6

    p_arvind = policy_engine.get_params(book, "arvind-office-supplies", "catering", "2026-05-01")
    assert p_arvind.fx_rates["GBP"] == 104.5
