from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[2]
RUNNER = SKILL_ROOT / "scripts" / "coworker-live.ps1"
POWERSHELL = shutil.which("powershell.exe") or shutil.which("powershell")


def run_command(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    assert run_command("git", "init", cwd=root).returncode == 0
    assert run_command("git", "config", "user.name", "Coworker Test", cwd=root).returncode == 0
    assert run_command("git", "config", "user.email", "coworker@example.test", cwd=root).returncode == 0
    (root / "README.md").write_text("# fixture\n", encoding="utf-8")
    assert run_command("git", "add", "README.md", cwd=root).returncode == 0
    assert run_command("git", "commit", "-m", "fixture", cwd=root).returncode == 0
    assert run_command("git", "checkout", "-b", "worker-test", cwd=root).returncode == 0
    return root


@pytest.fixture
def run_live():
    if not POWERSHELL:
        pytest.skip("Windows PowerShell is required")

    def invoke(
        action: str,
        *,
        repo: Path,
        task_id: str,
        **options: object,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(RUNNER),
            "-Action",
            action,
            "-Repo",
            str(repo),
            "-TaskId",
            task_id,
        ]
        for name, value in options.items():
            if value is not None:
                command.extend([f"-{name}", str(value)])
        return run_command(*command, cwd=repo)

    return invoke


def test_preflight_returns_repo_branch_head_and_dirty_paths(repo: Path, run_live) -> None:
    (repo / "user-note.txt").write_text("keep", encoding="utf-8")

    result = run_live("preflight", repo=repo, task_id="demo")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["state"] == "PREFLIGHT"
    assert payload["branch"] == "worker-test"
    assert payload["head"] == run_command("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()
    assert "?? user-note.txt" in payload["dirty"]


@pytest.mark.parametrize("task_id", ["../escape", "a/b", "a b", ""])
def test_preflight_rejects_unsafe_task_id(repo: Path, run_live, task_id: str) -> None:
    result = run_live("preflight", repo=repo, task_id=task_id)

    assert result.returncode != 0
    assert "TaskId must match" in result.stderr


def test_preflight_rejects_non_git_directory(tmp_path: Path, run_live) -> None:
    result = run_live("preflight", repo=tmp_path, task_id="demo")

    assert result.returncode != 0
    assert "not a Git worktree" in result.stderr


def write_fake_claude(
    repo: Path,
    *,
    payload: str | None = None,
    exit_code: int = 0,
    delay_seconds: int = 0,
) -> Path:
    launcher = repo / "fake-claude.cmd"
    result = payload or json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "worker complete",
            "session_id": "11111111-1111-1111-1111-111111111111",
        }
    )
    launcher.write_text(
        "@echo off\n"
        "echo %* > \"%~dp0claude-args.log\"\n"
        + (f"powershell -NoProfile -Command Start-Sleep -Seconds {delay_seconds}\n" if delay_seconds else "")
        + f"echo {result}\n"
        + f"exit /b {exit_code}\n",
        encoding="ascii",
    )
    return launcher


def write_contract_files(repo: Path) -> dict[str, Path]:
    files = {
        "PromptFile": repo / "prompt.md",
        "Plan": repo / "plan.md",
        "Handoff": repo / "handoff.md",
        "Report": repo / "report.md",
        "Review": repo / "review.md",
    }
    files["PromptFile"].write_text("Role: executor\nDo the bounded task.\n", encoding="utf-8")
    files["Plan"].write_text("# Plan\n", encoding="utf-8")
    files["Handoff"].write_text("# Handoff\n", encoding="utf-8")
    return files


def wait_for_state(run_live, repo: Path, task_id: str, expected: str, timeout: float = 12) -> dict:
    deadline = time.monotonic() + timeout
    last: dict = {}
    while time.monotonic() < deadline:
        result = run_live("status", repo=repo, task_id=task_id)
        if result.returncode == 0:
            last = json.loads(result.stdout)
            if last["state"] == expected:
                return last
        time.sleep(0.1)
    raise AssertionError(f"task did not reach {expected}; last status: {last}")


