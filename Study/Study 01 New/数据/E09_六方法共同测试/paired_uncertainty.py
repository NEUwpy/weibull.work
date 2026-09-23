"""Fixed-design paired Monte Carlo interval for AMDM's J1 improvement."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
df = pd.read_csv(HERE / "per_sample.csv.gz")
names = ["AMDM", "MDM-0.1", "MDM-opt-n"]
wide = df[df.method.isin(names)].pivot(index=["cell_id", "repeat_id"], columns="method", values="score")
assert wide.shape == (4800, 3) and not wide.isna().any().any()
arr = wide[names].to_numpy().reshape(48, 100, 3)
rng = np.random.default_rng(20260923)
draws = 2000
idx = rng.integers(0, 100, size=(draws, 48, 100))
sampled = np.take_along_axis(arr[None, :, :, :], idx[:, :, :, None], axis=2)
j = np.sqrt(sampled.mean(axis=(1, 2)))
out = {"bootstrap": "paired repeat resampling within each of the 48 fixed cells",
       "draws": draws, "seed": 20260923, "methods": names,
       "comparisons": {}}
for k, name in [(1, "MDM-0.1"), (2, "MDM-opt-n")]:
    absolute = j[:, k] - j[:, 0]
    relative = 1 - j[:, 0] / j[:, k]
    out["comparisons"][name] = {
        "J1_absolute_reduction": float(np.sqrt(arr[:, :, k].mean()) - np.sqrt(arr[:, :, 0].mean())),
        "J1_absolute_reduction_CI95": [float(x) for x in np.quantile(absolute, [.025, .975])],
        "J1_relative_reduction": float(1 - np.sqrt(arr[:, :, 0].mean()) / np.sqrt(arr[:, :, k].mean())),
        "J1_relative_reduction_CI95": [float(x) for x in np.quantile(relative, [.025, .975])],
    }
(HERE / "paired_interval.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(out["comparisons"], indent=2))
