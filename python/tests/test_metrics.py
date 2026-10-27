"""
评价指标模块测试

当前权威口径：
- 第七轮常用指标为默认主口径：Bias、SD、RMSE、MAE。
- beta/eta 可附相对 Bias、相对 RMSE；gamma 不输出相对指标。
- 工程寿命分位点 x_R 输出 Bias、SD、RMSE、MAE 与相对 Bias/RMSE。
- S2R 的 MdAPE、MedRel、IQR、P95/P99、Valid Rate 保留为 diagnostics。
"""

import math
import sys
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "python"))

from studies.common.metrics import (
    DEFAULT_R_LEVELS,
    DEFAULT_STANDARD_R_LEVELS,
    aggregate_param_metrics,
    aggregate_standard_metrics,
    check_status,
    param_relative_errors,
    quantile_est,
    quantile_relative_error,
    quantile_true,
    summarize_relative_errors,
    summarize_standard_errors,
)


class TestCoreDefinitions:
    def test_default_r_levels_match_s2r_spec(self):
        assert DEFAULT_R_LEVELS == (0.50, 0.90, 0.95, 0.99, 0.999)

    def test_param_relative_errors_use_eta_for_gamma(self):
        errors = param_relative_errors(
            beta_hat=2.2,
            eta_hat=110.0,
            gamma_hat=15.0,
            beta=2.0,
            eta=100.0,
            gamma=10.0,
        )

        assert errors["beta"] == pytest.approx(0.1)
        assert errors["eta"] == pytest.approx(0.1)
        assert errors["gamma"] == pytest.approx(0.05)

    def test_quantile_true_and_estimate_match_when_params_match(self):
        x_true = quantile_true(2.0, 100.0, 10.0, 0.90)
        x_est = quantile_est(2.0, 100.0, 10.0, 0.90)

        assert x_true == pytest.approx(10.0 + 100.0 * (-math.log(0.90)) ** 0.5)
        assert x_est == pytest.approx(x_true)

    def test_quantile_relative_error_is_signed(self):
        err = quantile_relative_error(
            beta_hat=2.0,
            eta_hat=100.0,
            gamma_hat=20.0,
            beta=2.0,
            eta=100.0,
            gamma=10.0,
            R=0.90,
        )

        assert err > 0


class TestDistributionSummary:
    def test_summary_reports_s2r_metric_family(self):
        summary = summarize_relative_errors([-0.2, -0.1, 0.0, 0.1, 2.0])

        assert summary["mdape"] == pytest.approx(0.1)
        assert summary["med_rel"] == pytest.approx(0.0)
        assert summary["p25_rel"] == pytest.approx(-0.1)
        assert summary["p75_rel"] == pytest.approx(0.1)
        assert summary["reliqr"] == pytest.approx(0.2)
        assert summary["p5_rel"] < -0.1
        assert summary["p95_rel"] > 1.0
        assert summary["p95_abs"] > 1.0
        assert summary["p99_abs"] > summary["p95_abs"]

    def test_summary_ignores_nonfinite_values(self):
        summary = summarize_relative_errors([float("nan"), -0.1, 0.1, float("inf")])

        assert summary["mdape"] == pytest.approx(0.1)
        assert summary["med_rel"] == pytest.approx(0.0)

    def test_empty_summary_uses_none_values(self):
        summary = summarize_relative_errors([float("nan")])

        assert summary["mdape"] is None
        assert summary["p95_abs"] is None


class TestStandardSummary:
    def test_standard_summary_reports_bias_sd_rmse_mae(self):
        summary = summarize_standard_errors([10.0, -5.0, 0.0])

        assert summary["n"] == 3
        assert summary["bias"] == pytest.approx(5.0 / 3.0)
        assert summary["sd"] == pytest.approx(7.637626, rel=1e-6)
        assert summary["rmse"] == pytest.approx(math.sqrt(125.0 / 3.0))
        assert summary["mae"] == pytest.approx(5.0)
        assert summary["mse"] == pytest.approx(125.0 / 3.0)

    def test_standard_summary_ignores_nonfinite_values(self):
        summary = summarize_standard_errors([float("nan"), -2.0, 2.0, float("inf")])

        assert summary["n"] == 2
        assert summary["bias"] == pytest.approx(0.0)
        assert summary["rmse"] == pytest.approx(2.0)

    def test_empty_standard_summary_uses_none_values(self):
        summary = summarize_standard_errors([float("nan")])

        assert summary == {
            "n": 0,
            "bias": None,
            "sd": None,
            "mse": None,
            "rmse": None,
            "mae": None,
        }


class TestStatus:
    def test_valid_estimate_is_success(self):
        assert check_status(2.0, 100.0, 10.0, 2.0, 100.0, 10.0) == "success"

    def test_invalid_beta_or_eta_is_failure(self):
        assert check_status(0.0, 100.0, 10.0, 2.0, 100.0, 10.0) == "failure"
        assert check_status(2.0, -1.0, 10.0, 2.0, 100.0, 10.0) == "failure"

    def test_nonfinite_gamma_is_failure(self):
        assert check_status(2.0, 100.0, float("nan"), 2.0, 100.0, 10.0) == "failure"

    def test_unconverged_is_failure(self):
        assert check_status(2.0, 100.0, 10.0, 2.0, 100.0, 10.0, converged=False) == "failure"

    def test_gamma_at_sample_min_is_failure(self):
        status = check_status(
            2.0,
            100.0,
            12.0,
            2.0,
            100.0,
            10.0,
            sample_min=12.0,
        )

        assert status == "failure"

    def test_large_but_valid_error_is_still_success(self):
        assert check_status(10.0, 100.0, 10.0, 2.0, 100.0, 10.0) == "success"


