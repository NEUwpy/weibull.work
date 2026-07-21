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


def test_formal_execute_dispatches_a_e1_to_run_a_e1_staged(monkeypatch):
    from unittest.mock import MagicMock
    script_dir = SCRIPT.parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    import run_study02a
    fake_staged = MagicMock(return_value={"dispatch": "run_a_e1_staged"})
    fake_module = MagicMock(return_value={"dispatch": "run_formal_module"})
    monkeypatch.setattr(run_study02a, "run_a_e1_staged", fake_staged)
    monkeypatch.setattr(run_study02a, "run_formal_module", fake_module)
    monkeypatch.setattr(
        "sys.argv",
        ["run_study02a.py", "formal-execute", "--module", "A-E1", "--run-id", "test-run",
         "--artifact-root", "artifacts/runs", "--cache-root", "artifacts/cache",
         "--max-fits", "10", "--owner-id", "test-owner"],
    )
    run_study02a.main()
    fake_staged.assert_called_once()
    fake_module.assert_not_called()
    kwargs = fake_staged.call_args.kwargs
    assert kwargs["module_id"] == "A-E1"
    assert kwargs["run_id"] == "test-run"
    assert str(kwargs["artifact_root"]).endswith("artifacts/runs")
    assert str(kwargs["cache_root"]).endswith("artifacts/cache")
    assert kwargs["owner_id"] == "test-owner"
    assert kwargs["max_fits"] == 10


def test_formal_execute_dispatches_a_e3_a_e2_to_run_module(monkeypatch):
    from unittest.mock import MagicMock
    script_dir = SCRIPT.parent
    if str(script_dir) not in sys.path:
        sys.path.insert(0, str(script_dir))
    import run_study02a
    for mod in ("A-E3", "A-E2"):
        fake_staged = MagicMock(return_value={"dispatch": "run_a_e1_staged"})
        fake_module = MagicMock(return_value={"dispatch": "run_formal_module"})
        monkeypatch.setattr(run_study02a, "run_a_e1_staged", fake_staged)
        monkeypatch.setattr(run_study02a, "run_formal_module", fake_module)
        monkeypatch.setattr(
            "sys.argv",
            ["run_study02a.py", "formal-execute", "--module", mod, "--run-id", "test-run",
             "--artifact-root", ".", "--cache-root", "."],
        )
        run_study02a.main()
        fake_staged.assert_not_called()
        fake_module.assert_called_once()
        call_kwargs = fake_module.call_args.kwargs
        assert call_kwargs["module_id"] == mod
