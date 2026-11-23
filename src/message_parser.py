"""
src/message_parser.py
Owner: Member 2 (Message Parser)
Depends on: src.schemas

Splits negotiation threads and extracts the latest supplier offer
as a RawOffer according to the procurement playbook.
"""

from __future__ import annotations

import re
from typing import List, Optional

from src.schemas import RawOffer, ThreadText, VALID_PERIODS, VALID_UNIT_TOKENS

# ---------------------------------------------------------------------------
# Numeric and word-number parsing tables
# ---------------------------------------------------------------------------

ONES: dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}

TENS: dict[str, int] = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}

SCALES: dict[str, int] = {
    "crore": 10_000_000,
    "crores": 10_000_000,
    "million": 1_000_000,
    "millions": 1_000_000,
    "lakh": 100_000,
    "lac": 100_000,
    "lakhs": 100_000,
    "thousand": 1_000,
    "thousands": 1_000,
    "hundred": 100,
    "hundreds": 100,
}


CURRENCY_WORDS: set[str] = {
    "rupee", "rupees", "rs", "inr", "dollar", "dollars", "usd",
    "euro", "euros", "eur", "pound", "pounds", "gbp", "aed", "sgd", "jpy", "yen",
}


def words_to_number(text: str) -> Optional[float]:
    """Convert an English words representation of a number into a float."""
    if any(c.isdigit() for c in text):
        return None
    cleaned = text.replace("-", " ").strip()
    words = re.findall(r"[a-zA-Z]+", cleaned.lower())
    if not words:
        return None
    valid_words = set(ONES) | set(TENS) | set(SCALES) | {"and"} | CURRENCY_WORDS
    if not all(w in valid_words for w in words):
        return None
    num_words = [w for w in words if w in ONES or w in TENS or w in SCALES or w == "and"]
    if not num_words:
        return None
    total = 0
    current = 0
    has_num = False
    for w in num_words:
        if w in ONES:
            current += ONES[w]
            has_num = True
        elif w in TENS:
            current += TENS[w]
            has_num = True
        elif w in ("hundred", "hundreds"):
            current = (current if current else 1) * 100
            has_num = True
        elif w in SCALES:
            scale = SCALES[w]
            current = (current if current else 1) * scale
            total += current
            current = 0
            has_num = True
        elif w == "and":
            continue
    total += current
    return float(total) if has_num else None


def clean_num_str(num_str: str, suffix: Optional[str] = None) -> float:
    """Clean comma-grouped numbers and scale with thousand/k/lakh/million/crore suffix."""
    s = num_str.strip().replace(",", "").replace(" ", "").replace("\xa0", "")
    if not s:
        raise ValueError("empty number string")
    val = float(s)
    if suffix:
        suf = suffix.lower()
        if suf in ("lakh", "lakhs", "lac"):
            val *= 100_000
        elif suf in ("k", "thousand", "thousands"):
            val *= 1_000
        elif suf in ("m", "million", "millions"):
            val *= 1_000_000
        elif suf in ("crore", "crores"):
            val *= 10_000_000
    return val


# ---------------------------------------------------------------------------
# Currency, GST, Billing Period, Unit Token Detectors
# ---------------------------------------------------------------------------

def _detect_currency(s: str) -> Optional[str]:
    """Detect 3-letter currency code from symbols or text."""
    if "₹" in s or re.search(r"\b(?:rs\.?|inr|rupees)\b", s, re.IGNORECASE):
        return "INR"
    if "$" in s or re.search(r"\busd\b", s, re.IGNORECASE):
        return "USD"
    if "€" in s or re.search(r"\beur\b", s, re.IGNORECASE):
        return "EUR"
    if "£" in s or re.search(r"\bgbp\b", s, re.IGNORECASE):
        return "GBP"
    if "¥" in s or re.search(r"\bjpy\b", s, re.IGNORECASE):
        return "JPY"
    if re.search(r"\baed\b", s, re.IGNORECASE):
        return "AED"
    if re.search(r"\bsgd\b", s, re.IGNORECASE):
        return "SGD"
    if re.search(r"\baud\b", s, re.IGNORECASE):
        return "AUD"
    if re.search(r"\bcad\b", s, re.IGNORECASE):
        return "CAD"
    if re.search(r"\bchf\b", s, re.IGNORECASE):
        return "CHF"
    return None