class TestAggregate:
    def _make_result(
        self,
        beta_hat,
        eta_hat,
        gamma_hat,
        beta=2.0,
        eta=100.0,
        gamma=10.0,
        time=0.1,
        converged=True,
    ):
        return {
            "beta_hat": beta_hat,
            "eta_hat": eta_hat,
            "gamma_hat": gamma_hat,
            "beta": beta,
            "eta": eta,
            "gamma": gamma,
            "time": time,
            "converged": converged,
        }

    def test_empty_input(self):
        assert aggregate_param_metrics([])["n_total"] == 0

    def test_failure_excluded_from_accuracy_but_in_denominator(self):
        agg = aggregate_param_metrics([
            self._make_result(2.0, 100.0, 10.0),
            self._make_result(None, None, None),
        ])

        assert agg["n_total"] == 2
        assert agg["n_valid"] == 1
        assert agg["n_failure"] == 1
        assert agg["valid_rate"] == pytest.approx(0.5)
        assert agg["failure_rate"] == pytest.approx(0.5)
        assert agg["mdape_beta"] == pytest.approx(0.0)

    def test_large_valid_error_enters_tail_statistics(self):
        agg = aggregate_param_metrics([
            self._make_result(2.0, 100.0, 10.0),
            self._make_result(2.2, 100.0, 10.0),
            self._make_result(10.0, 100.0, 10.0),
        ])

        assert agg["n_valid"] == 3
        assert agg["mdape_beta"] == pytest.approx(0.1)
        assert agg["p95_abs_beta"] > 3.0

    def test_param_distribution_uses_latest_metric_family(self):
        agg = aggregate_param_metrics([
            self._make_result(2.0, 100.0, 10.0),
            self._make_result(2.2, 110.0, 15.0),
            self._make_result(1.8, 90.0, 5.0),
        ])

        for param in ("beta", "eta", "gamma"):
            summary = agg["param_distribution"][param]
            assert set(summary) == {
                "mdape",
                "med_rel",
                "p25_rel",
                "p75_rel",
                "reliqr",
                "p5_rel",
                "p95_rel",
                "p95_abs",
                "p99_abs",
            }

        assert agg["mdape_beta"] == pytest.approx(0.1)
        assert agg["med_rel_beta"] == pytest.approx(0.0)

    def test_quantile_distribution_uses_same_metric_family(self):
        agg = aggregate_param_metrics([
            self._make_result(2.0, 100.0, 10.0),
            self._make_result(2.1, 105.0, 12.0),
            self._make_result(1.9, 95.0, 8.0),
        ])

        for R in DEFAULT_R_LEVELS:
            summary = agg["quantile_distribution"][R]
            assert set(summary) == {
                "mdape",
                "med_rel",
                "p25_rel",
                "p75_rel",
                "reliqr",
                "p5_rel",
                "p95_rel",
                "p95_abs",
                "p99_abs",
            }

    def test_old_metrics_are_not_emitted(self):
        agg = aggregate_param_metrics([
            self._make_result(2.0, 100.0, 10.0),
            self._make_result(2.1, 105.0, 12.0),
        ])

        for old_key in ("ne_mean", "ne_std", "nqe_mean", "re_mean", "outlier_rate", "n_outlier"):
            assert old_key not in agg

    def test_standard_metrics_are_default_output(self):
        agg = aggregate_standard_metrics([
            self._make_result(2.2, 110.0, 12.0),
            self._make_result(1.8, 90.0, 8.0),
            self._make_result(None, None, None),
        ])

        assert agg["n_total"] == 3
        assert agg["n_valid"] == 2
        assert agg["n_failure"] == 1
        assert agg["valid_rate"] == pytest.approx(2.0 / 3.0)

        beta_abs = agg["param_standard"]["beta"]["absolute"]
        assert beta_abs["bias"] == pytest.approx(0.0)
        assert beta_abs["sd"] == pytest.approx(0.2828427, rel=1e-6)
        assert beta_abs["rmse"] == pytest.approx(0.2)
        assert beta_abs["mae"] == pytest.approx(0.2)

        beta_rel = agg["param_standard"]["beta"]["relative"]
        assert beta_rel["bias"] == pytest.approx(0.0)
        assert beta_rel["rmse"] == pytest.approx(0.1)

        assert "relative" not in agg["param_standard"]["gamma"]
        assert "diagnostics" in agg
        assert "param_distribution" in agg["diagnostics"]

    def test_standard_quantile_metrics_include_x095_and_x099_by_default(self):
        agg = aggregate_standard_metrics([
            self._make_result(2.0, 100.0, 10.0),
            self._make_result(2.2, 110.0, 12.0),
        ])

        assert DEFAULT_STANDARD_R_LEVELS == (0.95, 0.99)
        assert set(agg["quantile_standard"]) == {0.95, 0.99}

        for R in DEFAULT_STANDARD_R_LEVELS:
            item = agg["quantile_standard"][R]
            assert set(item) == {"absolute", "relative"}
            assert "rmse" in item["absolute"]
            assert "rmse" in item["relative"]

    def test_s2r_diagnostics_do_not_emit_old_ne_family(self):
        agg = aggregate_standard_metrics([
            self._make_result(2.0, 100.0, 10.0),
            self._make_result(2.1, 105.0, 12.0),
        ])

        diagnostics = agg["diagnostics"]
        for old_key in ("ne_mean", "ne_std", "nqe_mean", "re_mean", "outlier_rate", "n_outlier"):
            assert old_key not in diagnostics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
