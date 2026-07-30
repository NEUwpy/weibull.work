import json
import re
import shutil
import subprocess
import time
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
MAILBOX = SKILL / "scripts" / "coworker-mailbox.ps1"
RESOLVER = SKILL / "scripts" / "resolve-coworker-skill.ps1"


def ps(script: Path, *args: str, check: bool = True):
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *map(str, args),
        ],
        text=True,
        capture_output=True,
        check=check,
    )


def write_version(path: Path, version: str, updated_at: str):
    path.mkdir(parents=True, exist_ok=True)
    (path / "VERSION.json").write_text(
        json.dumps(
            {
                "name": "coworker",
                "version": version,
                "updated_at": updated_at,
            }
        ),
        encoding="utf-8",
    )
    (path / "SKILL.md").write_text(f"# coworker {version}\n", encoding="utf-8")


def test_skill_and_version_metadata_match():
    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    version = json.loads((SKILL / "VERSION.json").read_text(encoding="utf-8"))
    assert re.search(rf"^version:\s*{re.escape(version['version'])}\s*$", skill_text, re.M)
    assert re.search(
        rf"^updated_at:\s*{re.escape(version['updated_at'])}\s*$",
        skill_text,
        re.M,
    )


def test_referenced_resources_exist():
    for rel in [
        "references/protocol.md",
        "references/dispatch.md",
        "references/duplex-mailbox.md",
        "references/incremental-review.md",
        "references/version-resolution.md",
        "scripts/coworker-mailbox.ps1",
        "scripts/resolve-coworker-skill.ps1",
        "templates/review-state.md",
    ]:
        assert (SKILL / rel).is_file(), rel


def test_mailbox_roundtrip_pause_resume_and_archive(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    body_a = tmp_path / "a.md"
    body_b = tmp_path / "b.md"
    body_a.write_text("# task\n", encoding="utf-8")
    body_b.write_text("# report\n", encoding="utf-8")

    init = json.loads(
        ps(MAILBOX, "-Action", "init", "-Repo", repo, "-TaskId", "demo").stdout
    )
    assert init["event"] == "initialized"

    sent = json.loads(
        ps(
            MAILBOX,
            "-Action",
            "send",
            "-Repo",
            repo,
            "-TaskId",
            "demo",
            "-Role",
            "codex",
            "-Type",
            "task",
            "-BodyFile",
            body_a,
        ).stdout
    )
    assert sent["message_id"] == 1

    received = json.loads(
        ps(
            MAILBOX,
            "-Action",
            "wait",
            "-Repo",
            repo,
            "-TaskId",
            "demo",
            "-Role",
            "opencode",
            "-TimeoutSeconds",
            "2",
        ).stdout
    )
    assert received["event"] == "message"
    assert Path(received["archive_path"]).is_file()

    ps(
        MAILBOX,
        "-Action",
        "send",
        "-Repo",
        repo,
        "-TaskId",
        "demo",
        "-Role",
        "opencode",
        "-Type",
        "report",
        "-BodyFile",
        body_b,
    )
    received_reply = json.loads(
        ps(
            MAILBOX,
            "-Action",
            "wait",
            "-Repo",
            repo,
            "-TaskId",
            "demo",
            "-Role",
            "codex",
            "-TimeoutSeconds",
            "2",
        ).stdout
    )
    reply_text = Path(received_reply["archive_path"]).read_text(encoding="utf-8-sig")
    assert "reply_to: 1" in reply_text

    ps(
        MAILBOX,
        "-Action",
        "set-mode",
        "-Repo",
        repo,
        "-TaskId",
        "demo",
        "-Mode",
        "manual",
    )
    paused = json.loads(
        ps(
            MAILBOX,
            "-Action",
            "wait",
            "-Repo",
            repo,
            "-TaskId",
            "demo",
            "-Role",
            "codex",
            "-TimeoutSeconds",
            "2",
        ).stdout
    )
    assert paused == {"event": "control", "mode": "manual"}

    ps(
        MAILBOX,
        "-Action",
        "set-mode",
        "-Repo",
        repo,
        "-TaskId",
        "demo",
        "-Mode",
        "auto",
    )
    state = json.loads(
        ps(MAILBOX, "-Action", "status", "-Repo", repo, "-TaskId", "demo").stdout
    )
    assert state["mode"] == "auto"
    assert state["archived_messages"] == 2
    assert not list((repo / "coworker" / "runtime" / "demo").glob("*.lock"))


def test_role_lock_blocks_second_waiter(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    ps(MAILBOX, "-Action", "init", "-Repo", repo, "-TaskId", "locktest")
    first = subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(MAILBOX),
            "-Action",
            "wait",
            "-Repo",
            str(repo),
            "-TaskId",
            "locktest",
            "-Role",
            "codex",
            "-TimeoutSeconds",
            "5",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        lock = repo / "coworker" / "runtime" / "locktest" / "codex.lock"
        for _ in range(30):
            if lock.exists():
                break
            time.sleep(0.1)
        second = ps(
            MAILBOX,
            "-Action",
            "wait",
            "-Repo",
            repo,
            "-TaskId",
            "locktest",
            "-Role",
            "codex",
            "-TimeoutSeconds",
            "1",
            check=False,
        )
        assert second.returncode != 0
        assert "lock" in second.stderr.lower()
        ps(
            MAILBOX,
            "-Action",
            "set-mode",
            "-Repo",
            repo,
            "-TaskId",
            "locktest",
            "-Mode",
            "manual",
        )
        first.communicate(timeout=5)
        assert first.returncode == 0
    finally:
        if first.poll() is None:
            first.kill()


def test_resolver_selects_newer_version(tmp_path):
    global_copy = tmp_path / "global"
    project_copy = tmp_path / "project"
    write_version(global_copy, "2.1.0", "2026-07-30T10:00:00+08:00")
    write_version(project_copy, "2.0.0", "2026-07-30T11:00:00+08:00")
    result = json.loads(
        ps(
            RESOLVER,
            "-GlobalPath",
            global_copy,
            "-ProjectPath",
            project_copy,
        ).stdout
    )
    assert result["selected_kind"] == "global"
    assert result["reason"] == "newer_version"
    assert result["synchronization_needed"] is True


def test_resolver_uses_updated_at_then_detects_conflict(tmp_path):
    global_copy = tmp_path / "global"
    project_copy = tmp_path / "project"
    write_version(global_copy, "2.1.0", "2026-07-30T12:00:00+08:00")
    write_version(project_copy, "2.1.0", "2026-07-30T11:00:00+08:00")
    result = json.loads(
        ps(
            RESOLVER,
            "-GlobalPath",
            global_copy,
            "-ProjectPath",
            project_copy,
        ).stdout
    )
    assert result["selected_kind"] == "global"
    assert result["reason"] == "newer_updated_at"

    write_version(project_copy, "2.1.0", "2026-07-30T12:00:00+08:00")
    (project_copy / "extra.txt").write_text("different", encoding="utf-8")
    conflict = ps(
        RESOLVER,
        "-GlobalPath",
        global_copy,
        "-ProjectPath",
        project_copy,
        check=False,
    )
    assert conflict.returncode == 2
    assert json.loads(conflict.stdout)["event"] == "VERSION_CONFLICT"