def _detect_gst(s: str) -> bool:
    """Return True if the text indicates GST is included."""
    return bool(
        re.search(
            r"\b(?:gst\s+(?:included|inclusive)|inclusive\s+of\s+gst|including\s+gst|incl\.?\s*gst|\(gst\s+included\))\b",
            s,
            re.IGNORECASE,
        )
    )


def _detect_period(s: str) -> Optional[str]:
    """Detect billing period ('month' or 'year') if present."""
    if re.search(r"\bper\s+month\b|\bmonthly\b", s, re.IGNORECASE):
        return "month"
    if re.search(r"\bper\s+(?:year|annum)\b|\byearly\b|\bannually\b", s, re.IGNORECASE):
        return "year"
    return None


def _detect_unit_token(s: str) -> Optional[str]:
    """Detect unit token ('dozen', 'ream', 'pack', 'unit') if present."""
    if re.search(r"\bper\s+dozen\b|\bdozen\b", s, re.IGNORECASE):
        return "dozen"
    if re.search(r"\bper\s+ream\b|\bream\b", s, re.IGNORECASE):
        return "ream"
    if re.search(r"\bper\s+pack\b|\bpack\b", s, re.IGNORECASE):
        return "pack"
    if re.search(r"\bper\s+unit\b", s, re.IGNORECASE):
        return "unit"
    return None


# ---------------------------------------------------------------------------
# Public Functions Required by Contract
# ---------------------------------------------------------------------------

def split_thread(raw_message: str) -> ThreadText:
    """Split the complete supplier conversation into ThreadText parts.

    Returns:
      ThreadText with:
        latest: latest supplier message only (str).
        earlier_supplier: list of earlier supplier messages in chronological order.
        earlier_acme: list of earlier Acme messages in chronological order.
        full: original complete raw_message string.
    """
    if not raw_message or not isinstance(raw_message, str):
        return ThreadText(
            latest="",
            earlier_supplier=[],
            earlier_acme=[],
            full=raw_message or "",
        )

    pattern = re.compile(r"\[(Earlier|Latest) message\s*[-—]\s*([^\]]+)\]", re.IGNORECASE)
    matches = list(pattern.finditer(raw_message))

    # Single message thread without markers
    if not matches:
        return ThreadText(
            latest=raw_message.strip(),
            earlier_supplier=[],
            earlier_acme=[],
            full=raw_message,
        )

    earlier_supplier: List[str] = []
    earlier_acme: List[str] = []
    latest: str = ""

    for idx, match in enumerate(matches):
        kind = match.group(1).title()
        sender = match.group(2)
        body_start = match.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw_message)
        body = raw_message[body_start:body_end].strip()

        if kind == "Latest":
            latest = body
        else:
            if "acme" in sender.lower():
                earlier_acme.append(body)
            else:
                earlier_supplier.append(body)

    if not latest and matches:
        latest = raw_message[matches[-1].end():].strip()

    return ThreadText(
        latest=latest,
        earlier_supplier=earlier_supplier,
        earlier_acme=earlier_acme,
        full=raw_message,
    )


