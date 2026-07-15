from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import os

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
        "predecessor": None,
    }
    kwargs.update(overrides)
    return materialize_run(**kwargs)


def _canonical(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _write_success(run_dir: Path, claim: dict, checkpoint: bytes = b"checkpoint", curve=None) -> dict:
    """Write a valid bound triple (checkpoint.pt + fit_status.json + evidence.json) and return its hashes."""
    fit_id = claim["fit_id"]; run_id = claim["run_id"]
    out = run_dir / "outputs" / fit_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "checkpoint.pt").write_bytes(checkpoint)
    checkpoint_sha = hashlib.sha256(checkpoint).hexdigest()
    (out / "fit_status.json").write_bytes(_canonical(
        {"checkpoint_sha256": checkpoint_sha, "fit_id": fit_id, "run_id": run_id, "status": "succeeded", "test_access_count": 0}))
    history = [1.0, 0.9, 0.8] if curve is None else list(curve)
    evidence = {
        "evidence_version": "study02-formal-fit-evidence-v1", "fit_id": fit_id, "run_id": run_id,
        "checkpoint_sha256": checkpoint_sha, "actual_epochs": len(history), "best_epoch_one_based": 1,
        "hit_epoch_100": False, "early_stop_reason": "patience_exhausted",
        "terminal_validation_slope": 0.0, "validation_curve": history, "test_access_count": 0,
    }
    (out / "evidence.json").write_bytes(_canonical(evidence))
    return {f"outputs/{fit_id}/{name}": hashlib.sha256((out / name).read_bytes()).hexdigest()
            for name in ("checkpoint.pt", "fit_status.json", "evidence.json")}


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
    with pytest.raises(ValueError, match="cache root|existing run"):
        _create(tmp_path, cache_root=tmp_path / "different-cache")


def test_plan_or_state_tampering_is_detected(tmp_path):
    result = _create(tmp_path)
    run_dir = Path(result["run_dir"])
    (run_dir / "plan.jsonl").write_bytes((run_dir / "plan.jsonl").read_bytes() + b"{}\n")
    from study02a.formal_scheduler import status_run
    with pytest.raises(ValueError, match="plan"):
        status_run(run_dir, cache_root=tmp_path / "cache")


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
        return claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id=owner, owner_nonce=f"nonce-{owner}", timestamp="2026-07-13T00:00:00Z")

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(claim, ("worker-a", "worker-b")))
    assert sorted(item["status"] for item in outcomes) == ["claimed", "monitor_only"]
    assert len(list((run_dir / "claims").glob("*.json"))) == 1


def test_stale_claim_recovers_only_without_outputs(tmp_path, monkeypatch):
    run_dir = Path(_create(tmp_path)["run_dir"])
    from study02a.formal_scheduler import claim_next_fit, recover_claim

    claim = claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="dead", owner_nonce="nonce-dead", timestamp="2026-07-13T00:00:00Z")
    monkeypatch.setattr("study02a.formal_scheduler._process_start_token", lambda _pid: claim["process_start_token"] + "-ended")
    recovered = recover_claim(run_dir, cache_root=tmp_path / "cache", timestamp="2026-07-13T00:01:00Z")
    assert recovered["status"] == "released_to_pending"
    monkeypatch.undo()
    again = claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="next", owner_nonce="nonce-next", timestamp="2026-07-13T00:02:00Z")
    assert again["fit_id"] == claim["fit_id"]


