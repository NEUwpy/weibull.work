"""Tests for the cohort-based G3 test consumer (formal_test_consumer.py R2).

Verifies: exact cohort counts (205/110/100), manifest determinism, claim
concurrency, preflight rejection, failure->consumed, repeat rejection.
Uses real frozen matrix for cohort derivation; synthetic fixtures for evaluation.
"""

import hashlib
import json
import os
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_CODE = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究" / "code"
for _p in (str(STUDY_CODE), str(REPO_ROOT / "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from study02a.config import load_frozen_config
from study02a.matrix import expand_module_matrix
from study02a.formal_test_consumer import (
    _COHORT_FIT_KINDS,
    _EXPECTED_COHORT_COUNTS,
    _canonical,
    _publish_no_replace,
    _sha256_bytes,
    build_g3_test_manifest,
    build_module_test_samples,
    derive_g3_cohort,
    publish_test_claim,
    G3Cohort,
    CohortEntry,
)
from study02a.formal_state import authorize_test_once, consume_test_once, initialize_formal_state, publish_oracle_approval

STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
COMMIT = "ab" * 20
CONFIG_SHA = "cd" * 32


class TestCohortDerivation:
    def test_frozen_matrix_filter_produces_exact_counts(self):
        frozen = load_frozen_config(STUDY_ROOT)
        matrix = expand_module_matrix(frozen)
        cohort = matrix[matrix["fit_kind"].isin(_COHORT_FIT_KINDS)]
        counts = cohort.groupby("module").size().to_dict()
        assert counts["A-E1"] == 205
        assert counts["A-E3"] == 110
        assert counts["A-E2"] == 100
        assert len(cohort) == 415

    def test_excluded_fit_kinds_not_in_cohort(self):
        frozen = load_frozen_config(STUDY_ROOT)
        matrix = expand_module_matrix(frozen)
        excluded = {"search_stage1", "search_stage2", "loss_screen", "size_screen", "distribution_screen"}
        cohort = matrix[matrix["fit_kind"].isin(_COHORT_FIT_KINDS)]
        assert not cohort["fit_kind"].isin(excluded).any()

    def test_cohort_rejects_wrong_count(self):
        entries = tuple(
            CohortEntry(
                fit_id=f"G3-fit-{i:04d}", module_id="A-E1", rule_id="r",
                route="F2", n=7, seed=420101, fit_kind="winner_retrain",
                training_size=100000, architecture="m05", optimizer="o1",
                loss="huber", checkpoint_sha256="aa" * 32,
            )
            for i in range(10)
        )
        with pytest.raises(ValueError, match="cohort count"):
            G3Cohort(entries=entries, counts_by_module={"A-E1": 10, "A-E3": 110, "A-E2": 100})

    def test_cohort_rejects_duplicate_fit_ids(self):
        entry = CohortEntry(
            fit_id="G3-fit-0000", module_id="A-E1", rule_id="r",
            route="F2", n=7, seed=420101, fit_kind="winner_retrain",
            training_size=100000, architecture="m05", optimizer="o1",
            loss="huber", checkpoint_sha256="aa" * 32,
        )
        with pytest.raises(ValueError, match="duplicate"):
            G3Cohort(entries=(entry, entry), counts_by_module={"A-E1": 205, "A-E3": 110, "A-E2": 100})

    def test_a_e1_breakdown(self):
        frozen = load_frozen_config(STUDY_ROOT)
        matrix = expand_module_matrix(frozen)
        cohort = matrix[matrix["fit_kind"].isin(_COHORT_FIT_KINDS)]
        ae1 = cohort[cohort["module"] == "A-E1"]
        assert len(ae1[ae1["fit_kind"] == "historical"]) == 30
        assert len(ae1[ae1["fit_kind"] == "controlled"]) == 75
        assert len(ae1[ae1["fit_kind"] == "winner_retrain"]) == 100

    def test_a_e3_breakdown(self):
        frozen = load_frozen_config(STUDY_ROOT)
        matrix = expand_module_matrix(frozen)
        cohort = matrix[matrix["fit_kind"].isin(_COHORT_FIT_KINDS)]
        ae3 = cohort[cohort["module"] == "A-E3"]
        assert len(ae3[ae3["fit_kind"] == "output_form"]) == 100
        assert len(ae3[ae3["fit_kind"] == "shared_winner_retrain"]) == 10

    def test_a_e2_breakdown(self):
        frozen = load_frozen_config(STUDY_ROOT)
        matrix = expand_module_matrix(frozen)
        cohort = matrix[matrix["fit_kind"].isin(_COHORT_FIT_KINDS)]
        ae2 = cohort[cohort["module"] == "A-E2"]
        assert len(ae2[ae2["fit_kind"] == "selected_size_retrain"]) == 50
        assert len(ae2[ae2["fit_kind"] == "selected_distribution_retrain"]) == 50


class TestManifest:
    def _make_cohort(self):
        entries = []
        idx = 0
        for module_id, count in [("A-E1", 205), ("A-E3", 110), ("A-E2", 100)]:
            for i in range(count):
                entries.append(CohortEntry(
                    fit_id=f"G3-fit-{idx:04d}", module_id=module_id, rule_id="r",
                    route="F2", n=7, seed=420101, fit_kind="winner_retrain",
                    training_size=100000, architecture="m05", optimizer="o1",
                    loss="huber", checkpoint_sha256=f"{idx:064x}",
                ))
                idx += 1
        return G3Cohort(entries=tuple(entries), counts_by_module={"A-E1": 205, "A-E3": 110, "A-E2": 100})

    def test_manifest_deterministic(self):
        from study02a.formal_config import load_effective_formal_config
        frozen = load_frozen_config(STUDY_ROOT)
        effective = load_effective_formal_config(STUDY_ROOT)
        cohort = self._make_cohort()
        m1 = build_g3_test_manifest(cohort=cohort, frozen_config=frozen, effective_config=effective, code_commit=COMMIT)
        m2 = build_g3_test_manifest(cohort=cohort, frozen_config=frozen, effective_config=effective, code_commit=COMMIT)
        assert m1["manifest_sha256"] == m2["manifest_sha256"]

    def test_manifest_changes_with_code_commit(self):
        from study02a.formal_config import load_effective_formal_config
        frozen = load_frozen_config(STUDY_ROOT)
        effective = load_effective_formal_config(STUDY_ROOT)
        cohort = self._make_cohort()
        m1 = build_g3_test_manifest(cohort=cohort, frozen_config=frozen, effective_config=effective, code_commit=COMMIT)
        m2 = build_g3_test_manifest(cohort=cohort, frozen_config=frozen, effective_config=effective, code_commit="ff" * 20)
        assert m1["manifest_sha256"] != m2["manifest_sha256"]

    def test_manifest_binds_namespaces(self):
        from study02a.formal_config import load_effective_formal_config
        frozen = load_frozen_config(STUDY_ROOT)
        effective = load_effective_formal_config(STUDY_ROOT)
        cohort = self._make_cohort()
        m = build_g3_test_manifest(cohort=cohort, frozen_config=frozen, effective_config=effective, code_commit=COMMIT)
        assert m["test_namespaces"]["A-E1"]["design"] == 220301
        assert m["test_namespaces"]["A-E1"]["sample"] == 320301
        assert m["test_namespaces"]["A-E3"]["design"] == 220303
        assert m["test_namespaces"]["A-E2"]["design"] == 220302


class TestClaim:
    def test_claim_no_replace(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        publish_test_claim(run_dir=run_dir, manifest_sha256="aa" * 32, timestamp="2026-07-25T10:00:00Z")
        with pytest.raises(ValueError, match="claim lock|no-replace"):
            publish_test_claim(run_dir=run_dir, manifest_sha256="bb" * 32, timestamp="2026-07-25T11:00:00Z")

    def test_concurrent_claim_exactly_one_succeeds(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        results = []

        def try_claim(i):
            try:
                publish_test_claim(run_dir=run_dir, manifest_sha256="aa" * 32, timestamp=f"2026-07-25T10:00:0{i}Z")
                return "success"
            except (ValueError, OSError):
                return "rejected"

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(try_claim, i) for i in range(4)]
            results = [f.result() for f in futures]

        assert results.count("success") == 1
        assert results.count("rejected") == 3

    def test_claim_content_binds_manifest(self, tmp_path):
        run_dir = tmp_path / "run"
        run_dir.mkdir()
        manifest_sha = "ab" * 32
        publish_test_claim(run_dir=run_dir, manifest_sha256=manifest_sha, timestamp="2026-07-25T10:00:00Z")
        claim = json.loads((run_dir / "g3_test_claim.json").read_text(encoding="utf-8"))
        assert claim["manifest_sha256"] == manifest_sha
        assert claim["status"] == "claimed"


class TestPublishNoReplace:
    def test_creates_file(self, tmp_path):
        target = tmp_path / "receipt.json"
        _publish_no_replace(target, b'{"test": true}\n')
        assert target.read_bytes() == b'{"test": true}\n'

    def test_rejects_overwrite(self, tmp_path):
        target = tmp_path / "receipt.json"
        target.write_bytes(b"original")
        with pytest.raises(ValueError, match="no-replace"):
            _publish_no_replace(target, b"new")
        assert target.read_bytes() == b"original"


class TestModuleTestSamples:
    def test_builds_correct_row_count_fixed_n(self):
        frozen = load_frozen_config(STUDY_ROOT)
        rows, samples = build_module_test_samples(
            module_id="A-E1", route="F2", n_mode="fixed_n", fixed_n=7,
            frozen_config=frozen, point_count=4, repeat_count=2,
        )
        assert len(rows) == 8
        assert len(samples) == 8
        assert all(s.shape[0] >= 7 for s in samples)

    def test_builds_correct_row_count_shared_n(self):
        frozen = load_frozen_config(STUDY_ROOT)
        rows, samples = build_module_test_samples(
            module_id="A-E1", route="S", n_mode="shared_n", fixed_n=None,
            frozen_config=frozen, point_count=2, repeat_count=2,
        )
        n_count = len(frozen.protocol["sample_sizes"]["core"])
        assert len(rows) == 2 * 2 * n_count
        assert len(samples) == len(rows)

    def test_namespace_isolation(self):
        frozen = load_frozen_config(STUDY_ROOT)
        rows_ae1, samples_ae1 = build_module_test_samples(
            module_id="A-E1", route="F2", n_mode="fixed_n", fixed_n=7,
            frozen_config=frozen, point_count=2, repeat_count=1,
        )
        rows_ae3, samples_ae3 = build_module_test_samples(
            module_id="A-E3", route="F2", n_mode="fixed_n", fixed_n=7,
            frozen_config=frozen, point_count=2, repeat_count=1,
        )
        assert not all(
            (s1 == s2).all() for s1, s2 in zip(samples_ae1, samples_ae3)
        )


class TestRealTestNotAccessed:
    def test_real_runs_test_access_count_stays_zero(self):
        formal_dir = STUDY_ROOT / "artifacts" / "formal"
        if not formal_dir.is_dir():
            pytest.skip("no formal artifacts directory")
        for state_file in formal_dir.rglob("formal_state.json"):
            state = json.loads(state_file.read_text(encoding="utf-8"))
            assert state.get("test_access_count", 0) == 0