def parse_amount(text: str) -> Optional[float]:
    """Parse a numeric amount from text.

    Supports:
    - Standard numeric amounts (e.g. 12662, 12662.50).
    - Comma-separated formats including Indian grouping (e.g. ₹1,19,990, ₹44,07,800).
    - Decimal amounts.
    - Lakh notation (e.g. 1.2 lakh -> 120000.0, 2 lakh -> 200000.0).
    - Thousand / k notation (e.g. 18.5k -> 18500.0, 1.5k -> 1500.0).
    - English words notation (e.g. 'one lakh twenty thousand' -> 120000.0).
    - Currency symbols and codes (₹, Rs, INR, $, USD, €, EUR, £, GBP, ¥, JPY, AED, SGD).

    Returns None when no valid price is present or when ambiguous.
    Avoids accidental extraction of quantities, dates, percentages, and phone numbers.
    """
    if not text or not isinstance(text, str):
        return None

    t = text.strip()

    # 1. Number in words (only if no digits)
    w_val = words_to_number(t)
    if w_val is not None:
        return w_val

    # 2. Pure numeric string with optional commas/decimal/currency/suffix
    m_pure = re.fullmatch(
        r"^(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP|¥|JPY|SGD|AED|AUD|CAD)?\s*(\d[\d,]*(?:\.\d+)?)\s*(lakhs?|lac|thousand|thousands|k|million|millions|crore|crores)?$",
        t,
        re.IGNORECASE,
    )
    if m_pure:
        try:
            return clean_num_str(m_pure.group(1), m_pure.group(2))
        except ValueError:
            return None

    # 3. Number in words preceded by quotation phrase and followed by 'rupees'
    m_words_rupees = re.search(
        r"(?:is|offer is|quote|price is|do)\s+([a-z\s-]+?)\s+rupees",
        t,
        re.IGNORECASE,
    )
    if m_words_rupees:
        val = words_to_number(m_words_rupees.group(1))
        if val is not None:
            return val

    # 4. Search for numbers associated with currency or explicit scale suffix
    curr_pattern = re.compile(
        r"(?:(?P<c_pre>₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP|¥|JPY|SGD|AED|AUD|CAD)\s*)?"
        r"(?P<num>\d[\d,]*(?:\.\d+)?)"
        r"(?:\s*(?P<suf>\b(?:lakhs?|lac|thousand|thousands|k|million|millions|crore|crores)\b))?"
        r"(?:\s*(?P<c_post>₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP|¥|JPY|SGD|AED|AUD|CAD)\b)?",
        re.IGNORECASE,
    )

    found: List[float] = []
    for m in curr_pattern.finditer(t):
        c_pre = m.group("c_pre")
        c_post = m.group("c_post")
        suf = m.group("suf")
        num = m.group("num")
        start = m.start()
        end = m.end()

        # Disqualify percentages (e.g. '10%')
        if end < len(t) and t[end : end + 1] == "%":
            continue

        # Disqualify dates (e.g. '2026-10-13')
        if (start > 0 and t[start - 1 : start] in "-/") or (
            end < len(t) and t[end : end + 1] in "-/"
        ):
            continue

        # Disqualify numbers without currency or scale suffix (e.g. quantity or duration)
        if not c_pre and not c_post and not suf:
            continue

        try:
            val = clean_num_str(num, suf)
            found.append(val)
        except ValueError:
            continue

    if len(found) == 1:
        return found[0]
    elif len(found) > 1:
        # If all found values are identical, return it
        if len(set(found)) == 1:
            return found[0]
        # Ambiguous multiple distinct amounts
        return None

    return None


