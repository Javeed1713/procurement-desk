"""
tests/test_message_parser.py
Comprehensive test suite for src/message_parser.py.
Owner: Member 2 (Message Parser)
"""

import pytest

from src import message_parser
from src.schemas import RawOffer, ThreadText


# ---------------------------------------------------------------------------
# Interface and Contract Verification
# ---------------------------------------------------------------------------

def test_module_exposes_agreed_interface():
    """Verify that all agreed function names exist and are callable."""
    expected = ["split_thread", "parse_amount", "extract_offer"]
    for name in expected:
        fn = getattr(message_parser, name, None)
        assert callable(fn), f"message_parser missing callable {name}"


# ---------------------------------------------------------------------------
# Tests for split_thread
# ---------------------------------------------------------------------------

def test_split_thread_single_message():
    """A thread with a single supplier message and no markers."""
    raw = "Namaste team,\nWe quote Rs. 1,500 per fixture.\nWarm regards,\nVendor A"
    result = message_parser.split_thread(raw)

    assert isinstance(result, ThreadText)
    assert result.latest == raw.strip()
    assert result.earlier_supplier == []
    assert result.earlier_acme == []
    assert result.full == raw


def test_split_thread_multi_message_chronological_order():
    """Split a multi-message thread and verify order and separation."""
    raw = (
        "[Earlier message — Supplier X, 2026-10-01]\n"
        "Our initial quote was ₹10,000 per unit.\n\n"
        "[Earlier message — Acme Procurement]\n"
        "We can offer ₹8,500 per unit.\n\n"
        "[Earlier message — Supplier X, 2026-10-05]\n"
        "We can reduce to ₹9,200 per unit.\n\n"
        "[Latest message — Supplier X, 2026-10-10]\n"
        "Our final price is ₹8,900 per unit.\n"
    )
    result = message_parser.split_thread(raw)

    assert result.latest == "Our final price is ₹8,900 per unit."
    assert len(result.earlier_supplier) == 2
    assert result.earlier_supplier[0] == "Our initial quote was ₹10,000 per unit."
    assert result.earlier_supplier[1] == "We can reduce to ₹9,200 per unit."
    assert len(result.earlier_acme) == 1
    assert result.earlier_acme[0] == "We can offer ₹8,500 per unit."
    assert result.full == raw


def test_split_thread_acme_identification():
    """Acme messages must never be classified as supplier messages."""
    raw = (
        "[Earlier message — Acme Procurement]\n"
        "Our counteroffer is ₹5,000.\n\n"
        "[Latest message — Vendor Corp, 2026-11-01]\n"
        "We accept ₹5,200.\n"
    )
    result = message_parser.split_thread(raw)

    assert result.earlier_supplier == []
    assert result.earlier_acme == ["Our counteroffer is ₹5,000."]
    assert result.latest == "We accept ₹5,200."


def test_split_thread_earlier_lists_are_always_lists():
    """Contract: earlier_supplier and earlier_acme must always be lists, never strings."""
    # Empty earlier lists
    result1 = message_parser.split_thread("Single message")
    assert isinstance(result1.earlier_supplier, list)
    assert isinstance(result1.earlier_acme, list)

    # Populated earlier lists
    raw = (
        "[Earlier message — Supplier A, 2026-09-01]\nQuote 1\n\n"
        "[Earlier message — Acme Procurement]\nCounter 1\n\n"
        "[Latest message — Supplier A, 2026-09-05]\nQuote 2"
    )
    result2 = message_parser.split_thread(raw)
    assert isinstance(result2.earlier_supplier, list)
    assert isinstance(result2.earlier_acme, list)
    assert all(isinstance(x, str) for x in result2.earlier_supplier)
    assert all(isinstance(x, str) for x in result2.earlier_acme)


def test_split_thread_empty_and_malformed_input():
    """Handle empty strings and malformed formats safely."""
    empty_result = message_parser.split_thread("")
    assert empty_result.latest == ""
    assert empty_result.earlier_supplier == []
    assert empty_result.earlier_acme == []
    assert empty_result.full == ""

    whitespace_result = message_parser.split_thread("   \n\t  ")
    assert whitespace_result.latest == ""
    assert whitespace_result.earlier_supplier == []
    assert whitespace_result.earlier_acme == []


# ---------------------------------------------------------------------------
# Tests for parse_amount
# ---------------------------------------------------------------------------

