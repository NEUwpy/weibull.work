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
import pandas as pd

from study02a.pilot import project_formal_runtime, run_pilot


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


def test_runtime_projection_uses_matrix_sizes_batches_epochs_and_headroom():
    matrix = pd.DataFrame([
        {"training_size": 1000, "optimizer": "adam_historical"},
        {"training_size": -1, "optimizer": "selected:A-E3_optimizer"},
    ])
    settings = {
        "formal_max_epochs": 10,
        "unknown_training_size": 4000,
        "unknown_optimizer_batch_size": 128,
        "parallel_workers": 4,
        "wall_time_limit_hours": 1,
        "runtime_headroom_factor": 2.0,
    }
    result = project_formal_runtime(matrix, {32: 0.1, 128: 0.2, 512: 0.3}, settings)
    expected = ((32 * 10 * 0.1) + (32 * 10 * 0.2)) * 2.0
    assert result["projected_serial_seconds"] == expected
    assert result["projected_wall_seconds"] == expected / 4
    assert result["runtime_gate_pass"] is True
