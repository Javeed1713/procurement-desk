"""
src/utils.py
Owner: Member 4 (Project Integration)
Depends on: src.schemas, src.policy_engine, src.decision_engine (via decide)

Data loading, row conversion, batch prediction, evaluation, submission
validation and writing. This is the top layer, used by notebooks/main.ipynb.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from src.decision_engine import decide
from src.policy_engine import PolicyBook
from src.schemas import ThreadRecord


def find_data_dir() -> Path:
    """Locate the data/ folder whether the code runs locally or on Kaggle."""
    candidates = [
        Path("data"),
        Path("../data"),
        Path("../../data"),
        Path("/kaggle/input/procurement-desk/data"),
        Path("/kaggle/input/procurement-desk"),
    ]
    for c in candidates:
        if c.is_dir() and (c / "playbook").exists():
            return c
    # Fallback to local default
    return Path("data")


def load_threads(path: str | Path) -> pd.DataFrame:
    """Load a threads CSV into a DataFrame with the eight expected columns."""
    df = pd.read_csv(path)
    expected_cols = [
        "thread_id",
        "date",
        "supplier",
        "category",
        "quantity",
        "round",
        "our_last_counter",
        "supplier_message",
    ]
    for col in expected_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    return df


def row_to_thread(row: pd.Series) -> ThreadRecord:
    """Convert one DataFrame row into a ThreadRecord."""
    counter_val = row.get("our_last_counter")
    our_last_counter = float(counter_val) if pd.notna(counter_val) else None
    return ThreadRecord(
        thread_id=str(row["thread_id"]),
        date=str(row["date"]),
        supplier=str(row["supplier"]),
        category=str(row["category"]),
        quantity=int(row["quantity"]),
        round=int(row["round"]),
        our_last_counter=our_last_counter,
        raw_message=str(row["supplier_message"]),
    )


def predict_dataframe(df: pd.DataFrame, book: PolicyBook) -> tuple[pd.DataFrame, pd.DataFrame, list]:
    """Run decide() on every thread row.

    Returns exactly three values, in this fixed order:
      1. predictions_df: DataFrame with columns thread_id and label
      2. trace_df: DataFrame with one row per thread holding its decision trace
      3. errors: list of processing errors (empty when every thread succeeded)

    Do not change the order of these return values.
    """
    preds: list[dict[str, str]] = []
    traces: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for idx, row in df.iterrows():
        try:
            record = row_to_thread(row)
            res = decide(record, book)
            lbl = res.decision.to_label()
            preds.append({"thread_id": record.thread_id, "label": lbl})
            traces.append({
                "thread_id": record.thread_id,
                "label": lbl,
                "price": res.price,
                "limit": res.limit,
                "trace": " | ".join(res.trace),
            })
        except Exception as exc:
            tid = str(row.get("thread_id", f"row_{idx}"))
            errors.append({"thread_id": tid, "error": str(exc)})
            preds.append({"thread_id": tid, "label": "ESCALATE:MISSING_INFO:"})
            traces.append({"thread_id": tid, "label": "ERROR", "trace": str(exc)})

    return pd.DataFrame(preds), pd.DataFrame(traces), errors


def evaluate_predictions(pred: pd.DataFrame, truth: pd.DataFrame) -> dict:
    """Compare predicted labels with the truth labels and return metrics."""
    merged = pred.merge(truth, on="thread_id", suffixes=("_pred", "_true"))
    total = len(merged)
    if total == 0:
        return {"total": 0, "accuracy": 0.0}

    exact_match = (merged["label_pred"] == merged["label_true"]).sum()
    pred_actions = merged["label_pred"].str.split(":").str[0]
    true_actions = merged["label_true"].str.split(":").str[0]
    action_match = (pred_actions == true_actions).sum()

    pred_reasons = merged["label_pred"].str.split(":").str[1]
    true_reasons = merged["label_true"].str.split(":").str[1]
    reason_match = (pred_reasons == true_reasons).sum()

    pred_counters = merged["label_pred"].str.split(":").str[2]
    true_counters = merged["label_true"].str.split(":").str[2]
    counter_match = (pred_counters == true_counters).sum()

    return {
        "total": total,
        "exact_match": int(exact_match),
        "accuracy": float(exact_match / total),
        "action_accuracy": float(action_match / total),
        "reason_accuracy": float(reason_match / total),
        "counter_accuracy": float(counter_match / total),
    }


def validate_submission(sub: pd.DataFrame, threads: pd.DataFrame, sample_sub: pd.DataFrame) -> list[str]:
    """Return a list of human-readable validation errors. An empty list means valid."""
    errors: list[str] = []

    if list(sub.columns) != ["thread_id", "label"]:
        errors.append(f"Invalid columns: {list(sub.columns)}; expected ['thread_id', 'label']")

    if len(sub) != len(threads):
        errors.append(f"Row count mismatch: got {len(sub)}, expected {len(threads)}")

    if not sub["thread_id"].equals(threads["thread_id"]):
        errors.append("Thread IDs or their ordering do not match threads.csv")

    if sub.isna().any().any():
        errors.append("Submission contains null or NaN values")

    pattern = re.compile(
        r"^(?:ACCEPT:ACCEPTABLE_PRICE:|REJECT:(?:ABOVE_WALKAWAY|BLACKLISTED_SUPPLIER):|"
        r"ESCALATE:(?:MISSING_INFO|PROMPT_INJECTION|BANNED_TERM|OVER_APPROVAL_LIMIT):|"
        r"COUNTER:COUNTER_OFFER:[1-9]\d*)$"
    )
    for idx, row in sub.iterrows():
        lbl = str(row.get("label", ""))
        if not pattern.match(lbl):
            errors.append(f"Invalid label format at row {idx} ({row.get('thread_id')}): '{lbl}'")
            if len(errors) >= 10:
                errors.append("...further label errors truncated")
                break

    return errors


def write_submission(df: pd.DataFrame, path: str | Path) -> None:
    """Write the final thread_id,label CSV."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False)

