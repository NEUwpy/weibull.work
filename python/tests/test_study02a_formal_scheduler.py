from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
CODE = STUDY_ROOT / "code"
MATRIX = STUDY_ROOT / "artifacts" / "pilot" / "G3-matrix" / "experiment_matrix.csv"
SCRIPT = CODE / "run_study02a.py"
sys.path.insert(0, str(CODE))
sys.path.insert(0, str(ROOT / "python"))


def _create(tmp_path: Path, **overrides):
    from study02a.formal_scheduler import materialize_run

    kwargs = {
        "study_root": STUDY_ROOT,
        "matrix_path": MATRIX,
        "module_id": "A-E1",
        "run_id": "G3-AE1-plan-v1",
        "artifact_root": tmp_path / "artifacts",
        "cache_root": tmp_path / "cache",
        "code_commit": "a" * 40,
        "predecessor": None,
    }
    kwargs.update(overrides)
    return materialize_run(**kwargs)


def test_exact_matrix_and_a_e1_plan_are_canonical(tmp_path):
    result = _create(tmp_path)
    run_dir = Path(result["run_dir"])
    rows = [json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 349
    assert [row["fit_id"] for row in rows] == [f"G3-fit-{i:04d}" for i in range(349)]
    assert {row["module_id"] for row in rows} == {"A-E1"}
    assert all(row["test_access_count"] == 0 for row in rows)
    assert all(len(row["training_cache_key"]) == len(row["validation_cache_key"]) == 64 for row in rows)
    payload = (run_dir / "plan.jsonl").read_bytes()
    assert payload.endswith(b"\n")
    assert hashlib.sha256(payload).hexdigest() == result["plan_sha256"]


def test_downstream_without_verified_predecessor_writes_nothing(tmp_path):
    with pytest.raises(ValueError, match="predecessor"):
        _create(tmp_path, module_id="A-E3", run_id="G3-AE3-plan-v1")
    assert not (tmp_path / "artifacts" / "A-E3" / "G3-AE3-plan-v1").exists()


def test_same_run_is_idempotent_but_changed_binding_fails_closed(tmp_path):
    first = _create(tmp_path)
    second = _create(tmp_path)
    assert second["status"] == "existing_exact"
    assert second["plan_sha256"] == first["plan_sha256"]
    with pytest.raises(ValueError, match="existing run"):
        _create(tmp_path, code_commit="b" * 40)


def test_plan_or_state_tampering_is_detected(tmp_path):
    result = _create(tmp_path)
    run_dir = Path(result["run_dir"])
    (run_dir / "plan.jsonl").write_bytes((run_dir / "plan.jsonl").read_bytes() + b"{}\n")
    from study02a.formal_scheduler import status_run
    with pytest.raises(ValueError, match="plan"):
        status_run(run_dir)


def test_duplicate_missing_cross_rule_and_over_cap_matrices_fail_before_output(tmp_path):
    text = MATRIX.read_text(encoding="utf-8")
    variants = {
        "duplicate": text + text.splitlines(True)[1],
        "missing": "".join(text.splitlines(True)[:-1]),
        "cross": text.replace("A-E1_historical,A-E1", "A-E3_loss,A-E3", 1),
        "cap": text + "".join(text.splitlines(True)[1:82]),
    }
    for name, payload in variants.items():
        path = tmp_path / f"{name}.csv"
        path.write_text(payload, encoding="utf-8", newline="")
        with pytest.raises(ValueError):
            _create(tmp_path / name, matrix_path=path, run_id=name)
        assert not (tmp_path / name / "artifacts").exists()


def test_concurrent_claim_has_exactly_one_live_owner(tmp_path):
    run_dir = Path(_create(tmp_path)["run_dir"])
    from study02a.formal_scheduler import claim_next_fit

    def claim(owner):
        return claim_next_fit(run_dir, owner_id=owner, process_id=12345, timestamp="2026-07-13T00:00:00Z")

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, ("worker-a", "worker-b")))
    assert sorted(item["status"] for item in outcomes) == ["claimed", "monitor_only"]
    assert len(list((run_dir / "claims").glob("*.json"))) == 1