def test_stale_claim_with_orphaned_output_is_cleaned_and_recovered(tmp_path, monkeypatch):
    run_dir = Path(_create(tmp_path)["run_dir"])
    from study02a.formal_scheduler import claim_next_fit, recover_claim

    claim = claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="dead", owner_nonce="nonce-dead", timestamp="2026-07-13T00:00:00Z")
    monkeypatch.setattr("study02a.formal_scheduler._process_start_token", lambda _pid: claim["process_start_token"] + "-ended")
    output = run_dir / claim["expected_outputs"][0]["relative_path"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("partial", encoding="utf-8")  # orphaned output from a crashed executor (no success event)
    recovered = recover_claim(run_dir, cache_root=tmp_path / "cache", timestamp="2026-07-13T00:01:00Z")
    assert recovered["status"] == "released_to_pending"
    assert not output.parent.exists()  # orphaned outputs removed so the fit re-runs deterministically


def test_terminal_failure_is_immutable_and_not_retried(tmp_path):
    run_dir = Path(_create(tmp_path)["run_dir"])
    from study02a.formal_scheduler import claim_next_fit, record_fit_failed

    claim = claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="worker", owner_nonce="nonce-worker", timestamp="2026-07-13T00:00:00Z")
    record_fit_failed(run_dir, cache_root=tmp_path / "cache", fit_id=claim["fit_id"], owner_id="worker", owner_nonce="nonce-worker", failure_code="fit_error", timestamp="2026-07-13T00:01:00Z")
    nxt = claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="worker-2", owner_nonce="nonce-worker-2", timestamp="2026-07-13T00:02:00Z")
    assert nxt["fit_id"] != claim["fit_id"]
    with pytest.raises((FileExistsError, ValueError)):
        record_fit_failed(run_dir, cache_root=tmp_path / "cache", fit_id=claim["fit_id"], owner_id="worker", owner_nonce="nonce-worker", failure_code="again", timestamp="2026-07-13T00:03:00Z")


def test_status_is_read_only_and_reports_hashes_counts_and_claim(tmp_path):
    run_dir = Path(_create(tmp_path)["run_dir"])
    from study02a.formal_scheduler import claim_next_fit, status_run
    claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="worker", owner_nonce="nonce-worker", timestamp="2026-07-13T00:00:00Z")
    before = {p: p.read_bytes() for p in run_dir.rglob("*") if p.is_file()}
    status = status_run(run_dir, cache_root=tmp_path / "cache")
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


def test_status_and_claim_rebuild_current_authority_and_require_exact_cache(tmp_path, monkeypatch):
    run_dir = Path(_create(tmp_path)["run_dir"])
    import study02a.formal_scheduler as scheduler
    with pytest.raises(ValueError, match="cache"):
        scheduler.status_run(run_dir, cache_root=tmp_path / "wrong-cache")
    monkeypatch.setattr(scheduler, "_git_sha", lambda _root: "b" * 40)
    with pytest.raises(ValueError, match="authority|manifest|code"):
        scheduler.status_run(run_dir, cache_root=tmp_path / "cache")
    with pytest.raises(ValueError, match="authority|manifest|code"):
        scheduler.claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="w", owner_nonce="nonce-w", timestamp="2026-07-13T00:00:00Z")


def test_exact_repo_matrix_path_rejects_identical_copy(tmp_path):
    copied = tmp_path / "matrix.csv"
    copied.write_bytes(MATRIX.read_bytes())
    with pytest.raises(ValueError, match="matrix path"):
        _create(tmp_path, matrix_path=copied)


