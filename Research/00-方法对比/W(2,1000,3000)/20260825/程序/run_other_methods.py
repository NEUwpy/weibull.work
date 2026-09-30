"""Run the four non-MDM production estimators on the frozen 100 samples.

Display-name mapping follows the user's handwritten result-table labels:
LS -> LSE, LRE -> LRE, WMLM -> WMLE, MLM -> MLE.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


PROGRAM_DIR = Path(__file__).resolve().parent
TASK_DIR = PROGRAM_DIR.parent / '结果' / '复算输出'
ROOT = PROGRAM_DIR / '依赖快照'
PYTHON_DIR = ROOT / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from studies.common.metrics import aggregate_standard_metrics  # noqa: E402
from studies.common.runner import run_method  # noqa: E402


TRUE_BETA = 2.0
TRUE_ETA = 1000.0
TRUE_GAMMA = 3000.0
METHODS = (
    ("lse", "LS", "LSE"),
    ("lre", "LRE", "LRE"),
    ("wmle", "WMLM", "WMLE"),
    ("mle", "MLM", "MLE"),
)


def load_samples() -> dict[tuple[int, int], list[float]]:
    grouped: dict[tuple[int, int], list[tuple[int, float]]] = defaultdict(list)
    with (TASK_DIR / "samples.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (int(row["sample_size"]), int(row["sample_id"]))
            grouped[key].append((int(row["observation_index"]), float(row["value"])))

    samples = {
        key: [value for _, value in sorted(observations)]
        for key, observations in grouped.items()
    }
    expected = {(n, sample_id) for n in (7, 15) for sample_id in range(1, 51)}
    if set(samples) != expected:
        raise RuntimeError(f"Sample keys mismatch: got {len(samples)}, expected {len(expected)}")
    for (n, sample_id), sample in samples.items():
        if len(sample) != n:
            raise RuntimeError(f"Sample n={n}, id={sample_id} has {len(sample)} values")
    return samples


def git_version() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def main() -> None:
    samples = load_samples()
    rows: list[dict] = []

    for n in (7, 15):
        for sample_id in range(1, 51):
            sample = samples[(n, sample_id)]
            for method_id, display_name, implementation_name in METHODS:
                result = run_method(method_id, sample)
                extra = result.get("extra") or {}
                solution_info = extra.get("solution_info") or {}
                solution_status = (
                    solution_info.get("status")
                    or extra.get("raw_status")
                    or ("ok" if result.get("converged") else extra.get("error", "failed"))
                )
                rows.append(
                    {
                        "beta": TRUE_BETA,
                        "eta": TRUE_ETA,
                        "gamma": TRUE_GAMMA,
                        "sample_size": n,
                        "sample_id": sample_id,
                        "repeat_id": sample_id - 1,
                        "display_name": display_name,
                        "method_id": result["method_id"],
                        "implementation_name": implementation_name,
                        "beta_hat": result.get("beta_hat"),
                        "eta_hat": result.get("eta_hat"),
                        "gamma_hat": result.get("gamma_hat"),
                        "r_squared": result.get("r_squared"),
                        "converged": bool(result.get("converged")),
                        "sample_min": min(sample),
                        "runtime_seconds": result.get("time"),
                        "solution_status": solution_status,
                        "solution_info": json.dumps(solution_info, ensure_ascii=False, sort_keys=True),
                    }
                )

    fieldnames = list(rows[0])
    with (TASK_DIR / "other_method_estimates.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summaries: list[dict] = []
    for n in (7, 15):
        for method_id, display_name, implementation_name in METHODS:
            group = [
                row for row in rows
                if row["sample_size"] == n and row["method_id"] == method_id
            ]
            summary = aggregate_standard_metrics(group)
            summaries.append(
                {
                    "sample_size": n,
                    "display_name": display_name,
                    "method_id": method_id,
                    "implementation_name": implementation_name,
                    **summary,
                }
            )

    summary_fields = list(summaries[0])
    with (TASK_DIR / "other_method_summary.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(summaries)

    manifest = {
        "task": "other production estimators on frozen W(2,1000,3000) samples",
        "true_parameters": {"beta": TRUE_BETA, "eta": TRUE_ETA, "gamma": TRUE_GAMMA},
        "sample_source": "samples.csv generated by run_task.py",
        "sample_sizes": [7, 15],
        "samples_per_size": 50,
        "method_label_mapping": {
            display_name: {"method_id": method_id, "implementation": implementation_name}
            for method_id, display_name, implementation_name in METHODS
        },
        "code_version": git_version(),
        "row_count": len(rows),
        "metric_contract": "python/studies/common/metrics.py aggregate_standard_metrics",
    }
    (TASK_DIR / "other_method_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"rows={len(rows)} summaries={len(summaries)}")
    for summary in summaries:
        print(
            f"n={summary['sample_size']} {summary['display_name']}->{summary['method_id']} "
            f"valid={summary['n_valid']}/{summary['n_total']} "
            f"gamma_rmse={summary.get('rmse_gamma')}"
        )


if __name__ == "__main__":
    main()