def test_start_collect_resume_preserves_claude_session(repo: Path, run_live) -> None:
    files = write_contract_files(repo)
    claude = write_fake_claude(repo)

    started = run_live(
        "start",
        repo=repo,
        task_id="demo",
        ClaudeCommand=claude,
        **files,
    )

    assert started.returncode == 0, started.stderr
    first = wait_for_state(run_live, repo, "demo", "AWAITING_CODEX_REVIEW")
    assert first["round"] == 1
    assert first["claude_session_id"] == "11111111-1111-1111-1111-111111111111"
    files["Report"].write_text("# Worker report\n", encoding="utf-8")
    collected = run_live("collect", repo=repo, task_id="demo")
    assert collected.returncode == 0, collected.stderr
    assert json.loads(collected.stdout)["result"] == "worker complete"

    files["Review"].write_text("Verdict: REVISE\nFix the evidence table.\n", encoding="utf-8")
    resumed = run_live(
        "resume",
        repo=repo,
        task_id="demo",
        Review=files["Review"],
        ClaudeCommand=claude,
    )
    assert resumed.returncode == 0, resumed.stderr
    second = wait_for_state(run_live, repo, "demo", "AWAITING_CODEX_REVIEW")
    assert second["round"] == 2
    assert second["claude_session_id"] == first["claude_session_id"]
    args = (repo / "claude-args.log").read_text(encoding="utf-8")
    assert "--resume 11111111-1111-1111-1111-111111111111" in args


def test_start_rejects_duplicate_live_worker(repo: Path, run_live) -> None:
    files = write_contract_files(repo)
    claude = write_fake_claude(repo, delay_seconds=3)

    first = run_live("start", repo=repo, task_id="duplicate", ClaudeCommand=claude, **files)
    second = run_live("start", repo=repo, task_id="duplicate", ClaudeCommand=claude, **files)

    assert first.returncode == 0, first.stderr
    assert second.returncode != 0
    assert "already" in second.stderr.lower()
    run_live("cancel", repo=repo, task_id="duplicate")


def test_collect_requires_worker_report(repo: Path, run_live) -> None:
    files = write_contract_files(repo)
    claude = write_fake_claude(repo)
    result = run_live("start", repo=repo, task_id="missing-report", ClaudeCommand=claude, **files)
    assert result.returncode == 0, result.stderr
    wait_for_state(run_live, repo, "missing-report", "AWAITING_CODEX_REVIEW")

    collected = run_live("collect", repo=repo, task_id="missing-report")

    assert collected.returncode != 0
    assert "report" in collected.stderr.lower()


@pytest.mark.parametrize(
    ("payload", "exit_code"),
    [("not-json", 0), (None, 7)],
)
def test_worker_failures_pause_task(
    repo: Path,
    run_live,
    payload: str | None,
    exit_code: int,
) -> None:
    files = write_contract_files(repo)
    claude = write_fake_claude(repo, payload=payload, exit_code=exit_code)

    result = run_live("start", repo=repo, task_id=f"failure-{exit_code}", ClaudeCommand=claude, **files)

    assert result.returncode == 0, result.stderr
    status = wait_for_state(run_live, repo, f"failure-{exit_code}", "PAUSED")
    assert status["exit_code"] == exit_code


def test_status_reports_stale_recorded_pid(repo: Path, run_live) -> None:
    runtime = repo / "coworker" / "runtime" / "stale"
    runtime.mkdir(parents=True)
    (runtime / "state.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task_id": "stale",
                "repo": str(repo),
                "state": "WORKER_RUNNING",
                "worker_pid": 99999999,
                "heartbeat_path": str(runtime / "heartbeat.txt"),
            }
        ),
        encoding="utf-8",
    )

    result = run_live("status", repo=repo, task_id="stale")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["worker_alive"] is False


def test_cancel_refuses_task_without_recorded_pid(repo: Path, run_live) -> None:
    result = run_live("cancel", repo=repo, task_id="never-started")

    assert result.returncode != 0
    assert "recorded" in result.stderr.lower()


def test_skill_contract_routes_codex_controller_and_guards_executor() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "## Live Loop" in skill
    assert "Codex Controller" in skill
    assert "Role: executor" in skill
    assert "references/live-loop.md" in skill


def test_documentation_covers_public_actions_and_verdicts() -> None:
    reference = (SKILL_ROOT / "references" / "live-loop.md").read_text(encoding="utf-8")
    dispatch = (SKILL_ROOT / "references" / "dispatch.md").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "coworker" / "README.md").read_text(encoding="utf-8")

    for action in ("preflight", "start", "resume", "status", "collect", "cancel"):
        assert f"-Action {action}" in reference
    for verdict in ("APPROVE", "REVISE", "BLOCK"):
        assert verdict in reference
    assert "Role: executor" in dispatch
    assert "runtime" in readme.lower()


def test_documentation_ignores_local_runtime_state() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "/coworker/runtime/" in gitignore.splitlines()