def test_stale_claim_recovers_only_without_outputs(tmp_path):
    run_dir = Path(_create(tmp_path)["run_dir"])
    from study02a.formal_scheduler import claim_next_fit, recover_claim

    claim = claim_next_fit(run_dir, owner_id="dead", process_id=99999999, timestamp="2026-07-13T00:00:00Z")
    recovered = recover_claim(run_dir, timestamp="2026-07-13T00:01:00Z")
    assert recovered["status"] == "released_to_pending"
    again = claim_next_fit(run_dir, owner_id="next", process_id=99999998, timestamp="2026-07-13T00:02:00Z")
    assert again["fit_id"] == claim["fit_id"]


def test_stale_claim_with_any_output_refuses_recovery(tmp_path):
    run_dir = Path(_create(tmp_path)["run_dir"])
    from study02a.formal_scheduler import claim_next_fit, recover_claim

    claim = claim_next_fit(run_dir, owner_id="dead", process_id=99999999, timestamp="2026-07-13T00:00:00Z")
    output = Path(claim["expected_output_paths"][0])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("partial", encoding="utf-8")
    with pytest.raises(ValueError, match="output"):
        recover_claim(run_dir, timestamp="2026-07-13T00:01:00Z")


def test_terminal_failure_is_immutable_and_not_retried(tmp_path):
    run_dir = Path(_create(tmp_path)["run_dir"])
    from study02a.formal_scheduler import claim_next_fit, record_fit_failed

    claim = claim_next_fit(run_dir, owner_id="worker", process_id=99999999, timestamp="2026-07-13T00:00:00Z")
    record_fit_failed(run_dir, fit_id=claim["fit_id"], owner_id="worker", failure_code="fit_error", timestamp="2026-07-13T00:01:00Z")
    nxt = claim_next_fit(run_dir, owner_id="worker-2", process_id=99999998, timestamp="2026-07-13T00:02:00Z")
    assert nxt["fit_id"] != claim["fit_id"]
    with pytest.raises((FileExistsError, ValueError)):
        record_fit_failed(run_dir, fit_id=claim["fit_id"], owner_id="worker", failure_code="again", timestamp="2026-07-13T00:03:00Z")


def test_status_is_read_only_and_reports_hashes_counts_and_claim(tmp_path):
    run_dir = Path(_create(tmp_path)["run_dir"])
    from study02a.formal_scheduler import claim_next_fit, status_run
    claim_next_fit(run_dir, owner_id="worker", process_id=12345, timestamp="2026-07-13T00:00:00Z")
    before = {p: p.read_bytes() for p in run_dir.rglob("*") if p.is_file()}
    status = status_run(run_dir)
    after = {p: p.read_bytes() for p in run_dir.rglob("*") if p.is_file()}
    assert before == after
    assert status["counts"] == {"pending": 348, "claimed": 1, "succeeded": 0, "failed": 0}
    assert status["live_claim"]["owner_id"] == "worker"


def test_public_surface_and_cli_have_no_test_or_executor_arguments(tmp_path):
    import study02a.formal_scheduler as scheduler
    for name in scheduler.__all__:
        signature = inspect.signature(getattr(scheduler, name))
        assert all("test" not in parameter.lower() and "executor" not in parameter.lower() for parameter in signature.parameters)
    help_result = subprocess.run([sys.executable, str(SCRIPT), "formal-select", "--help"], cwd=ROOT, check=True, capture_output=True, text=True)
    assert "test-path" not in help_result.stdout
    assert "dataset" not in help_result.stdout
    assert "executor" not in help_result.stdout


def test_cli_dry_run_status_and_claim_next(tmp_path):
    common = [sys.executable, str(SCRIPT), "formal-select", "--module", "A-E1", "--run-id", "cli-v1", "--artifact-root", str(tmp_path / "artifacts"), "--cache-root", str(tmp_path / "cache")]
    made = subprocess.run(common + ["--dry-run"], cwd=ROOT, check=True, capture_output=True, text=True)
    run_dir = Path(json.loads(made.stdout)["run_dir"])
    subprocess.run(common + ["--claim-next", "--owner-id", "cli-worker"], cwd=ROOT, check=True, capture_output=True, text=True)
    before = {p: p.read_bytes() for p in run_dir.rglob("*") if p.is_file()}
    shown = subprocess.run(common + ["--status"], cwd=ROOT, check=True, capture_output=True, text=True)
    assert json.loads(shown.stdout)["counts"]["claimed"] == 1
    assert before == {p: p.read_bytes() for p in run_dir.rglob("*") if p.is_file()}