def test_event_truncation_reorder_forged_tail_and_state_forgery_reject(tmp_path):
    run_dir = Path(_create(tmp_path)["run_dir"])
    from study02a.formal_scheduler import claim_next_fit, status_run
    claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="worker", owner_nonce="nonce-worker", timestamp="2026-07-13T00:00:00Z")
    event_files = sorted((run_dir / "events").glob("*.json"))
    assert len(event_files) == 2
    tail = event_files[-1]
    tail_bytes = tail.read_bytes()
    tail.unlink()
    with pytest.raises(ValueError, match="event|tail|state|claims"):
        status_run(run_dir, cache_root=tmp_path / "cache")
    tail.write_bytes(tail_bytes)
    forged = json.loads(tail_bytes)
    forged["seq"] = 99
    tail.write_bytes((json.dumps(forged, sort_keys=True, separators=(",", ":")) + "\n").encode())
    with pytest.raises(ValueError, match="event|canonical|sequence"):
        status_run(run_dir, cache_root=tmp_path / "cache")
    tail.write_bytes(tail_bytes)
    state_path = run_dir / "scheduler_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["fit_states"][next(iter(state["fit_states"]))] = "succeeded"
    state_path.write_bytes((json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
    with pytest.raises(ValueError, match="replay|state"):
        status_run(run_dir, cache_root=tmp_path / "cache")


def test_success_requires_exact_contained_complete_nonempty_outputs(tmp_path):
    run_dir = Path(_create(tmp_path)["run_dir"])
    from study02a.formal_scheduler import claim_next_fit, record_fit_succeeded
    claim = claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="worker", owner_nonce="nonce-worker", timestamp="2026-07-13T00:00:00Z")
    with pytest.raises(ValueError, match="output"):
        record_fit_succeeded(run_dir, cache_root=tmp_path / "cache", fit_id=claim["fit_id"], owner_id="worker", owner_nonce="nonce-worker", output_hashes={}, timestamp="2026-07-13T00:01:00Z")
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"x")
    with pytest.raises(ValueError, match="output|relative|expected"):
        record_fit_succeeded(run_dir, cache_root=tmp_path / "cache", fit_id=claim["fit_id"], owner_id="worker", owner_nonce="nonce-worker", output_hashes={str(outside): hashlib.sha256(b"x").hexdigest()}, timestamp="2026-07-13T00:01:00Z")
    expected = claim["expected_outputs"]
    exact = _write_success(run_dir, claim)
    with pytest.raises(ValueError, match="extra|expected"):
        record_fit_succeeded(run_dir, cache_root=tmp_path / "cache", fit_id=claim["fit_id"], owner_id="worker", owner_nonce="nonce-worker", output_hashes={**exact, "outputs/extra": "0" * 64}, timestamp="2026-07-13T00:01:00Z")
    # tampering the bound evidence (its checkpoint binding) must be rejected
    fit_id = claim["fit_id"]
    ev_path = run_dir / "outputs" / fit_id / "evidence.json"
    tampered = json.loads(ev_path.read_bytes()); tampered["checkpoint_sha256"] = "0" * 64
    ev_path.write_bytes(_canonical(tampered))
    tampered_hashes = {**exact, f"outputs/{fit_id}/evidence.json": hashlib.sha256(ev_path.read_bytes()).hexdigest()}
    with pytest.raises(ValueError, match="evidence|bind|authority|fit"):
        record_fit_succeeded(run_dir, cache_root=tmp_path / "cache", fit_id=fit_id, owner_id="worker", owner_nonce="nonce-worker", output_hashes=tampered_hashes, timestamp="2026-07-13T00:01:00Z")
    # rewrite correct evidence and record cleanly
    exact = _write_success(run_dir, claim)
    receipt = record_fit_succeeded(run_dir, cache_root=tmp_path / "cache", fit_id=fit_id, owner_id="worker", owner_nonce="nonce-worker", output_hashes=exact, timestamp="2026-07-13T00:01:00Z")
    assert receipt["state"] == "succeeded"


def test_failed_fit_refuses_outputs_and_recovery_cleans_orphans(tmp_path, monkeypatch):
    run_dir = Path(_create(tmp_path)["run_dir"])
    from study02a.formal_scheduler import claim_next_fit, record_fit_failed, recover_claim
    claim = claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="dead", owner_nonce="nonce-dead", timestamp="2026-07-13T00:00:00Z")
    monkeypatch.setattr("study02a.formal_scheduler._process_start_token", lambda _pid: claim["process_start_token"] + "-ended")
    output_dir = run_dir / "outputs" / claim["fit_id"]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ".partial.tmp").write_bytes(b"partial")
    # a failed fit must not carry any (hidden/temp) output
    with pytest.raises(ValueError, match="output"):
        record_fit_failed(run_dir, cache_root=tmp_path / "cache", fit_id=claim["fit_id"], owner_id="dead", owner_nonce="nonce-dead", failure_code="infra", timestamp="2026-07-13T00:01:00Z")
    # recovery cleans the orphaned output dir (including hidden/temp) and releases the fit
    recovered = recover_claim(run_dir, cache_root=tmp_path / "cache", timestamp="2026-07-13T00:01:00Z")
    assert recovered["status"] == "released_to_pending"
    assert not output_dir.exists()


