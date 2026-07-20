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
        assert os.path.exists(PER_SAMPLE)
    def test_overall_exists(self):
        assert os.path.exists(OVERALL)
    def test_summary_n7_exists(self):
        assert os.path.exists(N7)
    def test_summary_n10_exists(self):
        assert os.path.exists(N10)
    def test_summary_n20_exists(self):
        assert os.path.exists(N20)
    def test_scale_check_exists(self):
        assert os.path.exists(SCALE_CHECK)
    def test_manifest_exists(self):
        assert os.path.exists(MANIFEST)


class TestPerSampleResults:
    @pytest.fixture(autouse=True)
    def load(self):
        self.df = pd.read_csv(PER_SAMPLE)

    def test_total_rows(self):
        expected = len(METHODS) * len(N_VALUES) * N_REPEATS
        assert len(self.df) == expected

    def test_all_methods_present(self):
        for m in METHODS:
            assert m in self.df["method"].values

    def test_repeat_counts(self):
        for method in METHODS:
            for n in N_VALUES:
                count = len(self.df[(self.df["method"] == method) & (self.df["n"] == n)])
                assert count == N_REPEATS

    def test_unique_repeat_ids(self):
        for method in METHODS:
            for n in N_VALUES:
                subset = self.df[(self.df["method"] == method) & (self.df["n"] == n)]
                assert subset["repeat_id"].nunique() == N_REPEATS

    def test_L_i_full_coverage(self):
        """Every single row must have a valid L_i (including failure penalty)."""
        for method in self.df["method"].unique():
            dm = self.df[self.df["method"] == method]
            missing = dm["L_i"].isna().sum()
            assert missing == 0, f"{method}: {missing} rows missing L_i"
            e_b_missing = dm["e_beta"].isna().sum()
            assert e_b_missing == 0, f"{method}: {e_b_missing} rows missing e_beta"

    def test_mle_failure_penalty(self):
        mle = self.df[self.df["method"] == "mle"]
        failed = mle[mle["converged"] == False]
        assert len(failed) > 0, "MLE should have failures"
        L_vals = failed["L_i"].dropna()
        assert len(L_vals) == len(failed), f"MLE failures missing L_i: {len(failed) - len(L_vals)}"
        assert (L_vals == 3.0).all(), f"MLE failure L_i should all be 3.0, got {L_vals.unique()}"
        assert failed["failure_reason"].notna().all(), "MLE failures should have failure_reason"

    def test_sample_hash_unique_per_sample(self):
        """Each (n, repeat_id) pair must have exactly one content hash across methods."""
        for n in N_VALUES:
            subset = self.df[self.df["n"] == n]
            groups = subset.groupby("repeat_id")["sample_content_hash"].apply(set)
            for rid, hashes in groups.items():
                real_hashes = {h for h in hashes if h and len(h) >= 8}
                assert len(real_hashes) == 1, f"n={n} rid={rid}: {len(real_hashes)} distinct hashes"

    def test_sample_hashes_match_MDM01(self):
        """All traditional-method hashes must match MDM-0.1 for every (n, rid)."""
        mdm01 = self.df[self.df["method"] == "MDM-0.1"][["n", "repeat_id", "sample_content_hash"]]
        mdm01 = mdm01.set_index(["n", "repeat_id"])
        mdm01.columns = ["expected_hash"]
        for method in ["mle", "wmle", "lse", "lre"]:
            dm = self.df[self.df["method"] == method][["n", "repeat_id", "sample_content_hash"]]
            dm = dm.set_index(["n", "repeat_id"])
            merged = dm.join(mdm01, how="inner")
            mismatches = (merged["sample_content_hash"] != merged["expected_hash"]).sum()
            assert mismatches == 0, f"{method}: {mismatches} hash mismatches vs MDM-0.1"


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
            assert (valid >= 0).all()

    def test_mle_j1(self):
        mle_j1 = self.df[self.df["method"] == "mle"]["pooled_J1"].values[0]
        assert abs(mle_j1 - 1.762) < 0.001


class TestPerNTable:
    @pytest.mark.parametrize("path,n_val", [(N7, 7), (N10, 10), (N20, 20)])
    def test_rows_per_method(self, path, n_val):
        df = pd.read_csv(path)
        params_per_method = 3
        expected = len(METHODS) * params_per_method
        assert len(df) == expected

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
            assert "norm" in scales and "display" in scales

    def test_lse_scale_equivariance(self):
        lse = self.df[self.df["method"] == "lse"]
        valid = lse[lse["converged"].astype(bool) & lse["beta_hat"].notna()]
        pivoted = valid.pivot_table(
            index=["n", "repeat_id"], columns="scale",
            values=["beta_hat", "eta_hat", "gamma_hat"],
        )
        if "beta_hat" in pivoted.columns and "norm" in pivoted["beta_hat"].columns:
            beta_diff = (pivoted["beta_hat"]["norm"] - pivoted["beta_hat"]["display"]).abs().max()
            assert beta_diff < 1e-5
        if "eta_hat" in pivoted.columns:
            eta_ratio = pivoted["eta_hat"]["display"] / pivoted["eta_hat"]["norm"]
            eta_dev = (eta_ratio - 1000.0).abs().max()
            assert eta_dev < 1.0
        if "gamma_hat" in pivoted.columns:
            gamma_ratio = pivoted["gamma_hat"]["display"] / pivoted["gamma_hat"]["norm"]
            gamma_dev = (gamma_ratio - 1000.0).abs().max()
            assert gamma_dev < 1.0

    def test_lse_gamma_scale(self):
        lse = self.df[self.df["method"] == "lse"]
        valid = lse[lse["converged"].astype(bool) & lse["beta_hat"].notna()]
        pivoted = valid.pivot_table(
            index=["n", "repeat_id"], columns="scale", values=["gamma_hat"],
        )
        if "gamma_hat" in pivoted.columns:
            gamma_ratio = pivoted["gamma_hat"]["display"] / pivoted["gamma_hat"]["norm"]
            gamma_dev = (gamma_ratio.dropna() - 1000.0).abs().max()
            assert gamma_dev < 1.0, f"LSE gamma ratio deviates by {gamma_dev}"


class TestManifest:
    def test_manifest_has_keys(self):
        import json
        with open(MANIFEST, "r", encoding="utf-8") as f:
            m = json.load(f)
        required = ["run_id", "seed_namespace", "parameter_grid", "methods",
                     "input_hashes", "output_hashes", "n_failures_per_method",
                     "failure_penalty"]
        for key in required:
            assert key in m

    def test_output_hashes_count(self):
        import json
        with open(MANIFEST, "r", encoding="utf-8") as f:
            m = json.load(f)
        expected = {"per_sample_results.csv", "overall_summary.csv",
                     "summary_n7.csv", "summary_n10.csv", "summary_n20.csv",
                     "scale_equivariance_check.csv", "manifest.json"}
        actual = set(m.get("output_hashes", {}).keys())
        missing = expected - actual
        assert not missing, f"Missing output hashes: {missing}"
