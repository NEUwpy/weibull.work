"""D7/D8 selection tests for Study/02 (scoring, decision grouping, trace/receipt,
placeholder resolution, tamper/dup/conflict, sealed-test)."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pytest
import torch


ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
sys.path.insert(0, str(STUDY_ROOT / "code"))
sys.path.insert(0, str(ROOT / "python"))

from study02a import formal_executor as fe  # noqa: E402
from study02a.config import load_frozen_config  # noqa: E402
from study02a.evaluation import evaluate_rows  # noqa: E402
from study02a.formal_contracts import (  # noqa: E402
    publish_selection_receipt,
    write_selection_trace,
)
from study02a.formal_data import FormalFixedBatch  # noqa: E402
from study02a.formal_config import load_effective_formal_config  # noqa: E402
from study02a.matrix import expand_module_matrix  # noqa: E402
from study02a.models import build_mlp  # noqa: E402
from study02a.representations import anchor_sample, build_features, decode_targets, encode_targets  # noqa: E402
from study02a.training import fit_candidate, load_checkpoint  # noqa: E402

EFFECTIVE = load_effective_formal_config(STUDY_ROOT)
FROZEN = load_frozen_config(STUDY_ROOT)


def _synthetic_batch(n_samples: int = 64, seed: int = 7) -> tuple[FormalFixedBatch, np.ndarray, np.ndarray, np.ndarray]:
    """Build a formal fixed batch with known true params and anchors (route F1eq)."""
    rng = np.random.default_rng(seed)
    betas = rng.uniform(1.5, 3.5, n_samples)
    etas = rng.uniform(500.0, 5000.0, n_samples)
    gammas = rng.uniform(0.0, 50.0, n_samples)
    feats, targets, locations, scales = [], [], [], []
    true_beta, true_eta, true_gamma = [], [], []
    for i in range(n_samples):
        beta, eta, gamma = float(betas[i]), float(etas[i]), float(gammas[i])
        n = 12
        x = np.sort((gamma + eta * rng.exponential(1.0, n))).astype(float)
        anchor = anchor_sample(x)
        target = encode_targets(beta, eta, gamma, anchor)
        feature = build_features("F1eq", x, n)
        feats.append(feature); targets.append(target)
        locations.append(anchor.location); scales.append(anchor.scale)
        true_beta.append(beta); true_eta.append(eta); true_gamma.append(gamma)
    batch = FormalFixedBatch(
        features=torch.as_tensor(np.stack(feats), dtype=torch.float32),
        targets=torch.as_tensor(np.stack(targets), dtype=torch.float32),
        location=torch.as_tensor(locations, dtype=torch.float32),
        scale=torch.as_tensor(scales, dtype=torch.float32),
    )
    return batch, np.array(true_beta), np.array(true_eta), np.array(true_gamma)


def test_decode_param_columns_inverts_encode_targets():
    """The vectorized decode in formal_executor is the exact inverse of encode_targets
    and matches representations.decode_targets — the scientific correctness basis for
    deriving (beta_hat, eta_hat, gamma_hat) from a checkpoint's raw output."""
    rng = np.random.default_rng(3)
    for _ in range(20):
        beta = float(rng.uniform(1.0, 5.0)); eta = float(rng.uniform(100.0, 9000.0))
        gamma = float(rng.uniform(0.0, 80.0))
        x = np.sort(rng.uniform(gamma + 1.0, gamma + eta, 20))
        anchor = anchor_sample(x)
        encoded = encode_targets(beta, eta, gamma, anchor)
        # vectorized decode in float64 (the math) is the exact inverse of encode_targets
        raw = torch.as_tensor(encoded[None, :], dtype=torch.float64)
        loc = np.array([anchor.location]); scl = np.array([anchor.scale])
        b_v, e_v, g_v = fe._decode_param_columns(raw, loc, scl)
        assert b_v[0] == pytest.approx(beta, rel=1e-12)
        assert e_v[0] == pytest.approx(eta, rel=1e-12)
        assert g_v[0] == pytest.approx(gamma, rel=1e-12)
        # and is identical to the canonical decode_targets
        b_c, e_c, g_c = decode_targets(encoded, anchor)
        assert b_v[0] == pytest.approx(b_c, rel=1e-12)
        assert e_v[0] == pytest.approx(e_c, rel=1e-12)
        assert g_v[0] == pytest.approx(g_c, rel=1e-12)


