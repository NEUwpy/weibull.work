"""Fail-closed numerical and export QA for Study01 submission figures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
from PIL import Image


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
MAIN = ROOT / "main"
SUPP = ROOT / "supplementary"
DERIVED = ROOT / "data" / "derived"
TABLES = ROOT / "tables"

FIGURES = {
    "fig1_method_structure": MAIN,
    "fig2_overall_delta_risk": MAIN,
    "fig3_per_n_J1": MAIN,
    "fig4_selector_mechanism": MAIN,
    "fig5_decision_mechanism": MAIN,
    "fig6_support_validation": MAIN,
    "supp_fig_seed_stability": SUPP,
    "supp_fig_unseen_beta": SUPP,
    "supp_fig_traditional_per_n": SUPP,
    "supp_fig_quantile_rmse": SUPP,
    "supp_fig_parameter_guided": SUPP,
    "supp_fig_parameter_landscape": SUPP,
    "supp_fig_z_only_learning_curve": SUPP,
}
FORMATS = ("png", "svg", "pdf", "tiff")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assert_close(actual, expected, tolerance=5e-7):
    if abs(float(actual) - float(expected)) > tolerance:
        raise AssertionError(f"{actual} != {expected} within {tolerance}")


def check_exports():
    records = []
    for stem, folder in FIGURES.items():
        for extension in FORMATS:
            path = folder / f"{stem}.{extension}"
            if not path.is_file() or path.stat().st_size < 1000:
                raise AssertionError(f"Missing or empty export: {path}")
            records.append({
                "file": str(path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            })

        png = folder / f"{stem}.png"
        with Image.open(png) as image:
            width, height = image.size
            if width < 900 or height < 500:
                raise AssertionError(f"PNG too small: {png} -> {image.size}")

        svg_text = (folder / f"{stem}.svg").read_text(encoding="utf-8")
        if "<text" not in svg_text:
            raise AssertionError(f"SVG has no editable text: {stem}")
        if "fonttype='path'" in svg_text or "fonttype=\"path\"" in svg_text:
            raise AssertionError(f"SVG text was converted to paths: {stem}")

        if not (folder / f"{stem}.pdf").read_bytes().startswith(b"%PDF"):
            raise AssertionError(f"Invalid PDF header: {stem}")
    return records


def check_scientific_values():
    curve = pd.read_csv(DERIVED / "fig2_delta_risk.csv")
    if len(curve) != 26 or curve["delta"].nunique() != 26:
        raise AssertionError("Figure 2 must contain all 26 candidate offsets")
    best = curve.loc[curve["J1"].idxmin()]
    assert_close(best["delta"], 0.06, 1e-12)
    assert_close(best["J1"], 0.624518, 5e-7)
    default = curve.loc[(curve["delta"] - 0.10).abs().idxmin()]
    assert_close(default["J1"], 0.6304091999323667)

    layers = pd.read_csv(DERIVED / "fig2_decision_conditions.csv")
    if layers["layer"].tolist() != ["Default", "L1", "L2", "L3", "L4", "L5", "L6"]:
        raise AssertionError("Figure 2 decision-reference order changed")
    assert_close(layers.loc[layers["layer"] == "L6", "J1"].iloc[0],
                 0.4922971152637207)
    expected_groups = [
        "fixed_or_n_conditioned", "fixed_or_n_conditioned",
        "fixed_or_n_conditioned", "parameter_conditioned_average",
        "parameter_conditioned_average", "parameter_conditioned_average",
        "sample_level_hindsight",
    ]
    if layers["condition_group"].tolist() != expected_groups:
        raise AssertionError("Figure 2 decision-condition grouping changed")

    main = pd.read_csv(DERIVED / "fig3_main_results_by_n.csv")
    if main["n"].tolist() != [7, 10, 15, 20]:
        raise AssertionError("Figure 3 sample-size order changed")
    expected_adaptive = [0.701337127247328, 0.6070629116585652,
                         0.5293829329592756, 0.47556735574356884]
    for actual, expected in zip(main["adaptive"], expected_adaptive):
        assert_close(actual, expected)
    expected_improvement = [8.119, 7.620, 6.318, 5.984]
    for actual, expected in zip(main["adaptive_improvement_pct"], expected_improvement):
        assert_close(actual, expected, 0.01)
    if "recovered_hindsight_gap_pct" in main.columns:
        raise AssertionError(
            "Figure 3 source must not label the Default-L6 gap as recoverable"
        )

    paired = pd.read_csv(DERIVED / "fig3_sample_loss_difference_quantiles.csv")
    if paired["n"].tolist() != [7, 10, 15, 20] or not (paired["n_samples"] == 12000).all():
        raise AssertionError("Figure 3 paired-loss sample contract changed")
    expected_improved = [62.525, 66.00833333333334,
                         62.15, 58.508333333333326]
    for actual, expected in zip(paired["improved_pct"], expected_improved):
        assert_close(actual, expected, 1e-10)
    for row in paired.itertuples():
        values = [row.q01, row.q05, row.q25, row.q50,
                  row.q75, row.q95, row.q99]
        if values != sorted(values):
            raise AssertionError("Figure 3 paired-loss quantiles are not monotone")

    components = pd.read_csv(TABLES / "supp_table_parameter_error_decomposition.csv")
    if components["parameter"].tolist() != ["beta", "eta", "gamma"]:
        raise AssertionError("Parameter-error decomposition order changed")
    expected_component_reductions = [13.555, 13.868, 14.932]
    for actual, expected in zip(components["mse_contribution_reduction_pct"],
                                expected_component_reductions):
        assert_close(actual, expected, 0.01)
    expected_default_rmse = [0.4032024329, 0.3614166461, 0.3228336497]
    expected_adaptive_rmse = [0.3748804985, 0.3354213448, 0.2977575681]
    for actual, expected in zip(components["default_normalized_rmse"],
                                expected_default_rmse):
        assert_close(actual, expected, 1e-9)
    for actual, expected in zip(components["adaptive_normalized_rmse"],
                                expected_adaptive_rmse):
        assert_close(actual, expected, 1e-9)

    figure3_svg = (MAIN / "fig3_per_n_J1.svg").read_text(encoding="utf-8")
    if "seed" in figure3_svg.lower():
        raise AssertionError("Figure 3 must not display training-seed information")

    representative = pd.read_csv(DERIVED / "fig4_representative_curve.csv")
    if len(representative) != 26 or representative["delta"].nunique() != 26:
        raise AssertionError("Figure 4 representative case must contain 26 offsets")
    if representative["selected_delta"].nunique() != 1 or representative["oracle_delta"].nunique() != 1:
        raise AssertionError("Figure 4 representative case has inconsistent selected/oracle offsets")
    if not set(representative[["selected_delta", "oracle_delta"]].iloc[0]).issubset(set(curve["delta"])):
        raise AssertionError("Figure 4 selected/oracle offsets are outside the candidate grid")

    confusion = pd.read_csv(DERIVED / "fig4_delta_confusion.csv")
    if len(confusion) != 26 * 26 or confusion["oracle_delta"].nunique() != 26 or confusion["selected_delta"].nunique() != 26:
        raise AssertionError("Figure 4 selection correspondence must contain the full 26 x 26 grid")
    row_sums = confusion.groupby("oracle_delta")["row_percent"].sum()
    if not ((row_sums - 100).abs() < 1e-7).all():
        raise AssertionError("Figure 4 correspondence rows do not sum to 100%")

    regret = pd.read_csv(DERIVED / "fig4_excess_loss_quantiles.csv")
    if len(regret) != 12 or set(regret["n"]) != {7, 10, 15, 20} or set(regret["quantile"]) != {0.5, 0.9, 0.99}:
        raise AssertionError("Figure 4 excess-loss source must contain 4 n x 3 quantiles")
    for _, group in regret.groupby("n"):
        values = group.sort_values("quantile")["excess_loss"].tolist()
        if not values[0] <= values[1] <= values[2]:
            raise AssertionError("Figure 4 excess-loss quantiles are not monotone")

    cells = pd.read_csv(DERIVED / "fig5_within_cell_hindsight.csv")
    if (len(cells) != 160 or cells["beta"].nunique() != 8 or
            cells["gamma_over_eta"].nunique() != 5 or cells["n"].nunique() != 4):
        raise AssertionError("Figure 5 within-cell evidence must contain 160 cells")
    assert_close(cells["l6_effective_delta_count"].median(), 6.09, 1e-2)
    risk_path = pd.read_csv(DERIVED / "fig5_z_only_risk_path.csv")
    expected_methods = [
        "Default", "Paper-MLP", "In-domain-current-MLP",
        "Z-only-empirical-reference", "L6-complete-information",
    ]
    if risk_path["method"].tolist() != expected_methods:
        raise AssertionError("Figure 5 risk path is incomplete or reordered")
    expected_risks = [0.3926912312, 0.3395311145, 0.3226679985,
                      0.3156581752, 0.2406463568]
    for actual, expected in zip(risk_path["R_mean_loss"], expected_risks):
        assert_close(actual, expected, 1e-9)

    learning = pd.read_csv(DERIVED / "supp_z_only_learning_curve.csv")
    if len(learning) != 20 or set(learning["repeats_per_cell"]) != {40, 80, 120, 160, 200}:
        raise AssertionError("Z-only learning diagnostic must contain 4 n x 5 sizes")

    landscape = pd.read_csv(DERIVED / "supp_parameter_landscape.csv")
    if (len(landscape) != 160 or landscape["beta"].nunique() != 8 or
            landscape["gamma_over_eta"].nunique() != 5 or landscape["n"].nunique() != 4):
        raise AssertionError("Supplementary landscape must contain 8 beta x 5 ratio x 4 n cells")
    if int((landscape["improvement_pct"] < 0).sum()) != 35:
        raise AssertionError("Supplementary landscape deterioration-cell count changed")
    assert_close(landscape["improvement_pct"].min(), -17.504974, 1e-5)

    unseen_main = pd.read_csv(DERIVED / "fig6_unseen_beta_improvement.csv")
    if len(unseen_main) != 8 or unseen_main["held_out_beta"].nunique() != 8:
        raise AssertionError("Figure 6 unseen-parameter panel must contain 8 held-out beta levels")
    if set(unseen_main.columns) != {"held_out_beta", "improvement_pct"}:
        raise AssertionError("Figure 6 unseen-parameter source must use the fixed primary seed")
    negative = unseen_main[unseen_main["improvement_pct"] <= 0]
    if negative["held_out_beta"].tolist() != [1.5]:
        raise AssertionError("Only held-out beta=1.5 should lack improvement")

    traditional_main = pd.read_csv(DERIVED / "fig6_traditional_by_n.csv")
    if len(traditional_main) != 16 or traditional_main["method"].nunique() != 4:
        raise AssertionError("Figure 6 traditional panel must contain 4 n x 4 methods")

    quantile_main = pd.read_csv(DERIVED / "fig6_quantile_rmse.csv")
    if (len(quantile_main) != 15 or quantile_main["method"].nunique() != 5 or
            set(quantile_main.columns) != {"method", "quantile", "rmse"}):
        raise AssertionError("Figure 6 quantile source must retain all 3 quantiles x 5 methods")

    main_results = pd.read_csv(DERIVED / "fig3_main_results_by_n.csv")
    if "raw_mean" in main_results or "raw_min" in main_results or "raw_max" in main_results:
        raise AssertionError("Figure 3 must use the fixed primary seed, not a seed aggregate")

    seeds = pd.read_csv(DERIVED / "supp_seed_stability.csv")
    if len(seeds) != 15 or seeds["seed"].nunique() != 3:
        raise AssertionError("Seed-stability source must contain 3 seeds x 5 summaries")

    unseen = pd.read_csv(DERIVED / "supp_unseen_beta.csv")
    if len(unseen) != 24 or unseen["beta"].nunique() != 8:
        raise AssertionError("Unseen-beta source must contain 8 beta x 3 methods")

    traditional = pd.read_csv(DERIVED / "supp_traditional_by_n.csv")
    if len(traditional) != 20 or traditional["method"].nunique() != 5:
        raise AssertionError("Traditional comparison must contain 4 n x 5 methods")

    quantile = pd.read_csv(DERIVED / "supp_quantile_rmse.csv")
    if len(quantile) != 15 or quantile["method"].nunique() != 5:
        raise AssertionError("Quantile source must contain 3 quantiles x 5 methods")
    w95 = quantile[(quantile["method"] == "WMLE") &
                   (quantile["quantile"] == "x0.95")]["rmse"].iloc[0]
    assert_close(w95, 0.1985605836051415)

    # ---- PG negative supporting experiment (supp figure + tables) ----
    pg_boot = pd.read_csv(DERIVED / "supp_pg_bootstrap.csv")
    if len(pg_boot) != 12:
        raise AssertionError("PG bootstrap source must contain all 12 one-step variants")
    if set(pg_boot["variant"]) != {"one_step"}:
        raise AssertionError("PG bootstrap source must be one-step rows only")
    # best rule: WMLE / PG-beta / interpolated
    best_boot = pg_boot[(pg_boot["estimator"] == "WMLE")
                        & (pg_boot["family"] == "PG-beta")
                        & (pg_boot["mapping"] == "interpolated")].iloc[0]
    assert_close(best_boot["observed_j1_diff"], 0.020287, 1e-5)
    assert_close(best_boot["ci_low"], 0.018586, 1e-5)
    assert_close(best_boot["ci_high"], 0.021947, 1e-5)
    if (pg_boot["observed_j1_diff"] <= 0).any():
        raise AssertionError("Not every one-step PG rule is worse than Default")

    pg_by_beta = pd.read_csv(DERIVED / "supp_pg_by_beta.csv")
    if pg_by_beta["true_beta"].tolist() != [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]:
        raise AssertionError("PG by-beta source must cover all 8 true-beta levels")
    diff_15 = pg_by_beta[pg_by_beta["true_beta"] == 1.5]["J1_diff"].iloc[0]
    assert_close(diff_15, -0.01043267, 1e-5)   # beta=1.5 exception (PG better)
    others = pg_by_beta[pg_by_beta["true_beta"] != 1.5]["J1_diff"]
    if (others <= 0).any():
        raise AssertionError("PG by-beta must be worse than Default for beta=2.0..5.0")

    pg_cell = pd.read_csv(DERIVED / "supp_pg_cell_correctness.csv")
    if len(pg_cell) != 16 or pg_cell["estimator"].nunique() != 2:
        raise AssertionError("PG cell-correctness source must contain 8 beta x 2 estimators")
    beta_levels = sorted(pg_cell["true_beta"].astype(float).unique().tolist())
    expected_betas = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
    if beta_levels != expected_betas:
        raise AssertionError(f"PG cell-correctness true-beta levels wrong: {beta_levels}")
    wmle_all_rate = pg_cell[pg_cell["estimator"] == "WMLE"]["correct_rate"].mean()
    if not (0.05 < wmle_all_rate < 0.35):
        raise AssertionError("WMLE nearest-cell correctness is outside the expected range")


def main():
    records = check_exports()
    check_scientific_values()
    report = {
        "status": "PASS",
        "backend": "Python/matplotlib only",
        "figures": len(FIGURES),
        "formats_per_figure": list(FORMATS),
        "exports_verified": len(records),
        "scientific_checks": [
            "26-point delta curve and minimum",
            "default delta J1",
            "seven decision references",
            "four per-n main results and observed hindsight-gap fractions",
            "48,000 paired sample losses, improved proportions, and quantile monotonicity",
            "three-parameter normalized error decomposition",
            "representative risk curve and full 26 x 26 offset correspondence",
            "excess-loss quantile monotonicity",
            "160-cell hindsight-choice diversity and five-condition risk path",
            "Z-only data-size diagnostic",
            "160-cell supplementary parameter landscape and 35 deterioration cells",
            "eight held-out parameter levels in the main validation composite",
            "four-method traditional comparison in the main validation composite",
            "three-quantile source retained for the main validation composite",
            "three-seed source cardinality",
            "eight held-out beta levels",
            "five-method traditional comparison",
            "three-quantile engineering comparison",
            "12 one-step PG rules, best-rule paired CI, beta=1.5 exception, "
            "cell-correctness diagnostic",
        ],
        "editable_svg_text": True,
        "files": records,
    }
    (ROOT / "provenance" / "submission_figure_qa.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("PASS: 13 figures, 52 exports, editable SVG text, scientific values verified")


if __name__ == "__main__":
    main()
