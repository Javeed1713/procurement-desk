"""
scripts/generate_both_submissions.py
Ensures submission_v1_09951.csv is generated from the pristine baseline (git HEAD)
and submission_v2.csv is generated from the improved code.
Then compares both across all 2,000 threads and all 40 sample threads.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import types
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.schemas import ThreadRecord
from src.decision_engine import decide
import src.policy_engine as policy_engine_v2
import src.security_checker as security_checker_v2

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


def load_baseline_modules():
    """Load pristine baseline modules from git HEAD."""
    base_policy_code = subprocess.check_output(["git", "show", "HEAD:src/policy_engine.py"]).decode("utf-8-sig")
    base_security_code = subprocess.check_output(["git", "show", "HEAD:src/security_checker.py"]).decode("utf-8-sig")

    # Create dummy modules
    sec_mod = types.ModuleType("src.security_checker")
    exec(compile(base_security_code, "src/security_checker.py", "exec"), sec_mod.__dict__)

    pol_mod = types.ModuleType("src.policy_engine")
    pol_mod.__dict__["src"] = sys.modules["src"]
    pol_mod.__dict__["src.schemas"] = sys.modules["src.schemas"]
    exec(compile(base_policy_code, "src/policy_engine.py", "exec"), pol_mod.__dict__)

    return pol_mod, sec_mod


def run_prediction_with_modules(df: pd.DataFrame, pol_mod, sec_mod, book):
    import src.decision_engine as de
    orig_pol = de.get_params, de.normalize_offer, de.price_limit, de.counter_price, de.is_final_round, de.exceeds_approval_limit, de.find_banned_terms
    orig_sec = de.detect_prompt_injection, de.is_blacklisted

    # Patch decision_engine functions
    de.get_params = pol_mod.get_params
    de.normalize_offer = pol_mod.normalize_offer
    de.price_limit = pol_mod.price_limit
    de.counter_price = pol_mod.counter_price
    de.is_final_round = pol_mod.is_final_round
    de.exceeds_approval_limit = pol_mod.exceeds_approval_limit
    de.find_banned_terms = pol_mod.find_banned_terms
    de.detect_prompt_injection = sec_mod.detect_prompt_injection
    de.is_blacklisted = sec_mod.is_blacklisted

    results = []
    try:
        for _, row in df.iterrows():
            t = row_to_thread(row)
            res = de.decide(t, book)
            results.append({"thread_id": t.thread_id, "label": res.decision.to_label(), "trace": " | ".join(res.trace)})
    finally:
        # Restore
        (de.get_params, de.normalize_offer, de.price_limit, de.counter_price, de.is_final_round, de.exceeds_approval_limit, de.find_banned_terms) = orig_pol
        (de.detect_prompt_injection, de.is_blacklisted) = orig_sec

    return results


def main():
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    df_threads = pd.read_csv(THREADS_CSV)
    df_sample = pd.read_csv(SAMPLE_THREADS)
    df_answers = pd.read_csv(SAMPLE_ANSWERS)
    answers = dict(zip(df_answers["thread_id"], df_answers["label"]))

    # 1. BASELINE PREDICTIONS
    print("--- 1. Generating Pristine Baseline (v1) ---")
    base_pol, base_sec = load_baseline_modules()
    book_v1 = base_pol.load_policy(PLAYBOOK_DIR)
    
    # Baseline on samples
    base_sample_preds = run_prediction_with_modules(df_sample, base_pol, base_sec, book_v1)
    base_sample_correct = sum(1 for p in base_sample_preds if p["label"] == answers[p["thread_id"]])
    print(f"Baseline sample accuracy: {base_sample_correct}/{len(df_sample)} = {base_sample_correct/len(df_sample):.4f}")

    # Baseline on full 2,000 threads
    base_full_preds = run_prediction_with_modules(df_threads, base_pol, base_sec, book_v1)
    df_v1 = pd.DataFrame([{"thread_id": p["thread_id"], "label": p["label"]} for p in base_full_preds])
    sub_v1_path = OUTPUTS_DIR / "submission_v1_09951.csv"
    df_v1.to_csv(sub_v1_path, index=False)
    print(f"Pristine baseline submission saved: {sub_v1_path} ({len(df_v1)} rows)")

    # 2. IMPROVED PREDICTIONS
    print("\n--- 2. Generating Improved (v2) ---")
    book_v2 = policy_engine_v2.load_policy(PLAYBOOK_DIR)
    
    # Improved on samples
    v2_sample_preds = []
    for _, row in df_sample.iterrows():
        t = row_to_thread(row)
        res = decide(t, book_v2)
        v2_sample_preds.append({"thread_id": t.thread_id, "label": res.decision.to_label(), "trace": " | ".join(res.trace)})
    
    v2_sample_correct = sum(1 for p in v2_sample_preds if p["label"] == answers[p["thread_id"]])
    print(f"Improved sample accuracy: {v2_sample_correct}/{len(df_sample)} = {v2_sample_correct/len(df_sample):.4f}")

    # Improved on full 2,000 threads
    v2_full_preds = []
    for _, row in df_threads.iterrows():
        t = row_to_thread(row)
        res = decide(t, book_v2)
        v2_full_preds.append({"thread_id": t.thread_id, "label": res.decision.to_label(), "trace": " | ".join(res.trace)})
    
    df_v2 = pd.DataFrame([{"thread_id": p["thread_id"], "label": p["label"]} for p in v2_full_preds])
    sub_v2_path = OUTPUTS_DIR / "submission_v2.csv"
    df_v2.to_csv(sub_v2_path, index=False)
    print(f"Improved submission saved: {sub_v2_path} ({len(df_v2)} rows)")

    # 3. COMPARISON ANALYSIS
    print("\n--- 3. Comparison Analysis ---")
    diffs = []
    for p1, p2, (_, row) in zip(base_full_preds, v2_full_preds, df_threads.iterrows()):
        if p1["label"] != p2["label"]:
            diffs.append({
                "thread_id": p1["thread_id"],
                "supplier": row["supplier"],
                "category": row["category"],
                "round": row["round"],
                "v1_baseline": p1["label"],
                "v2_improved": p2["label"],
                "message_excerpt": row["supplier_message"].replace("\n", " ")[:100],
            })

    print(f"Total differences across 2,000 threads: {len(diffs)}")
    diff_df = pd.DataFrame(diffs)
    diff_df.to_csv(AUDIT_DIR / "v1_vs_v2_differences.csv", index=False)
    print(f"Differences saved to: {AUDIT_DIR / 'v1_vs_v2_differences.csv'}")

    # Breakdown of differences by reason
    change_types = {}
    for d in diffs:
        key = f"{d['v1_baseline'].split(':')[0]} -> {d['v2_improved'].split(':')[0]}"
        change_types[key] = change_types.get(key, 0) + 1
    print("Action transition breakdown:", change_types)

    # Detailed report data
    print("\nSample of 10 differences:")
    for d in diffs[:10]:
        print(f"  {d['thread_id']}: {d['v1_baseline']} -> {d['v2_improved']} | {d['supplier']} ({d['category']})")


if __name__ == "__main__":
    main()
