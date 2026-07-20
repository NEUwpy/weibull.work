from pathlib import Path
import json
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究" / "code" / "run_study02a.py"


def test_validate_config_cli_reports_frozen_hashes():
    result = subprocess.run([sys.executable, str(SCRIPT), "validate-config"], cwd=REPO_ROOT, check=True, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    assert payload["status"] == "frozen_oracle_approved"
    assert payload["screening_formal_seed_overlap"] == []


def test_expand_matrix_cli_writes_sealed_manifest(tmp_path):
    output = tmp_path / "matrix"
    subprocess.run([sys.executable, str(SCRIPT), "expand-matrix", "--output", str(output)], cwd=REPO_ROOT, check=True)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["test_state"] == "sealed"
    assert manifest["total_fits"] == 820
    assert (output / "experiment_matrix.csv").exists()


def test_pilot_cli_never_opens_test_data(tmp_path):
    output = tmp_path / "pilot-cli"
    subprocess.run([
        sys.executable, str(SCRIPT), "pilot", "--output", str(output), "--run-id", "pilot-cli",
        "--points", "4", "--repeats", "1", "--n", "5", "--ledger", str(tmp_path / "ledger.jsonl"),
        "--skip-methods", "--skip-train-smoke",
    ], cwd=REPO_ROOT, check=True, capture_output=True, text=True)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["test_state"] == "sealed"
    assert manifest["total_samples"] == 4
