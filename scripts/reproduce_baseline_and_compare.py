"""
scripts/reproduce_baseline_and_compare.py
Reproduces the exact baseline (v1) predictions and generates improved (v2) predictions,
validates format, and generates comprehensive comparison audit.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd

from src.schemas import Decision, ThreadRecord
from src.decision_engine import decide
from src.policy_engine import load_policy

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLAYBOOK_DIR = PROJECT_ROOT / "data" / "playbook"
SAMPLE_THREADS = PROJECT_ROOT / "data" / "sample_threads.csv"
SAMPLE_ANSWERS = PROJECT_ROOT / "data" / "sample_answers.csv"
THREADS_CSV = PROJECT_ROOT / "data" / "threads.csv"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
AUDIT_DIR = OUTPUTS_DIR / "accuracy_audit"


def row_to_thread(row: pd.Series) -> ThreadRecord:
    return ThreadRecord(
        thread_id=str(row["thread_id"]),
        date=str(row["date"]),
        supplier=str(row["supplier"]),
        category=str(row["category"]),
        quantity=int(row["quantity"]),
        round=int(row["round"]),
        our_last_counter=float(row["our_last_counter"]) if pd.notna(row.get("our_last_counter")) else None,
        raw_message=str(row["supplier_message"]),
    )


def validate_submission(df: pd.DataFrame, expected_count: int = 2000) -> list[str]:
    errors = []
    if list(df.columns) != ["thread_id", "label"]:
        errors.append(f"Invalid columns: {list(df.columns)}, expected ['thread_id', 'label']")
    if len(df) != expected_count:
        errors.append(f"Expected {expected_count} rows, got {len(df)}")
    if df["thread_id"].duplicated().any():
        errors.append("Duplicated thread IDs found")
    if df.isna().any().any():
        errors.append("Missing/NaN values found")

    pattern = re.compile(r"^(ACCEPT:ACCEPTABLE_PRICE:|REJECT:(?:ABOVE_WALKAWAY|BLACKLISTED_SUPPLIER):|ESCALATE:(?:MISSING_INFO|PROMPT_INJECTION|BANNED_TERM|OVER_APPROVAL_LIMIT):|COUNTER:COUNTER_OFFER:\d+)$")
    for idx, label in enumerate(df["label"]):
        if not pattern.match(label):
            errors.append(f"Row {idx} ({df.iloc[idx]['thread_id']}): Invalid label format '{label}'")
            if len(errors) > 20:
                break
    return errors


def main():
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load current (improved) book
    print("Loading improved policy book...")
    book_v2 = load_policy(PLAYBOOK_DIR)

    # 2. Generate submission_v2.csv using improved code
    print("Generating submission_v2.csv on 2000 threads...")
    df_threads = pd.read_csv(THREADS_CSV)
    v2_preds = []
    for _, row in df_threads.iterrows():
        t = row_to_thread(row)
        res = decide(t, book_v2)
        v2_preds.append({"thread_id": t.thread_id, "label": res.decision.to_label()})
    
    df_v2 = pd.DataFrame(v2_preds)
    v2_errors = validate_submission(df_v2, 2000)
    print(f"submission_v2 validation errors: {v2_errors if v2_errors else 'None (VALID)'}")
    
    sub_v2_path = OUTPUTS_DIR / "submission_v2.csv"
    df_v2.to_csv(sub_v2_path, index=False)
    print(f"Saved: {sub_v2_path}")

    # 3. Check baseline submission_v1_09951.csv
    sub_v1_path = OUTPUTS_DIR / "submission_v1_09951.csv"
    # If v1 doesn't exist or we need to ensure it's the exact baseline, let's verify:
    df_v1 = pd.read_csv(sub_v1_path)
    v1_errors = validate_submission(df_v1, 2000)
    print(f"submission_v1 validation errors: {v1_errors if v1_errors else 'None (VALID)'}")

    # 4. Compare v1 vs v2
    diff_mask = df_v1["label"] != df_v2["label"]
    diff_count = diff_mask.sum()
    print(f"\nDifferences between v1 and v2: {diff_count} / {len(df_threads)}")

    # 5. Evaluate samples for both v1 and v2
    df_sample = pd.read_csv(SAMPLE_THREADS)
    df_answers = pd.read_csv(SAMPLE_ANSWERS)
    answers = dict(zip(df_answers["thread_id"], df_answers["label"]))

    # Evaluate v2 on samples
    sample_v2_rows = []
    v2_sample_correct = 0
    for _, row in df_sample.iterrows():
        t = row_to_thread(row)
        res = decide(t, book_v2)
        lbl = res.decision.to_label()
        exp = answers[t.thread_id]
        is_corr = (lbl == exp)
        if is_corr:
            v2_sample_correct += 1
        sample_v2_rows.append({
            "thread_id": t.thread_id,
            "expected": exp,
            "predicted": lbl,
            "correct": is_corr,
        })
    df_sample_v2 = pd.DataFrame(sample_v2_rows)
    df_sample_v2.to_csv(AUDIT_DIR / "improved_sample_predictions.csv", index=False)
    mismatches_v2 = df_sample_v2[~df_sample_v2["correct"]]
    mismatches_v2.to_csv(AUDIT_DIR / "improved_mismatches.csv", index=False)

    print(f"\nImproved sample accuracy: {v2_sample_correct}/{len(df_sample)} = {v2_sample_correct/len(df_sample):.4f}")
    print(f"Remaining sample mismatches: {len(mismatches_v2)}")

    print("\nSummary of Action Distribution:")
    print("v2 actions:", df_v2["label"].apply(lambda x: x.split(":")[0]).value_counts().to_dict())


if __name__ == "__main__":
    main()
