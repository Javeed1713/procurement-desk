"""
src/utils.py
Owner: Member 4 (Project Integration)
Depends on: src.schemas, src.policy_engine, src.decision_engine (via decide)

Data loading, row conversion, batch prediction, evaluation, submission
validation and writing. This is the top layer, used by notebooks/main.ipynb.

Phase 3 status: STUB. Bodies raise NotImplementedError until Phase 5.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.policy_engine import PolicyBook
from src.schemas import ThreadRecord

_PHASE5_MSG = "Phase 5: to be implemented by Member 4 (Integration)."


def find_data_dir() -> Path:
    """Locate the data/ folder whether the code runs locally or on Kaggle."""
    raise NotImplementedError(_PHASE5_MSG)


def load_threads(path: str | Path) -> pd.DataFrame:
    """Load a threads CSV into a DataFrame with the eight expected columns."""
    raise NotImplementedError(_PHASE5_MSG)


def row_to_thread(row: pd.Series) -> ThreadRecord:
    """Convert one DataFrame row into a ThreadRecord."""
    raise NotImplementedError(_PHASE5_MSG)


def predict_dataframe(df: pd.DataFrame, book: PolicyBook) -> tuple[pd.DataFrame, pd.DataFrame, list]:
    """Run decide() on every thread row.

    Returns exactly three values, in this fixed order:
      1. predictions_df: DataFrame with columns thread_id and label
      2. trace_df: DataFrame with one row per thread holding its decision trace
      3. errors: list of processing errors (empty when every thread succeeded)

    Do not change the order of these return values.
    """
    raise NotImplementedError(_PHASE5_MSG)


def evaluate_predictions(pred: pd.DataFrame, truth: pd.DataFrame) -> dict:
    """Compare predicted labels with the truth labels and return metrics."""
    raise NotImplementedError(_PHASE5_MSG)


def validate_submission(sub: pd.DataFrame, threads: pd.DataFrame, sample_sub: pd.DataFrame) -> list[str]:
    """Return a list of human-readable validation errors. An empty list means valid."""
    raise NotImplementedError(_PHASE5_MSG)


def write_submission(df: pd.DataFrame, path: str | Path) -> None:
    """Write the final thread_id,label CSV."""
    raise NotImplementedError(_PHASE5_MSG)