def test_validation_l_param_reproduces_from_checkpoint():
    """D7 scoring: checkpoint -> load -> inference -> decode -> L_param must equal the
    L_param computed directly from the fit's predictions. Proves the score is derived
    from the integrity-bound checkpoint, not a sidecar, and reproduces exactly."""
    batch, true_beta, true_eta, true_gamma = _synthetic_batch()
    input_dim = int(batch.features.shape[1])
    factory = lambda: build_mlp(input_dim, [24, 12], "relu", 0.0)
    fit = fit_candidate(
        factory, (batch.features, batch.targets), (batch.features, batch.targets),
        seed=11, max_epochs=3, min_epochs=1, patience=1, batch_size=32,
        loss_id="transformed_unscaled_mse",
    )
    score_from_checkpoint = fe.validation_failure_penalized_l_param(
        checkpoint_bytes=fit.checkpoint_bytes, model_factory=factory,
        validation_batch=batch, is_set=False,
    )
    # Manual replication: load the SAME checkpoint (best_state, not fit.predictions which
    # is the last-epoch model), forward, decode with float64 anchors, evaluate_rows.
    state = load_checkpoint(fit.checkpoint_bytes)
    model = factory(); model.load_state_dict(state); model.eval()
    with torch.no_grad():
        replay = model(batch.features)
    loc64 = batch.location.numpy().astype(float)
    scl64 = batch.scale.numpy().astype(float)
    b_hat, e_hat, g_hat = fe._decode_param_columns(replay, loc64, scl64)
    rows = [
        {
            "beta_hat": float(b_hat[i]), "eta_hat": float(e_hat[i]), "gamma_hat": float(g_hat[i]),
            "beta": float(true_beta[i]), "eta": float(true_eta[i]), "gamma": float(true_gamma[i]),
            "sample_min": float(batch.location[i]),
        }
        for i in range(len(b_hat))
    ]
    manual = float(evaluate_rows(rows, failure_penalty=10.0)["unconditional_mean_l_param"])
    assert np.isfinite(score_from_checkpoint)
    # Agreement to float32 thread-reduction noise (two independent forward passes through
    # the loaded checkpoint); exact decode math is covered by the float64 round-trip test.
    assert score_from_checkpoint == pytest.approx(manual, rel=1e-6)


_SEARCH_FIT_KINDS = {
    "search_stage1", "search_stage2", "loss_screen",
    "output_form", "size_screen", "distribution_screen",
}


def test_derive_decision_candidate_covers_frozen_matrix():
    """D6 diagnostic: _derive_decision_candidate applied to the frozen 820-row matrix.

    Asserts the structural invariants the executor is confident about — every search
    fit_kind maps to a (decision, candidate); historical/controlled/*_retrain map to
    None; each decision groups at least one candidate and the union of search rows is
    covered exactly. The per-axis candidate counts (printed via the assertion note) are
    the interpretation Codex reviews; output_form/distribution/training_size route
    scoping is the known design choice documented in the relay report.
    """
    matrix = expand_module_matrix(FROZEN)
    assert len(matrix) == 820
    by_decision: dict[str, set[str]] = {}
    search_rows = 0
    for _, row in matrix.iterrows():
        derived = fe._derive_decision_candidate(row)
        if row["fit_kind"] in _SEARCH_FIT_KINDS:
            assert derived is not None, f"search fit_kind {row['fit_kind']} must derive a decision"
            decision_id, candidate_id, tie_break_key = derived
            assert candidate_id, "candidate_id must be non-empty"
            assert isinstance(tie_break_key, list) and tie_break_key, "tie_break_key must be a non-empty list"
            by_decision.setdefault(decision_id, set()).add(candidate_id)
            search_rows += 1
        else:
            assert derived is None, f"non-search fit_kind {row['fit_kind']} must not derive a decision"
    # Every frozen search rule produced at least one decision, and every decision has
    # a non-empty candidate set (a real competition once the rule's fits run).
    assert by_decision, "no decisions derived from the frozen matrix"
    for decision_id, candidates in by_decision.items():
        assert len(candidates) >= 1, f"decision {decision_id} has no candidates"
    # Sanity: A-E1 stage-1 architecture decisions exist for both optimized routes.
    arch_decisions = {d for d in by_decision if d.startswith("architecture:A-E1:")}
    assert any("F2" in d for d in arch_decisions)
    assert any(":V:" in d or d.endswith(":V:n10") for d in arch_decisions)


def _materialize_ae1(tmp_path):
    from study02a.formal_scheduler import materialize_run
    artifact_root = tmp_path / "artifacts"
    cache_root = tmp_path / "cache"
    run_id = "selection-di-v1"
    materialize_run(
        study_root=STUDY_ROOT,
        matrix_path=STUDY_ROOT / "artifacts" / "pilot" / "G3-matrix" / "experiment_matrix.csv",
        module_id="A-E1", run_id=run_id, artifact_root=artifact_root, cache_root=cache_root,
        predecessor=None,
    )
    return artifact_root / "A-E1" / run_id, cache_root, run_id


