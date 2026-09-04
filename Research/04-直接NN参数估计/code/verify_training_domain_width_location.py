"""Independent, analyzer-free verification of key width/location summaries."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve()
RESEARCH_ROOT = HERE.parents[1]
RUN_ROOT = RESEARCH_ROOT / "artifacts" / "training_domain_width_location_v1"
ANALYSIS_DIR = RUN_ROOT / "analysis"
RUNNER = HERE.with_name("run_training_domain_width_location.py")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def metrics(group: pd.DataFrame) -> dict[str, float]:
    valid = group[group["status"].eq("success")]
    return {
        "J1": float(np.sqrt(group["loss_primary"].to_numpy(float).mean())),
        "beta_rmse": float(np.sqrt(np.square(valid["beta_rel_error"].to_numpy(float)).mean())),
        "eta_rmse": float(np.sqrt(np.square(valid["eta_rel_error"].to_numpy(float)).mean())),
        "gamma_rmse": float(np.sqrt(np.square(valid["gamma_rel_error"].to_numpy(float)).mean())),
        "x0.95_rmse": float(np.sqrt(np.square(valid["x0.95_rel_error"].to_numpy(float)).mean())),
        "failure_rate": float(1 - len(valid) / len(group)),
    }


def compare_family(frame: pd.DataFrame, table: pd.DataFrame, domain_ids: list[str],
                   selector) -> tuple[dict, float]:
    recomputed = {}
    max_difference = 0.0
    for policy in ("fixed_total", "fixed_density"):
        for domain_id in domain_ids:
            group = selector(frame[(frame["budget_policy"] == policy) & (frame["domain_id"] == domain_id)])
            values = metrics(group)
            row = table[(table["budget_policy"] == policy) & (table["domain_id"] == domain_id)].iloc[0]
            for name, value in values.items():
                max_difference = max(max_difference, abs(value - float(row[name])))
            recomputed[f"{policy}|{domain_id}"] = values
    return recomputed, max_difference


def main() -> None:
    manifest = json.loads((RUN_ROOT / "manifest.json").read_text(encoding="utf-8"))
    frame = pd.read_csv(RUN_ROOT / "per_sample_results.csv.gz", low_memory=False)
    width_table = pd.read_csv(ANALYSIS_DIR / "width_common_beta_summary.csv")
    location_table = pd.read_csv(ANALYSIS_DIR / "location_aligned_summary.csv")

    width, width_diff = compare_family(
        frame, width_table, manifest["effect_families"]["width"],
        lambda group: group[group["beta"].between(2.5, 3.5)],
    )
    location, location_diff = compare_family(
        frame, location_table, manifest["effect_families"]["location"],
        lambda group: group[(group["beta"] - (group["train_beta_min"] + group["train_beta_max"]) / 2).between(-0.5, 0.5)],
    )

    scenario_keys = []
    reference = None
    keys_equal = True
    for (policy, domain), group in frame.groupby(["budget_policy", "domain_id"], sort=True):
        keys = group[["beta", "gamma_over_eta", "n", "repeat_id"]].to_numpy()
        if reference is None:
            reference = keys
        else:
            keys_equal = keys_equal and np.array_equal(reference, keys)
        scenario_keys.append({"budget_policy": policy, "domain_id": domain, "rows": len(keys)})

    allocations_ok = True
    for spec in manifest["scenarios"]:
        values = list(spec["cell_allocation"].values())
        allocations_ok &= sum(values) == int(spec["n_train_per_n"])
        if spec["budget_policy"] == "fixed_total":
            allocations_ok &= sum(values) == 12_000 and max(values) - min(values) <= 1
        else:
            allocations_ok &= set(values) == {300}

    source_values = manifest["failure_penalty_contract"]["source_values_by_n"].values()
    checks = {
        "row_count": len(frame) == 1_512_000 == int(manifest["validation"]["n_rows"]),
        "model_count": int(manifest["validation"]["n_models"]) == 48,
        "shared_test_keys_exact": bool(keys_equal),
        "training_allocations": bool(allocations_ok),
        "failure_penalty": math_isclose(float(manifest["failure_penalty"]), max(float(x) for x in source_values)),
        "runner_sha256": sha256_file(RUNNER) == manifest["code_sha256"],
        "width_summary": width_diff < 1e-12,
        "location_summary": location_diff < 1e-12,
    }
    result = {
        "status": "pass" if all(checks.values()) else "fail",
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "max_abs_difference": {"width": width_diff, "location": location_diff},
        "scenario_keys": scenario_keys,
        "independent_width_metrics": width,
        "independent_location_metrics": location,
    }
    path = RUN_ROOT / "independent_verification.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if result["status"] != "pass":
        raise RuntimeError(json.dumps(checks))
    print(f"INDEPENDENT_VERIFICATION_PASS width_diff={width_diff:.3g} location_diff={location_diff:.3g}")


def math_isclose(left: float, right: float) -> bool:
    return abs(left - right) <= 1e-12 * max(1.0, abs(left), abs(right))


if __name__ == "__main__":
    main()