def test_parse_amount_indian_notation():
    """Indian comma notation with lakh and crore groupings."""
    assert message_parser.parse_amount("₹1,19,990") == 119990.0
    assert message_parser.parse_amount("₹44,07,800") == 4407800.0
    assert message_parser.parse_amount("Rs. 1,506") == 1506.0
    assert message_parser.parse_amount("Rs 12,662") == 12662.0


def test_parse_amount_comma_separated_and_decimals():
    """Standard international comma and decimal notations."""
    assert message_parser.parse_amount("$1,234.56") == 1234.56
    assert message_parser.parse_amount("GBP 79.75") == 79.75
    assert message_parser.parse_amount("INR 4,049.50") == 4049.5
    assert message_parser.parse_amount("1,500.5") == 1500.5


def test_parse_amount_lakh_and_k_notation():
    """Scale suffixes: lakh, k, thousand, crore."""
    assert message_parser.parse_amount("₹1.2 lakh") == 120000.0
    assert message_parser.parse_amount("1.2 lakh") == 120000.0
    assert message_parser.parse_amount("2 lakh") == 200000.0
    assert message_parser.parse_amount("18.5k") == 18500.0
    assert message_parser.parse_amount("₹18.5k") == 18500.0
    assert message_parser.parse_amount("1.5 thousand") == 1500.0
    assert message_parser.parse_amount("1 crore") == 10000000.0


def test_parse_amount_in_words():
    """Amounts expressed in English words."""
    assert message_parser.parse_amount("one lakh twenty thousand") == 120000.0
    assert message_parser.parse_amount("fifty thousand") == 50000.0
    assert message_parser.parse_amount("two thousand five hundred") == 2500.0
    assert message_parser.parse_amount("twenty-six thousand four hundred rupees") == 26400.0
    assert message_parser.parse_amount("two hundred sixty-six rupees") == 266.0
    assert message_parser.parse_amount("thirteen thousand rupees") == 13000.0


def test_parse_amount_currencies():
    """Supported and detected currency notations."""
    assert message_parser.parse_amount("$760") == 760.0
    assert message_parser.parse_amount("USD 760") == 760.0
    assert message_parser.parse_amount("€1200") == 1200.0
    assert message_parser.parse_amount("EUR 1200") == 1200.0
    assert message_parser.parse_amount("£79.75") == 79.75
    assert message_parser.parse_amount("GBP 79.75") == 79.75
    assert message_parser.parse_amount("¥50,000") == 50000.0
    assert message_parser.parse_amount("JPY 50,000") == 50000.0
    assert message_parser.parse_amount("AED 462") == 462.0
    assert message_parser.parse_amount("SGD 150") == 150.0


def test_parse_amount_avoids_non_price_numbers():
    """Avoid accidental extraction of dates, quantities, percentages, and durations."""
    msg = (
        "For the 150 headsets you requested on 2026-10-07, with 20% advance "
        "and delivery within 30 days, we quote ₹4,049 per headset."
    )
    assert message_parser.parse_amount(msg) == 4049.0

    # Non-price sentences must return None
    assert message_parser.parse_amount("Delivery within 3 weeks of PO.") is None
    assert message_parser.parse_amount("Prices valid for 30 days.") is None
    assert message_parser.parse_amount("Standard net-45 payment terms apply.") is None
    assert message_parser.parse_amount("Payment terms: 20% advance, balance net-30.") is None
    assert message_parser.parse_amount("For the 50 monitors you requested.") is None


def test_parse_amount_missing_and_ambiguous():
    """Return None for missing or ambiguous amounts."""
    assert message_parser.parse_amount("") is None
    assert message_parser.parse_amount("No price mentioned here.") is None
    # Ambiguous conflicting amounts
    assert message_parser.parse_amount("The price could be ₹1,000 or ₹2,000.") is None


# ---------------------------------------------------------------------------
# Tests for extract_offer
# ---------------------------------------------------------------------------

def test_extract_offer_standard_single_quote():
    """Standard offer extraction with currency and units."""
    thread = ThreadText(
        latest="Good morning,\nFor the 50 monitors you requested, we quote Rs. 12,662 per monitor.",
        earlier_supplier=[],
        earlier_acme=[],
        full="...",
    )
    offer = message_parser.extract_offer(thread, quantity=50)

    assert offer.status == "OK"
    assert offer.amount == 12662.0
    assert offer.currency == "INR"
    assert offer.gst_inclusive is False
    assert offer.period is None
    assert offer.unit_token is None


