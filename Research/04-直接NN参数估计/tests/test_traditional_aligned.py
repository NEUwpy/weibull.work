from pathlib import Path
import importlib.util

import pandas as pd
import pytest

PATH = Path(__file__).resolve().parents[1] / "code/run_traditional_aligned.py"
SPEC = importlib.util.spec_from_file_location("traditional_aligned", PATH)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def rows():
    return pd.DataFrame([
        dict(method=m, beta=2., gamma_over_eta=.5, n=10, repeat_id=0,
             status="success", failure_reason="", loss_primary=.2)
        for m in MOD.METHODS
    ])


def test_shared_sample_pair_accepted():
    MOD.validate(rows(), 1)


def test_duplicate_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        MOD.validate(pd.concat([rows(), rows()]), 2)


def test_different_sample_keys_rejected():
    frame = rows()
    frame.loc[1, "repeat_id"] = 1
    with pytest.raises(ValueError, match="sample set"):
        MOD.validate(frame, 1)


def test_failure_requires_reason_and_finite_penalty():
    frame = rows()
    frame.loc[0, "status"] = "failure"
    with pytest.raises(ValueError, match="without reason"):
        MOD.validate(frame, 1)
    frame.loc[0, "failure_reason"] = "solver_failure"
    MOD.validate(frame, 1)
    frame.loc[0, "loss_primary"] = float("nan")
    with pytest.raises(ValueError, match="nonfinite"):
        MOD.validate(frame, 1)