def test_pid_reuse_uses_creation_token_not_pid_alone(tmp_path, monkeypatch):
    run_dir = Path(_create(tmp_path)["run_dir"])
    import study02a.formal_scheduler as scheduler
    claim = scheduler.claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="worker", owner_nonce="nonce-worker", timestamp="2026-07-13T00:00:00Z")
    monkeypatch.setattr(scheduler, "_process_start_token", lambda _pid: claim["process_start_token"] + "-reused")
    recovered = scheduler.recover_claim(run_dir, cache_root=tmp_path / "cache", timestamp="2026-07-13T00:01:00Z")
    assert recovered["status"] == "released_to_pending"


def test_transaction_journal_recovers_state_after_event_publication_crash(tmp_path, monkeypatch):
    run_dir = Path(_create(tmp_path)["run_dir"])
    import study02a.formal_scheduler as scheduler
    original = scheduler._atomic_replace
    calls = {"count": 0}
    def crash_once(path, payload):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("simulated crash")
        return original(path, payload)
    monkeypatch.setattr(scheduler, "_atomic_replace", crash_once)
    with pytest.raises(OSError, match="simulated crash"):
        scheduler.claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="worker", owner_nonce="nonce-worker", timestamp="2026-07-13T00:00:00Z")
    monkeypatch.setattr(scheduler, "_atomic_replace", original)
    outcome = scheduler.claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="worker-2", owner_nonce="nonce-worker-2", timestamp="2026-07-13T00:01:00Z")
    assert outcome["status"] == "monitor_only"
    assert not (run_dir / ".scheduler.journal").exists()


def test_claim_hardlink_and_extra_receipt_are_rejected(tmp_path):
    run_dir = Path(_create(tmp_path)["run_dir"])
    from study02a.formal_scheduler import claim_next_fit, status_run
    claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="worker", owner_nonce="nonce-worker", timestamp="2026-07-13T00:00:00Z")
    claim_path = next((run_dir / "claims").glob("*.json"))
    hardlink = tmp_path / "claim-hardlink.json"
    os.link(claim_path, hardlink)
    with pytest.raises(ValueError, match="hard-linked"):
        status_run(run_dir, cache_root=tmp_path / "cache")
    hardlink.unlink()
    (run_dir / "receipts").mkdir(exist_ok=True)
    (run_dir / "receipts" / "forged.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="extra|unbound|receipt"):
        status_run(run_dir, cache_root=tmp_path / "cache")


def test_dead_stale_lock_is_cleared_only_after_identity_check(tmp_path):
    run_dir = Path(_create(tmp_path)["run_dir"])
    import study02a.formal_scheduler as scheduler
    stale = {"host_id": scheduler.socket.gethostname(), "lock_version": "study02-formal-scheduler-lock-v1", "owner_nonce": "dead-lock", "process_id": 99999999, "process_start_token": "dead-token"}
    (run_dir / ".scheduler.lock").write_bytes((json.dumps(stale, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode())
    claim = scheduler.claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="worker", owner_nonce="nonce-worker", timestamp="2026-07-13T00:00:00Z")
    assert claim["status"] == "claimed"
    assert not (run_dir / ".scheduler.lock").exists()


def test_cli_wrong_cache_root_fails_for_status_and_claim(tmp_path):
    common = [sys.executable, str(SCRIPT), "formal-select", "--module", "A-E1", "--run-id", "cli-authority-v1", "--artifact-root", str(tmp_path / "artifacts"), "--cache-root", str(tmp_path / "cache")]
    subprocess.run(common + ["--dry-run"], cwd=ROOT, check=True, capture_output=True, text=True)
    wrong = common.copy()
    wrong[wrong.index(str(tmp_path / "cache"))] = str(tmp_path / "wrong-cache")
    assert subprocess.run(wrong + ["--status"], cwd=ROOT, capture_output=True, text=True).returncode != 0
    assert subprocess.run(wrong + ["--claim-next"], cwd=ROOT, capture_output=True, text=True).returncode != 0


def test_public_manifest_has_no_matrix_bytes_injection_and_claim_owns_pid(tmp_path):
    from study02a.formal_contracts import build_formal_manifest
    from study02a.formal_scheduler import claim_next_fit
    assert "matrix_snapshot" not in inspect.signature(build_formal_manifest).parameters
    assert "process_id" not in inspect.signature(claim_next_fit).parameters
    run_dir = Path(_create(tmp_path)["run_dir"])
    with pytest.raises(TypeError, match="process_id"):
        claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="borrower", owner_nonce="borrowed-nonce", process_id=os.getpid(), timestamp="2026-07-13T00:00:00Z")


def test_scoped_scientific_code_drift_rejects_resume(tmp_path, monkeypatch):
    run_dir = Path(_create(tmp_path)["run_dir"])
    import study02a.formal_scheduler as scheduler
    original = scheduler._scoped_code_snapshot(STUDY_ROOT)
    monkeypatch.setattr(scheduler, "_scoped_code_snapshot", lambda _root: {**original, "scoped_code_sha256": "f" * 64})
    with pytest.raises(ValueError, match="code|authority|drift"):
        scheduler.status_run(run_dir, cache_root=tmp_path / "cache")


def test_external_controller_anchor_rejects_coordinated_run_local_rollback(tmp_path):
    run_dir = Path(_create(tmp_path)["run_dir"])
    from study02a.formal_scheduler import claim_next_fit, status_run
    genesis_state = (run_dir / "scheduler_state.json").read_bytes()
    claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="worker", owner_nonce="nonce-worker", timestamp="2026-07-13T00:00:00Z")
    claim_file = next((run_dir / "claims").glob("*.json"))
    tail_event = sorted((run_dir / "events").glob("*.json"))[-1]
    claim_file.unlink(); tail_event.unlink(); (run_dir / "scheduler_state.json").write_bytes(genesis_state)
    with pytest.raises(ValueError, match="controller|anchor|tail|count"):
        status_run(run_dir, cache_root=tmp_path / "cache")