def extract_offer(text: ThreadText, quantity: int) -> RawOffer:
    """Extract the latest supplier offer from a ThreadText.

    Populates:
      - status: 'OK' or 'NO_PRICE'
      - amount: per-unit price in original currency (divided by quantity if quoted as total)
      - currency: 3-letter currency code (e.g. 'INR', 'USD', 'EUR', 'GBP')
      - gst_inclusive: bool
      - period: 'month', 'year', or None
      - unit_token: 'unit', 'dozen', 'pack', 'ream', or None
      - notes: list of diagnostic notes

    Uses only the latest supplier message, except for 'previous-quote' discount
    interpretations where earlier_supplier messages are examined.
    """
    latest = text.latest or ""
    if not latest.strip():
        return RawOffer(status="NO_PRICE", notes=["empty latest message"])

    currency = _detect_currency(latest)
    gst_inclusive = _detect_gst(latest)
    period = _detect_period(latest)
    unit_token = _detect_unit_token(latest)
    notes: List[str] = []

    # 1. Previous quote discount: "D% off our previous quote"
    m_prev = re.search(
        r"(?:a\s+further\s+)?(\d+(?:\.\d+)?)\s*%\s*(?:off|discount\s+(?:on|off))\s+our\s+previous\s+quote",
        latest,
        re.IGNORECASE,
    )
    if m_prev:
        if not text.earlier_supplier:
            return RawOffer(
                status="NO_PRICE",
                currency=currency,
                gst_inclusive=gst_inclusive,
                period=period,
                unit_token=unit_token,
                notes=["discount on previous quote but earlier_supplier is empty"],
            )
        prev_text = ThreadText(
            latest=text.earlier_supplier[-1],
            earlier_supplier=[],
            earlier_acme=[],
            full=text.earlier_supplier[-1],
        )
        prev_offer = extract_offer(prev_text, quantity)
        if prev_offer.amount is None:
            return RawOffer(
                status="NO_PRICE",
                currency=currency,
                gst_inclusive=gst_inclusive,
                period=period,
                unit_token=unit_token,
                notes=["earlier supplier quote has no usable price"],
            )
        discount_pct = float(m_prev.group(1))
        amount = prev_offer.amount * (1.0 - discount_pct / 100.0)
        currency = currency or prev_offer.currency
        if period is None:
            period = prev_offer.period
        if unit_token is None:
            unit_token = prev_offer.unit_token
        gst_inclusive = gst_inclusive or prev_offer.gst_inclusive
        return RawOffer(
            status="OK",
            amount=amount,
            currency=currency,
            gst_inclusive=gst_inclusive,
            period=period,
            unit_token=unit_token,
            notes=["discounted from previous quote"],
        )

    amount: Optional[float] = None

    # 2. Correction: "CORRECTION — the price in my previous email should read X, not Y"
    m_corr = re.search(
        r"CORRECTION\s*[-—]\s*the\s+price\s+in\s+my\s+previous\s+email\s+should\s+read\s+(.+?)(?:,\s*not\s+|\s+not\s+)",
        latest,
        re.IGNORECASE,
    )
    if m_corr:
        corr_text = m_corr.group(1)
        amount = parse_amount(corr_text)
        currency = currency or _detect_currency(corr_text)
        if period is None:
            period = _detect_period(corr_text)
        if unit_token is None:
            unit_token = _detect_unit_token(corr_text)
        gst_inclusive = gst_inclusive or _detect_gst(corr_text)
        notes.append("corrected price extracted")

    # 3. Range: "between X and Y" -> Precedent P-01: evaluate at upper bound
    elif re.search(
        r"between\s+(.+?)\s+and\s+(.+?)(?:\s+per\b|\s+depending\b|\s+for\b|[\r\n]|$)",
        latest,
        re.IGNORECASE,
    ):
        m_range = re.search(
            r"between\s+(.+?)\s+and\s+(.+?)(?:\s+per\b|\s+depending\b|\s+for\b|[\r\n]|$)",
            latest,
            re.IGNORECASE,
        )
        assert m_range is not None
        p1 = parse_amount(m_range.group(1))
        p2 = parse_amount(m_range.group(2))
        if p1 is not None and p2 is not None:
            amount = max(p1, p2)
            notes.append("range evaluated at upper bound")
        elif p1 is not None:
            amount = p1
        elif p2 is not None:
            amount = p2

    # 4. List price discount: "D% discount on our list price of X"
    elif re.search(
        r"(\d+(?:\.\d+)?)\s*%\s*(?:discount\s+(?:on|off)|off)\s+our\s+list\s+price\s+of\s+([^\n]+?)(?:\s+per\b|[\r\n]|$)",
        latest,
        re.IGNORECASE,
    ):
        m_list = re.search(
            r"(\d+(?:\.\d+)?)\s*%\s*(?:discount\s+(?:on|off)|off)\s+our\s+list\s+price\s+of\s+([^\n]+?)(?:\s+per\b|[\r\n]|$)",
            latest,
            re.IGNORECASE,
        )
        assert m_list is not None
        discount_pct = float(m_list.group(1))
        base = parse_amount(m_list.group(2))
        if base is not None:
            amount = base * (1.0 - discount_pct / 100.0)
            notes.append("list price discount applied")

    # 5. Free items: "plus M free ... for every K you pay for" (Precedents P-02, P-05)
    elif re.search(
        r"plus\s+(\d+)\s+free\s+\w+\s+for\s+every\s+(\d+)\s+you\s+pay\s+for",
        latest,
        re.IGNORECASE,
    ):
        m_free = re.search(
            r"plus\s+(\d+)\s+free\s+\w+\s+for\s+every\s+(\d+)\s+you\s+pay\s+for",
            latest,
            re.IGNORECASE,
        )
        assert m_free is not None
        free_m = int(m_free.group(1))
        pay_k = int(m_free.group(2))
        base_text = latest[: m_free.start()] + latest[m_free.end() :]
        base = parse_amount(base_text)
        if base is not None:
            amount = base * pay_k / (pay_k + free_m)
            notes.append("free items promotion applied")

    # 6. Tiered pricing: "for orders of up to N ..., and Y for larger orders"
    elif re.search(
        r"for\s+orders\s+of\s+up\s+to\s+(\d+)\s+\w+,\s+and\s+([^\n]+?)\s+for\s+larger\s+orders",
        latest,
        re.IGNORECASE,
    ):
        m_tier = re.search(
            r"for\s+orders\s+of\s+up\s+to\s+(\d+)\s+\w+,\s+and\s+([^\n]+?)\s+for\s+larger\s+orders",
            latest,
            re.IGNORECASE,
        )
        assert m_tier is not None
        threshold = int(m_tier.group(1))
        larger_text = m_tier.group(2)
        lower_text = latest[: m_tier.start()]
        if quantity <= threshold:
            amount = parse_amount(lower_text)
            notes.append(f"tier for qty <= {threshold} selected")
        else:
            amount = parse_amount(larger_text)
            notes.append(f"tier for qty > {threshold} selected")

    # 7. Volume discount: "with a further D% off for orders of N ... or more"
    elif re.search(
        r"with\s+a\s+further\s+(\d+(?:\.\d+)?)\s*%\s*off\s+for\s+orders\s+of\s+(\d+)\s+\w+\s+or\s+more",
        latest,
        re.IGNORECASE,
    ):
        m_vol = re.search(
            r"with\s+a\s+further\s+(\d+(?:\.\d+)?)\s*%\s*off\s+for\s+orders\s+of\s+(\d+)\s+\w+\s+or\s+more",
            latest,
            re.IGNORECASE,
        )
        assert m_vol is not None
        discount_pct = float(m_vol.group(1))
        threshold = int(m_vol.group(2))
        base_text = latest[: m_vol.start()]
        base = parse_amount(base_text)
        if base is not None:
            if quantity >= threshold:
                amount = base * (1.0 - discount_pct / 100.0)
                notes.append("volume discount applied")
            else:
                amount = base
                notes.append("volume discount threshold not met")

    # 8. Standard single amount
    if amount is None:
        amount = parse_amount(latest)

    # Total price conversion (quoted total divided by requested quantity)
    if amount is not None:
        is_total = bool(
            re.search(
                r"\b(?:in\s+total(?:\s+for\s+all)?|total\s+for\s+all|\bfor\s+all\s+\d+\b)\b|\bquote\s+.*?\s+in\s+total\b|\btotal\b",
                latest,
                re.IGNORECASE,
            )
        )
        if is_total and quantity > 0:
            amount = amount / quantity
            notes.append(f"total divided by quantity {quantity}")

    status = "OK" if amount is not None else "NO_PRICE"
    return RawOffer(
        status=status,
        amount=amount,
        currency=currency,
        gst_inclusive=gst_inclusive,
        period=period,
        unit_token=unit_token,
        notes=notes,
    )