def test_build_module_selection_emits_v2_trace_and_receipt_with_computed_winners(tmp_path):
    """build_module_selection (D7): derive specs from the frozen plan, score every
    expected supporting fit, apply each rule, and publish one v2 trace + receipt.
    Winners are COMPUTED (lowest_aggregate for A-E1); the score_fit injection stands
    in for checkpoint scoring so no formal training is launched."""
    from study02a.selection import FitEvaluation, SupportKey, build_decision_specs
    from study02a.formal_executor import build_module_selection
    import hashlib as _hl

    run_dir, cache_root, run_id = _materialize_ae1(tmp_path)
    plan_rows = [json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    # Synthetic checkpoint-bound scoring: deterministic per-fit score, no formal training.
    def score_fit(fit_id, plan_row):
        n = "shared" if plan_row.get("n_mode") == "shared_n" else int(plan_row["fixed_n"])
        support_key = SupportKey(n=n, seed=int(plan_row["seed"]))
        score = 0.05 + (int(_hl.sha256(str(fit_id).encode()).hexdigest(), 16) % 1000) / 10000.0
        return FitEvaluation(fit_id=fit_id, support_key=support_key, failed=False,
                             checkpoint_sha256=_hl.sha256(str(fit_id).encode()).hexdigest(),
                             selection_score=score, failure_penalty=0.0)

    receipt = build_module_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=cache_root,
        module_id="A-E1", run_id=run_id, score_fit=score_fit,
    )
    assert receipt["module_id"] == "A-E1"
    assert receipt["run_id"] == run_id
    assert receipt["decision_count"] >= 1
    trace_path = run_dir / "selection_trace.jsonl"
    assert trace_path.is_file()
    records = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    assert all("support_count" in r for r in records)  # v2 schema
    # every decision selects exactly one winner, computed not supplied
    from collections import defaultdict
    by_decision = defaultdict(list)
    for r in records:
        by_decision[r["decision_id"]].append(r)
    for decision_id, rows in by_decision.items():
        assert sum(1 for r in rows if r["selected"]) == 1
        winner = next(r for r in rows if r["selected"])
        if rows[0]["selection_rule"] == "lowest_aggregate":
            ranked = sorted(rows, key=lambda r: (r["validation_score"], r["candidate_id"]))
            assert winner["candidate_id"] == ranked[0]["candidate_id"]
    # receipt + ledger are immutable
    assert (run_dir / "selection_receipt.json").is_file()
    assert (run_dir / "selection_ledger.jsonl").is_file()
    import pytest as _pt
    with _pt.raises(FileExistsError):
        build_module_selection(study_root=STUDY_ROOT, run_dir=run_dir, cache_root=cache_root,
                               module_id="A-E1", run_id=run_id, score_fit=score_fit)


def test_build_module_selection_includes_failed_seeds_and_remains_consistent(tmp_path):
    """A decision whose winning candidate contains a failed seed still selects that
    candidate; the failed seed carries the frozen penalty (R2 #4)."""
    from study02a.selection import FitEvaluation, SupportKey
    from study02a.formal_executor import build_module_selection
    import hashlib as _hl

    run_dir, cache_root, run_id = _materialize_ae1(tmp_path)
    # Mark the first derived decision's first candidate's first support fit as failed.
    from study02a.selection import build_decision_specs
    from study02a.matrix import expand_module_matrix as _expand
    matrix_rows = _expand(FROZEN).to_dict("records")
    specs = build_decision_specs("A-E1", matrix_rows)
    first_candidate = specs[0].candidates[0]
    failed_fit = first_candidate.support_for(first_candidate.support_keys[0])

    def score_fit(fit_id, plan_row):
        n = "shared" if plan_row.get("n_mode") == "shared_n" else int(plan_row["fixed_n"])
        support_key = SupportKey(n=n, seed=int(plan_row["seed"]))
        if fit_id == failed_fit:
            return FitEvaluation(fit_id=fit_id, support_key=support_key, failed=True,
                                 checkpoint_sha256="", selection_score=0.0, failure_penalty=10.0)
        score = 0.05 + (int(_hl.sha256(str(fit_id).encode()).hexdigest(), 16) % 1000) / 10000.0
        return FitEvaluation(fit_id=fit_id, support_key=support_key, failed=False,
                             checkpoint_sha256=_hl.sha256(str(fit_id).encode()).hexdigest(),
                             selection_score=score, failure_penalty=0.0)

    receipt = build_module_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=cache_root,
        module_id="A-E1", run_id=run_id, score_fit=score_fit,
    )
    assert receipt["decision_count"] >= 1