def test_recovery_reclaims_stale_controller_lock(repo: Path, run_live) -> None:
    files = write_contract_files(repo)
    claude = write_fake_claude(repo)
    runtime = repo / "coworker" / "runtime" / "stale-lock"
    runtime.mkdir(parents=True)
    (runtime / "controller.lock").write_text(
        json.dumps({"pid": 99999999, "created_at": "2000-01-01T00:00:00Z"}),
        encoding="utf-8",
    )

    started = run_live("start", repo=repo, task_id="stale-lock", ClaudeCommand=claude, **files)

    assert started.returncode == 0, started.stderr
    wait_for_state(run_live, repo, "stale-lock", "AWAITING_CODEX_REVIEW")
    assert not (runtime / "controller.lock").exists()


def test_recovery_refuses_live_controller_lock(repo: Path, run_live) -> None:
    files = write_contract_files(repo)
    claude = write_fake_claude(repo)
    runtime = repo / "coworker" / "runtime" / "live-lock"
    runtime.mkdir(parents=True)
    (runtime / "controller.lock").write_text(
        json.dumps({"pid": os.getpid(), "created_at": "2000-01-01T00:00:00Z"}),
        encoding="utf-8",
    )

    started = run_live("start", repo=repo, task_id="live-lock", ClaudeCommand=claude, **files)

    assert started.returncode != 0
    assert "lock" in started.stderr.lower()
    assert not (runtime / "state.json").exists()


def test_recovery_state_writes_are_atomic(repo: Path, run_live) -> None:
    files = write_contract_files(repo)
    claude = write_fake_claude(repo)
    result = run_live("start", repo=repo, task_id="atomic", ClaudeCommand=claude, **files)
    assert result.returncode == 0, result.stderr
    wait_for_state(run_live, repo, "atomic", "AWAITING_CODEX_REVIEW")
    runtime = repo / "coworker" / "runtime" / "atomic"

    state = json.loads((runtime / "state.json").read_text(encoding="utf-8-sig"))

    assert state["state"] == "AWAITING_CODEX_REVIEW"
    assert list(runtime.glob("state.json.*.tmp")) == []


def test_recovery_collects_after_controller_restart(repo: Path, run_live) -> None:
    files = write_contract_files(repo)
    claude = write_fake_claude(repo)
    result = run_live("start", repo=repo, task_id="restart", ClaudeCommand=claude, **files)
    assert result.returncode == 0, result.stderr
    wait_for_state(run_live, repo, "restart", "AWAITING_CODEX_REVIEW")
    files["Report"].write_text("# durable report\n", encoding="utf-8")

    recovered_status = run_live("status", repo=repo, task_id="restart")
    recovered_collect = run_live("collect", repo=repo, task_id="restart")

    assert json.loads(recovered_status.stdout)["state"] == "AWAITING_CODEX_REVIEW"
    assert json.loads(recovered_collect.stdout)["claude_session_id"]


def test_recovery_refuses_resume_without_review(repo: Path, run_live) -> None:
    files = write_contract_files(repo)
    claude = write_fake_claude(repo)
    result = run_live("start", repo=repo, task_id="no-review", ClaudeCommand=claude, **files)
    assert result.returncode == 0, result.stderr
    wait_for_state(run_live, repo, "no-review", "AWAITING_CODEX_REVIEW")

    resumed = run_live("resume", repo=repo, task_id="no-review")

    assert resumed.returncode != 0
    assert "review" in resumed.stderr.lower()


def test_recovery_rejects_contract_path_escape(repo: Path, run_live, tmp_path: Path) -> None:
    files = write_contract_files(repo)
    outside = tmp_path / "outside.md"
    outside.write_text("Role: executor\n", encoding="utf-8")
    files["PromptFile"] = outside
    claude = write_fake_claude(repo)

    result = run_live("start", repo=repo, task_id="escape", ClaudeCommand=claude, **files)

    assert result.returncode != 0
    assert "escapes the repository" in result.stderr


def test_recovery_preserves_unrelated_dirty_file(repo: Path, run_live) -> None:
    files = write_contract_files(repo)
    claude = write_fake_claude(repo)
    user_file = repo / "unrelated-user-work.txt"
    user_file.write_text("do not touch\n", encoding="utf-8")
    before = run_command("git", "status", "--short", cwd=repo).stdout

    result = run_live("start", repo=repo, task_id="preserve", ClaudeCommand=claude, **files)
    assert result.returncode == 0, result.stderr
    wait_for_state(run_live, repo, "preserve", "AWAITING_CODEX_REVIEW")

    assert user_file.read_text(encoding="utf-8") == "do not touch\n"
    assert "?? unrelated-user-work.txt" in before
    assert "?? unrelated-user-work.txt" in run_command("git", "status", "--short", cwd=repo).stdout
