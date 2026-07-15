"""Tests for the Study/02 formal execution driver (Task 9c.3)."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest
import torch


ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
sys.path.insert(0, str(STUDY_ROOT / "code"))
sys.path.insert(0, str(ROOT / "python"))

from study02a import formal_executor as fe  # noqa: E402
from study02a.config import load_frozen_config  # noqa: E402
from study02a.formal_config import load_effective_formal_config  # noqa: E402
from study02a.formal_runner import build_training_spec, build_validation_spec  # noqa: E402
from study02a.models import build_mlp  # noqa: E402
from study02a.training import fit_candidate  # noqa: E402


FROZEN = load_frozen_config(STUDY_ROOT)
EFFECTIVE = load_effective_formal_config(STUDY_ROOT)


def _plan_row(**overrides):
    base = {
        "plan_version": "study02-formal-plan-row-v2", "plan_index": 0, "run_id": "r1",
        "fit_id": "G3-fit-0000", "fit_range": [0, 0], "matrix_row_sha256": "0"*64,
        "module_id": "A-E1", "rule_id": "A-E1_historical", "route": "H0_hsm",
        "distribution": "legacy_grid", "n_mode": "shared_n", "fixed_n": None,
        "loss": "raw_train_z_mse", "architecture": "historical_128_64_32",
        "optimizer": "adam_historical", "training_size": 7000, "seed": 420101,
        "effective_config_sha256": EFFECTIVE.effective_config_sha256, "code_commit": "0"*40,
        "training_cache_key": "", "validation_cache_key": "",
        "training_cache_path": "", "validation_cache_path": "",
        "predecessor_trace_sha256": "0"*64,
        "expected_outputs": [
            {"relative_path": "outputs/G3-fit-0000/checkpoint.pt", "content_type": "binary", "required": True},
            {"relative_path": "outputs/G3-fit-0000/fit_status.json", "content_type": "canonical_json", "required": True},
        ],
        "test_access_count": 0,
    }
    base.update(overrides)
    return base


def test_checkpoint_canonical_bytes_hash_to_checkpoint_sha256():
    """D1: sha256(FitResult.checkpoint_bytes) == checkpoint_sha256 (the on-disk contract)."""
    import hashlib
    tx = torch.randn(32, 4); ty = torch.randn(32, 3); vx = torch.randn(8, 4); vy = torch.randn(8, 3)
    fit = fit_candidate(lambda: build_mlp(4, [8], "relu", 0.0), (tx, ty), (vx, vy),
                        seed=1, max_epochs=2, min_epochs=1, patience=1, batch_size=16)
    assert len(fit.checkpoint_bytes) > 0
    assert hashlib.sha256(fit.checkpoint_bytes).hexdigest() == fit.checkpoint_sha256


def test_resolve_model_factory_concrete_and_fail_closed():
    mlp_factory = fe.resolve_model_factory("m05", FROZEN, input_dim=15)
    assert mlp_factory() is not None
    deep_factory = fe.resolve_model_factory("d01", FROZEN, input_dim=None)
    assert deep_factory() is not None
    hist_factory = fe.resolve_model_factory("historical_128_64_32", FROZEN, input_dim=7)
    assert hist_factory() is not None
    with pytest.raises(NotImplementedError):
        fe.resolve_model_factory("selected:A-E1_architecture", FROZEN, input_dim=15)
    with pytest.raises(NotImplementedError):
        fe.resolve_model_factory("selected_top_1", FROZEN, input_dim=15)
    with pytest.raises(ValueError):
        fe.resolve_model_factory("unknown_x", FROZEN, input_dim=15)


def test_resolve_optimizer_hyperparams_concrete_and_fail_closed():
    s1 = fe.resolve_optimizer_hyperparams("stage1", FROZEN)
    assert s1["batch_size"] == 512 and s1["lr"] == pytest.approx(1e-3)
    hist = fe.resolve_optimizer_hyperparams("adam_historical", FROZEN)
    assert hist["batch_size"] == 32
    o1 = fe.resolve_optimizer_hyperparams("o1", FROZEN)
    assert o1["batch_size"] == 128 and o1["lr"] == pytest.approx(3e-4)
    with pytest.raises(NotImplementedError):
        fe.resolve_optimizer_hyperparams("selected:A-E1_optimizer", FROZEN)


def test_resolve_loss_id_passthrough_and_fail_closed():
    assert fe.resolve_loss_id("raw_train_z_mse") == "raw_train_z_mse"
    assert fe.resolve_loss_id("transformed_train_z_huber") == "transformed_train_z_huber"
    with pytest.raises(NotImplementedError):
        fe.resolve_loss_id("selected:A-E1_loss")


def test_is_selection_dependent_defers_placeholder_fits():
    # concrete historical/controlled/stage1 fits are executable; selected:* / selected_top_* defer to D7
    assert fe._is_selection_dependent(_plan_row()) is False  # historical_128_64_32 / adam_historical
    assert fe._is_selection_dependent(_plan_row(architecture="m05", optimizer="stage1")) is False
    assert fe._is_selection_dependent(_plan_row(architecture="selected_top_1", optimizer="o1")) is True
    assert fe._is_selection_dependent(_plan_row(architecture="selected:A-E1_architecture", optimizer="selected:A-E1_optimizer")) is True


def test_reconstruct_a_e1_specs_cache_keys_match_scheduler(tmp_path):
    """The executor rebuilds the exact same spec the scheduler planned (no drift)."""
    # Build the spec the way the scheduler does, then compare cache_key to what the executor reconstructs.
    training = build_training_spec(route="H0_hsm", distribution="legacy_grid", n_mode="shared_n",
                                   fixed_n=None, training_rows=7000, frozen_config=FROZEN, effective_config=EFFECTIVE)
    validation = build_validation_spec(route="H0_hsm", distribution="legacy_grid", n_mode="shared_n",
                                       fixed_n=None, frozen_config=FROZEN, effective_config=EFFECTIVE)
    row = _plan_row(training_cache_key=training.cache_key, validation_cache_key=validation.cache_key)
    t_spec, v_spec = fe.reconstruct_a_e1_specs(row, FROZEN, EFFECTIVE)
    assert t_spec.cache_key == training.cache_key
    assert v_spec.cache_key == validation.cache_key
    # drift must fail closed:
    with pytest.raises(ValueError):
        fe.reconstruct_a_e1_specs(_plan_row(training_cache_key="0"*64, validation_cache_key=validation.cache_key), FROZEN, EFFECTIVE)


def test_run_module_rejects_non_a_e1_modules(tmp_path):
    with pytest.raises(NotImplementedError):
        fe.run_module(study_root=STUDY_ROOT, module_id="A-E3", run_id="r1",
                      artifact_root=tmp_path, cache_root=tmp_path / "cache")


def test_d7_d8_placeholders_fail_closed():
    with pytest.raises(NotImplementedError):
        fe.build_module_selection(study_root=STUDY_ROOT, run_dir=Path("."), cache_root=Path("."),
                                  module_id="A-E1", run_id="r1")
    with pytest.raises(NotImplementedError):
        fe.resolve_selected_placeholders()
    with pytest.raises(NotImplementedError):
        fe.reconstruct_deferred_specs()


@pytest.mark.slow
def test_smoke_a_e1_one_fit_end_to_end(tmp_path, monkeypatch):
    """End-to-end: materialize A-E1, claim+train+record ONE real fit; assert scheduler integrity.

    Requires a clean ``code/`` tree (the scheduler authority check fails on dirty scientific
    code), so run after committing. Training epochs are reduced via a fast wrapper so this
    exercises the full plumbing (dataset build/cache, training-only scaler, canonical
    checkpoint + 5-field fit_status binding, metrics sidecar, record_fit_succeeded, authority
    rebuild) in seconds rather than the full 100-epoch formal contract.
    """
    # fail fast with a clear message if code/ is dirty (materialize_run would reject it)
    status = __import__("subprocess").run(
        ["git", "status", "--porcelain", "--",
         str((STUDY_ROOT / "code").relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert not status.stdout.strip(), "code/ must be clean for the scheduler authority check"

    def fast_fixed(model_factory, train_batch, val_batch, effective, *, seed, loss_id, lr, weight_decay, batch_size, optimizer_id="adamw"):
        return fit_candidate(
            model_factory,
            (train_batch.features, train_batch.targets),
            (val_batch.features, val_batch.targets),
            seed=seed, max_epochs=2, min_epochs=1, patience=1,
            batch_size=min(int(batch_size), 64), loss_id=loss_id, lr=lr, weight_decay=weight_decay,
            optimizer_id=optimizer_id,
        )
    monkeypatch.setattr(fe, "fit_fixed_candidate", fast_fixed)

    artifact_root = tmp_path / "artifact"
    cache_root = tmp_path / "cache"
    summary = fe.run_module(
        study_root=STUDY_ROOT, module_id="A-E1", run_id="smoke-0001",
        artifact_root=artifact_root, cache_root=cache_root, owner_id="smoke-test", max_fits=1,
    )
    assert summary["succeeded_count"] == 1
    assert summary["failed_count"] == 0
    fit_id = summary["succeeded"][0]

    from study02a.formal_scheduler import status_run, _rebuild_authority
    run_dir = artifact_root / "A-E1" / "smoke-0001"
    stat = status_run(run_dir, cache_root=cache_root)
    assert stat["test_access_count"] == 0
    assert stat["counts"]["succeeded"] == 1
    manifest, plan, state, events = _rebuild_authority(run_dir, cache_root)
    assert state["fit_states"][fit_id] == "succeeded"
    # checkpoint.pt is loadable and reproduces the model; fit_status binds the checkpoint; evidence binds trajectory
    import hashlib, json
    from study02a.training import load_checkpoint
    checkpoint = (run_dir / "outputs" / fit_id / "checkpoint.pt").read_bytes()
    binding = json.loads((run_dir / "outputs" / fit_id / "fit_status.json").read_bytes())
    assert binding == {"checkpoint_sha256": hashlib.sha256(checkpoint).hexdigest(),
                       "fit_id": fit_id, "run_id": "smoke-0001", "status": "succeeded", "test_access_count": 0}
    evidence = json.loads((run_dir / "outputs" / fit_id / "evidence.json").read_bytes())
    assert evidence["checkpoint_sha256"] == binding["checkpoint_sha256"]
    assert evidence["actual_epochs"] >= 1 and len(evidence["validation_curve"]) == evidence["actual_epochs"]
    state_dict = load_checkpoint(checkpoint)
    assert set(state_dict) and all(isinstance(t, torch.Tensor) for t in state_dict.values())
    # no untrusted metrics sidecar exists (selection signal must derive from the bound checkpoint)
    assert not (run_dir / "metrics").exists()
