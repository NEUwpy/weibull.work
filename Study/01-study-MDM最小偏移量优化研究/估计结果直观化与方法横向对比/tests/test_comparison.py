"""
Verification tests for method comparison study.
Run: pytest tests/test_comparison.py -v
"""

import os
import sys
import math
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code"))
run_comp_path = os.path.join(os.path.dirname(__file__), "..", "code", "run_comparison.py")
if os.path.exists(run_comp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("run_comparison", run_comp_path)
    mod = importlib.util.module_from_spec(spec)

ARTIFACTS_DIR = os.path.join(os.path.dirname(__file__), "..", "artifacts")
PER_SAMPLE = os.path.join(ARTIFACTS_DIR, "per_sample_results.csv")
OVERALL = os.path.join(ARTIFACTS_DIR, "overall_summary.csv")
N7 = os.path.join(ARTIFACTS_DIR, "summary_n7.csv")
N10 = os.path.join(ARTIFACTS_DIR, "summary_n10.csv")
N20 = os.path.join(ARTIFACTS_DIR, "summary_n20.csv")
SCALE_CHECK = os.path.join(ARTIFACTS_DIR, "scale_equivariance_check.csv")
MANIFEST = os.path.join(ARTIFACTS_DIR, "manifest.json")

METHODS = ["mle", "wmle", "lse", "lre", "MDM-0.1", "MDM-MLP", "MDM-L6-oracle"]
N_VALUES = [7, 10, 20]
N_REPEATS = 1000


class TestArtifactsExist:
    def test_per_sample_exists(self):
        assert os.path.exists(PER_SAMPLE), f"Missing {PER_SAMPLE}"

    def test_overall_exists(self):
        assert os.path.exists(OVERALL), f"Missing {OVERALL}"

    def test_summary_n7_exists(self):
        assert os.path.exists(N7), f"Missing {N7}"

    def test_summary_n10_exists(self):
        assert os.path.exists(N10), f"Missing {N10}"

    def test_summary_n20_exists(self):
        assert os.path.exists(N20), f"Missing {N20}"

    def test_scale_check_exists(self):
        assert os.path.exists(SCALE_CHECK), f"Missing {SCALE_CHECK}"

    def test_manifest_exists(self):
        assert os.path.exists(MANIFEST), f"Missing {MANIFEST}"


class TestPerSampleResults:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = pd.read_csv(PER_SAMPLE)

    def test_total_rows(self):
        expected = len(METHODS) * len(N_VALUES) * N_REPEATS
        assert len(self.df) == expected, f"Expected {expected} rows, got {len(self.df)}"

    def test_all_methods_present(self):
        for m in METHODS:
            assert m in self.df["method"].values, f"Method {m} not found"

    def test_all_n_present(self):
        for n in N_VALUES:
            assert n in self.df["n"].values, f"n={n} not found"

    def test_repeat_counts(self):
        for method in METHODS:
            for n in N_VALUES:
                count = len(self.df[(self.df["method"] == method) & (self.df["n"] == n)])
                assert count == N_REPEATS, f"{method} n={n}: expected {N_REPEATS}, got {count}"

    def test_unique_repeat_ids(self):
        for method in METHODS:
            for n in N_VALUES:
                subset = self.df[(self.df["method"] == method) & (self.df["n"] == n)]
                assert subset["repeat_id"].nunique() == N_REPEATS

    def test_sample_hash_consistency(self):
        for n in N_VALUES:
            for rid in [0, 42, 999]:
                hashes = set()
                for method in METHODS:
                    subset = self.df[(self.df["method"] == method) & (self.df["n"] == n) & (self.df["repeat_id"] == rid)]
                    if len(subset) > 0:
                        hashes.add(subset.iloc[0]["sample_content_hash"])
                assert len(hashes) == 1, f"Sample hash mismatch at n={n} rid={rid}: {hashes}"


class TestOverallSummary:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = pd.read_csv(OVERALL)

    def test_all_methods_in_summary(self):
        for m in METHODS:
            assert m in self.df["method"].values

    def test_j1_ordering(self):
        j1_map = dict(zip(self.df["method"], self.df["pooled_J1"]))
        assert j1_map["MDM-L6-oracle"] < j1_map["MDM-MLP"]
        assert j1_map["MDM-MLP"] < j1_map["MDM-0.1"]

    def test_no_negative_rmse(self):
        for col in ["beta_RMSE", "eta_RMSE", "gamma_RMSE"]:
            valid = self.df[col].dropna()
            assert (valid >= 0).all(), f"Negative values in {col}"


class TestPerNTable:
    @pytest.mark.parametrize("path,n_val", [(N7, 7), (N10, 10), (N20, 20)])
    def test_rows_per_method(self, path, n_val):
        df = pd.read_csv(path)
        params_per_method = 3
        expected = len(METHODS) * params_per_method
        assert len(df) == expected, f"n={n_val}: expected {expected}, got {len(df)}"

    @pytest.mark.parametrize("path,n_val", [(N7, 7), (N10, 10), (N20, 20)])
    def test_success_count_consistency(self, path, n_val):
        df = pd.read_csv(path)
        for method in METHODS:
            rows = df[df["method"] == method]
            n_success = rows["n_success_total"].unique()
            assert len(n_success) == 1, f"n={n_val} {method}: inconsistent n_success_total"


class TestScaleEquivariance:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = pd.read_csv(SCALE_CHECK)

    def test_both_scales_present(self):
        for method in ["mle", "wmle", "lse", "lre"]:
            subset = self.df[self.df["method"] == method]
            scales = set(subset["scale"])
            assert "norm" in scales, f"{method} missing norm scale"
            assert "display" in scales, f"{method} missing display scale"

    def test_lse_scale_equivariance(self):
        lse = self.df[self.df["method"] == "lse"]
        valid = lse[lse["converged"].astype(bool) & lse["beta_hat"].notna()]
        pivoted = valid.pivot_table(
            index=["n", "repeat_id"], columns="scale",
            values=["beta_hat", "eta_hat", "gamma_hat"],
        )
        if "beta_hat" in pivoted.columns and "norm" in pivoted["beta_hat"].columns:
            beta_diff = (pivoted["beta_hat"]["norm"] - pivoted["beta_hat"]["display"]).abs().max()
            assert beta_diff < 1e-5, f"LSE beta not scale-invariant: max diff {beta_diff}"
        if "eta_hat" in pivoted.columns:
            eta_ratio = pivoted["eta_hat"]["display"] / pivoted["eta_hat"]["norm"]
            eta_ratio_diff = (eta_ratio - 1000.0).abs().max()
            assert eta_ratio_diff < 1.0, f"LSE eta ratio off: max |ratio-1000|={eta_ratio_diff}"


class TestManifest:
    def test_manifest_has_keys(self):
        import json
        with open(MANIFEST, "r", encoding="utf-8") as f:
            m = json.load(f)
        required = ["run_id", "seed_namespace", "parameter_grid", "methods",
                     "input_hashes", "output_hashes", "n_failures_per_method"]
        for key in required:
            assert key in m, f"Missing manifest key: {key}"
