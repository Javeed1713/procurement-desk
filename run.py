"""run.py — generate submission.csv from threads.csv.

Usage:
    python run.py
"""

import pandas as pd
from pathlib import Path
from src.policy_engine import load_policy
from src.decision_engine import decide
from src.schemas import ThreadRecord


def main() -> None:
    book = load_policy("data/playbook")
    df = pd.read_csv("data/threads.csv")

    preds = []
    for _, row in df.iterrows():
        our_last = row.get("our_last_counter")
        t = ThreadRecord(
            thread_id=str(row["thread_id"]),
            date=str(row["date"]),
            supplier=str(row["supplier"]),
            category=str(row["category"]),
            quantity=int(row["quantity"]),
            round=int(row["round"]),
            our_last_counter=float(our_last) if pd.notna(our_last) else None,
            raw_message=str(row["supplier_message"]),
        )
        res = decide(t, book)
        preds.append({"thread_id": t.thread_id, "label": res.decision.to_label()})

    out_path = Path("submission.csv")
    pd.DataFrame(preds).to_csv(out_path, index=False)
    print(f"Wrote {len(preds)} predictions to {out_path}")


if __name__ == "__main__":
    main()
