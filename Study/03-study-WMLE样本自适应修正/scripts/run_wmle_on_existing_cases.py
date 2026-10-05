"""Re-run production WMLE on the existing W(beta, eta, gamma) case samples.

This keeps the historical sample realization intact where a workbook or CSV is
available.  The cases are summarized separately from diagnostic_grid_v1 because
their seed namespaces and source protocols differ.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


TASK_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = TASK_DIR / "evidence" / "source-task"
sys.path.insert(0, str(REPO_ROOT / "python"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from studies.common.runner import run_method  # noqa: E402
from run_wmle_diagnostic_grid import sample_features, write_csv  # noqa: E402


CASES = (
    {"case_id": "W2_1000_3000", "beta": 2.0, "eta": 1000.0, "gamma": 3000.0, "source": "top_level_csv", "source_path": "samples.csv", "seed_namespace": 20260825, "sizes": (7, 15)},
    {"case_id": "W2_1000_500", "beta": 2.0, "eta": 1000.0, "gamma": 500.0, "source": "xlsx", "source_path": "260826-W2,1000,500/W(2,1000,500).xlsx", "seed_namespace": 20260826, "sizes": (7, 15)},
    {"case_id": "W2_1000_1000", "beta": 2.0, "eta": 1000.0, "gamma": 1000.0, "source": "xlsx", "source_path": "260921-W2参数估计案例/W(2,1000,1000)/2,1000,1000.xlsx", "seed_namespace": 20260921, "sizes": (7, 15, 30)},
    {"case_id": "W3_1000_500", "beta": 3.0, "eta": 1000.0, "gamma": 500.0, "source": "xlsx", "source_path": "260907-W3参数估计案例/W(3,1000,500)/3,1000,500.xlsx", "seed_namespace": 20260907, "sizes": (7, 15)},
    {"case_id": "W3_1000_1000", "beta": 3.0, "eta": 1000.0, "gamma": 1000.0, "source": "xlsx", "source_path": "260907-W3参数估计案例/W(3,1000,1000)/3,1000,1000.xlsx", "seed_namespace": 20260907, "sizes": (7, 15)},
    {"case_id": "W3_1000_3000", "beta": 3.0, "eta": 1000.0, "gamma": 3000.0, "source": "xlsx", "source_path": "260907-W3参数估计案例/W(3,1000,3000)/3,1000,3000.xlsx", "seed_namespace": 20260907, "sizes": (7, 15)},
    {"case_id": "W5_1000_500", "beta": 5.0, "eta": 1000.0, "gamma": 500.0, "source": "xlsx", "source_path": "260906-W5参数估计案例/W(5,1000,500)/5,1000,500.xlsx", "seed_namespace": 20260906, "sizes": (7, 15)},
    {"case_id": "W5_1000_3000", "beta": 5.0, "eta": 1000.0, "gamma": 3000.0, "source": "xlsx", "source_path": "260906-W5参数估计案例/W(5,1000,3000)/5,1000,3000.xlsx", "seed_namespace": 20260906, "sizes": (7, 15)},
)


def load_csv_samples(path: Path) -> dict[int, list[float]]:
    df = pd.read_csv(path)
    output: dict[int, list[float]] = defaultdict(list)
    for _, row in df.sort_values(["sample_size", "sample_id", "observation_index"]).iterrows():
        output[int(row["sample_size"]) * 1000 + int(row["sample_id"])] .append(float(row["value"]))
    return dict(output)


def load_xlsx_samples(path: Path, sizes: tuple[int, ...]) -> dict[int, list[float]]:
    xl = pd.ExcelFile(path)
    output: dict[int, list[float]] = {}
    for sheet_index, n in enumerate(sizes):
        # The W(2,1000,1000) workbook alternates sample and summary sheets;
        # the other case workbooks contain the sample sheets consecutively.
        sheet_ref = (0, 2, 4)[sheet_index] if len(sizes) == 3 else sheet_index
        df = pd.read_excel(path, sheet_name=xl.sheet_names[sheet_ref], header=0)
        sample_id = 0
        for _, row in df.iterrows():
            nums = pd.to_numeric(row.iloc[1:], errors="coerce").dropna().to_numpy(dtype=float)
            if len(nums) < n:
                continue
            values = np.sort(nums[-n:])
            sample_id += 1
            output[n * 1000 + sample_id] = values.tolist()
        if sample_id != 50:
            raise RuntimeError(f"{path} n={n}: expected 50 samples, parsed {sample_id}")
    return output


def main() -> None:
    out_dir = TASK_DIR / "results" / "existing_cases_v1"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    inventory: list[dict] = []
    for case in CASES:
        source_path = SOURCE_ROOT / case["source_path"]
        if case["source"] == "top_level_csv":
            samples = load_csv_samples(source_path)
        else:
            samples = load_xlsx_samples(source_path, case["sizes"])
        inventory.append({**case, "source_path": str(source_path), "sample_count": len(samples), "source_exists": source_path.exists()})
        for n in case["sizes"]:
            for sample_id in range(1, 51):
                sample = np.asarray(samples[n * 1000 + sample_id], dtype=float)
                result = run_method("wmle", sample)
                extra = result.get("extra") or {}
                solution = extra.get("solution_info") or {}
                beta_hat, eta_hat, gamma_hat = result.get("beta_hat"), result.get("eta_hat"), result.get("gamma_hat")
                features = sample_features(sample)
                row = {**case, "source_path": str(source_path), "sample_size": n, "sample_id": sample_id, "beta_hat": beta_hat, "eta_hat": eta_hat, "gamma_hat": gamma_hat, "converged": bool(result.get("converged")), **features, "solution_status": solution.get("status") or extra.get("raw_status") or ("ok" if result.get("converged") else "failed"), "objective": solution.get("objective")}
                if row["converged"] and all(v is not None for v in (beta_hat, eta_hat, gamma_hat)):
                    row.update({"rel_error_beta": (beta_hat - case["beta"]) / case["beta"], "rel_error_eta": (eta_hat - case["eta"]) / case["eta"], "rel_error_gamma": (gamma_hat - case["gamma"]) / case["eta"]})
                    row["abs_rel_error_max"] = max(abs(row["rel_error_beta"]), abs(row["rel_error_eta"]), abs(row["rel_error_gamma"]))
                else:
                    row.update({"rel_error_beta": None, "rel_error_eta": None, "rel_error_gamma": None, "abs_rel_error_max": None})
                rows.append(row)

    summary: list[dict] = []
    for case in CASES:
        for n in case["sizes"]:
            group = [r for r in rows if r["case_id"] == case["case_id"] and r["sample_size"] == n]
            valid = [r for r in group if r["abs_rel_error_max"] is not None]
            out = {"case_id": case["case_id"], "beta": case["beta"], "eta": case["eta"], "gamma": case["gamma"], "sample_size": n, "n_total": len(group), "n_valid": len(valid), "failure_rate": (len(group)-len(valid))/len(group)}
            for name in ("beta", "eta", "gamma"):
                values = np.asarray([r[f"rel_error_{name}"] for r in valid], dtype=float)
                out[f"rel_bias_{name}"] = float(np.mean(values)) if len(values) else None
                out[f"rel_rmse_{name}"] = float(np.sqrt(np.mean(values**2))) if len(values) else None
                out[f"rel_p95_abs_{name}"] = float(np.percentile(np.abs(values), 95)) if len(values) else None
            out["extreme_rate_ge_50pct"] = float(np.mean([r["abs_rel_error_max"] >= 0.5 for r in valid])) if valid else None
            out["extreme_rate_ge_100pct"] = float(np.mean([r["abs_rel_error_max"] >= 1.0 for r in valid])) if valid else None
            summary.append(out)

    write_csv(out_dir / "wmle_existing_cases_long.csv", rows)
    write_csv(out_dir / "wmle_existing_cases_summary.csv", summary)
    write_csv(out_dir / "case_inventory.csv", inventory)
    (out_dir / "manifest.json").write_text(json.dumps({"protocol": "existing_cases_v1", "cases": inventory, "note": "Existing case realizations are kept separate from diagnostic_grid_v1 because source seed namespaces and workbook protocols differ."}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"cases={len(CASES)} rows={len(rows)}")
    for row in summary:
        print(row["case_id"], "n", row["sample_size"], "valid", f"{row['n_valid']}/{row['n_total']}", "failure", row["failure_rate"], "extreme50", row["extreme_rate_ge_50pct"])


if __name__ == "__main__":
    main()
