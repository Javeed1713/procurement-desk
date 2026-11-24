"""
scripts/run_audit.py
Baseline audit: run predictions on 40 labelled samples and compare to ground truth.
"""
from __future__ import annotations

import json
import csv
import sys
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.policy_engine import load_policy, get_params, normalize_offer, counter_price, price_limit, is_final_round
from src.message_parser import split_thread, extract_offer
from src.decision_engine import decide
from src.schemas import ThreadRecord

PLAYBOOK_DIR = PROJECT_ROOT / "data" / "playbook"
SAMPLE_THREADS = PROJECT_ROOT / "data" / "sample_threads.csv"
SAMPLE_ANSWERS = PROJECT_ROOT / "data" / "sample_answers.csv"
THREADS_CSV = PROJECT_ROOT / "data" / "threads.csv"
AUDIT_DIR = PROJECT_ROOT / "outputs" / "accuracy_audit"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


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


def predict_all(df: pd.DataFrame, book) -> list[dict]:
    results = []
    for _, row in df.iterrows():
        thread = row_to_thread(row)
        try:
            result = decide(thread, book)
            label = result.decision.to_label()
            trace = result.trace
            price = result.price
            limit = result.limit
        except Exception as e:
            label = f"ERROR:{e}"
            trace = [str(e)]
            price = None
            limit = None
        results.append({
            "thread_id": thread.thread_id,
            "predicted_label": label,
            "price": price,
            "limit": limit,
            "trace": " | ".join(trace),
        })
    return results


def main():
    print("Loading playbook...")
    book = load_policy(PLAYBOOK_DIR)
    print(f"  Categories: {list(book.categories.keys())}")
    print(f"  Amendments: {len(book.amendments)}")
    print(f"  Suppliers: {len(book.suppliers)}")

    print("\nLoading sample data...")
    df_threads = pd.read_csv(SAMPLE_THREADS)
    df_answers = pd.read_csv(SAMPLE_ANSWERS)

    print(f"  {len(df_threads)} sample threads, {len(df_answers)} answers")

    print("\nRunning predictions on 40 samples...")
    preds = predict_all(df_threads, book)

    pred_df = pd.DataFrame(preds)
    answers = dict(zip(df_answers["thread_id"], df_answers["label"]))

    # Compare
    rows = []
    correct = 0
    action_correct = 0
    reason_correct = 0
    counter_correct = 0

    for p in preds:
        tid = p["thread_id"]
        predicted = p["predicted_label"]
        expected = answers.get(tid, "UNKNOWN")

        is_correct = (predicted == expected)
        if is_correct:
            correct += 1

        pred_parts = predicted.split(":")
        exp_parts = expected.split(":")

        pred_action = pred_parts[0] if pred_parts else ""
        pred_reason = pred_parts[1] if len(pred_parts) > 1 else ""
        pred_counter = pred_parts[2] if len(pred_parts) > 2 else ""

        exp_action = exp_parts[0] if exp_parts else ""
        exp_reason = exp_parts[1] if len(exp_parts) > 1 else ""
        exp_counter = exp_parts[2] if len(exp_parts) > 2 else ""

        if pred_action == exp_action:
            action_correct += 1
        if pred_reason == exp_reason:
            reason_correct += 1
        if pred_counter == exp_counter:
            counter_correct += 1

        rows.append({
            "thread_id": tid,
            "expected": expected,
            "predicted": predicted,
            "correct": is_correct,
            "action_match": pred_action == exp_action,
            "reason_match": pred_reason == exp_reason,
            "counter_match": pred_counter == exp_counter,
            "price": p["price"],
            "limit": p["limit"],
            "trace": p["trace"],
        })

    total = len(preds)
    accuracy = correct / total

    # Action distribution
    action_counts = {}
    for p in preds:
        a = p["predicted_label"].split(":")[0]
        action_counts[a] = action_counts.get(a, 0) + 1

    metrics = {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "action_accuracy": action_correct / total,
        "reason_accuracy": reason_correct / total,
        "counter_accuracy": counter_correct / total,
        "action_distribution": action_counts,
    }

    print(f"\n=== BASELINE RESULTS ===")
    print(f"Accuracy: {correct}/{total} = {accuracy:.4f} ({accuracy*100:.2f}%)")
    print(f"Action accuracy: {action_correct}/{total}")
    print(f"Reason accuracy: {reason_correct}/{total}")
    print(f"Counter accuracy: {counter_correct}/{total}")
    print(f"Action distribution: {action_counts}")

    # Mismatches
    mismatches = [r for r in rows if not r["correct"]]
    print(f"\nMismatches ({len(mismatches)}):")
    for m in mismatches:
        print(f"  {m['thread_id']}: expected={m['expected']}  got={m['predicted']}")
        print(f"    price={m['price']:.2f} limit={m['limit']}  trace={m['trace'][:120]}")

    # Save outputs
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    pred_df_out = pd.DataFrame([{"thread_id": r["thread_id"], "label": r["predicted"]} for r in rows])
    pred_df_out.to_csv(AUDIT_DIR / "baseline_sample_predictions.csv", index=False)

    mismatch_df = pd.DataFrame(mismatches)
    mismatch_df.to_csv(AUDIT_DIR / "baseline_mismatches.csv", index=False)

    with open(AUDIT_DIR / "baseline_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\nSaved audit outputs to {AUDIT_DIR}")

    # Now run full 2000-thread prediction (baseline submission)
    print("\nRunning full 2000-thread prediction (baseline submission)...")
    df_full = pd.read_csv(THREADS_CSV)
    print(f"  {len(df_full)} threads in full dataset")

    full_preds = predict_all(df_full, book)
    full_errors = [p for p in full_preds if p["predicted_label"].startswith("ERROR:")]
    print(f"  Errors: {len(full_errors)}")
    if full_errors:
        for e in full_errors[:5]:
            print(f"    {e['thread_id']}: {e['predicted_label']}")

    sub_df = pd.DataFrame([{"thread_id": p["thread_id"], "label": p["predicted_label"]} for p in full_preds])
    sub_path = OUTPUTS_DIR / "submission_v1_09951.csv"
    sub_df.to_csv(sub_path, index=False)
    print(f"\nBaseline submission saved: {sub_path}")
    print(f"Rows: {len(sub_df)}")
    print(f"Sample:\n{sub_df.head(10).to_string()}")


if __name__ == "__main__":
    main()
