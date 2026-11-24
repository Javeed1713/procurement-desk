"""Tests for src/policy_engine.py. Owner: Member 1 (Policy Engine)."""

from pathlib import Path

import pytest

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


def test_precedent_p03_contract_rate_override():
    """Precedent P-03: Supplier USD contract rate replaces default table rate."""
    params = _make_params(fx_rates={"INR": 1.0, "USD": 82.0})
    offer = RawOffer(status="OK", amount=760.0, currency="USD")
    norm = policy_engine.normalize_offer(offer, params)
    assert norm.ok is True
    assert norm.price == pytest.approx(62320.0)


def test_precedent_p06_crm_subscription_normalization():
    """Precedent P-06: Monthly quote for annual CRM normalized to yearly."""
    params = _make_params(billing_period="year")
    offer = RawOffer(status="OK", amount=1600.0, currency="INR", period="month")
    norm = policy_engine.normalize_offer(offer, params)
    assert norm.ok is True
    assert norm.price == pytest.approx(19200.0)


def test_precedent_p07_auto_renewal_banned():
    """Precedent P-07: 'the contract continues from year to year unless either party gives notice'."""
    text = "the contract continues from year to year unless either party gives notice"
    banned = policy_engine.find_banned_terms(text)
    assert "auto_renewal" in banned


def test_banned_terms_allowed_exceptions():
    """Allowed terms must not be flagged as banned."""
    assert policy_engine.find_banned_terms("We are not asking for exclusivity.") == []
    assert policy_engine.find_banned_terms("There is no automatic renewal; renewal only if both parties sign again.") == []
    assert policy_engine.find_banned_terms("Payment terms: 20% advance, balance net-30 after delivery.") == []
    assert policy_engine.find_banned_terms("30% advance is acceptable to us if that helps your finance team.") == []


def test_banned_terms_violations():
    """All playbook banned terms must be detected."""
    assert "upfront_over_30_pct" in policy_engine.find_banned_terms("We need 40% of the order value upfront.")
    assert "upfront_over_30_pct" in policy_engine.find_banned_terms("Payment terms: 60% advance, balance on delivery.")
    assert "upfront_over_30_pct" in policy_engine.find_banned_terms("We will need half the order value upfront.")
    assert "unlimited_liability" in policy_engine.find_banned_terms("Acme's liability under this contract shall be unlimited.")
    assert "exclusivity" in policy_engine.find_banned_terms("Acme agrees to use us as its exclusive supplier for three years.")
    assert "auto_renewal" in policy_engine.find_banned_terms("The agreement renews on its own at the end of every term.")
    assert "auto_renewal" in policy_engine.find_banned_terms("This agreement auto-renews every year unless cancelled in writing.")


def test_supplier_walkaway_cap_category_scoped():
    """Supplier price cap for one category must NOT affect another category."""
    playbook_path = Path("data/playbook")
    if not playbook_path.exists():
        return
    book = policy_engine.load_policy(playbook_path)

    # Monsoon Foods has cap for headsets of 4,500
    p_headsets = policy_engine.get_params(book, "monsoon-foods", "headsets", "2026-11-27")
    assert p_headsets.walkaway == 4500.0
    assert p_headsets.walkaway_source == "supplier_contract_cap"

    # Laptops must use category walkaway (70,000), not the headset cap!
    p_laptops = policy_engine.get_params(book, "monsoon-foods", "laptops", "2026-11-27")
    assert p_laptops.walkaway == 70000.0
    assert p_laptops.walkaway_source == "category"


def test_blacklisted_supplier_status_parsed_correctly():
    """Markdown bold markers must not prevent blacklisted status detection."""
    playbook_path = Path("data/playbook")
    if not playbook_path.exists():
        return
    book = policy_engine.load_policy(playbook_path)
    for sup_id in ["orbit-electronics", "greenleaf-facility-care", "lumen-workspace"]:
        sup = book.suppliers.get(sup_id)
        assert sup is not None, f"Supplier {sup_id} missing"
        assert sup.status == "BLACKLISTED", f"Expected BLACKLISTED for {sup_id}, got {sup.status}"


def test_probation_supplier_status_parsed_correctly():
    """Markdown bold markers must not prevent probation status detection."""
    playbook_path = Path("data/playbook")
    if not playbook_path.exists():
        return
    book = policy_engine.load_policy(playbook_path)
    for sup_id in ["banyan-guarding", "jade-express", "vertex-mobile", "zephyr-saas"]:
        sup = book.suppliers.get(sup_id)
        assert sup is not None, f"Supplier {sup_id} missing"
        assert sup.status == "PROBATION", f"Expected PROBATION for {sup_id}, got {sup.status}"



# ---------------------------------------------------------------------------
# Phase 2 Fix 1: Exclusivity "only from us" / "only from this supplier" tests
# ---------------------------------------------------------------------------

def test_exclusivity_only_from_us_is_banned():
    """'only from us' phrasing must trigger ESCALATE:BANNED_TERM."""
    text = "Acme will buy these items only from us for the next two years."
    result = policy_engine.find_banned_terms(text)
    assert "exclusivity" in result, f"Expected 'exclusivity' banned term, got: {result}"


def test_exclusivity_only_from_this_supplier_is_banned():
    """'only from this supplier' phrasing must trigger ESCALATE:BANNED_TERM."""
    text = "We require that Acme buy only from this supplier going forward."
    result = policy_engine.find_banned_terms(text)
    assert "exclusivity" in result, f"Expected 'exclusivity' banned term, got: {result}"


def test_not_asking_for_exclusivity_is_allowed():
    """'We are not asking for exclusivity' must NOT trigger banned-term check."""
    text = "We are not asking for exclusivity."
    result = policy_engine.find_banned_terms(text)
    assert "exclusivity" not in result, f"Should not flag exclusivity here, got: {result}"


def test_for_exclusivity_lookbehind_is_allowed():
    """'for exclusivity' (preceded by 'for') must NOT match."""
    text = "We are not negotiating for exclusivity in this round."
    result = policy_engine.find_banned_terms(text)
    assert "exclusivity" not in result, f"Should not flag exclusivity here, got: {result}"


# ---------------------------------------------------------------------------
# Phase 2 Fix 4: Missing billing period for security-guards category
# ---------------------------------------------------------------------------

def test_missing_billing_period_security_guards():
    """A price with no billing period for security-guards must return MISSING_INFO."""
    from pathlib import Path
    from src.schemas import RawOffer

    playbook_path = Path("data/playbook")
    if not playbook_path.exists():
        return

    book = policy_engine.load_policy(playbook_path)
    params = policy_engine.get_params(book, "banyan-guarding", "security-guards", "2026-11-15")
    assert params.billing_period == "month", (
        f"security-guards should have billing_period='month', got {params.billing_period}"
    )
    # Offer with no period (like "Rs. 8,300 per guard for this order")
    offer = RawOffer(status="OK", amount=8300.0, currency="INR", gst_inclusive=False, period=None)
    norm = policy_engine.normalize_offer(offer, params)
    assert not norm.ok, "Offer without period should not normalize successfully"
    assert norm.missing_reason == "missing_billing_period", (
        f"Expected missing_billing_period, got {norm.missing_reason}"
    )
