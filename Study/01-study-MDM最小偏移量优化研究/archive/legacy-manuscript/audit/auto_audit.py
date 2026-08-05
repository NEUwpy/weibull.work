"""Archived G7 manuscript audit for Study01.

The public ``audit_manuscript`` function preserves the old feature-route
claims-to-data checks after the manuscript package moved under ``archive/``.
It is not the audit path for the current Dimensional-RAW paper.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REQUIRED_CLAIM_IDS = {f"C{i:03d}" for i in range(1, 34)}
STALE_STATUS_TERMS = ("未生成", "待生成", "需生成", "需检查", "待补充")


@dataclass(frozen=True)
class AuditPaths:
    study_root: Path
    repo_root: Path
    claims_csv: Path
    figure_checklist_csv: Path
    reference_checklist_csv: Path
    submission_checklist_md: Path
    figure_index_md: Path
    paper_md: Path
    supplementary_md: Path

    @classmethod
    def defaults(cls) -> "AuditPaths":
        audit_dir = Path(__file__).resolve().parent
        legacy_manuscript_root = audit_dir.parent
        study_root = legacy_manuscript_root.parents[1]
        return cls(
            study_root=study_root,
            repo_root=study_root.parents[1],
            claims_csv=audit_dir / "claims-to-data.csv",
            figure_checklist_csv=audit_dir / "figure-checklist.csv",
            reference_checklist_csv=audit_dir / "reference-checklist.csv",
            submission_checklist_md=audit_dir / "submission-checklist.md",
            figure_index_md=legacy_manuscript_root / "figure-index.md",
            paper_md=legacy_manuscript_root / "paper.md",
            supplementary_md=legacy_manuscript_root / "supplementary.md",
        )

    def with_overrides(self, **overrides: str | Path | None) -> "AuditPaths":
        values = self.__dict__.copy()
        for key, value in overrides.items():
            if value is not None:
                values[key] = Path(value).resolve()
        return AuditPaths(**values)


@dataclass(frozen=True)
class ClaimSpec:
    source_file: str
    source_field: str
    actual: Any
    tolerance: float | None = None


def _load_config(study_root: Path):
    config_path = study_root / "code" / "config.py"
    spec = importlib.util.spec_from_file_location("study01_audit_config", config_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load config: {config_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _claim_specs(paths: AuditPaths) -> dict[str, ClaimSpec]:
    formal = paths.study_root / "artifacts" / "formal"
    config = _load_config(paths.study_root)

    with (formal / "E2_oracle_layers" / "summary.json").open(encoding="utf-8") as f:
        ladder = {r["layer"]: r["J1_global"] for r in json.load(f)["results"]["ladder"]}

    seed_stability = pd.read_csv(
        formal / "E3b_vector_mlp" / "seed_stability.csv"
    )
    ablation = pd.read_csv(
        formal / "E4_robustness" / "E4a_feature_ablation.csv"
    )
    with (formal / "E4_robustness" / "summary_e4d.json").open(encoding="utf-8") as f:
        per_track = json.load(f)["per_track_pooled_J1"]

    cohort = pd.read_csv(
        formal / "delta_upper_bound_audit" / "cohort_summary.csv"
    )
    endpoint = cohort[cohort["cohort_delta"] == 0.50].iloc[0]
    endpoint_dist = ast.literal_eval(endpoint["extended_best_delta_distribution"])

    real = pd.read_csv(
        formal
        / "real_data"
        / "nist-6061-t6-fatigue"
        / "real_holdout_results.csv"
    )
    nn = real[real["method"] == "nn"]
    nn_ids = sorted(nn["model_id"].unique())

    l2_n20 = real[(real["train_n"] == 20) & (real["method"] == "l2")][
        ["repeat_index", "D"]
    ]
    default_n20 = real[
        (real["train_n"] == 20) & (real["method"] == "default")
    ][["repeat_index", "D"]]
    paired = l2_n20.merge(
        default_n20, on="repeat_index", suffixes=("_l2", "_default")
    )
    diff = paired["D_l2"] - paired["D_default"]
    paired_value = (
        int((diff < -1e-9).sum()),
        int((diff > 1e-9).sum()),
        int((np.abs(diff) <= 1e-9).sum()),
    )

    default_n7_sv = float(
        real[(real["train_n"] == 7) & (real["method"] == "default")][
            "support_set_violation"
        ].mean()
    )
    nn_n7_sv = float(
        nn[nn["train_n"] == 7]
        .groupby("model_id")["support_set_violation"]
        .mean()
        .median()
    )

    def seed_value(seed: int) -> float:
        return float(seed_stability[seed_stability["seed"] == seed]["pooled_J1"].iloc[0])

    def ablation_value(group: str) -> float:
        return float(
            ablation[ablation["feature_group"] == group]["pooled_J1"].mean()
        )

    def default_median(train_n: int) -> float:
        return float(
            real[
                (real["train_n"] == train_n) & (real["method"] == "default")
            ]["D"].median()
        )

    def nn_median_of_medians(train_n: int) -> float:
        medians = [
            float(
                nn[(nn["train_n"] == train_n) & (nn["model_id"] == model_id)][
                    "D"
                ].median()
            )
            for model_id in nn_ids
        ]
        return float(np.median(medians))

    ladder_src = "artifacts/formal/E2_oracle_layers/summary.json"
    seed_src = "artifacts/formal/E3b_vector_mlp/seed_stability.csv"
    ablation_src = "artifacts/formal/E4_robustness/E4a_feature_ablation.csv"
    e4d_src = "artifacts/formal/E4_robustness/summary_e4d.json"
    r2_src = "artifacts/formal/delta_upper_bound_audit/cohort_summary.csv"
    real_src = (
        "artifacts/formal/real_data/nist-6061-t6-fatigue/"
        "real_holdout_results.csv"
    )

    specs = {
        "C001": ClaimSpec(ladder_src, "ladder.Default.J1", ladder["Default"], 5e-10),
        "C002": ClaimSpec(ladder_src, "ladder.L1.J1", ladder["L1"], 5e-10),
        "C003": ClaimSpec(ladder_src, "ladder.L2.J1", ladder["L2"], 5e-10),
        "C004": ClaimSpec(ladder_src, "ladder.L3.J1", ladder["L3"], 5e-10),
        "C005": ClaimSpec(ladder_src, "ladder.L4.J1", ladder["L4"], 5e-10),
        "C006": ClaimSpec(ladder_src, "ladder.L5.J1", ladder["L5"], 5e-10),
        "C007": ClaimSpec(ladder_src, "ladder.L6.J1", ladder["L6"], 5e-10),
        "C008": ClaimSpec(seed_src, "seed42.pooled_J1", seed_value(42), 5e-7),
        "C009": ClaimSpec(seed_src, "seed2026.pooled_J1", seed_value(2026), 5e-7),
        "C010": ClaimSpec(seed_src, "seed3407.pooled_J1", seed_value(3407), 5e-7),
        "C011": ClaimSpec(
            ablation_src, "full.pooled_J1.mean", ablation_value("full"), 5e-7
        ),
        "C012": ClaimSpec(
            ablation_src,
            "scale_quantile.pooled_J1.mean",
            ablation_value("scale_quantile"),
            5e-7,
        ),
        "C013": ClaimSpec(
            ablation_src, "shape.pooled_J1.mean", ablation_value("shape"), 5e-7
        ),
        "C014": ClaimSpec(
            ablation_src, "n.pooled_J1.mean", ablation_value("n"), 5e-7
        ),
        "C015": ClaimSpec(
            e4d_src,
            "E4b_boundary.Vector-MLP-L6.J1",
            per_track["E4b_boundary"]["Vector-MLP-L6"]["J1"],
            5e-15,
        ),
        "C016": ClaimSpec(
            e4d_src,
            "E4c_offgrid.Vector-MLP-L6.J1",
            per_track["E4c_offgrid"]["Vector-MLP-L6"]["J1"],
            5e-15,
        ),
        "C017": ClaimSpec(
            r2_src, "cohort_0.50.n_migrated", int(endpoint["n_migrated"]), 0
        ),
        "C018": ClaimSpec(
            r2_src,
            "cohort_0.50.migration_rate",
            float(endpoint["migration_rate"]),
            5e-7,
        ),
        "C019": ClaimSpec(
            r2_src,
            "ext_best_dist_key_0.5",
            int(endpoint_dist.get("0.5", endpoint_dist.get(0.5, 0))),
            0,
        ),
        "C020": ClaimSpec(
            r2_src,
            "ext_best_dist_key_1.0",
            int(endpoint_dist.get("1.0", endpoint_dist.get(1.0, 0))),
            0,
        ),
        "C021": ClaimSpec(real_src, "default_n7.D.median", default_median(7), 5e-5),
        "C022": ClaimSpec(
            real_src, "default_n10.D.median", default_median(10), 5e-5
        ),
        "C023": ClaimSpec(
            real_src, "default_n20.D.median", default_median(20), 5e-5
        ),
        "C024": ClaimSpec(
            real_src, "nn_n7.median_of_medians", nn_median_of_medians(7), 5e-5
        ),
        "C025": ClaimSpec(
            real_src, "nn_n10.median_of_medians", nn_median_of_medians(10), 5e-5
        ),
        "C026": ClaimSpec(
            real_src, "nn_n20.median_of_medians", nn_median_of_medians(20), 5e-5
        ),
        "C027": ClaimSpec(real_src, "paired_n20", paired_value),
        "C028": ClaimSpec(real_src, "default_n7.SV.mean", default_n7_sv, 5e-4),
        "C029": ClaimSpec(
            real_src, "nn_n7.SV.median_of_15", nn_n7_sv, 5e-4
        ),
        "C030": ClaimSpec(
            "code/config.py",
            "BETA_GRID",
            "-".join(str(x) for x in config.BETA_GRID),
        ),
        "C031": ClaimSpec(
            "code/config.py",
            "GAMMA_OVER_ETA_GRID",
            "-".join(str(x) for x in config.GAMMA_OVER_ETA_GRID),
        ),
        "C032": ClaimSpec(
            "code/config.py", "N_GRID", "-".join(str(x) for x in config.N_GRID)
        ),
        "C033": ClaimSpec(
            "Study/015-study-NN输入表征与样本量机制研究",
            "exists",
            "exists",
        ),
    }
    return specs


def _format_actual(value: Any) -> str:
    if isinstance(value, tuple):
        return "-".join(str(x) for x in value)
    return str(value)


def _resolve_claim_source(paths: AuditPaths, source_file: str) -> Path:
    if source_file.startswith("manuscript/"):
        return paths.paper_md.parent / source_file.removeprefix("manuscript/")
    if source_file.startswith(("artifacts/", "code/")):
        return paths.study_root / source_file
    return paths.repo_root / source_file


def _check_claim_registry(paths: AuditPaths, errors: list[str]) -> None:
    if not paths.claims_csv.exists():
        errors.append(f"claims registry missing: {paths.claims_csv}")
        return

    claims = pd.read_csv(paths.claims_csv, dtype=str, keep_default_na=False)
    required_columns = {
        "claim_id",
        "source_file",
        "source_field",
        "expected_value",
    }
    missing_columns = required_columns - set(claims.columns)
    if missing_columns:
        errors.append(
            "claims registry missing columns: " + ", ".join(sorted(missing_columns))
        )
        return

    claim_ids = claims["claim_id"].tolist()
    actual_id_set = set(claim_ids)
    if len(claim_ids) != len(actual_id_set):
        errors.append("claims registry contains duplicate claim_id values")
    missing = REQUIRED_CLAIM_IDS - actual_id_set
    extra = actual_id_set - REQUIRED_CLAIM_IDS
    if missing:
        errors.append("claims registry missing IDs: " + ", ".join(sorted(missing)))
    if extra:
        errors.append("claims registry has unexpected IDs: " + ", ".join(sorted(extra)))
    if len(claims) != len(REQUIRED_CLAIM_IDS):
        errors.append(
            f"claims registry row count is {len(claims)}, expected "
            f"{len(REQUIRED_CLAIM_IDS)}"
        )

    specs = _claim_specs(paths)
    for claim_id in sorted(REQUIRED_CLAIM_IDS & actual_id_set):
        rows = claims[claims["claim_id"] == claim_id]
        if len(rows) != 1:
            continue
        row = rows.iloc[0]
        spec = specs[claim_id]
        if row["source_file"] != spec.source_file:
            errors.append(
                f"{claim_id} source_file mismatch: {row['source_file']!r} != "
                f"{spec.source_file!r}"
            )
        if row["source_field"] != spec.source_field:
            errors.append(
                f"{claim_id} source_field mismatch: {row['source_field']!r} != "
                f"{spec.source_field!r}"
            )

        source_path = _resolve_claim_source(paths, spec.source_file)
        if not source_path.exists():
            errors.append(f"{claim_id} source does not exist: {spec.source_file}")

        expected = row["expected_value"].strip()
        if spec.tolerance is not None:
            try:
                expected_number = float(expected)
            except ValueError:
                errors.append(f"{claim_id} expected_value is not numeric: {expected!r}")
                continue
            if abs(float(spec.actual) - expected_number) > spec.tolerance:
                errors.append(
                    f"{claim_id} value mismatch: registry={expected_number}, "
                    f"artifact={spec.actual}, tolerance={spec.tolerance}"
                )
        elif expected != _format_actual(spec.actual):
            errors.append(
                f"{claim_id} value mismatch: registry={expected!r}, "
                f"artifact={_format_actual(spec.actual)!r}"
            )


def _check_status_terms(path: Path, label: str, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"{label} missing: {path}")
        return
    text = path.read_text(encoding="utf-8")
    for stale in STALE_STATUS_TERMS:
        if stale in text:
            errors.append(f'{label} contains stale status "{stale}"')


def audit_manuscript(
    *,
    study_root: str | Path | None = None,
    repo_root: str | Path | None = None,
    claims_csv: str | Path | None = None,
    figure_checklist_csv: str | Path | None = None,
    reference_checklist_csv: str | Path | None = None,
    submission_checklist_md: str | Path | None = None,
    figure_index_md: str | Path | None = None,
    paper_md: str | Path | None = None,
    supplementary_md: str | Path | None = None,
    run_git_check: bool = False,
    verbose: bool = False,
) -> list[str]:
    """Return every audit error; an empty list means the audit passed."""

    paths = AuditPaths.defaults().with_overrides(
        study_root=study_root,
        repo_root=repo_root,
        claims_csv=claims_csv,
        figure_checklist_csv=figure_checklist_csv,
        reference_checklist_csv=reference_checklist_csv,
        submission_checklist_md=submission_checklist_md,
        figure_index_md=figure_index_md,
        paper_md=paper_md,
        supplementary_md=supplementary_md,
    )
    errors: list[str] = []

    try:
        _check_claim_registry(paths, errors)
    except Exception as exc:  # fail closed on unreadable or malformed evidence
        errors.append(f"claim recomputation failed: {type(exc).__name__}: {exc}")

    formal = paths.study_root / "artifacts" / "formal"
    figure_dir = paths.paper_md.parent / "figures"

    generated_figures = [
        "fig6_feature_ablation",
        "fig7_boundary_offgrid",
        "fig8_upper_bound_audit",
        "fig9_real_data_comparison",
        "fig_s1_crossfit",
        "fig_s2_beta_profile",
        "fig_s3_seed_stability",
        "fig_s4_ablation_folds",
        "fig_s5_boundary_folds",
        "fig_s6_upper_bound_dist",
        "fig_s7_nn_15model_dist",
        "fig_s8_support_set",
    ]
    for name in generated_figures:
        for extension in ("png", "svg", "pdf"):
            path = figure_dir / f"{name}.{extension}"
            if not path.exists() or path.stat().st_size <= 200:
                errors.append(f"generated figure missing or empty: {path.name}")

    _check_status_terms(paths.figure_index_md, "figure-index", errors)
    _check_status_terms(paths.figure_checklist_csv, "figure-checklist", errors)
    _check_status_terms(paths.submission_checklist_md, "submission-checklist", errors)

    if not paths.reference_checklist_csv.exists():
        errors.append(f"reference checklist missing: {paths.reference_checklist_csv}")
    else:
        references = pd.read_csv(
            paths.reference_checklist_csv, dtype=str, keep_default_na=False
        )
        expected_dois = {
            "[3]": "10.1142/S0219455423500852",
            "[4]": "10.12068/j.issn.1005-3026.2025.20240194",
            "[7]": "10.1016/j.probengmech.2025.103828",
        }
        for reference, doi in expected_dois.items():
            rows = references[references["ref_number"] == reference]
            if len(rows) != 1:
                errors.append(f"reference {reference} must appear exactly once")
                continue
            row = rows.iloc[0]
            if "已核实" not in row["status"]:
                errors.append(f"reference {reference} is not verified")
            if row["doi"] != doi:
                errors.append(
                    f"reference {reference} DOI mismatch: {row['doi']!r} != {doi!r}"
                )

    texts: dict[str, str] = {}
    for label, path in (
        ("paper", paths.paper_md),
        ("supplementary", paths.supplementary_md),
    ):
        if not path.exists():
            errors.append(f"{label} missing: {path}")
            texts[label] = ""
        else:
            texts[label] = path.read_text(encoding="utf-8")

    for label, text in texts.items():
        for stale in (
            "-Spread",
            "-Shape",
            "理论上限",
            "边际递减",
            "单侧两样本KS",
            "正文不可获得",
            "待用户补充",
        ):
            if stale in text:
                errors.append(f'{label} contains stale term "{stale}"')

    for number in range(1, 10):
        if f"Figure {number}" not in texts["paper"]:
            errors.append(f"paper does not cite Figure {number}")
    for number in range(1, 9):
        if (
            f"Figure S{number}" not in texts["supplementary"]
            and f"S{number}:" not in texts["supplementary"]
        ):
            errors.append(f"supplementary does not cite Figure S{number}")

    if "每个beta各300" in texts["supplementary"]:
        errors.append("supplementary contains stale per-beta count")
    if (
        "5×3×20=300" not in texts["supplementary"]
        and "5x3x20=300" not in texts["supplementary"]
    ):
        errors.append("supplementary lacks the correct 5x3x20=300 count")

    try:
        trend = pd.read_csv(
            formal / "E2_beta_profile_audit" / "trend_summary.csv"
        )
        rhos = trend[
            (trend["metric"] == "local_gradient_slope")
            & trend["scope"].str.startswith("n=")
        ]
        expected_rhos = {"n=7": -0.463, "n=10": -0.495, "n=20": -0.529}
        if len(rhos) != 3:
            errors.append(f"S2 per-n Spearman row count is {len(rhos)}, expected 3")
        for scope, expected in expected_rhos.items():
            rows = rhos[rhos["scope"] == scope]
            if len(rows) != 1 or abs(float(rows.iloc[0]["spearman_rho"]) - expected) >= 0.05:
                errors.append(f"S2 Spearman rho mismatch for {scope}")
    except Exception as exc:
        errors.append(f"S2 recomputation failed: {type(exc).__name__}: {exc}")

    try:
        comparison = pd.read_csv(
            formal / "E4_robustness" / "E4d_paired_comparisons_by_model.csv"
        )
        if len(comparison) != 90:
            errors.append(f"S5 row count is {len(comparison)}, expected 90")
        default_rows = comparison[comparison["reference_model"] == "Default"]
        if len(default_rows) != 30:
            errors.append(
                f"S5 Default-reference row count is {len(default_rows)}, expected 30"
            )
    except Exception as exc:
        errors.append(f"S5 recomputation failed: {type(exc).__name__}: {exc}")

    study15 = paths.repo_root / "Study" / "015-study-NN输入表征与样本量机制研究"
    if not study15.exists():
        errors.append(f"Study1.5 path missing: {study15}")

    if run_git_check:
        result = subprocess.run(
            ["git", "diff", "--check", "a52c3023..HEAD"],
            cwd=paths.repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0 or result.stdout.strip():
            errors.append("git diff --check a52c3023..HEAD failed")

    if verbose:
        if errors:
            print(f"{len(errors)} AUDIT ERROR(S):")
            for error in errors:
                print(f"  FAIL: {error}")
        else:
            print("ALL AUDIT CHECKS PASSED")
    return errors


def main() -> int:
    errors = audit_manuscript(verbose=True)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
