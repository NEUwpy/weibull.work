"""Fail-closed tests for the corrected P2 pre-rerun implementation."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

CODE_DIR = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE_DIR))

_RELATED_PREFIXES = (
    "run_E4_formal_validation",
    "config",
    "utils",
    "studies",
    "methods",
)
_PREIMPORT_MODULES = {
    name: module
    for name, module in sys.modules.items()
    if name in _RELATED_PREFIXES
    or name.startswith(tuple(prefix + "." for prefix in _RELATED_PREFIXES))
}
try:
    import p2_config as cfg
    import run_E4_formal_validation as e4
    import run_p2_evaluate as evaluator
    import run_p2_generate as generator
    import run_p2_vector_mlp as vector
finally:
    for name in list(sys.modules):
        if name in _RELATED_PREFIXES or name.startswith(
            tuple(prefix + "." for prefix in _RELATED_PREFIXES)
        ):
            sys.modules.pop(name, None)
    sys.modules.update(_PREIMPORT_MODULES)


def _valid_rows(combo=("P2-NI", 1.5, 0.1, 15), repeats=2):
    track, beta, ge, n = combo
    combo_id = generator._combo_id(*combo)
    rows = []
    for repeat_id in range(repeats):
        sample = generator.reconstruct_sample(beta, ge, n, repeat_id)
        sample_hash = generator._sample_sha256(sample)
        for delta in cfg.DELTA_GRID:
            rows.append(
                {
                    "track": track,
                    "combo_id": combo_id,
                    "beta": beta,
                    "eta": cfg.ETA,
                    "gamma": ge * cfg.ETA,
                    "gamma_over_eta": ge,
                    "n": n,
                    "repeat_id": repeat_id,
                    "sample_sha256": sample_hash,
                    "delta": delta,
                    "beta_hat": beta,
                    "eta_hat": cfg.ETA,
                    "gamma_hat": ge * cfg.ETA,
                    "r_squared": 1.0,
                    "converged": True,
                    "time_ms": 0.0,
                    "status": "success",
                    "failure_reason": "",
                }
            )
    return rows


def _write_rows(path: Path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=generator.MDM_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _fake_generation_package(root: Path) -> None:
    (root / "chunks").mkdir(parents=True)
    files = {
        "run_context.json": {
            "generation_commit": "abc123",
            "approved_parent_commit": cfg.P2_APPROVED_PARENT_COMMIT,
            "input_hashes": {"fixture": "hash"},
        },
        "progress.json": {"completed": [{"combo_id": "fixture"}]},
        "manifest.json": {
            "generation_commit": "abc123",
            "combo_counts": {"total": 1},
            "chunks": [{"path": "fixture.csv"}],
        },
    }
    for name, payload in files.items():
        (root / name).write_text(json.dumps(payload), encoding="utf-8")
    (root / "chunks" / "fixture.csv").write_text("x\n1\n", encoding="utf-8")
    relative_files = [
        "run_context.json",
        "progress.json",
        "manifest.json",
        "chunks/fixture.csv",
    ]
    lines = [
        f"{hashlib.sha256((root / name).read_bytes()).hexdigest()}  {name}"
        for name in relative_files
    ]
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestJ1:
    def test_formula_has_no_divide_by_three(self):
        loss = cfg.compute_j1_squared(2.5, 2.0, 1.5, 1.0, 0.8, 0.5)
        expected = 0.25**2 + 0.5**2 + 0.3**2
        assert loss == pytest.approx(expected)
        assert cfg.compute_j1([loss]) == pytest.approx(math.sqrt(expected))

    def test_pooled_is_not_combo_j1_mean(self):
        # Equal sample counts are not required for this distinction.
        pooled = cfg.compute_j1([0.0, 0.0, 4.0])
        combo_mean = np.mean([cfg.compute_j1([0.0, 0.0]), cfg.compute_j1([4.0])])
        assert pooled != pytest.approx(combo_mean)


class TestStableSamples:
    def test_cross_process_sample_hash(self):
        code = (
            "import sys,numpy as np,hashlib;"
            f"sys.path.insert(0,{str(CODE_DIR)!r});"
            "from run_p2_generate import reconstruct_sample,_sample_sha256;"
            "print(_sample_sha256(reconstruct_sample(2.0,0.5,15,7)))"
        )
        first = subprocess.check_output([sys.executable, "-c", code], text=True).strip()
        second = subprocess.check_output([sys.executable, "-c", code], text=True).strip()
        assert first == second
        assert len(first) == 64

    def test_feature_sample_matches_generation_sample(self):
        sample = generator.reconstruct_sample(2.0, 0.5, 15, 0)
        generated_hash = generator._sample_sha256(sample)
        risk = pd.DataFrame(_valid_rows(("P2-NI", 2.0, 0.5, 15), repeats=1))
        features, _ = vector.prepare_p2_features(risk)
        assert features.iloc[0]["sample_sha256"] == generated_hash
        expected = e4.compute_sample_features(sample)
        for column in e4.SAMPLE_FEATURE_COLS:
            assert features.iloc[0][column] == pytest.approx(expected[column])


class TestChunkValidation:
    def test_valid_chunk_and_sha(self, tmp_path):
        path = tmp_path / "chunk.csv"
        _write_rows(path, _valid_rows())
        receipt = generator.validate_chunk(
            path, ("P2-NI", 1.5, 0.1, 15), repeats=2
        )
        assert receipt["rows"] == 52
        assert receipt["samples"] == 2
        assert receipt["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()

    @pytest.mark.parametrize(
        "mutation",
        ["missing_row", "wrong_hash", "wrong_combo", "duplicate_key", "failed_no_reason"],
    )
    def test_corrupt_chunk_fails_closed(self, tmp_path, mutation):
        rows = _valid_rows()
        if mutation == "missing_row":
            rows.pop()
        elif mutation == "wrong_hash":
            rows[0]["sample_sha256"] = "0" * 64
        elif mutation == "wrong_combo":
            rows[0]["beta"] = 9.0
        elif mutation == "duplicate_key":
            rows[-1] = dict(rows[0])
        elif mutation == "failed_no_reason":
            rows[0]["status"] = "failed"
        path = tmp_path / "bad.csv"
        _write_rows(path, rows)
        with pytest.raises(generator.P2GenerationError):
            generator.validate_chunk(
                path, ("P2-NI", 1.5, 0.1, 15), repeats=2
            )

    def test_sha_mismatch_fails_closed(self, tmp_path):
        path = tmp_path / "chunk.csv"
        _write_rows(path, _valid_rows())
        with pytest.raises(generator.P2GenerationError, match="SHA256"):
            generator.validate_chunk(
                path,
                ("P2-NI", 1.5, 0.1, 15),
                repeats=2,
                expected_sha256="0" * 64,
            )


class TestOutputProtection:
    def test_formal_generation_is_sealed(self):
        assert cfg.P2_FORMAL_AUTHORIZED is False
        with pytest.raises(generator.P2GenerationError, match="sealed"):
            generator.run_generation(combos=[])

    def test_nonempty_output_without_context_is_rejected(self, tmp_path):
        (tmp_path / "foreign.txt").write_text("x", encoding="utf-8")
        with pytest.raises(generator.P2GenerationError, match="non-empty"):
            generator.run_generation(
                output_dir=tmp_path,
                combos=[],
                repeats=1,
                smoke=True,
            )

    @pytest.mark.parametrize(
        "unsafe",
        [
            generator.FORMAL_DIR,
            generator.FORMAL_DIR / "nested",
            generator.FORMAL_DIR.parent,
            generator.PROJECT_ROOT / "p2-smoke",
        ],
    )
    def test_smoke_cannot_target_formal_or_repository_paths(self, unsafe):
        with pytest.raises(generator.P2GenerationError, match="outside"):
            generator.run_smoke(unsafe)

    def test_internal_smoke_flag_cannot_bypass_formal_directory(self):
        with pytest.raises(generator.P2GenerationError, match="outside"):
            generator.run_generation(
                output_dir=generator.FORMAL_DIR,
                combos=[],
                repeats=1,
                smoke=True,
            )


class TestFailureContract:
    def test_failed_sample_receives_penalty_and_reason(self):
        risk = pd.DataFrame(_valid_rows(repeats=1))
        mask = np.isclose(risk["delta"], cfg.DEFAULT_DELTA)
        risk.loc[mask, "status"] = "failed"
        risk.loc[mask, "failure_reason"] = "synthetic_failure"
        risk.loc[mask, ["beta_hat", "eta_hat", "gamma_hat"]] = np.nan
        risk = e4.compute_loss(risk)
        rows = evaluator.evaluate_fixed_delta(
            risk, cfg.DEFAULT_DELTA, "Default", failure_penalty=7.0
        )
        assert rows.iloc[0]["failed"]
        assert rows.iloc[0]["true_loss"] == 7.0
        assert rows.iloc[0]["failure_reason"] == "synthetic_failure"

    def test_all_methods_share_each_model_penalty(self):
        risk = pd.DataFrame(_valid_rows(repeats=1))
        for delta in (cfg.DEFAULT_DELTA, cfg.L1_DELTA):
            mask = np.isclose(risk["delta"], delta)
            risk.loc[mask, "status"] = "failed"
            risk.loc[mask, "failure_reason"] = "synthetic_failure"
            risk.loc[mask, ["beta_hat", "eta_hat", "gamma_hat"]] = np.nan
        risk = e4.compute_loss(risk)
        receipts = [
            {"fold": "combo_fold_1", "seed": 42, "failure_penalty": 2.5},
            {"fold": "combo_fold_2", "seed": 2026, "failure_penalty": 7.0},
        ]
        rows, summary = evaluator.evaluate_baselines(risk, receipts)
        assert len(rows) == 4
        for (fold, seed), group in rows.groupby(["fold", "seed"]):
            expected = next(
                item["failure_penalty"]
                for item in receipts
                if item["fold"] == fold and item["seed"] == seed
            )
            assert set(group["true_loss"]) == {expected}
            assert set(group["failure_penalty"]) == {expected}
            assert group["failed"].all()
        assert len(summary["rows"]) == 4

    def test_shared_failure_resolver_matches_vector_contract(self):
        resolved = evaluator.apply_failure_contract(
            np.nan, "failed", "synthetic_failure", 3.25
        )
        assert resolved["failed"] is True
        assert resolved["failure_reason"] == "synthetic_failure"
        assert np.isnan(resolved["true_loss_complete_case"])
        assert resolved["true_loss"] == 3.25
        source = (CODE_DIR / "run_p2_vector_mlp.py").read_text(encoding="utf-8")
        assert "apply_failure_contract(" in source
        assert 'row["true_loss"] = penalty' not in source


class TestEvaluationSeal:
    def test_evaluation_preflight_binds_context_hashes_and_exact_files(
        self, tmp_path, monkeypatch
    ):
        _fake_generation_package(tmp_path)
        monkeypatch.setattr(
            vector,
            "_git",
            lambda *args: "" if args == ("status", "--porcelain") else "abc123",
        )
        monkeypatch.setattr(
            vector, "_input_hashes", lambda: {"fixture": "hash"}
        )
        receipt = vector.validate_evaluation_preflight(tmp_path, formal=False)
        assert receipt["context"]["generation_commit"] == "abc123"
        assert len(receipt["sealed"]) == 4

    @pytest.mark.parametrize("mutation", ["context", "hash", "extra"])
    def test_evaluation_preflight_rejects_drift(
        self, tmp_path, monkeypatch, mutation
    ):
        _fake_generation_package(tmp_path)
        monkeypatch.setattr(
            vector,
            "_git",
            lambda *args: "" if args == ("status", "--porcelain") else "abc123",
        )
        monkeypatch.setattr(
            vector, "_input_hashes", lambda: {"fixture": "hash"}
        )
        if mutation == "context":
            context = json.loads(
                (tmp_path / "run_context.json").read_text(encoding="utf-8")
            )
            context["generation_commit"] = "drift"
            (tmp_path / "run_context.json").write_text(
                json.dumps(context), encoding="utf-8"
            )
        elif mutation == "hash":
            (tmp_path / "chunks" / "fixture.csv").write_text(
                "corrupt", encoding="utf-8"
            )
        else:
            (tmp_path / "foreign.bin").write_bytes(b"x")
        with pytest.raises(vector.P2VectorError):
            vector.validate_evaluation_preflight(tmp_path, formal=False)

    def test_complete_outputs_are_atomic_and_fully_sealed(
        self, tmp_path, monkeypatch
    ):
        generation = tmp_path / "generation"
        generation.mkdir()
        (generation / "manifest.json").write_text("{}", encoding="utf-8")
        digest = hashlib.sha256(
            (generation / "manifest.json").read_bytes()
        ).hexdigest()
        (generation / "SHA256SUMS").write_text(
            f"{digest}  manifest.json\n", encoding="utf-8"
        )
        monkeypatch.setattr(vector, "_git", lambda *args: "abc123")
        frame = pd.DataFrame([{"x": 1}])
        vector.write_complete_evaluation(
            tmp_path,
            frame,
            frame,
            frame,
            {"ok": True},
            generation_root=generation,
        )
        sealed = vector._read_and_verify_sha256sums(tmp_path)
        assert sealed == {
            "generation/manifest.json",
            "generation/SHA256SUMS",
            "p2_vector_per_sample.csv",
            "p2_vector_model_summary.csv",
            "p2_baseline_per_sample.csv",
            "p2_evaluation_summary.json",
        }
        assert not list(tmp_path.rglob("*.tmp"))

    def test_unknown_output_blocks_final_seal(self, tmp_path, monkeypatch):
        generation = tmp_path / "generation"
        generation.mkdir()
        (generation / "manifest.json").write_text("{}", encoding="utf-8")
        (tmp_path / "foreign.txt").write_text("x", encoding="utf-8")
        monkeypatch.setattr(vector, "_git", lambda *args: "abc123")
        frame = pd.DataFrame([{"x": 1}])
        with pytest.raises(vector.P2VectorError, match="output set mismatch"):
            vector.write_complete_evaluation(
                tmp_path,
                frame,
                frame,
                frame,
                {"ok": True},
                generation_root=generation,
            )


class TestInvalidV1Tombstone:
    def test_v1_manifests_are_machine_readable_invalid(self):
        invalid_dir = (
            CODE_DIR.parent
            / "artifacts"
            / "formal"
            / cfg.INVALID_V1_OUTPUT_DIR_NAME
        )
        for name in ("manifest.json", "evaluation_manifest.json"):
            payload = json.loads((invalid_dir / name).read_text(encoding="utf-8"))
            assert payload["status"] == "INVALID_NONDETERMINISTIC_SEED"
            assert payload["valid_evidence"] is False
            assert payload["replacement_run_id"] == cfg.P2_RUN_ID


class TestProductionContract:
    def test_adapter_uses_e4_single_source(self):
        contract = vector.verify_production_contract()
        assert contract["feature_columns"] == e4.SAMPLE_FEATURE_COLS
        assert contract["hidden_layers"] == e4.MLP_HIDDEN_LAYERS
        assert contract["validation_fraction"] == e4.MLP_VALIDATION_FRACTION
        assert contract["n_iter_no_change"] == e4.MLP_N_ITER_NO_CHANGE
        assert contract["seeds"] == e4.STABILITY_SEEDS

    def test_adapter_has_no_local_mlp_implementation(self):
        source = (CODE_DIR / "run_p2_vector_mlp.py").read_text(encoding="utf-8")
        assert "MLPRegressor(" not in source
        assert "repeat_id % " not in source
        assert "seed=42001" not in source
        assert "e4._train_mlp" in source
        assert "e4._evaluate_single_model_indexed" in source

    def test_real_production_train_helper(self):
        rng = np.random.default_rng(1)
        x = rng.normal(size=(40, 13)).astype(np.float32)
        y = np.abs(rng.normal(size=(40, 26))).astype(np.float32)
        model, scaler = e4._train_mlp(x, y, seed=42)
        prediction = scaler.inverse_transform(model.predict(x[:2]))
        assert prediction.shape == (2, 26)

    def test_indexed_evaluator_matches_historical_helper(self):
        class Model:
            def predict(self, x):
                values = np.tile(np.arange(26, dtype=float), (len(x), 1))
                values[1] = values[1, ::-1]
                return values

        class IdentityScaler:
            @staticmethod
            def inverse_transform(values):
                return values

        feature_rows = []
        loss_rows = []
        for repeat_id in [0, 1]:
            sample = generator.reconstruct_sample(1.5, 0.1, 15, repeat_id)
            features = e4.compute_sample_features(sample)
            features.update(
                {
                    "beta": 1.5,
                    "eta": 1.0,
                    "gamma": 0.1,
                    "gamma_over_eta": 0.1,
                    "n": 15,
                    "repeat_id": repeat_id,
                }
            )
            feature_rows.append(features)
            for delta in e4.DELTA_GRID:
                loss_rows.append(
                    {
                        "beta": 1.5,
                        "gamma_over_eta": 0.1,
                        "n": 15,
                        "repeat_id": repeat_id,
                        "delta": delta,
                        "loss": repeat_id + delta,
                    }
                )
        feature_frame = pd.DataFrame(feature_rows)
        loss_frame = pd.DataFrame(loss_rows)
        means = {column: 0.0 for column in e4.FEATURE_COLS_ZSCORE}
        stds = {column: 1.0 for column in e4.FEATURE_COLS_ZSCORE}
        args = (
            Model(),
            IdentityScaler(),
            feature_frame,
            loss_frame,
            means,
            stds,
            9.0,
            "combo_fold_1",
            42,
        )
        historical = e4._evaluate_single_model(*args)
        indexed = e4._evaluate_single_model_indexed(*args)
        assert indexed == historical


class TestModelFirst:
    def test_model_summary_keeps_models_separate(self):
        rows = pd.DataFrame(
            [
                {
                    "track": "P2-NI",
                    "fold": "f1",
                    "seed": 42,
                    "true_loss": 0.0,
                    "failed": False,
                    "selected_delta": 0.1,
                    "regret": 0.0,
                },
                {
                    "track": "P2-NI",
                    "fold": "f2",
                    "seed": 42,
                    "true_loss": 4.0,
                    "failed": False,
                    "selected_delta": 0.1,
                    "regret": 1.0,
                },
            ]
        )
        summary = vector._model_summaries(rows)
        assert len(summary) == 2
        assert sorted(summary["pooled_J1"]) == [0.0, 2.0]
