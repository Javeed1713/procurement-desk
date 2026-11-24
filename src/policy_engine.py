"""
src/policy_engine.py
Owner: Member 1 (Policy Engine)
Depends on: src.schemas

Loads the playbook, resolves the policy parameters for a thread, normalizes
offers into INR per unit, calculates concession limits and counter prices,
and finds banned terms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
import math
from pathlib import Path
import re
from typing import Any, Optional

from src.schemas import NormalizedOffer, Params, RawOffer

_DEFAULT_FX_RATES: dict[str, float] = {
    "INR": 1.0,
    "USD": 84.5,
    "EUR": 91.0,
    "GBP": 106.0,
}

_DEFAULT_UNIT_TOKENS: dict[str, int] = {
    "unit": 1,
    "dozen": 12,
}


@dataclass
class CategoryRule:
    name: str
    aliases: set[str] = field(default_factory=set)
    unit_text: str = "unit"
    gst_rate: float = 0.0
    target: float = 0.0
    walkaway: float = 0.0
    rounds: int = 3
    beta: float = 1.0
    approval_limit: Optional[float] = None
    billing_period: Optional[str] = None
    units_per_token: dict[str, int] = field(default_factory=lambda: dict(_DEFAULT_UNIT_TOKENS))


@dataclass
class AmendmentRule:
    amendment_id: str
    effective_date: str
    categories: set[str]
    changes: dict[str, Any]


@dataclass
class SupplierRule:
    supplier_id: str
    status: str = "APPROVED"
    walkaway_caps: dict[str, float] = field(default_factory=dict)
    fx_overrides: dict[str, float] = field(default_factory=dict)


@dataclass
class PolicyBook:
    """Container for parsed playbook data."""

    root: Path
    categories: dict[str, CategoryRule] = field(default_factory=dict)
    amendments: list[AmendmentRule] = field(default_factory=list)
    suppliers: dict[str, SupplierRule] = field(default_factory=dict)
    fx_rates: dict[str, float] = field(default_factory=lambda: dict(_DEFAULT_FX_RATES))
    banned_term_patterns: list[tuple[str, re.Pattern[str]]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def _parse_number(raw: str) -> Optional[float]:
    if not raw:
        return None
    s = raw.strip()
    pct_match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*%", s)
    if pct_match:
        return float(pct_match.group(1)) / 100.0
    num_match = re.search(r"([0-9][0-9,]*(?:\.[0-9]+)?)", s)
    if not num_match:
        return None
    val = float(num_match.group(1).replace(",", ""))
    lower = s.lower()
    # Use word-boundary matching to avoid false positives from words containing
    # "lac" (e.g. "replaces", "place") or "crore" as substrings.
    if re.search(r"\bcrore[s]?\b", lower):
        val *= 10_000_000.0
    elif re.search(r"\b(?:lakh[s]?|lac)\b", lower):
        val *= 100_000.0
    elif re.search(r"\bk\b", lower):
        val *= 1_000.0
    return val


def _extract_kv_pairs(markdown_text: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for line in markdown_text.splitlines():
        line_clean = re.sub(r"^\s*[-*+]\s*", "", line).strip()
        m = re.match(r"^\*{0,2}(.+?)\*{0,2}\s*:\s*(.+)$", line_clean)
        if m:
            raw_key = re.sub(r"\([^)]*\)", "", m.group(1)).strip().lower()
            key = re.sub(r"[^a-z0-9]+", "_", raw_key).strip("_")
            # Strip leading/trailing bold markers (**) that may have been
            # captured as part of the value when the regex matches across bold text.
            value = re.sub(r"^\*{1,2}\s*", "", m.group(2)).strip()
            pairs[key] = value
    return pairs


def _parse_category_file(path: Path) -> CategoryRule:
    text = path.read_text(encoding="utf-8")
    kv = _extract_kv_pairs(text)
    slug = _slug(path.stem)
    aliases = {slug}

    title_m = re.search(r"^#\s*Category\s*:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
    if title_m:
        title_slug = _slug(title_m.group(1))
        if title_slug:
            aliases.add(title_slug)

    gst_raw = kv.get("gst_rate") or kv.get("gst") or "0"
    gst_val = _parse_number(gst_raw)
    if gst_val is None:
        gst_val = 0.0
    elif gst_val > 1.0 and "%" not in gst_raw:
        gst_val = gst_val / 100.0

    target_val = _parse_number(kv.get("target_price") or kv.get("target") or "0") or 0.0
    walkaway_val = _parse_number(
        kv.get("walk_away_price") or kv.get("walkaway_price") or kv.get("walkaway") or "0"
    ) or 0.0
    rounds_val = int(_parse_number(kv.get("negotiation_rounds") or kv.get("max_rounds") or kv.get("rounds") or "3") or 3)
    beta_val = _parse_number(kv.get("concession_exponent") or kv.get("beta") or "1.0") or 1.0

    approval_raw = kv.get("approval_limit") or kv.get("approval_threshold") or ""
    approval_val = _parse_number(approval_raw) if approval_raw and "none" not in approval_raw.lower() else None

    unit_text = (kv.get("normalized_unit") or kv.get("unit") or "unit").strip()
    billing_period: Optional[str] = None
    unit_lower = unit_text.lower()
    if "per month" in unit_lower or "/month" in unit_lower or "monthly" in unit_lower:
        billing_period = "month"
    elif "per year" in unit_lower or "/year" in unit_lower or "annual" in unit_lower or "yearly" in unit_lower:
        billing_period = "year"

    units_per_token = dict(_DEFAULT_UNIT_TOKENS)
    for m in re.finditer(r"\b(dozen|pack|ream|box|case|set)\b[^\n\r]{0,40}?(\d+)\s*(?:units?|pcs?|pieces?|sheets?|meals?)", text, re.IGNORECASE):
        units_per_token[m.group(1).lower()] = int(m.group(2))

    return CategoryRule(
        name=slug,
        aliases=aliases,
        unit_text=unit_text,
        gst_rate=gst_val,
        target=target_val,
        walkaway=walkaway_val,
        rounds=rounds_val,
        beta=beta_val,
        approval_limit=approval_val,
        billing_period=billing_period,
        units_per_token=units_per_token,
    )


def _apply_change_sentence(sentence: str, changes: dict[str, Any], target_cats: set[str]) -> None:
    s = sentence.strip()
    if not s:
        return

    for_m = re.search(r"\bfor\s+([A-Za-z0-9 &/-]+?)(?:\s+is\s+|\s+are\s+|\s+becomes?\s+|\.|$)", s, re.IGNORECASE)
    if for_m:
        cat_slug = _slug(for_m.group(1))
        if cat_slug:
            target_cats.add(cat_slug)

    if re.search(r"\bwalk-?away\s+price\b", s, re.IGNORECASE):
        val = _parse_number(s)
        if val is not None:
            changes["walkaway"] = val
    elif re.search(r"\btarget\s+price\b", s, re.IGNORECASE):
        val = _parse_number(s)
        if val is not None:
            changes["target"] = val
    elif re.search(r"\bgst(?:\s+rate)?\b", s, re.IGNORECASE):
        val = _parse_number(s)
        if val is not None:
            changes["gst_rate"] = val
    elif re.search(r"\bapproval\s+limit\b", s, re.IGNORECASE):
        val = _parse_number(s)
        if val is not None:
            changes["approval_limit"] = val
    elif re.search(r"\b(?:negotiation\s+)?rounds?\b", s, re.IGNORECASE):
        val = _parse_number(s)
        if val is not None:
            changes["rounds"] = int(val)
    elif re.search(r"\b(?:concession\s+exponent|beta)\b", s, re.IGNORECASE):
        val = _parse_number(s)
        if val is not None:
            changes["beta"] = val


def _parse_amendment_file(path: Path) -> AmendmentRule:
    text = path.read_text(encoding="utf-8")
    kv = _extract_kv_pairs(text)

    date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", kv.get("effective_from") or kv.get("effective_date") or text)
    eff_date = date_match.group(1) if date_match else "1900-01-01"

    categories: set[str] = set()
    heading_m = re.search(r"^#\s*AMD-\d+\s*:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
    if heading_m:
        h_slug = _slug(heading_m.group(1))
        if h_slug:
            categories.add(h_slug)

    changes: dict[str, Any] = {}
    change_raw = kv.get("change") or ""
    for part in re.split(r"[;\n]+", change_raw):
        _apply_change_sentence(part, changes, categories)

    return AmendmentRule(
        amendment_id=path.stem,
        effective_date=eff_date,
        categories=categories,
        changes=changes,
    )


def _parse_supplier_file(path: Path) -> SupplierRule:
    text = path.read_text(encoding="utf-8")
    kv = _extract_kv_pairs(text)
    slug = _slug(path.stem)

    status_raw = (kv.get("status") or "APPROVED").strip()
    status_upper = status_raw.upper()
    if status_upper.startswith("BLACKLIST"):
        status = "BLACKLISTED"
    elif status_upper.startswith("PROBATION"):
        status = "PROBATION"
    else:
        status = "APPROVED"

    walkaway_caps: dict[str, float] = {}
    fx_overrides: dict[str, float] = {}

    contract_raw = kv.get("contract") or ""
    for clause in re.split(r"[;\n]+", contract_raw):
        c = clause.strip()
        if not c:
            continue
        for curr in ("USD", "EUR", "GBP"):
            if re.search(rf"\b{curr}\b", c, re.IGNORECASE) and re.search(
                r"\b(?:converted|rate|fx|exchange)\b", c, re.IGNORECASE
            ):
                rate_val = _parse_number(c)
                if rate_val is not None:
                    fx_overrides[curr] = rate_val

        if re.search(r"\b(?:walk-?away|price)\s*cap\b", c, re.IGNORECASE):
            cap_val = _parse_number(c)
            if cap_val is not None:
                cat_m = re.search(r"\bfor\s+([A-Za-z0-9 &/-]+?)(?:\s+(?:is|of)\s+|\.|$)", c, re.IGNORECASE)
                cat_key = _slug(cat_m.group(1)) if cat_m else "*"
                walkaway_caps[cat_key] = cap_val

    return SupplierRule(
        supplier_id=slug,
        status=status,
        walkaway_caps=walkaway_caps,
        fx_overrides=fx_overrides,
    )


def _build_banned_term_patterns() -> list[tuple[str, re.Pattern[str]]]:
    return [
        (
            "auto_renewal",
            re.compile(
                r"(?<!\bno\s)(?<!\bnot\s)(?<!\bwithout\s)(?<!\bnever\s)"
                r"\b(?:auto(?:matic(?:ally)?)?[_\s-]renew(?:s|al|ed)?|"
                r"continues?\s+(?:from\s+)?(?:year|month|term)\s+to\s+(?:year|month|term)\s+unless|"
                r"renews?\s+on\s+its\s+own)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "upfront_over_30_pct",
            re.compile(
                r"\b(?:3[1-9]|[4-9]\d|100)\s*%\s*(?:of\s+[^\n.,;]+?\s+)?(?:upfront|advance|deposit|prepayment)|"
                r"(?:upfront|advance|deposit|prepayment)\s*(?:of\s*)?(?:3[1-9]|[4-9]\d|100)\s*%|"
                r"\bhalf\s+(?:of\s+)?(?:the\s+)?(?:order\s+value\s+)?(?:upfront|in\s+advance)",
                re.IGNORECASE,
            ),
        ),
        (
            "unlimited_liability",
            re.compile(
                r"\bunlimited\s+liability\b|\bliability\b[^\n.,;]{0,50}\bunlimited\b",
                re.IGNORECASE,
            ),
        ),
        (
            "exclusivity",
            re.compile(
                r"\b(?:exclusive\s+supplier|exclusive\s+partner|exclusive\s+agreement|exclusive\s+contract|exclusive\s+dealing|must\s+buy\s+(?:only|exclusively))\b|"
                r"\bonly\s+from\s+(?:us|this\s+supplier)\b|"
                r"\bbuy\s+(?:\w+\s+){0,5}only\s+from\s+us\b|"
                r"(?<!\bno\s)(?<!\bwithout\s)(?<!\bfor\s)\bexclusivity\b",
                re.IGNORECASE,
            ),
        ),
    ]


def _resolve_category(book: PolicyBook, category: str) -> CategoryRule:
    slug = _slug(category)
    if slug in book.categories:
        return book.categories[slug]
    for rule in book.categories.values():
        if slug in rule.aliases:
            return rule
    return CategoryRule(name=slug, aliases={slug})


def load_policy(playbook_dir: str | Path) -> PolicyBook:
    """Parse the playbook folder into a PolicyBook."""
    root = Path(playbook_dir)
    categories: dict[str, CategoryRule] = {}
    amendments: list[AmendmentRule] = []
    suppliers: dict[str, SupplierRule] = {}
    fx_rates = dict(_DEFAULT_FX_RATES)

    fx_doc = root / "policies" / "units-and-currency.md"
    if fx_doc.exists():
        fx_text = fx_doc.read_text(encoding="utf-8")
        for curr in ("USD", "EUR", "GBP"):
            m = re.search(rf"\b{curr}\b\s*(?:=|:|is|@)?\s*(?:INR|₹)?\s*([0-9]+(?:\.[0-9]+)?)", fx_text)
            if m:
                fx_rates[curr] = float(m.group(1))

    cat_dir = root / "categories"
    if cat_dir.exists():
        for p in sorted(cat_dir.glob("*.md")):
            rule = _parse_category_file(p)
            categories[rule.name] = rule

    amd_dir = root / "amendments"
    if amd_dir.exists():
        for p in sorted(amd_dir.glob("*.md")):
            amendments.append(_parse_amendment_file(p))
    amendments.sort(key=lambda a: (a.effective_date, a.amendment_id))

    sup_dir = root / "suppliers"
    if sup_dir.exists():
        for p in sorted(sup_dir.glob("*.md")):
            srule = _parse_supplier_file(p)
            suppliers[srule.supplier_id] = srule

    return PolicyBook(
        root=root,
        categories=categories,
        amendments=amendments,
        suppliers=suppliers,
        fx_rates=fx_rates,
        banned_term_patterns=_build_banned_term_patterns(),
    )


def get_params(book: PolicyBook, supplier: str, category: str, on_date: str) -> Params:
    """Resolve all policy values for one supplier, category and date."""
    sup_key = _slug(supplier)
    cat = _resolve_category(book, category)
    cat_key = cat.name
    sup = book.suppliers.get(sup_key) or SupplierRule(supplier_id=sup_key)

    target = float(cat.target)
    walkaway = float(cat.walkaway)
    gst_rate = float(cat.gst_rate)
    rounds = int(cat.rounds)
    beta = float(cat.beta)
    approval_limit = cat.approval_limit
    applied_amendments: list[str] = []

    match_keys = set(cat.aliases)
    match_keys.add(cat_key)
    match_keys.add(_slug(category))

    for amd in book.amendments:
        if amd.effective_date <= on_date and (not amd.categories or (amd.categories & match_keys) or "*" in amd.categories):
            applied_amendments.append(amd.amendment_id)
            if "target" in amd.changes:
                target = float(amd.changes["target"])
            if "walkaway" in amd.changes:
                walkaway = float(amd.changes["walkaway"])
            if "gst_rate" in amd.changes:
                gst_rate = float(amd.changes["gst_rate"])
            if "rounds" in amd.changes:
                rounds = int(amd.changes["rounds"])
            if "beta" in amd.changes:
                beta = float(amd.changes["beta"])
            if "approval_limit" in amd.changes:
                approval_limit = float(amd.changes["approval_limit"])

    walkaway_source = "category"
    cap_override: Optional[float] = None
    for k in match_keys:
        if k in sup.walkaway_caps:
            cap_override = sup.walkaway_caps[k]
            break
    if cap_override is None:
        cap_override = sup.walkaway_caps.get("*")
    if cap_override is not None:
        walkaway = float(cap_override)
        walkaway_source = "supplier_contract_cap"

    fx_rates = dict(book.fx_rates)
    fx_rates.update(sup.fx_overrides)

    return Params(
        category=cat_key,
        supplier=sup_key,
        as_of=on_date,
        unit_text=cat.unit_text,
        gst_rate=gst_rate,
        target=target,
        walkaway=walkaway,
        rounds=rounds,
        beta=beta,
        approval_limit=approval_limit,
        billing_period=cat.billing_period,
        units_per_token=dict(cat.units_per_token),
        fx_rates=fx_rates,
        supplier_status=sup.status,
        walkaway_source=walkaway_source,
        applied_amendments=applied_amendments,
    )


def normalize_offer(raw: RawOffer, params: Params) -> NormalizedOffer:
    """Convert a RawOffer into an INR, pre-GST, per-unit price (or a missing reason)."""
    steps: list[str] = []

    if raw.status != "OK" or raw.amount is None or not math.isfinite(raw.amount) or raw.amount <= 0:
        return NormalizedOffer(ok=False, price=None, missing_reason="missing_or_invalid_offer", steps=steps)

    if params.billing_period is not None and raw.period is None:
        return NormalizedOffer(ok=False, price=None, missing_reason="missing_billing_period", steps=steps)

    currency = (raw.currency or "INR").strip().upper()
    if currency not in params.fx_rates:
        return NormalizedOffer(ok=False, price=None, missing_reason=f"unsupported_currency:{currency}", steps=steps)

    rate = float(params.fx_rates[currency])
    price = float(raw.amount) * rate
    steps.append(f"fx:{currency}->{price}")

    if raw.gst_inclusive and params.gst_rate > 0:
        price = price / (1.0 + float(params.gst_rate))
        steps.append(f"ex_gst:{price}")

    if params.billing_period == "year" and raw.period == "month":
        price = price * 12.0
        steps.append(f"month_to_year:{price}")
    elif params.billing_period == "month" and raw.period == "year":
        price = price / 12.0
        steps.append(f"year_to_month:{price}")

    if raw.unit_token:
        token_key = raw.unit_token.lower()
        units_in_token = params.units_per_token.get(token_key)
        if units_in_token is None and token_key == "dozen":
            units_in_token = 12
        if units_in_token and units_in_token > 0:
            price = price / float(units_in_token)
            steps.append(f"unit_token:{token_key}/{units_in_token}->{price}")

    return NormalizedOffer(ok=True, price=price, missing_reason=None, steps=steps)


def price_limit(params: Params, round_no: int) -> float:
    """Return the concession limit L(r) for the given round (unrounded)."""
    target = float(params.target)
    walkaway = float(params.walkaway)
    total_rounds = int(params.rounds)
    if total_rounds <= 1:
        return walkaway if round_no > 1 else target
    clamped_r = max(1, min(int(round_no), total_rounds))
    progress = (clamped_r - 1) / float(total_rounds - 1)
    return target + (walkaway - target) * (progress ** float(params.beta))


def round_half_up(x: float) -> int:
    """Round to the nearest integer, with .5 always going up. Never use round()."""
    if not math.isfinite(x):
        raise ValueError("Cannot round non-finite value")
    dec = Decimal(str(x))
    return int(dec.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def counter_price(params: Params, round_no: int) -> int:
    """Return the integer counter price for the given round (half-up rounding)."""
    return round_half_up(price_limit(params, round_no))


def is_final_round(params: Params, round_no: int) -> bool:
    """Return True when round_no equals params.rounds."""
    return int(round_no) >= int(params.rounds)


def exceeds_approval_limit(unit_price: float, quantity: int, params: Params) -> bool:
    """Return True when the total order value exceeds the approval limit."""
    if params.approval_limit is None:
        return False
    total_value = float(unit_price) * float(quantity)
    return total_value > float(params.approval_limit)


def find_banned_terms(latest_text: str) -> list[str]:
    """Return the banned terms found in the latest supplier message."""
    if not latest_text:
        return []
    matched: list[str] = []
    for tag, pattern in _build_banned_term_patterns():
        if pattern.search(latest_text):
            matched.append(tag)
    return matched

