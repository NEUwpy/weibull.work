"""Generate 200 reproducible sorted samples for the temporary Weibull task."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np


WORK_DIR = Path(__file__).resolve().parent
REPO_ROOT = WORK_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT / "python"))

from studies.common.sample import generate_sample  # noqa: E402


BETA = 2.0
ETA = 1000.0
GAMMA = 3000.0
SAMPLE_SIZE = 7
REPEATS = 200
SEED_NAMESPACE = 20260826


rows: list[list[float | int]] = []
for repeat_id in range(REPEATS):
    sample = generate_sample(
        BETA,
        ETA,
        GAMMA,
        SAMPLE_SIZE,
        repeat_id,
        seed=SEED_NAMESPACE,
    )
    if sample.shape != (SAMPLE_SIZE,):
        raise RuntimeError(f"Unexpected sample shape for repeat {repeat_id}: {sample.shape}")
    if not np.all(np.diff(sample) >= 0):
        raise RuntimeError(f"Sample {repeat_id + 1} is not sorted")
    if float(sample[0]) < GAMMA:
        raise RuntimeError(f"Sample {repeat_id + 1} is below the location parameter")
    rows.append([repeat_id + 1, repeat_id, *[float(value) for value in sample]])

payload = {
    "parameters": {
        "distribution": "W(2,1000,3000)",
        "beta": BETA,
        "eta": ETA,
        "gamma": GAMMA,
        "sample_size": SAMPLE_SIZE,
        "groups": REPEATS,
        "seed_namespace": SEED_NAMESPACE,
        "sorted": True,
    },
    "headers": ["样本编号", "repeat_id", *[f"x_({index})" for index in range(1, 8)]],
    "rows": rows,
}

output_path = WORK_DIR / "samples_200.json"
output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

matrix = np.asarray([row[2:] for row in rows], dtype=float)
print(
    json.dumps(
        {
            "output": str(output_path),
            "groups": len(rows),
            "minimum": float(matrix.min()),
            "maximum": float(matrix.max()),
            "mean": float(matrix.mean()),
            "x1_mean": float(matrix[:, 0].mean()),
            "x7_mean": float(matrix[:, -1].mean()),
        },
        ensure_ascii=False,
    )
)
