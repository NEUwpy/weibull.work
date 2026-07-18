from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


SKILL_ROOT = Path(__file__).resolve().parents[1]
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

    def invoke(action: str, *, repo: Path, task_id: str) -> subprocess.CompletedProcess[str]:
        return run_command(
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
            cwd=repo,
        )

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