def test_extract_offer_gst_wording():
    """Verify GST inclusive and exclusive wording detection."""
    # GST inclusive
    inclusive_msg = "We offer INR 4,049 per headset including GST."
    t1 = ThreadText(latest=inclusive_msg, earlier_supplier=[], earlier_acme=[], full=inclusive_msg)
    o1 = message_parser.extract_offer(t1, quantity=150)
    assert o1.status == "OK"
    assert o1.amount == 4049.0
    assert o1.gst_inclusive is True

    # GST included in parentheses
    paren_msg = "Our revised offer is ₹21,494 per monitor (GST included)."
    t2 = ThreadText(latest=paren_msg, earlier_supplier=[], earlier_acme=[], full=paren_msg)
    o2 = message_parser.extract_offer(t2, quantity=100)
    assert o2.status == "OK"
    assert o2.amount == 21494.0
    assert o2.gst_inclusive is True

    # GST exclusive
    exclusive_msg = "We quote Rs. 1,500 per fixture excluding GST."
    t3 = ThreadText(latest=exclusive_msg, earlier_supplier=[], earlier_acme=[], full=exclusive_msg)
    o3 = message_parser.extract_offer(t3, quantity=100)
    assert o3.status == "OK"
    assert o3.amount == 1500.0
    assert o3.gst_inclusive is False


def test_extract_offer_billing_periods():
    """Verify detection of monthly and yearly billing periods."""
    month_msg = "Our price is ₹1,05,042 per site per month inclusive of GST."
    t1 = ThreadText(latest=month_msg, earlier_supplier=[], earlier_acme=[], full=month_msg)
    o1 = message_parser.extract_offer(t1, quantity=300)
    assert o1.status == "OK"
    assert o1.amount == 105042.0
    assert o1.period == "month"
    assert o1.gst_inclusive is True

    year_msg = "Our final price is ₹22,277 per seat per year."
    t2 = ThreadText(latest=year_msg, earlier_supplier=[], earlier_acme=[], full=year_msg)
    o2 = message_parser.extract_offer(t2, quantity=150)
    assert o2.status == "OK"
    assert o2.amount == 22277.0
    assert o2.period == "year"


def test_extract_offer_unit_tokens():
    """Verify detection of unit tokens: dozen, ream, pack, unit."""
    t_dozen = ThreadText(latest="We quote ₹1,200 per dozen boxes.", earlier_supplier=[], earlier_acme=[], full="")
    assert message_parser.extract_offer(t_dozen, quantity=10).unit_token == "dozen"

    t_ream = ThreadText(latest="We quote ₹450 per ream.", earlier_supplier=[], earlier_acme=[], full="")
    assert message_parser.extract_offer(t_ream, quantity=50).unit_token == "ream"

    t_pack = ThreadText(latest="We quote ₹300 per pack.", earlier_supplier=[], earlier_acme=[], full="")
    assert message_parser.extract_offer(t_pack, quantity=20).unit_token == "pack"


def test_extract_offer_total_price_division():
    """Total quoted price divided by quantity."""
    msg = "We are pleased to quote ₹44,07,800 in total for all 60 laptops."
    thread = ThreadText(latest=msg, earlier_supplier=[], earlier_acme=[], full=msg)
    offer = message_parser.extract_offer(thread, quantity=60)

    assert offer.status == "OK"
    assert offer.amount == pytest.approx(4407800.0 / 60.0)
    assert offer.currency == "INR"


def test_extract_offer_range_precedent_p01():
    """Precedent P-01: 'between X and Y' evaluated at upper bound."""
    msg = "For the 310 fixtures you requested, we offer between Rs. 1,506 and ₹1,638 per fixture depending on final specs."
    thread = ThreadText(latest=msg, earlier_supplier=[], earlier_acme=[], full=msg)
    offer = message_parser.extract_offer(thread, quantity=310)

    assert offer.status == "OK"
    assert offer.amount == 1638.0
    assert offer.currency == "INR"


def test_extract_offer_list_price_discount():
    """D% discount on list price: list_price * (1 - D/100)."""
    msg = "For the 25 meals you requested, we offer a 10% discount on our list price of INR 410 per meal."
    thread = ThreadText(latest=msg, earlier_supplier=[], earlier_acme=[], full=msg)
    offer = message_parser.extract_offer(thread, quantity=25)

    assert offer.status == "OK"
    assert offer.amount == pytest.approx(410.0 * 0.90)
    assert offer.currency == "INR"


