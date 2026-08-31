from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "code"
    / "run_study01_aligned_generalization.py"
)
SPEC = importlib.util.spec_from_file_location("r04_generalization", MODULE_PATH)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


def test_design_matches_study01_and_seed42():
    assert MOD.MODEL_SEED == 42
    assert MOD.TRAIN_BETAS == (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)
    assert MOD.GAMMA_RATIOS == (0.1, 0.25, 0.5, 0.75, 1.0)
    assert MOD.N_VALUES == (7, 10, 15, 20)
    assert MOD.TRAIN_REPEATS == 300
    assert len(MOD.TRAIN_BETAS) * len(MOD.GAMMA_RATIOS) * len(MOD.N_VALUES) * MOD.TRAIN_REPEATS == 48000


def test_beta_groups_and_test_counts():
    assert MOD.beta_group(1.5) == "seen_grid"
    assert MOD.beta_group(1.75) == "in_domain_unseen"
    assert MOD.beta_group(1.25) == "near_ood"
    assert MOD.beta_group(0.75) == "far_ood"
    counts = MOD.expected_test_counts()
    assert counts == {
        "seen_grid": 48000,
        "in_domain_unseen": 42000,
        "near_ood": 12000,
        "far_ood": 24000,
    }
    assert sum(counts.values()) == 126000


def test_training_and_test_namespaces_are_separate():
    assert MOD.TRAIN_SEED_NAMESPACE == "study01_nrmc_v1"
    assert MOD.TEST_SEED_NAMESPACE != MOD.TRAIN_SEED_NAMESPACE


def test_joint_loss_is_study01_j1_squared():
    got = MOD.joint_loss(2.2, 1100.0, 400.0, 2.0, 1000.0, 500.0)
    expected = (0.2 / 2.0) ** 2 + (100.0 / 1000.0) ** 2 + (-100.0 / 1000.0) ** 2
    assert abs(got - expected) < 1e-12
