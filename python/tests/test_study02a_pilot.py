from pathlib import Path
import json
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
PYTHON_ROOT = REPO_ROOT / "python"
for path in (STUDY_CODE, PYTHON_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from study02a.config import load_frozen_config
from study02a.pilot import run_pilot


def test_small_pilot_keeps_test_sealed_and_writes_auditable_outputs(tmp_path):
    config = load_frozen_config(STUDY_ROOT)
    output = tmp_path / "pilot-small"
    result = run_pilot(
        config,
        output,
        run_id="pilot-small",
        code_version="unit-test",
        points=4,
        repeats=1,
        n_values=[5],
        run_methods=False,
        train_smoke=False,
    )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert result["total_samples"] == 4
    assert manifest["test_state"] == "sealed"
    assert manifest["seed_namespace"] == 320204
    assert (output / "pilot_samples.csv.gz").exists()
    assert (output / "resource_estimate.json").exists()
    assert (output / "run_log.txt").exists()
    estimate = result["resource_estimate"]
    assert estimate["estimated_formal_result_rows"] == 768000
    assert estimate["estimated_formal_artifact_bytes"] > 0
    assert isinstance(estimate["resource_gate_pass"], bool)