def test_extract_offer_free_items_precedent_p02():
    """Precedent P-02: 'plus M free for every K you pay for' -> price * K / (K + M)."""
    msg = "For the 60 sites you requested, we can do ₹1,02,267 per site per month, plus 1 free site for every 10 you pay for."
    thread = ThreadText(latest=msg, earlier_supplier=[], earlier_acme=[], full=msg)
    offer = message_parser.extract_offer(thread, quantity=60)

    assert offer.status == "OK"
    assert offer.amount == pytest.approx(102267.0 * 10.0 / 11.0)
    assert offer.period == "month"


def test_extract_offer_tiered_pricing():
    """Tiered pricing: choose tier matching quantity."""
    msg = "We quote INR 28,518 per phone for orders of up to 20 phones, and ₹26,904 per phone for larger orders."
    thread = ThreadText(latest=msg, earlier_supplier=[], earlier_acme=[], full=msg)

    offer_small = message_parser.extract_offer(thread, quantity=15)
    assert offer_small.status == "OK"
    assert offer_small.amount == 28518.0

    offer_large = message_parser.extract_offer(thread, quantity=25)
    assert offer_large.status == "OK"
    assert offer_large.amount == 26904.0


def test_extract_offer_volume_discount():
    """Volume discount: applied only if quantity meets threshold."""
    msg = "Our revised offer is Rs. 1,000 per box, with a further 5% off for orders of 50 boxes or more."
    thread = ThreadText(latest=msg, earlier_supplier=[], earlier_acme=[], full=msg)

    offer_met = message_parser.extract_offer(thread, quantity=60)
    assert offer_met.status == "OK"
    assert offer_met.amount == pytest.approx(1000.0 * 0.95)

    offer_not_met = message_parser.extract_offer(thread, quantity=30)
    assert offer_not_met.status == "OK"
    assert offer_not_met.amount == 1000.0


def test_extract_offer_correction():
    """Correction replaces the old price with the new price."""
    msg = "CORRECTION — the price in my previous email should read Rs. 2,766 per box, not ₹3,181."
    thread = ThreadText(latest=msg, earlier_supplier=[], earlier_acme=[], full=msg)
    offer = message_parser.extract_offer(thread, quantity=10)

    assert offer.status == "OK"
    assert offer.amount == 2766.0
    assert offer.currency == "INR"


def test_extract_offer_previous_supplier_quote_handling():
    """Discount applied to the supplier's own earlier quote."""
    earlier_supplier_msg = "Our quote is ₹3,910 per headset."
    latest_msg = "For the 20 headsets you requested, our revised offer is a further 5% off our previous quote."

    thread = ThreadText(
        latest=latest_msg,
        earlier_supplier=[earlier_supplier_msg],
        earlier_acme=["We can offer ₹3,500 per headset."],
        full="...",
    )
    offer = message_parser.extract_offer(thread, quantity=20)

    assert offer.status == "OK"
    assert offer.amount == pytest.approx(3910.0 * 0.95)
    assert offer.currency == "INR"


def test_extract_offer_acme_counteroffer_never_interpreted_as_supplier_quote():
    """Never apply a previous quote discount to Acme's counteroffer."""
    # Here earlier_supplier is empty, only Acme counteroffer exists
    thread = ThreadText(
        latest="Our revised offer is a further 5% off our previous quote.",
        earlier_supplier=[],
        earlier_acme=["We can offer ₹3,500 per headset."],
        full="...",
    )
    offer = message_parser.extract_offer(thread, quantity=20)
    assert offer.status == "NO_PRICE"
    assert offer.amount is None


def test_extract_offer_missing_price():
    """Return NO_PRICE when message lacks a price."""
    thread = ThreadText(
        latest="Pricing will depend on the final specs; please share them and we will revert.",
        earlier_supplier=[],
        earlier_acme=[],
        full="...",
    )
    offer = message_parser.extract_offer(thread, quantity=100)

    assert offer.status == "NO_PRICE"
    assert offer.amount is None


def test_extract_offer_empty_input():
    """Return NO_PRICE for empty or whitespace messages."""
    thread = ThreadText(latest="", earlier_supplier=[], earlier_acme=[], full="")
    offer = message_parser.extract_offer(thread, quantity=10)
    assert offer.status == "NO_PRICE"
    assert offer.amount is None