def test_controller_key_is_external_to_run_and_manifest_binds_key_id(tmp_path):
    result = _create(tmp_path)
    run_dir = Path(result["run_dir"])
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    key_path = tmp_path / "artifacts" / ".study02-controller" / "keys" / "controller.hmac.key"
    assert key_path.is_file()
    assert run_dir not in key_path.parents
    assert hashlib.sha256(key_path.read_bytes()).hexdigest() == manifest["scheduler"]["authority"]["controller_key_id"]
    anchors = list((tmp_path / "artifacts" / ".study02-controller" / "runs" / "A-E1" / "G3-AE1-plan-v1" / "anchors").glob("*.json"))
    assert len(anchors) == 1
    canonical_key = STUDY_ROOT / "artifacts" / ".study02-controller" / "keys" / "controller.hmac.key"
    ignored = subprocess.run(["git", "check-ignore", str(canonical_key)], cwd=ROOT, capture_output=True, text=True)
    assert ignored.returncode == 0


@pytest.mark.skipif(os.name != "nt", reason="Windows FILETIME contract")
def test_windows_current_pid_creation_token_uses_real_filetime():
    import study02a.formal_scheduler as scheduler
    token = scheduler._process_start_token(os.getpid())
    assert token is not None and token.startswith("win-filetime-")
    assert int(token.removeprefix("win-filetime-")) > 0


def test_output_identity_change_after_one_read_snapshot_rejects(tmp_path, monkeypatch):
    run_dir = Path(_create(tmp_path)["run_dir"])
    import study02a.formal_scheduler as scheduler
    claim = scheduler.claim_next_fit(run_dir, cache_root=tmp_path / "cache", owner_id="worker", owner_nonce="nonce-worker", timestamp="2026-07-13T00:00:00Z")
    checkpoint = run_dir / claim["expected_outputs"][0]["relative_path"]
    output_hashes = _write_success(run_dir, claim)
    original = scheduler._read_identity_snapshot
    changed = {"done": False}
    def mutate_after_read(path):
        snapshot = original(path)
        if Path(path) == checkpoint and not changed["done"]:
            changed["done"] = True; checkpoint.write_bytes(b"changed-after-read")
        return snapshot
    monkeypatch.setattr(scheduler, "_read_identity_snapshot", mutate_after_read)
    with pytest.raises(ValueError, match="identity changed"):
        scheduler.record_fit_succeeded(run_dir, cache_root=tmp_path / "cache", fit_id=claim["fit_id"], owner_id="worker", owner_nonce="nonce-worker", output_hashes=output_hashes, timestamp="2026-07-13T00:01:00Z")
