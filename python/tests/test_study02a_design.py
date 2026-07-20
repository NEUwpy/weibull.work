from pathlib import Path
import sys

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
PYTHON_ROOT = REPO_ROOT / "python"
for path in (STUDY_CODE, PYTHON_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from studies.common.sample import generate_sample
from study02a.config import load_frozen_config
from study02a.design import (
    allocate_historical_rows,
    allocate_training_rows,
    generate_lifetime_sample,
    generate_parameter_points,
)


def test_role_parameter_points_are_deterministic_and_disjoint():
    cfg = load_frozen_config(STUDY_ROOT)
    train_a = generate_parameter_points("training", "core", 64, cfg)
    train_b = generate_parameter_points("training", "core", 64, cfg)
    valid = generate_parameter_points("validation", "core", 64, cfg)
    pd.testing.assert_frame_equal(train_a, train_b)
    assert train_a.merge(valid, on=["beta", "eta", "rho"]).empty
    assert (train_a["gamma"] == train_a["rho"] * train_a["eta"]).all()


def test_historical_shared_allocation_is_exact_and_role_disjoint():
    cfg = load_frozen_config(STUDY_ROOT)
    train = allocate_historical_rows("training", 7000, cfg)
    valid = allocate_historical_rows("validation", 2000, cfg)
    assert len(train) == 7000
    assert len(valid) == 2000
    assert train["cell_id"].nunique() == 400
    assert valid["cell_id"].nunique() == 100
    assert set(train["n"]) == {5, 7, 10, 15, 20}
    assert set(train["parameter_cell_id"]).isdisjoint(valid["parameter_cell_id"])


def test_legacy_and_continuous_training_allocations_have_requested_rows():
    cfg = load_frozen_config(STUDY_ROOT)
    legacy = allocate_training_rows("legacy_grid", "shared_n", 7000, cfg)
    continuous = allocate_training_rows("core_continuous", "fixed_n", 128, cfg, fixed_n=10)
    assert len(legacy) == 7000
    assert legacy["cell_id"].nunique() == 500
    assert len(continuous) == 128
    assert set(continuous["n"]) == {10}
    assert continuous[["beta", "eta", "rho"]].drop_duplicates().shape[0] == 128


def test_lifetime_sample_delegates_to_common_generator():
    row = {"beta": 2.0, "eta": 100.0, "gamma": 20.0, "n": 7, "repeat_id": 3}
    actual = generate_lifetime_sample(row, namespace=320201)
    expected = generate_sample(2.0, 100.0, 20.0, 7, 3, seed=320201)
    assert (actual == expected).all()
