from pathlib import Path
import inspect
import sys

import numpy as np
import torch


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))

from study02a.config import load_frozen_config
from study02a.models import build_mlp
from study02a.training import (
    expand_search_specs,
    fit_candidate,
    run_two_stage_search,
    seed_everything,
)


def test_two_stage_search_expansion_is_frozen():
    cfg = load_frozen_config(STUDY_ROOT)
    specs = expand_search_specs("F2", cfg.search)
    assert len(specs.stage1) == 12
    stage2 = specs.expand_stage2(["m04", "m01", "m08", "m05"])
    assert len(stage2) == 12
    assert {spec.optimizer_id for spec in stage2} == {"o1", "o2", "o3"}
    assert [spec.architecture_id for spec in stage2[:3]] == ["m01"] * 3


def test_search_api_cannot_receive_test_data():
    parameters = inspect.signature(run_two_stage_search).parameters
    assert "test" not in parameters
    assert parameters["validation_scorer"].default is inspect.Parameter.empty


def test_seed_everything_reproduces_numpy_and_torch():
    seed_everything(420001)
    first = (np.random.random(4), torch.rand(4))
    seed_everything(420001)
    second = (np.random.random(4), torch.rand(4))
    np.testing.assert_array_equal(first[0], second[0])
    assert torch.equal(first[1], second[1])


def test_smoke_fit_is_reproducible():
    rng = np.random.default_rng(12)
    x = torch.tensor(rng.normal(size=(128, 6)), dtype=torch.float32)
    y = torch.tensor(rng.normal(size=(128, 3)), dtype=torch.float32)
    train = (x[:96], y[:96])
    validation = (x[96:], y[96:])
    model_factory = lambda: build_mlp(6, (16, 8), "relu", 0.0)
    first = fit_candidate(model_factory, train, validation, seed=420001, max_epochs=8, min_epochs=2, patience=3)
    second = fit_candidate(model_factory, train, validation, seed=420001, max_epochs=8, min_epochs=2, patience=3)
    assert first.checkpoint_sha256 == second.checkpoint_sha256
    assert torch.equal(first.predictions, second.predictions)
