"""Integration and contract tests. Owner: Member 4 (Project Integration)."""

import inspect

import pandas as pd
import pytest

from src import decision_engine, message_parser, policy_engine, security_checker, utils
from src.schemas import Decision, NormalizedOffer, RawOffer, ThreadText


def test_all_modules_import():
    """Every architecture module imports and belongs to the src package."""
    modules = [policy_engine, message_parser, security_checker, decision_engine, utils]
    for module in modules:
        assert module.__name__.startswith("src."), f"unexpected module {module.__name__}"


def test_utils_exposes_agreed_interface():
    """Confirms the top-level helper functions exist."""
    for name in [
        "find_data_dir",
        "load_threads",
        "row_to_thread",
        "predict_dataframe",
        "evaluate_predictions",
        "validate_submission",
        "write_submission",
    ]:
        assert callable(getattr(utils, name, None)), f"missing {name}"


def test_predict_dataframe_parameter_order():
    """predict_dataframe must take (df, book) in that order."""
    params = list(inspect.signature(utils.predict_dataframe).parameters)
    assert params == ["df", "book"]


def test_decision_label_format_for_accept():
    """Non-COUNTER labels end with an empty price field."""
    assert Decision("ACCEPT", "ACCEPTABLE_PRICE").to_label() == "ACCEPT:ACCEPTABLE_PRICE:"


def test_decision_label_format_for_counter():
    """COUNTER labels carry the integer price."""
    assert Decision("COUNTER", "COUNTER_OFFER", 1234).to_label() == "COUNTER:COUNTER_OFFER:1234"


def test_invalid_action_reason_pair_is_rejected():
    """A reason that does not belong to its action must raise ValueError."""
    with pytest.raises(ValueError):
        Decision("ACCEPT", "COUNTER_OFFER")


def test_counter_without_price_is_rejected():
    """COUNTER must always include a price."""
    with pytest.raises(ValueError):
        Decision("COUNTER", "COUNTER_OFFER")


def test_price_on_non_counter_is_rejected():
    """Only COUNTER may carry a price."""
    with pytest.raises(ValueError):
        Decision("REJECT", "ABOVE_WALKAWAY", 500)


def test_normalized_offer_requires_price_when_ok():
    """A successful normalization must provide a price."""
    with pytest.raises(ValueError):
        NormalizedOffer(ok=True)


def test_raw_offer_rejects_unknown_status():
    """Only OK and NO_PRICE are valid RawOffer statuses."""
    with pytest.raises(ValueError):
        RawOffer(status="MAYBE")


def test_thread_text_accepts_lists():
    """earlier_supplier and earlier_acme are lists of strings."""
    text = ThreadText(
        latest="Price is 100",
        earlier_supplier=["Quote one", "Quote two"],
        earlier_acme=["Our counter"],
        full="whole thread",
    )
    assert text.earlier_supplier == ["Quote one", "Quote two"]
    assert text.earlier_acme == ["Our counter"]


def test_thread_text_rejects_string_earlier_supplier():
    """A plain string for earlier_supplier must raise TypeError."""
    with pytest.raises(TypeError):
        ThreadText(latest="x", earlier_supplier="not a list", earlier_acme=[], full="x")


def test_thread_text_rejects_string_earlier_acme():
    """A plain string for earlier_acme must raise TypeError."""
    with pytest.raises(TypeError):
        ThreadText(latest="x", earlier_supplier=[], earlier_acme="not a list", full="x")


def test_end_to_end_on_sample_data():
    """End-to-end pipeline test on sample data achieves 100% accuracy."""
    from pathlib import Path
    data_dir = utils.find_data_dir()
    sample_threads_path = data_dir / "sample_threads.csv"
    sample_answers_path = data_dir / "sample_answers.csv"
    playbook_path = data_dir / "playbook"

    if not sample_threads_path.exists() or not playbook_path.exists():
        pytest.skip("Sample data or playbook not found")

    book = policy_engine.load_policy(playbook_path)
    df_threads = utils.load_threads(sample_threads_path)
    df_truth = pd.read_csv(sample_answers_path)

    preds_df, traces_df, errors = utils.predict_dataframe(df_threads, book)
    assert len(errors) == 0, f"Errors encountered: {errors}"
    assert len(preds_df) == len(df_threads)

    metrics = utils.evaluate_predictions(preds_df, df_truth)
    assert metrics["accuracy"] == 1.0, f"Expected 100% sample accuracy, got {metrics['accuracy']}"


def test_cli_reproduces_final_submission(tmp_path):
    """Regenerate the selected artifact using the public CLI entry point."""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    if not (root / "data/threads.csv").exists():
        pytest.skip("Competition dataset is required for reproduction")
    (tmp_path / "data").symlink_to(root / "data", target_is_directory=True)
    subprocess.run([sys.executable, str(root / "run.py")], cwd=tmp_path, check=True)
    assert (tmp_path / "submission.csv").read_bytes() == (root / "submissionFinal.csv").read_bytes()
