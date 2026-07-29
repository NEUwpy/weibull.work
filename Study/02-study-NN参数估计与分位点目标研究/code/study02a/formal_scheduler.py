"""Fail-closed planning and resumable coordination for sealed Study/02 fits."""

from __future__ import annotations

import csv
import ctypes
from ctypes import wintypes
import hmac
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import threading
import time
import secrets
from dataclasses import asdict, is_dataclass
from typing import Any, Mapping, Sequence

from .config import load_frozen_config
from .formal_config import APPROVED_MAX_EPOCHS, APPROVED_MIN_EPOCHS, load_effective_formal_config
from .formal_contracts import (
    APPROVED_EFFECTIVE_CONFIG_SHA256, APPROVED_FORMAL_SEEDS, APPROVED_SCREENING_SEEDS,
    FROZEN_MATRIX_ROWS, FROZEN_MATRIX_SHA256, _build_formal_manifest_with_matrix_evidence,
    _open_verified_matrix_evidence, _terminal_ols_slope,
)
from .formal_runner import build_training_spec, build_validation_spec
from .matrix import expand_module_matrix


_MODULE_RULES = {
    "A-E1": ("A-E1_historical", "A-E1_controlled", "A-E1_optimized_supplement"),
    "A-E3": ("A-E3_loss", "A-E3_architecture", "A-E3_joint_independent", "A-E3_fixed_shared"),
    "A-E2": ("A-E2_training_size", "A-E2_distribution"),
}
_PLAN_FIELDS = {
    "plan_version", "plan_index", "run_id", "fit_id", "fit_range", "matrix_row_sha256",
    "module_id", "rule_id", "route", "distribution", "n_mode", "fixed_n", "loss",
    "architecture", "optimizer", "training_size", "seed", "effective_config_sha256",
    "code_commit", "training_cache_key", "validation_cache_key", "training_cache_path",
    "validation_cache_path", "predecessor_trace_sha256", "expected_outputs", "test_access_count",
}
_STATE_FIELDS = {
    "state_version", "run_id", "module_id", "authority_sha256", "plan_sha256", "fit_states",
    "live_claim", "event_count", "last_event_sha256", "test_access_count",
}
_EVENT_FIELDS = {
    "event_version", "seq", "event_type", "previous_event_sha256", "authority_sha256",
    "payload", "event_sha256", "test_access_count",
}
_CLAIM_FIELDS = {
    "claim_version", "run_id", "fit_id", "owner_id", "owner_nonce", "host_id", "process_id",
    "process_start_token", "started_at", "expected_outputs", "predecessor_event_sha256",
    "fit_identity_sha256", "authority_sha256", "test_access_count",
}
_RECEIPT_FIELDS = {
    "receipt_version", "run_id", "fit_id", "owner_id", "owner_nonce", "state", "details",
    "timestamp", "claim_receipt_sha256", "authority_sha256", "test_access_count",
}
_JOURNAL_FIELDS = {
    "journal_version", "before_state_sha256", "event_relative_path", "event_sha256",
    "event", "publications", "after_state", "after_state_sha256", "controller_anchor",
}
_LOCK_FIELDS = {"lock_version", "host_id", "process_id", "process_start_token", "owner_nonce"}
_FIT_STATUS_FIELDS = {"checkpoint_sha256", "fit_id", "run_id", "status", "test_access_count"}
_EVIDENCE_FIELDS = {
    "evidence_version", "fit_id", "run_id", "checkpoint_sha256", "actual_epochs",
    "best_epoch_one_based", "hit_epoch_100", "early_stop_reason",
    "terminal_validation_slope", "validation_curve", "test_access_count",
}
_ANCHOR_FIELDS = {
    "anchor_version", "module_id", "run_id", "seq", "event_count", "event_tail_sha256",
    "state_sha256", "authority_sha256", "previous_anchor_sha256", "controller_key_id",
    "hmac_sha256",
}
_ZERO_HASH = "0" * 64


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _identifier(value: str, label: str) -> str:
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
    if not isinstance(value, str) or not value or any(char not in allowed for char in value):
        raise ValueError(f"{label} must be a safe non-empty identifier")
    return value


def _hash(value: Any, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return value


def _resolved(path: Path) -> Path:
    return Path(path).absolute()


def _reject_alias(path: Path, *, require_file: bool = False) -> Path:
    path = _resolved(path)
    for current in (path, *path.parents):
        if not current.exists():
            continue
        info = current.lstat()
        reparse = getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if stat.S_ISLNK(info.st_mode) or reparse:
            raise ValueError(f"aliases/reparse points are forbidden: {current}")
        if current.is_file() and info.st_nlink != 1:
            raise ValueError(f"hard-linked files are forbidden: {current}")
    if require_file:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError(f"expected one plain file: {path}")
    return path


def _contained(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("output path must be a non-empty relative path")
    root = _resolved(root)
    candidate = _resolved(root / relative)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("output path escapes the run directory") from exc
    return candidate


def _write_no_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_replace(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _harden_controller_key(path: Path) -> None:
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    if os.name == "nt":
        account = os.environ.get("USERNAME")
        if account:
            try:
                subprocess.run(
                    ["icacls", str(path), "/inheritance:r", "/grant:r", f"{account}:(F)"],
                    check=False, capture_output=True, text=True,
                )
            except OSError:
                pass


def _controller_context(artifact_root: Path, *, create: bool) -> dict[str, Any]:
    root = _reject_alias(_resolved(artifact_root) / ".study02-controller")
    key_path = root / "keys" / "controller.hmac.key"
    if create and not key_path.exists():
        key_path.parent.mkdir(parents=True, exist_ok=True)
        created = False
        try:
            with key_path.open("xb") as handle:
                handle.write(secrets.token_bytes(32)); handle.flush(); os.fsync(handle.fileno())
            created = True
            _harden_controller_key(key_path)
        except FileExistsError:
            pass
        except Exception:
            if created:
                key_path.unlink(missing_ok=True)
            raise
    snapshot = _read_identity_snapshot(key_path)
    if len(snapshot["bytes"]) != 32:
        raise ValueError("controller HMAC key must be exactly 32 secret bytes")
    return {"root": root, "key_path": key_path, "key": snapshot["bytes"], "key_id": _sha(snapshot["bytes"])}


def _anchor_dir(run_dir: Path) -> Path:
    artifact_root = _resolved(run_dir).parents[1]
    return artifact_root / ".study02-controller" / "runs" / run_dir.parent.name / run_dir.name / "anchors"


def _sign_anchor(core: Mapping[str, Any], key: bytes) -> str:
    return hmac.new(key, _canonical(core), hashlib.sha256).hexdigest()


def _anchor_path(run_dir: Path, anchor: Mapping[str, Any]) -> Path:
    return _anchor_dir(run_dir) / f"{anchor['seq']:08d}-{anchor['event_tail_sha256']}.json"


def _make_anchor(run_dir: Path, event: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
    context = _controller_context(_resolved(run_dir).parents[1], create=False)
    directory = _anchor_dir(run_dir)
    previous = _ZERO_HASH
    if directory.exists():
        existing = sorted(Path(entry.path) for entry in os.scandir(_reject_alias(directory)))
        if existing:
            previous = _sha(_reject_alias(existing[-1], require_file=True).read_bytes())
    core = {"anchor_version": "study02-formal-controller-anchor-v1", "module_id": state["module_id"], "run_id": state["run_id"], "seq": event["seq"], "event_count": state["event_count"], "event_tail_sha256": event["event_sha256"], "state_sha256": _sha(_canonical(state)), "authority_sha256": state["authority_sha256"], "previous_anchor_sha256": previous, "controller_key_id": context["key_id"]}
    return {**core, "hmac_sha256": _sign_anchor(core, context["key"])}


def _publish_anchor(run_dir: Path, anchor: Mapping[str, Any]) -> None:
    path = _anchor_path(run_dir, anchor)
    if path.exists():
        if _reject_alias(path, require_file=True).read_bytes() != _canonical(anchor):
            raise ValueError("controller anchor conflicts with an existing signed checkpoint")
        return
    _write_no_replace(path, _canonical(anchor))


def _load_exact(path: Path, fields: set[str], label: str) -> tuple[bytes, dict[str, Any]]:
    path = _reject_alias(path, require_file=True)
    payload = path.read_bytes()
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid canonical UTF-8 JSON") from exc
    if not isinstance(value, dict) or set(value) != fields or payload != _canonical(value):
        raise ValueError(f"{label} must match its exact canonical schema")
    return payload, value


def _decode_exact(payload: bytes, fields: set[str], label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid canonical UTF-8 JSON") from exc
    if not isinstance(value, dict) or set(value) != fields or payload != _canonical(value):
        raise ValueError(f"{label} must match its exact canonical schema")
    return value


def _git_sha(study_root: Path) -> str:
    repo_root = _resolved(study_root).parents[1]
    value = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, capture_output=True, text=True).stdout.strip().lower()
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("current approved code SHA is invalid")
    return value


def _git_commit_exists(repo_root: Path, code_commit: str) -> None:
    """Verify a commit object exists in the git object database (content-addressed).

    Uses ``git cat-file -t`` (reads only from the object database, no checkout, no
    worktree). Raises ValueError if the object is missing or not a commit.
    """
    result = subprocess.run(
        ["git", "cat-file", "-t", code_commit],
        cwd=str(repo_root), capture_output=True, text=True,
    )
    if result.returncode != 0 or result.stdout.strip() != "commit":
        raise ValueError(
            f"historical code_commit {code_commit} is not a reachable git commit object"
        )


def _git_list_py_blobs(
    repo_root: Path, code_commit: str, tree_posix: str,
) -> list[tuple[str, str]]:
    """List ``(relative_posix_path, git_blob_sha)`` for .py blobs under ``tree_posix``.

    Uses ``git ls-tree -r <commit> -- <tree>``. Returns paths relative to
    ``tree_posix`` (forward slashes). Fails closed if the tree is missing at the
    sealed commit (path-set drift between seal time and verification).
    """
    result = subprocess.run(
        ["git", "-c", "core.quotePath=false", "ls-tree", "-r", code_commit, "--", tree_posix],
        cwd=str(repo_root), capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        raise ValueError(
            f"git ls-tree failed at {code_commit}:{tree_posix}: {result.stderr.strip()}"
        )
    prefix = tree_posix + "/"
    blobs: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if "\t" not in line:
            continue
        meta, path = line.split("\t", 1)
        parts = meta.split()
        if len(parts) != 3 or parts[1] != "blob":
            continue
        if not path.startswith(prefix) or not path.endswith(".py"):
            continue
        relative = path[len(prefix):]
        if "__pycache__" in relative.split("/"):
            continue
        blobs.append((relative, parts[2]))
    return blobs


def _git_read_paths_batch(
    repo_root: Path, code_commit: str, repo_paths: list[str],
) -> dict[str, bytes]:
    """Read multiple file blobs from the git object database in one subprocess.

    Uses ``git cat-file --batch`` with ``<commit>:<path>`` input lines (one
    subprocess for all paths). Returns raw blob content (git stores LF-normalized
    text). No checkout, no worktree. Fails closed on any missing path or non-blob.
    """
    if not repo_paths:
        return {}
    stdin_lines = [f"{code_commit}:{path}" for path in repo_paths]
    stdin_data = "\n".join(stdin_lines) + "\n"
    proc = subprocess.run(
        ["git", "-c", "core.quotePath=false", "cat-file", "--batch"],
        cwd=str(repo_root), input=stdin_data.encode("utf-8"),
        capture_output=True,
    )
    if proc.returncode != 0:
        raise ValueError("git cat-file --batch failed to read historical blobs")
    contents: dict[str, bytes] = {}
    data = proc.stdout
    pos = 0
    for expected_path in repo_paths:
        newline_idx = data.index(b"\n", pos)
        header = data[pos:newline_idx]
        pos = newline_idx + 1
        parts = header.split(b" ")
        if len(parts) < 3 or parts[1] != b"blob":
            raise ValueError(
                f"historical git path {expected_path!r} is missing or not a blob "
                f"at commit {code_commit} (header={header!r})"
            )
        size = int(parts[2])
        content = data[pos:pos + size]
        if len(content) != size:
            raise ValueError("git cat-file --batch truncated blob content")
        pos += size
        if pos < len(data) and data[pos:pos + 1] == b"\n":
            pos += 1
        contents[expected_path] = content
    return contents


def _crlf_normalize(content: bytes) -> bytes:
    """Normalize bytes to CRLF (LF -> CRLF, de-duplicating any existing CR)."""
    return content.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def _verify_scoped_code_against_git(
    study_root: Path, code_commit: str,
    sealed_files: Mapping[str, str], sealed_scoped_sha: str,
) -> None:
    """Verify sealed ``scoped_code_files`` against git blobs at ``code_commit``.

    Content-addressed: reads each scoped .py blob from the git object database
    (``git cat-file``, no checkout, no worktree) and compares its SHA-256 against the
    sealed manifest. R4-5: there is NO working-tree fallback -- only the git blob
    (LF-normalized, as git stores it) and its deterministic LF->CRLF reconstruction
    are tried. A file whose neither form matches the sealed hash fails closed.

    Line-ending tolerance: git blobs store LF-normalized text, but a Windows working
    tree may carry CRLF for files that were smudge-converted before the repo's
    ``eol=lf`` rule took effect. For each file we accept either the LF hash (git blob
    as-is) or the CRLF hash (LF->CRLF conversion), whichever matches the sealed hash.
    This is not a weakening: an attacker would need a SHA-256 preimage for either form
    to forge a file (computationally infeasible). Files whose sealed bytes carry
    mixed/inconsistent line endings (neither pure LF nor pure CRLF) cannot be
    reconstructed from the LF-normalized git blob and fail closed -- per R4-5 they
    MUST NOT be substituted from the current working tree.

    The aggregate ``scoped_code_sha256`` is recomputed from the matched per-file
    hashes and must equal ``sealed_scoped_sha``.
    """
    study_root = _resolved(study_root)
    repo_root = study_root.parents[1]
    code_tree_posix = (study_root.relative_to(repo_root) / "code").as_posix()
    shared_tree_posix = "python/studies"
    scoped_to_repo: dict[str, str] = {}
    all_repo_paths: list[str] = []
    seen_paths: set[str] = set()
    for scoped_prefix, tree_posix in (
        ("study02", code_tree_posix),
        ("studies", shared_tree_posix),
    ):
        for relative_posix, _blob_sha in _git_list_py_blobs(repo_root, code_commit, tree_posix):
            scoped_key = f"{scoped_prefix}/{relative_posix}"
            repo_path = f"{tree_posix}/{relative_posix}"
            scoped_to_repo[scoped_key] = repo_path
            if repo_path not in seen_paths:
                seen_paths.add(repo_path)
                all_repo_paths.append(repo_path)
    # Path-set gate: the scoped path set at the sealed commit must exactly match
    # what the manifest sealed. Added/removed files both fail closed.
    if set(scoped_to_repo) != set(sealed_files):
        sealed_only = set(sealed_files) - set(scoped_to_repo)
        git_only = set(scoped_to_repo) - set(sealed_files)
        raise ValueError(
            f"historical scoped path-set drift at {code_commit}: "
            f"sealed_only={sorted(sealed_only)[:5]}, git_only={sorted(git_only)[:5]}"
        )
    contents = _git_read_paths_batch(repo_root, code_commit, all_repo_paths)
    matched_files: dict[str, str] = {}
    for scoped_key, sealed_hash in sealed_files.items():
        repo_path = scoped_to_repo[scoped_key]
        content = contents[repo_path]
        lf_hash = _sha(content)
        if lf_hash == sealed_hash:
            matched_files[scoped_key] = lf_hash
            continue
        crlf_hash = _sha(_crlf_normalize(content))
        if crlf_hash == sealed_hash:
            matched_files[scoped_key] = crlf_hash
            continue
        # R4-5: fail closed. No working-tree fallback -- if neither the LF git blob
        # nor its deterministic CRLF reconstruction matches the sealed hash, the
        # sealed bytes cannot be recovered from git objects (the file likely had
        # mixed line endings at seal time). Report and stop; do not substitute.
        raise ValueError(
            f"historical scoped blob hash mismatch for {scoped_key!r} at "
            f"{code_commit}: sealed={sealed_hash[:16]}, "
            f"lf={lf_hash[:16]}, crlf={crlf_hash[:16]}"
        )
    recomputed = _sha(_canonical(matched_files))
    if recomputed != sealed_scoped_sha:
        raise ValueError(
            f"historical scoped_code_sha256 mismatch at {code_commit}: "
            f"sealed={sealed_scoped_sha[:16]}, recomputed={recomputed[:16]}"
        )


def _read_identity_snapshot(path: Path) -> dict[str, Any]:
    path = _reject_alias(path, require_file=True)
    with path.open("rb") as handle:
        before = os.fstat(handle.fileno()); payload = handle.read(); after = os.fstat(handle.fileno())
    final = path.stat()
    identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    if identity != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or identity != (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns):
        raise ValueError(f"file identity changed during one-read snapshot: {path}")
    return {"path": path, "bytes": payload, "identity": identity}


def _scoped_code_snapshot(study_root: Path) -> dict[str, Any]:
    """Hash the Study02 scientific code AND the shared research code it depends on.

    Data generation reaches outside ``code/``: ``design.py`` imports
    ``studies.common.sample``. A run is only reproducible if both the Study02 tree and
    the shared ``python/studies`` tree are bound into the authority, so a drift in
    either fails closed. Keys are namespaced (``study02/...``, ``studies/...``).
    """
    study_root = _resolved(study_root)
    repo_root = study_root.parents[1]
    files: dict[str, str] = {}
    code_root = study_root / "code"
    study_paths = sorted(path for path in code_root.rglob("*.py") if "__pycache__" not in path.parts)
    if not study_paths:
        raise ValueError("scoped Study02 production code tree is empty")
    for path in study_paths:
        snapshot = _read_identity_snapshot(path)
        files[f"study02/{path.relative_to(code_root).as_posix()}"] = _sha(snapshot["bytes"])
    shared_root = repo_root / "python" / "studies"
    if shared_root.is_dir():
        shared_paths = sorted(path for path in shared_root.rglob("*.py") if "__pycache__" not in path.parts)
        for path in shared_paths:
            snapshot = _read_identity_snapshot(path)
            files[f"studies/{path.relative_to(shared_root).as_posix()}"] = _sha(snapshot["bytes"])
    return {"files": files, "scoped_code_sha256": _sha(_canonical(files))}


def _assert_scoped_code_clean(study_root: Path) -> None:
    study_root = _resolved(study_root)
    repo_root = study_root.parents[1]
    scopes: list[Path] = [(study_root / "code").relative_to(repo_root)]
    shared_relative = Path("python") / "studies"
    if (repo_root / shared_relative).is_dir():
        scopes.append(shared_relative)
    dirty: list[str] = []
    for relative in scopes:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", str(relative)],
            cwd=repo_root, check=True, capture_output=True, text=True, encoding="utf-8",
        )
        if result.stdout.strip():
            dirty.append(str(relative))
    if dirty:
        raise ValueError(f"Study02 scoped scientific code tree is dirty: {dirty}")


def _process_start_token(process_id: int) -> str | None:
    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetProcessTimes.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
        ]
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, process_id)
        if not handle:
            return None
        try:
            creation = wintypes.FILETIME(); exit_time = wintypes.FILETIME()
            kernel = wintypes.FILETIME(); user = wintypes.FILETIME()
            if not kernel32.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time), ctypes.byref(kernel), ctypes.byref(user)):
                return None
            value = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
            return f"win-filetime-{value}"
        finally:
            kernel32.CloseHandle(handle)
    stat_path = Path(f"/proc/{process_id}/stat")
    if not stat_path.is_file():
        return None
    fields = stat_path.read_text(encoding="ascii").split()
    return f"proc-start-{fields[21]}" if len(fields) > 21 else None


def _identity_live(identity: Mapping[str, Any]) -> bool:
    return identity.get("host_id") == socket.gethostname() and _process_start_token(identity.get("process_id")) == identity.get("process_start_token")


def _identity_confirmed_dead(identity: Mapping[str, Any]) -> bool:
    return identity.get("host_id") == socket.gethostname() and _process_start_token(identity.get("process_id")) != identity.get("process_start_token")


def _matrix_snapshot(study_root: Path, matrix_path: Path):
    expected_path = _resolved(study_root / "artifacts" / "pilot" / "G3-matrix" / "experiment_matrix.csv")
    actual_path = _resolved(matrix_path)
    if actual_path != expected_path:
        raise ValueError("formal matrix path must be the exact frozen repository path")
    evidence = _open_verified_matrix_evidence(actual_path)
    payload = evidence.payload
    if _sha(payload) != FROZEN_MATRIX_SHA256:
        raise ValueError("formal matrix SHA-256 mismatch")
    try:
        rows = list(csv.DictReader(payload.decode("utf-8").splitlines()))
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("formal matrix is not canonical UTF-8 CSV") from exc
    if len(rows) != FROZEN_MATRIX_ROWS or len(rows) > 900 or len({row["fit_id"] for row in rows}) != len(rows):
        raise ValueError("formal matrix row identity/count/cap mismatch")
    frozen = load_frozen_config(study_root)
    expected = [{key: str(value) for key, value in row.items()} for row in expand_module_matrix(frozen).to_dict("records")]
    if rows != expected:
        raise ValueError("formal matrix differs from the independently reconstructed frozen order")
    return evidence, rows


def _distribution(row: Mapping[str, str]) -> str:
    if row["route"].startswith(("H0_", "H1")) or row["route"].endswith(":legacy_grid"):
        return "legacy_grid"
    return "extended_wide" if row["route"].endswith(":extended_wide") else "core_continuous"


def _plan_rows(study_root: Path, rows: Sequence[dict[str, str]], module_id: str, run_id: str, cache_root: Path, code_commit: str, predecessor_hash: str) -> list[dict[str, Any]]:
    frozen = load_frozen_config(study_root); effective = load_effective_formal_config(study_root)
    selected = [row for row in rows if row["module"] == module_id]
    result: list[dict[str, Any]] = []
    for index, row in enumerate(selected):
        shared = row["n"] == "shared"; fixed_n = None if shared else int(row["n"])
        n_mode = "shared_n" if shared else "fixed_n"; distribution = _distribution(row)
        training_size = int(row["training_size"])
        if module_id == "A-E1":
            route = row["route"]
            training = build_training_spec(route=route, distribution=distribution, n_mode=n_mode, fixed_n=fixed_n, training_rows=training_size, frozen_config=frozen, effective_config=effective)
            validation_distribution = "legacy_grid" if distribution == "legacy_grid" and route.startswith(("H0_", "H1")) else "core_continuous"
            validation = build_validation_spec(route=route, distribution=validation_distribution, n_mode=n_mode, fixed_n=fixed_n, frozen_config=frozen, effective_config=effective)
            training_key, validation_key = training.cache_key, validation.cache_key
        else:
            common = {"schema_version": "study02-formal-deferred-dataset-v1", "route": row["route"], "distribution": distribution, "n_mode": n_mode, "fixed_n": fixed_n, "training_size": training_size, "effective_config_sha256": effective.effective_config_sha256, "predecessor_trace_sha256": predecessor_hash}
            training_key = _sha(_canonical({**common, "role": "training"})); validation_key = _sha(_canonical({**common, "role": "validation"}))
        fit_number = int(row["fit_id"].rsplit("-", 1)[1])
        outputs = [
            {"relative_path": f"outputs/{row['fit_id']}/checkpoint.pt", "content_type": "binary", "required": True},
            {"relative_path": f"outputs/{row['fit_id']}/fit_status.json", "content_type": "fit_status_json", "required": True},
            {"relative_path": f"outputs/{row['fit_id']}/evidence.json", "content_type": "evidence_json", "required": True},
        ]
        item = {
            "plan_version": "study02-formal-plan-row-v2", "plan_index": index, "run_id": run_id,
            "fit_id": row["fit_id"], "fit_range": [fit_number, fit_number], "matrix_row_sha256": _sha(_canonical(row)),
            "module_id": module_id, "rule_id": row["rule_id"], "route": row["route"], "distribution": distribution,
            "n_mode": n_mode, "fixed_n": fixed_n, "loss": row["loss"], "architecture": row["architecture"],
            "optimizer": row["optimizer"], "training_size": training_size, "seed": int(row["seed"]),
            "effective_config_sha256": effective.effective_config_sha256, "code_commit": code_commit,
            "training_cache_key": training_key, "validation_cache_key": validation_key,
            "training_cache_path": str(cache_root / training_key), "validation_cache_path": str(cache_root / validation_key),
            "predecessor_trace_sha256": predecessor_hash, "expected_outputs": outputs, "test_access_count": 0,
        }
        if set(item) != _PLAN_FIELDS:
            raise AssertionError("internal formal plan schema mismatch")
        result.append(item)
    return result


def _predecessor_scope(predecessor: Any, artifact_root: Path) -> Mapping[str, Any] | None:
    if predecessor is None:
        return None
    value = dict(predecessor) if isinstance(predecessor, Mapping) else asdict(predecessor) if is_dataclass(predecessor) else None
    if value is None:
        raise ValueError("predecessor evidence must be a mapping or immutable dataclass")
    root = _resolved(artifact_root)
    # Control-plane v2: ``staged_ledger_path`` is optional (None for A-E1 root + legacy
    # callers); validate scope/alias only when present. ``trace_path``/``receipt_path``/
    # ``ledger_path`` remain required, so the loop below stays fail-closed for those.
    for field in ("trace_path", "receipt_path", "ledger_path", "staged_ledger_path"):
        if field not in value:
            if field == "staged_ledger_path":
                continue
            raise ValueError(f"predecessor evidence is missing {field}")
        raw = value.get(field)
        if field == "staged_ledger_path" and raw is None:
            continue
        original = Path(raw).absolute()
        _reject_alias(original, require_file=True)
        path = original.resolve(strict=True)
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError("predecessor evidence must remain inside the same artifact root") from exc
        value[field] = path
    return value


def _authority(*, study_root: Path, matrix_path: Path, module_id: str, run_id: str, artifact_root: Path, cache_root: Path, predecessor: Mapping[str, Any] | None, controller_key_id: str, matrix_bundle: tuple[Any, list[dict[str, str]]] | None = None, sealed_code_commit: str | None = None, sealed_code_snapshot: Mapping[str, Any] | None = None) -> tuple[dict[str, Any], list[dict[str, Any]], bytes, dict[str, Any]]:
    study_root = _reject_alias(study_root); cache_root = _reject_alias(cache_root)
    if sealed_code_commit is None:
        # Active run: assert the working tree is clean and derive code/scoped from HEAD.
        _assert_scoped_code_clean(study_root)
        code_commit = _git_sha(study_root)
        code_snapshot = _scoped_code_snapshot(study_root)
    else:
        # R3-C historical verification: use the sealed code_commit + pre-computed
        # content-addressed snapshot (read from git objects, NOT the working tree).
        # The caller (verify_historical_authority) is responsible for verifying the
        # commit exists and the snapshot matches the sealed authority before calling.
        if sealed_code_snapshot is None:
            raise ValueError("sealed_code_snapshot is required when sealed_code_commit is set")
        code_commit = sealed_code_commit
        code_snapshot = sealed_code_snapshot
    predecessor = _predecessor_scope(predecessor, artifact_root)
    matrix_evidence, matrix_rows = _matrix_snapshot(study_root, matrix_path) if matrix_bundle is None else matrix_bundle
    matrix_bytes = matrix_evidence.payload
    effective = load_effective_formal_config(study_root)
    selected = [row for row in matrix_rows if row["module"] == module_id]
    rules = tuple(dict.fromkeys(row["rule_id"] for row in selected)); fits = tuple(row["fit_id"] for row in selected)
    formal = _build_formal_manifest_with_matrix_evidence(effective_config=effective, module_id=module_id, run_id=run_id, code_commit=code_commit, matrix_path=matrix_path, matrix_evidence=matrix_evidence, rule_ids=rules, fit_ids=fits, role_namespaces={"training": "study02/formal/training", "validation": "study02/formal/validation"}, screening_seeds=APPROVED_SCREENING_SEEDS, formal_seeds=APPROVED_FORMAL_SEEDS, predecessor=predecessor)
    predecessor_hash = formal["predecessor"]["selection_trace_sha256"]
    plan = _plan_rows(study_root, matrix_rows, module_id, run_id, cache_root, code_commit, predecessor_hash)
    plan_bytes = b"".join(_canonical(row) for row in plan); plan_sha = _sha(plan_bytes)
    predecessor_input = None if predecessor is None else {key: str(value) if isinstance(value, Path) else value for key, value in predecessor.items()}
    authority = {"study_root": str(study_root), "matrix_path": str(_resolved(matrix_path)), "matrix_sha256": _sha(matrix_bytes), "cache_root": str(cache_root), "code_commit": code_commit, "scoped_code_sha256": code_snapshot["scoped_code_sha256"], "scoped_code_files": code_snapshot["files"], "controller_key_id": _hash(controller_key_id, "controller key ID"), "effective_config_sha256": effective.effective_config_sha256, "predecessor_input": predecessor_input, "predecessor_trace_sha256": predecessor_hash, "plan_sha256": plan_sha}
    authority_sha = _sha(_canonical(authority)); authority["authority_sha256"] = authority_sha
    return formal, plan, plan_bytes, authority


def _event(event_type: str, seq: int, previous: str, authority_sha: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    core = {"event_version": "study02-formal-scheduler-event-v2", "seq": seq, "event_type": event_type, "previous_event_sha256": previous, "authority_sha256": authority_sha, "payload": dict(payload), "test_access_count": 0}
    return {**core, "event_sha256": _sha(_canonical(core))}


def _event_path(run_dir: Path, event: Mapping[str, Any]) -> Path:
    return run_dir / "events" / f"{event['seq']:08d}-{event['event_sha256']}.json"


def _validate_plan(plan_bytes: bytes, manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    try:
        plan = [json.loads(line) for line in plan_bytes.decode("utf-8").splitlines()]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("formal plan must be canonical JSONL") from exc
    if b"".join(_canonical(row) for row in plan) != plan_bytes or _sha(plan_bytes) != manifest["scheduler"]["authority"]["plan_sha256"]:
        raise ValueError("formal plan canonical bytes/hash mismatch")
    for index, row in enumerate(plan):
        if not isinstance(row, dict) or set(row) != _PLAN_FIELDS or row["plan_index"] != index or row["test_access_count"] != 0:
            raise ValueError("formal plan row schema/order mismatch")
        outputs = row["expected_outputs"]
        if not isinstance(outputs, list) or len(outputs) != 3 or any(set(item) != {"relative_path", "content_type", "required"} or item["required"] is not True for item in outputs):
            raise ValueError("formal plan expected output schema mismatch")
    return plan


def _event_files(run_dir: Path) -> list[Path]:
    directory = _reject_alias(run_dir / "events")
    entries = list(os.scandir(directory))
    if any(not entry.is_file(follow_symlinks=False) for entry in entries):
        raise ValueError("event ledger contains a non-file entry")
    return [Path(entry.path) for entry in sorted(entries, key=lambda item: item.name)]


def _load_events(run_dir: Path, manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []; previous = _ZERO_HASH
    for seq, path in enumerate(_event_files(run_dir)):
        _, event = _load_exact(path, _EVENT_FIELDS, "scheduler event")
        core = {key: value for key, value in event.items() if key != "event_sha256"}
        expected_name = f"{seq:08d}-{event['event_sha256']}.json"
        if path.name != expected_name or event["seq"] != seq or event["previous_event_sha256"] != previous or event["event_sha256"] != _sha(_canonical(core)) or event["authority_sha256"] != manifest["scheduler"]["authority"]["authority_sha256"] or event["test_access_count"] != 0:
            raise ValueError("scheduler event canonical sequence/hash/authority mismatch")
        previous = event["event_sha256"]; events.append(event)
    if not events or events[0]["event_sha256"] != manifest["scheduler"]["genesis_event_sha256"]:
        raise ValueError("scheduler immutable genesis event mismatch")
    return events


def _claim_path(run_dir: Path, relative: str) -> Path:
    path = _contained(run_dir, relative)
    if path.parent != run_dir / "claims":
        raise ValueError("claim receipt path is outside the exact claims directory")
    return path


def _receipt_path(run_dir: Path, relative: str) -> Path:
    path = _contained(run_dir, relative)
    if path.parent != run_dir / "receipts":
        raise ValueError("terminal receipt path is outside the exact receipts directory")
    return path


def _replay(run_dir: Path, manifest: Mapping[str, Any], plan: Sequence[dict[str, Any]], events: Sequence[dict[str, Any]], virtual_records: Mapping[str, tuple[bytes, dict[str, Any]]] | None = None, allow_future_records: bool = False, _checkpoints: list[str] | None = None) -> dict[str, Any]:
    authority_sha = manifest["scheduler"]["authority"]["authority_sha256"]
    virtual_records = {} if virtual_records is None else dict(virtual_records)
    fit_states = {row["fit_id"]: "pending" for row in plan}; by_fit = {row["fit_id"]: row for row in plan}
    live: dict[str, Any] | None = None; referenced_claims: set[str] = set(); referenced_receipts: set[str] = set()

    def _snapshot_state(event_count: int, last_event_sha256: str) -> dict[str, Any]:
        # canonical scheduler state dict -- the single source of truth used both for the
        # return value and, when ``_checkpoints`` is provided, for the per-event authority
        # state hashes captured during one ordered replay (a snapshot, not a second state).
        return {"state_version": "study02-formal-scheduler-state-v2", "run_id": manifest["run_id"], "module_id": manifest["module_id"], "authority_sha256": authority_sha, "plan_sha256": manifest["scheduler"]["authority"]["plan_sha256"], "fit_states": dict(fit_states), "live_claim": live, "event_count": event_count, "last_event_sha256": last_event_sha256, "test_access_count": 0}

    for seq, event in enumerate(events):
        payload = event["payload"]; kind = event["event_type"]
        if seq == 0:
            if kind != "run_initialized" or set(payload) != {"run_id", "module_id", "plan_sha256"} or payload != {"run_id": manifest["run_id"], "module_id": manifest["module_id"], "plan_sha256": manifest["scheduler"]["authority"]["plan_sha256"]}:
                raise ValueError("scheduler genesis payload schema mismatch")
            if _checkpoints is not None:
                _checkpoints.append(_sha(_canonical(_snapshot_state(seq + 1, event["event_sha256"]))))
            continue
        if kind == "fit_claimed":
            if set(payload) != {"fit_id", "claim_relative_path", "claim_sha256"} or live is not None or fit_states.get(payload.get("fit_id")) != "pending":
                raise ValueError("fit_claimed event is not a valid replay transition")
            claim_path = _claim_path(run_dir, payload["claim_relative_path"])
            claim_bytes, claim = virtual_records.get(payload["claim_relative_path"], (None, None))
            if claim_bytes is None:
                claim_bytes, claim = _load_exact(claim_path, _CLAIM_FIELDS, "claim receipt")
            elif set(claim) != _CLAIM_FIELDS or claim_bytes != _canonical(claim):
                raise ValueError("virtual claim receipt schema mismatch")
            row = by_fit[payload["fit_id"]]
            if _sha(claim_bytes) != payload["claim_sha256"] or claim["fit_id"] != row["fit_id"] or claim["run_id"] != manifest["run_id"] or claim["authority_sha256"] != authority_sha or claim["fit_identity_sha256"] != _sha(_canonical(row)) or claim["expected_outputs"] != row["expected_outputs"] or claim["predecessor_event_sha256"] != event["previous_event_sha256"] or claim["test_access_count"] != 0:
                raise ValueError("claim receipt fit/authority/plan binding mismatch")
            if not all(isinstance(claim[field], str) and claim[field] for field in ("owner_id", "owner_nonce", "host_id", "process_start_token", "started_at")) or isinstance(claim["process_id"], bool) or not isinstance(claim["process_id"], int) or claim["process_id"] <= 0:
                raise ValueError("claim receipt owner/process identity schema mismatch")
            referenced_claims.add(claim_path.name); live = {**claim, "claim_relative_path": payload["claim_relative_path"], "claim_sha256": payload["claim_sha256"]}; fit_states[row["fit_id"]] = "claimed"
        elif kind == "claim_recovered":
            if set(payload) != {"fit_id", "timestamp", "reason"} or live is None or payload["fit_id"] != live["fit_id"] or payload["reason"] != "dead_identity_no_outputs":
                raise ValueError("claim_recovered event is not a valid replay transition")
            fit_states[live["fit_id"]] = "pending"; live = None
        elif kind in {"fit_succeeded", "fit_failed"}:
            terminal = kind.removeprefix("fit_")
            if set(payload) != {"fit_id", "receipt_relative_path", "receipt_sha256"} or live is None or payload["fit_id"] != live["fit_id"]:
                raise ValueError("terminal event is not a valid replay transition")
            receipt_path = _receipt_path(run_dir, payload["receipt_relative_path"])
            receipt_bytes, receipt = virtual_records.get(payload["receipt_relative_path"], (None, None))
            if receipt_bytes is None:
                receipt_bytes, receipt = _load_exact(receipt_path, _RECEIPT_FIELDS, "terminal receipt")
            elif set(receipt) != _RECEIPT_FIELDS or receipt_bytes != _canonical(receipt):
                raise ValueError("virtual terminal receipt schema mismatch")
            if _sha(receipt_bytes) != payload["receipt_sha256"] or receipt["run_id"] != manifest["run_id"] or receipt["fit_id"] != live["fit_id"] or receipt["owner_id"] != live["owner_id"] or receipt["owner_nonce"] != live["owner_nonce"] or receipt["state"] != terminal or receipt["claim_receipt_sha256"] != live["claim_sha256"] or receipt["authority_sha256"] != authority_sha or receipt["test_access_count"] != 0:
                raise ValueError("terminal receipt schema/fit/claim/authority mismatch")
            if terminal == "failed" and set(receipt["details"]) != {"failure_code"}:
                raise ValueError("failure receipt details schema mismatch")
            if terminal == "succeeded" and set(receipt["details"]) != {"output_hashes"}:
                raise ValueError("success receipt details schema mismatch")
            if terminal == "failed" and _output_snapshot(run_dir, live["fit_id"]):
                raise ValueError("failed terminal receipt conflicts with scientific output")
            if terminal == "succeeded":
                _validate_success_files(run_dir, by_fit[live["fit_id"]], receipt["details"]["output_hashes"])
            referenced_receipts.add(receipt_path.name); fit_states[live["fit_id"]] = terminal; live = None
        else:
            raise ValueError("unknown scheduler event type")
        if _checkpoints is not None:
            _checkpoints.append(_sha(_canonical(_snapshot_state(seq + 1, event["event_sha256"]))))
    for dirname, referenced in (("claims", referenced_claims), ("receipts", referenced_receipts)):
        directory = run_dir / dirname
        actual: set[str] = set()
        if directory.exists():
            entries = list(os.scandir(_reject_alias(directory)))
            if any(not entry.is_file(follow_symlinks=False) for entry in entries):
                raise ValueError(f"{dirname} contains alias or non-file entry")
            for entry in entries:
                _reject_alias(Path(entry.path), require_file=True); actual.add(entry.name)
        virtual_names = {Path(relative).name for relative in virtual_records if Path(relative).parent.as_posix() == dirname}
        available = actual | virtual_names
        if (not allow_future_records and available != referenced) or (allow_future_records and not referenced.issubset(available)) or actual & virtual_names:
            raise ValueError(f"{dirname} contains missing, extra, or unbound immutable records")
    return _snapshot_state(len(events), events[-1]["event_sha256"])


def _validate_controller_anchors(run_dir: Path, manifest: Mapping[str, Any], plan: Sequence[dict[str, Any]], events: Sequence[dict[str, Any]], final_state: Mapping[str, Any]) -> None:
    context = _controller_context(_resolved(run_dir).parents[1], create=False)
    if context["key_id"] != manifest["scheduler"]["authority"]["controller_key_id"]:
        raise ValueError("controller key ID differs from the immutable manifest authority")
    directory = _reject_alias(_anchor_dir(run_dir))
    entries = list(os.scandir(directory))
    if any(not entry.is_file(follow_symlinks=False) for entry in entries):
        raise ValueError("controller anchor directory contains a non-file entry")
    paths = [Path(entry.path) for entry in sorted(entries, key=lambda item: item.name)]
    if len(paths) != len(events):
        raise ValueError("controller anchor count does not match the run event count")
    # One ordered replay captures the canonical authority state hash after each event is
    # applied, so every signed anchor is compared against the exact state at its seq without
    # re-reading and re-validating the claim/receipt files for every prefix. Each claim and
    # receipt file is still read, structurally validated and hash-bound exactly once during
    # this single replay (no cached sidecar is ever trusted). ``_checkpoints[seq]`` is
    # byte-for-byte ``_sha(_canonical(_replay(events[:seq+1], allow_future_records=True)))``.
    checkpoints: list[str] = []
    _replay(run_dir, manifest, plan, events, allow_future_records=True, _checkpoints=checkpoints)
    previous = _ZERO_HASH
    for seq, (path, event) in enumerate(zip(paths, events)):
        anchor_bytes, anchor = _load_exact(path, _ANCHOR_FIELDS, "controller anchor")
        core = {key: value for key, value in anchor.items() if key != "hmac_sha256"}
        if path != _anchor_path(run_dir, anchor) or anchor["seq"] != seq or anchor["event_count"] != seq + 1 or anchor["event_tail_sha256"] != event["event_sha256"] or anchor["state_sha256"] != checkpoints[seq] or anchor["authority_sha256"] != final_state["authority_sha256"] or anchor["previous_anchor_sha256"] != previous or anchor["controller_key_id"] != context["key_id"] or not hmac.compare_digest(anchor["hmac_sha256"], _sign_anchor(core, context["key"])):
            raise ValueError("controller signed tail checkpoint does not match immutable replay")
        previous = _sha(anchor_bytes)


def _predecessor_from_manifest(manifest: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = manifest["scheduler"]["authority"]["predecessor_input"]
    return None if value is None else value


def _recover_journal(run_dir: Path) -> None:
    path = run_dir / ".scheduler.journal"
    if not path.exists():
        return
    _, journal = _load_exact(path, _JOURNAL_FIELDS, "scheduler transaction journal")
    event = journal["event"]
    publications = journal["publications"]
    anchor = journal["controller_anchor"]
    core = {key: value for key, value in event.items() if key != "event_sha256"} if isinstance(event, dict) else {}
    if not isinstance(event, dict) or set(event) != _EVENT_FIELDS or not isinstance(publications, list) or not isinstance(anchor, dict) or set(anchor) != _ANCHOR_FIELDS or journal["event_sha256"] != event["event_sha256"] or event["event_sha256"] != _sha(_canonical(core)) or not isinstance(journal["after_state"], dict) or set(journal["after_state"]) != _STATE_FIELDS or journal["after_state_sha256"] != _sha(_canonical(journal["after_state"])):
        raise ValueError("scheduler journal event/state schema mismatch")
    controller = _controller_context(_resolved(run_dir).parents[1], create=False)
    anchor_core = {key: value for key, value in anchor.items() if key != "hmac_sha256"}
    if anchor["event_tail_sha256"] != event["event_sha256"] or anchor["state_sha256"] != journal["after_state_sha256"] or anchor["controller_key_id"] != controller["key_id"] or not hmac.compare_digest(anchor["hmac_sha256"], _sign_anchor(anchor_core, controller["key"])):
        raise ValueError("scheduler journal controller anchor signature mismatch")
    state_path = run_dir / "scheduler_state.json"; current = _reject_alias(state_path, require_file=True).read_bytes(); current_sha = _sha(current)
    event_path = _contained(run_dir, journal["event_relative_path"])
    if event_path != _event_path(run_dir, event):
        raise ValueError("journal event path does not match the immutable event identity")
    if not isinstance(event["payload"], dict):
        raise ValueError("journal event payload must be an object")
    expected_publication = None
    if event["event_type"] == "fit_claimed":
        expected_publication = event["payload"].get("claim_relative_path")
    elif event["event_type"] in {"fit_succeeded", "fit_failed"}:
        expected_publication = event["payload"].get("receipt_relative_path")
    expected_publications = set() if expected_publication is None else {expected_publication}
    if {record.get("relative_path") for record in publications if isinstance(record, dict)} != expected_publications:
        raise ValueError("journal publications do not match the event schema")
    publication_payloads: list[tuple[Path, bytes]] = []
    for record in publications:
        if not isinstance(record, dict) or set(record) != {"relative_path", "sha256", "value"}:
            raise ValueError("journal publication schema mismatch")
        payload = _canonical(record["value"])
        if _sha(payload) != record["sha256"]:
            raise ValueError("journal publication hash mismatch")
        publication_payloads.append((_contained(run_dir, record["relative_path"]), payload))
    if current_sha == journal["before_state_sha256"]:
        for destination, payload in publication_payloads:
            if destination.exists():
                if _reject_alias(destination, require_file=True).read_bytes() != payload:
                    raise ValueError("journal publication conflicts with immutable record")
            else:
                _write_no_replace(destination, payload)
        if event_path.exists():
            if _reject_alias(event_path, require_file=True).read_bytes() != _canonical(event):
                raise ValueError("journal event path conflicts with immutable event")
        else:
            _write_no_replace(event_path, _canonical(event))
        _atomic_replace(state_path, _canonical(journal["after_state"]))
        _publish_anchor(run_dir, anchor)
    elif current_sha == journal["after_state_sha256"]:
        for destination, payload in publication_payloads:
            if not destination.is_file() or _reject_alias(destination, require_file=True).read_bytes() != payload:
                raise ValueError("journal after-state lacks its exact immutable publication")
        if not event_path.is_file() or _reject_alias(event_path, require_file=True).read_bytes() != _canonical(event):
            raise ValueError("journal after-state lacks its exact immutable event")
        _publish_anchor(run_dir, anchor)
    else:
        raise ValueError("journal matches neither before nor after state")
    path.unlink()


def _rebuild_authority(run_dir: Path, cache_root: Path, *, validate_controller: bool = True) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    run_dir = _reject_alias(run_dir); manifest_bytes = _reject_alias(run_dir / "manifest.json", require_file=True).read_bytes()
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("manifest must be canonical UTF-8 JSON") from exc
    if manifest_bytes != _canonical(manifest) or not isinstance(manifest.get("scheduler"), dict) or set(manifest["scheduler"]) != {"scheduler_version", "authority", "fit_count", "genesis_event_sha256", "test_access_count"}:
        raise ValueError("manifest must match exact scheduler schema/canonical bytes")
    authority = manifest["scheduler"]["authority"]
    if set(authority) != {"study_root", "matrix_path", "matrix_sha256", "cache_root", "code_commit", "scoped_code_sha256", "scoped_code_files", "controller_key_id", "effective_config_sha256", "predecessor_input", "predecessor_trace_sha256", "plan_sha256", "authority_sha256"}:
        raise ValueError("manifest authority schema mismatch")
    if _resolved(cache_root) != Path(authority["cache_root"]):
        raise ValueError("cache root differs from the immutable run authority")
    controller = _controller_context(_resolved(run_dir).parents[1], create=False)
    formal, expected_plan, expected_plan_bytes, current_authority = _authority(study_root=Path(authority["study_root"]), matrix_path=Path(authority["matrix_path"]), module_id=manifest["module_id"], run_id=manifest["run_id"], artifact_root=_resolved(run_dir).parents[1], cache_root=cache_root, predecessor=_predecessor_from_manifest(manifest), controller_key_id=controller["key_id"])
    if current_authority != authority:
        raise ValueError("current code/config/matrix/cache/predecessor authority drift")
    expected_scheduler = {"scheduler_version": "study02-formal-scheduler-v2", "authority": current_authority, "fit_count": len(expected_plan), "genesis_event_sha256": manifest["scheduler"]["genesis_event_sha256"], "test_access_count": 0}
    if {**formal, "scheduler": expected_scheduler} != manifest:
        raise ValueError("current authority does not reproduce the exact manifest")
    plan_bytes = _reject_alias(run_dir / "plan.jsonl", require_file=True).read_bytes(); plan = _validate_plan(plan_bytes, manifest)
    if plan_bytes != expected_plan_bytes or plan != expected_plan:
        raise ValueError("current authority does not reproduce the plan byte-for-byte")
    events = _load_events(run_dir, manifest); derived = _replay(run_dir, manifest, plan, events)
    state_bytes, state = _load_exact(run_dir / "scheduler_state.json", _STATE_FIELDS, "scheduler state")
    if state_bytes != _canonical(derived) or state != derived:
        raise ValueError("scheduler state differs from full immutable event replay")
    if validate_controller:
        _validate_controller_anchors(run_dir, manifest, plan, events, state)
    return manifest, plan, state, events


def verify_historical_authority(
    run_dir: Path, cache_root: Path, *,
    validate_controller: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    """Content-addressed historical verifier for terminal sealed predecessors (R3-C).

    R4-5: verifies ONLY sealed bytes. Does NOT call current production code
    (``_authority``/``_plan_rows``) to re-derive or "execute" historical state -- the
    sealed artifacts are verified directly through their content-addressed hashes:

    * canonical/versioned manifest bytes + exact scheduler/authority schema;
    * ``authority_sha256`` self-hash (the authority dict is sealed/intact);
    * frozen config/matrix hash cross-consistency (authority == manifest == constant);
    * commit/scoped code blobs from git objects at ``code_commit`` (LF or CRLF only,
      NO working-tree fallback -- fail-closed if neither deterministic form matches);
    * plan canonical bytes/SHA + matrix-row binding (each plan row's
      ``matrix_row_sha256`` matches the frozen matrix row);
    * events/claims/receipts/controller anchors + fit identity (full replay, the
      identical discipline to ``_rebuild_authority``);
    * all output SHAs.

    Accepts ONLY terminal sealed predecessors: ``live_claim is None`` AND every fit
    state is terminal (``succeeded``/``failed``); ``pending``/``claimed`` fail closed.

    The formal manifest段 byte-comparison (``{**formal, "scheduler": ...}``) is NOT
    applied: it is version-coupled and a sealed v1 manifest cannot be byte-reproduced
    by the current v2 build path. The sealed authority dict is verified directly via
    its ``authority_sha256`` self-hash instead, which is version-independent.
    """
    run_dir = _reject_alias(run_dir)
    manifest_bytes = _reject_alias(run_dir / "manifest.json", require_file=True).read_bytes()
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("manifest must be canonical UTF-8 JSON") from exc
    if manifest_bytes != _canonical(manifest) or not isinstance(manifest.get("scheduler"), dict) or set(manifest["scheduler"]) != {"scheduler_version", "authority", "fit_count", "genesis_event_sha256", "test_access_count"}:
        raise ValueError("manifest must match exact scheduler schema/canonical bytes")
    if manifest.get("manifest_version") not in ("study02-formal-v1", "study02-formal-v2"):
        raise ValueError("historical manifest_version is unsupported")
    authority = manifest["scheduler"]["authority"]
    if set(authority) != {"study_root", "matrix_path", "matrix_sha256", "cache_root", "code_commit", "scoped_code_sha256", "scoped_code_files", "controller_key_id", "effective_config_sha256", "predecessor_input", "predecessor_trace_sha256", "plan_sha256", "authority_sha256"}:
        raise ValueError("manifest authority schema mismatch")
    if _resolved(cache_root) != Path(authority["cache_root"]):
        raise ValueError("cache root differs from the immutable run authority")

    # R4-5: authority_sha256 self-hash. Proves the sealed authority dict is intact
    # (every field, including code/matrix/config/plan/predecessor hashes, is exactly
    # what was sealed) WITHOUT re-running current _authority/_plan_rows to re-derive it.
    authority_without_sha = {key: value for key, value in authority.items() if key != "authority_sha256"}
    if authority["authority_sha256"] != _sha(_canonical(authority_without_sha)):
        raise ValueError("historical authority_sha256 self-hash mismatch (sealed bytes tampered)")

    # R4-5: frozen config/matrix hash cross-consistency. The sealed authority, the
    # manifest block, and the frozen repository constant must all agree exactly.
    if authority["matrix_sha256"] != manifest["matrix"]["sha256"]:
        raise ValueError("historical authority matrix_sha256 disagrees with manifest matrix sha256")
    if authority["matrix_sha256"] != FROZEN_MATRIX_SHA256:
        raise ValueError("historical authority matrix_sha256 disagrees with the frozen matrix constant")
    if authority["effective_config_sha256"] != manifest["effective_config"]["sha256"]:
        raise ValueError("historical authority effective_config_sha256 disagrees with manifest")
    if authority["effective_config_sha256"] != APPROVED_EFFECTIVE_CONFIG_SHA256:
        raise ValueError("historical authority effective_config_sha256 disagrees with the frozen constant")
    if str(manifest["code_commit"]).lower() != str(authority["code_commit"]).lower():
        raise ValueError("historical manifest code_commit disagrees with authority code_commit")

    sealed_commit = authority["code_commit"]
    sealed_scoped_files = authority["scoped_code_files"]
    sealed_scoped_sha = authority["scoped_code_sha256"]
    sealed_study_root = Path(authority["study_root"])

    # R4-5: content-addressed scoped code verification. Reads git blobs from the
    # object database ONLY (git cat-file --batch). Each file is accepted if its LF
    # hash (git blob as stored) or its deterministic CRLF hash (LF->CRLF) matches the
    # sealed hash. NO working-tree fallback: a file whose neither form matches fails
    # closed and historical verify stops (mixed-line-ending files cannot be recovered
    # from the LF-normalized git blob and must NOT be substituted from the worktree).
    repo_root = _resolved(sealed_study_root).parents[1]
    _git_commit_exists(repo_root, sealed_commit)
    _verify_scoped_code_against_git(
        sealed_study_root, sealed_commit, sealed_scoped_files, sealed_scoped_sha,
    )

    # R4-5: plan canonical bytes/SHA verified directly from sealed bytes. Does NOT
    # call _authority/_plan_rows. ``_validate_plan`` checks that the plan is canonical
    # JSONL, the schema of each row matches _PLAN_FIELDS, and ``sha(plan_bytes)``
    # equals ``authority["plan_sha256"]`` (content-addressed).
    plan_bytes = _reject_alias(run_dir / "plan.jsonl", require_file=True).read_bytes()
    plan = _validate_plan(plan_bytes, manifest)
    if manifest["scheduler"]["fit_count"] != len(plan):
        raise ValueError("historical manifest fit_count does not match the plan length")

    # R4-5: matrix-row binding. Read the frozen matrix CSV (its SHA pins it to
    # ``FROZEN_MATRIX_SHA256`` via ``_open_verified_matrix_evidence``) and verify each
    # plan row's ``matrix_row_sha256`` equals ``sha(canonical(matrix_row))`` for the
    # corresponding fit_id. Content-addressed -- no _plan_rows re-derivation.
    matrix_evidence = _open_verified_matrix_evidence(Path(authority["matrix_path"]))
    matrix_rows_by_fit = {row["fit_id"]: row for row in matrix_evidence.rows}
    for row in plan:
        matrix_row = matrix_rows_by_fit.get(row["fit_id"])
        if matrix_row is None:
            raise ValueError(
                f"historical plan fit_id {row['fit_id']!r} is absent from the frozen matrix"
            )
        if row["matrix_row_sha256"] != _sha(_canonical(matrix_row)):
            raise ValueError(
                f"historical plan matrix_row_sha256 mismatch for {row['fit_id']!r}"
            )

    # Full journal/output replay (identical discipline to _rebuild_authority). The
    # replay verifies that every event/claim/receipt binds to ``authority_sha256`` and
    # that each claim's ``fit_identity_sha256`` equals ``sha(canonical(plan_row))``;
    # output SHAs are verified inside ``_validate_success_files``.
    events = _load_events(run_dir, manifest)
    derived = _replay(run_dir, manifest, plan, events)
    state_bytes, state = _load_exact(run_dir / "scheduler_state.json", _STATE_FIELDS, "scheduler state")
    if state_bytes != _canonical(derived) or state != derived:
        raise ValueError("scheduler state differs from full immutable event replay")
    if validate_controller:
        _validate_controller_anchors(run_dir, manifest, plan, events, state)
    # R4-5: historical terminal condition. Accepts ONLY terminal sealed predecessors:
    # no live claim AND every fit state is succeeded/failed (no pending/claimed).
    if state.get("live_claim") is not None:
        raise ValueError(
            "historical verifier requires a terminal sealed run (no live claim): "
            f"live_claim={state['live_claim']}"
        )
    non_terminal = {
        fit_id: status for fit_id, status in state["fit_states"].items()
        if status not in ("succeeded", "failed")
    }
    if non_terminal:
        raise ValueError(
            f"historical verifier requires all fits to be terminal "
            f"(succeeded/failed); non_terminal={non_terminal}"
        )
    return manifest, plan, state, events


def _lock_record(owner_nonce: str) -> dict[str, Any]:
    pid = os.getpid(); token = _process_start_token(pid)
    if token is None:
        raise ValueError("cannot establish scheduler process creation identity")
    return {"lock_version": "study02-formal-scheduler-lock-v1", "host_id": socket.gethostname(), "process_id": pid, "process_start_token": token, "owner_nonce": owner_nonce}


def _acquire(run_dir: Path, owner_nonce: str) -> Path:
    lock = run_dir / ".scheduler.lock"; desired = _canonical(_lock_record(owner_nonce))
    for _ in range(200):
        try:
            _write_no_replace(lock, desired); return lock
        except FileExistsError:
            try:
                _, existing = _load_exact(lock, _LOCK_FIELDS, "scheduler lock")
            except FileNotFoundError:
                continue
            if _identity_live(existing):
                time.sleep(0.005); continue
            if not _identity_confirmed_dead(existing):
                raise ValueError("scheduler lock owner liveness cannot be confirmed from this host")
            recovery = run_dir / ".scheduler.recovery.lock"
            try:
                _write_no_replace(recovery, desired)
            except FileExistsError:
                time.sleep(0.005); continue
            try:
                _, again = _load_exact(lock, _LOCK_FIELDS, "scheduler lock")
                if _identity_live(again):
                    continue
                if not _identity_confirmed_dead(again):
                    raise ValueError("scheduler stale lock identity is not confirmed dead")
                _recover_journal(run_dir); lock.unlink()
            finally:
                recovery.unlink(missing_ok=True)
    raise ValueError("scheduler lock owner remains live")


def _commit_transaction(run_dir: Path, before: Mapping[str, Any], event: Mapping[str, Any], after: Mapping[str, Any], publications: Sequence[tuple[str, Mapping[str, Any]]] = ()) -> None:
    event_path = _event_path(run_dir, event); relative = event_path.relative_to(run_dir).as_posix()
    records = [{"relative_path": item_path, "sha256": _sha(_canonical(value)), "value": dict(value)} for item_path, value in publications]
    anchor = _make_anchor(run_dir, event, after)
    journal = {"journal_version": "study02-formal-scheduler-journal-v1", "before_state_sha256": _sha(_canonical(before)), "event_relative_path": relative, "event_sha256": event["event_sha256"], "event": dict(event), "publications": records, "after_state": dict(after), "after_state_sha256": _sha(_canonical(after)), "controller_anchor": anchor}
    _write_no_replace(run_dir / ".scheduler.journal", _canonical(journal))
    for record in records:
        _write_no_replace(_contained(run_dir, record["relative_path"]), _canonical(record["value"]))
    _write_no_replace(event_path, _canonical(event))
    _atomic_replace(run_dir / "scheduler_state.json", _canonical(after))
    _publish_anchor(run_dir, anchor)
    (run_dir / ".scheduler.journal").unlink()


def _next_state(run_dir: Path, manifest: Mapping[str, Any], plan: Sequence[dict[str, Any]], events: Sequence[dict[str, Any]], event: Mapping[str, Any], publications: Sequence[tuple[str, Mapping[str, Any]]] = ()) -> dict[str, Any]:
    virtual = {path: (_canonical(value), dict(value)) for path, value in publications}
    return _replay(run_dir, manifest, plan, [*events, event], virtual_records=virtual)


def _output_snapshot(run_dir: Path, fit_id: str) -> list[Path]:
    directory = run_dir / "outputs" / fit_id
    if not directory.exists():
        return []
    _reject_alias(directory)
    entries = list(os.scandir(directory))
    paths = [Path(entry.path) for entry in entries]
    for path in paths:
        _reject_alias(path)
    return paths


def _validate_success_files(run_dir: Path, row: Mapping[str, Any], output_hashes: Mapping[str, str]) -> None:
    expected = {item["relative_path"] for item in row["expected_outputs"]}
    if not isinstance(output_hashes, Mapping) or set(output_hashes) != expected:
        raise ValueError("success output hashes must cover exactly all expected outputs, with no missing or extra path")
    output_dir = run_dir / "outputs" / row["fit_id"]
    snapshot = _output_snapshot(run_dir, row["fit_id"])
    if {path.relative_to(run_dir).as_posix() for path in snapshot} != expected:
        raise ValueError("output directory contains missing, extra, hidden, or nested output")
    file_snapshots: dict[str, dict[str, Any]] = {}
    for item in row["expected_outputs"]:
        relative = item["relative_path"]
        file_snapshots[relative] = _read_identity_snapshot(_contained(run_dir, relative))
    checkpoint_relative = next(item["relative_path"] for item in row["expected_outputs"] if item["content_type"] == "binary")
    checkpoint_sha = _sha(file_snapshots[checkpoint_relative]["bytes"])
    for item in row["expected_outputs"]:
        relative = item["relative_path"]; payload = file_snapshots[relative]["bytes"]
        if not payload or _sha(payload) != _hash(output_hashes[relative], "output SHA-256"):
            raise ValueError("scientific output is empty or its exact hash mismatches")
        content_type = item["content_type"]
        if content_type == "binary":
            continue
        if content_type == "fit_status_json":
            status_value = _decode_exact(payload, _FIT_STATUS_FIELDS, "fit status output")
            if status_value != {"checkpoint_sha256": checkpoint_sha, "fit_id": row["fit_id"], "run_id": row["run_id"], "status": "succeeded", "test_access_count": 0}:
                raise ValueError("fit status output does not bind the exact fit/checkpoint authority")
        elif content_type == "evidence_json":
            evidence = _decode_exact(payload, _EVIDENCE_FIELDS, "fit evidence output")
            if (evidence["evidence_version"] != "study02-formal-fit-evidence-v1"
                    or evidence["checkpoint_sha256"] != checkpoint_sha
                    or evidence["fit_id"] != row["fit_id"]
                    or evidence["run_id"] != row["run_id"]
                    or evidence["test_access_count"] != 0):
                raise ValueError("fit evidence output does not bind the exact fit/checkpoint authority")
            curve = evidence["validation_curve"]
            actual = int(evidence["actual_epochs"])
            if not isinstance(curve, list) or len(curve) != actual:
                raise ValueError("fit evidence validation curve does not match actual epochs")
            if actual < APPROVED_MIN_EPOCHS or actual > APPROVED_MAX_EPOCHS:
                raise ValueError("fit evidence actual epochs are outside the approved contract")
            if any((not isinstance(v, (int, float))) or isinstance(v, bool) or not math.isfinite(float(v)) for v in curve):
                raise ValueError("fit evidence validation curve must contain only finite values")
            expected_best = min(range(actual), key=lambda index: curve[index]) + 1
            if int(evidence["best_epoch_one_based"]) != expected_best:
                raise ValueError("fit evidence best epoch is not the validation-curve argmin")
            expected_hit = actual == APPROVED_MAX_EPOCHS
            if bool(evidence["hit_epoch_100"]) is not expected_hit:
                raise ValueError("fit evidence epoch-ceiling flag is inconsistent with actual epochs")
            expected_reason = "max_epochs" if expected_hit else "patience_exhausted"
            if str(evidence["early_stop_reason"]) != expected_reason:
                raise ValueError("fit evidence early-stop reason is inconsistent")
            expected_slope = _terminal_ols_slope(curve)
            if not math.isclose(float(evidence["terminal_validation_slope"]), expected_slope, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("fit evidence terminal validation slope does not match the curve")
        else:
            raise ValueError(f"unknown expected output content type: {content_type}")
    final_entries = list(os.scandir(_reject_alias(output_dir)))
    if {Path(entry.path).relative_to(run_dir).as_posix() for entry in final_entries} != expected:
        raise ValueError("output directory identity changed during validation")
    for relative, original in file_snapshots.items():
        final = _contained(run_dir, relative).stat()
        if original["identity"] != (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns):
            raise ValueError("output file identity changed after its one-read snapshot")


def materialize_run(*, study_root: Path, matrix_path: Path, module_id: str, run_id: str, artifact_root: Path, cache_root: Path, predecessor: Mapping[str, Any] | None) -> dict[str, Any]:
    module_id = _identifier(module_id, "module_id"); run_id = _identifier(run_id, "run_id")
    if module_id not in _MODULE_RULES:
        raise ValueError("unsupported formal module")
    artifact_root = _reject_alias(artifact_root); cache_root = _reject_alias(cache_root)
    matrix_bundle = _matrix_snapshot(study_root, matrix_path)
    formal, plan, plan_bytes, authority = _authority(study_root=study_root, matrix_path=matrix_path, module_id=module_id, run_id=run_id, artifact_root=artifact_root, cache_root=cache_root, predecessor=predecessor, controller_key_id=_ZERO_HASH, matrix_bundle=matrix_bundle)
    controller = _controller_context(artifact_root, create=True)
    authority = {key: value for key, value in authority.items() if key != "authority_sha256"}
    authority["controller_key_id"] = controller["key_id"]
    authority["authority_sha256"] = _sha(_canonical(authority))
    genesis = _event("run_initialized", 0, _ZERO_HASH, authority["authority_sha256"], {"run_id": run_id, "module_id": module_id, "plan_sha256": authority["plan_sha256"]})
    scheduler = {"scheduler_version": "study02-formal-scheduler-v2", "authority": authority, "fit_count": len(plan), "genesis_event_sha256": genesis["event_sha256"], "test_access_count": 0}
    manifest = {**formal, "scheduler": scheduler}; manifest_bytes = _canonical(manifest)
    run_dir = artifact_root / module_id / run_id
    if run_dir.exists():
        current, existing_plan, existing_state, existing_events = _rebuild_authority(run_dir, cache_root, validate_controller=False)
        anchor_directory = _anchor_dir(run_dir)
        anchors = list(os.scandir(anchor_directory)) if anchor_directory.exists() else []
        if not anchors:
            if len(existing_events) != 1:
                raise ValueError("non-genesis run is missing external controller anchors")
            _publish_anchor(run_dir, _make_anchor(run_dir, existing_events[0], existing_state))
        _validate_controller_anchors(run_dir, current, existing_plan, existing_events, existing_state)
        if _canonical(current) != manifest_bytes:
            raise ValueError("existing run differs from the exact current authority")
        return {"status": "existing_exact", "run_dir": str(run_dir), "plan_sha256": authority["plan_sha256"], "fit_count": len(plan), "test_access_count": 0}
    anchor_directory = _anchor_dir(run_dir)
    if anchor_directory.exists() and list(os.scandir(_reject_alias(anchor_directory))):
        raise ValueError("controller already contains an orphan or conflicting run anchor")
    stage = run_dir.with_name(f".{run_dir.name}.{os.getpid()}.{threading.get_ident()}.staging")
    try:
        stage.mkdir(parents=True)
        _write_no_replace(stage / "plan.jsonl", plan_bytes); _write_no_replace(stage / "manifest.json", manifest_bytes)
        _write_no_replace(_event_path(stage, genesis), _canonical(genesis))
        initial = _replay(stage, manifest, plan, [genesis]); _write_no_replace(stage / "scheduler_state.json", _canonical(initial))
        run_dir.parent.mkdir(parents=True, exist_ok=True); os.rename(stage, run_dir)
        _publish_anchor(run_dir, _make_anchor(run_dir, genesis, initial))
    except Exception:
        shutil.rmtree(stage, ignore_errors=True); raise
    return {"status": "created", "run_dir": str(run_dir), "plan_sha256": authority["plan_sha256"], "fit_count": len(plan), "test_access_count": 0}


def claim_next_fit(run_dir: Path, *, cache_root: Path, owner_id: str, owner_nonce: str, timestamp: str) -> dict[str, Any]:
    run_dir = _reject_alias(run_dir); owner_id = _identifier(owner_id, "owner_id"); owner_nonce = _identifier(owner_nonce, "owner_nonce")
    process_id = os.getpid()
    token = _process_start_token(process_id)
    if token is None:
        raise ValueError("claim process identity is not live")
    lock = _acquire(run_dir, owner_nonce)
    try:
        _recover_journal(run_dir); manifest, plan, state, events = _rebuild_authority(run_dir, cache_root)
        if state["live_claim"] is not None:
            return {"status": "monitor_only", **state["live_claim"]}
        row = next((item for item in plan if state["fit_states"][item["fit_id"]] == "pending"), None)
        if row is None:
            return {"status": "exhausted"}
        if _output_snapshot(run_dir, row["fit_id"]):
            raise ValueError("pending fit has conflicting scientific output")
        claim = {"claim_version": "study02-formal-claim-v2", "run_id": state["run_id"], "fit_id": row["fit_id"], "owner_id": owner_id, "owner_nonce": owner_nonce, "host_id": socket.gethostname(), "process_id": process_id, "process_start_token": token, "started_at": timestamp, "expected_outputs": row["expected_outputs"], "predecessor_event_sha256": events[-1]["event_sha256"], "fit_identity_sha256": _sha(_canonical(row)), "authority_sha256": state["authority_sha256"], "test_access_count": 0}
        relative = f"claims/{row['fit_id']}.{len(events):08d}.json"; _claim_path(run_dir, relative)
        event = _event("fit_claimed", len(events), events[-1]["event_sha256"], state["authority_sha256"], {"fit_id": row["fit_id"], "claim_relative_path": relative, "claim_sha256": _sha(_canonical(claim))})
        publications = [(relative, claim)]
        after = _next_state(run_dir, manifest, plan, events, event, publications); _commit_transaction(run_dir, state, event, after, publications)
        return {"status": "claimed", **after["live_claim"]}
    finally:
        lock.unlink(missing_ok=True)


def recover_claim(run_dir: Path, *, cache_root: Path, timestamp: str) -> dict[str, Any]:
    run_dir = _reject_alias(run_dir); lock = _acquire(run_dir, "recovery")
    try:
        _recover_journal(run_dir); manifest, plan, state, events = _rebuild_authority(run_dir, cache_root); claim = state["live_claim"]
        if claim is None:
            return {"status": "clean_pending"}
        if _identity_live(claim) or not _identity_confirmed_dead(claim):
            return {"status": "monitor_only", **claim}
        orphaned_outputs = _output_snapshot(run_dir, claim["fit_id"])
        if orphaned_outputs:
            # The executor died between writing outputs and recording success. Because no
            # success event exists for this still-claimed fit, the outputs are uncommitted;
            # remove them so the fit re-runs deterministically (recovery is possible instead
            # of a permanently stuck claim). The fit is confirmed dead, so these are not a
            # live owner's in-flight artifacts.
            output_dir = _reject_alias(run_dir / "outputs" / claim["fit_id"])
            shutil.rmtree(output_dir, ignore_errors=False)
        event = _event("claim_recovered", len(events), events[-1]["event_sha256"], state["authority_sha256"], {"fit_id": claim["fit_id"], "timestamp": timestamp, "reason": "dead_identity_no_outputs"})
        after = _next_state(run_dir, manifest, plan, events, event); _commit_transaction(run_dir, state, event, after)
        return {"status": "released_to_pending", "fit_id": claim["fit_id"]}
    finally:
        lock.unlink(missing_ok=True)


def _terminal(run_dir: Path, *, cache_root: Path, fit_id: str, owner_id: str, owner_nonce: str, terminal: str, details: Mapping[str, Any], timestamp: str) -> dict[str, Any]:
    run_dir = _reject_alias(run_dir); lock = _acquire(run_dir, owner_nonce)
    try:
        _recover_journal(run_dir); manifest, plan, state, events = _rebuild_authority(run_dir, cache_root); claim = state["live_claim"]
        if claim is None or claim["fit_id"] != fit_id or claim["owner_id"] != owner_id or claim["owner_nonce"] != owner_nonce:
            raise ValueError("terminal receipt does not own the exact live claim identity")
        if terminal == "failed" and _output_snapshot(run_dir, fit_id):
            raise ValueError("failed fit has scientific or partial output")
        if terminal == "succeeded":
            row = next(item for item in plan if item["fit_id"] == fit_id)
            _validate_success_files(run_dir, row, details["output_hashes"])
        receipt = {"receipt_version": "study02-formal-fit-terminal-v2", "run_id": state["run_id"], "fit_id": fit_id, "owner_id": owner_id, "owner_nonce": owner_nonce, "state": terminal, "details": dict(details), "timestamp": timestamp, "claim_receipt_sha256": claim["claim_sha256"], "authority_sha256": state["authority_sha256"], "test_access_count": 0}
        relative = f"receipts/{fit_id}.{terminal}.json"; _receipt_path(run_dir, relative)
        event = _event(f"fit_{terminal}", len(events), events[-1]["event_sha256"], state["authority_sha256"], {"fit_id": fit_id, "receipt_relative_path": relative, "receipt_sha256": _sha(_canonical(receipt))})
        publications = [(relative, receipt)]
        after = _next_state(run_dir, manifest, plan, events, event, publications); _commit_transaction(run_dir, state, event, after, publications)
        return {**receipt, "receipt_relative_path": relative}
    finally:
        lock.unlink(missing_ok=True)


def record_fit_failed(run_dir: Path, *, cache_root: Path, fit_id: str, owner_id: str, owner_nonce: str, failure_code: str, timestamp: str) -> dict[str, Any]:
    return _terminal(run_dir, cache_root=cache_root, fit_id=fit_id, owner_id=owner_id, owner_nonce=owner_nonce, terminal="failed", details={"failure_code": _identifier(failure_code, "failure_code")}, timestamp=timestamp)


def record_fit_succeeded(run_dir: Path, *, cache_root: Path, fit_id: str, owner_id: str, owner_nonce: str, output_hashes: Mapping[str, str], timestamp: str) -> dict[str, Any]:
    run_dir = _resolved(run_dir); manifest, plan, state, _ = _rebuild_authority(run_dir, cache_root)
    del manifest, state
    row = next((item for item in plan if item["fit_id"] == fit_id), None)
    if row is None:
        raise ValueError("fit is absent from the exact plan")
    _validate_success_files(run_dir, row, output_hashes)
    return _terminal(run_dir, cache_root=cache_root, fit_id=fit_id, owner_id=owner_id, owner_nonce=owner_nonce, terminal="succeeded", details={"output_hashes": dict(output_hashes)}, timestamp=timestamp)


def status_run(run_dir: Path, *, cache_root: Path) -> dict[str, Any]:
    if (_resolved(run_dir) / ".scheduler.journal").exists():
        raise ValueError("scheduler transaction requires deterministic mutation recovery")
    manifest, _, state, _ = _rebuild_authority(run_dir, cache_root)
    counts = {name: sum(value == name for value in state["fit_states"].values()) for name in ("pending", "claimed", "succeeded", "failed")}
    return {"run_id": state["run_id"], "module_id": state["module_id"], "plan_sha256": state["plan_sha256"], "authority_sha256": state["authority_sha256"], "matrix_sha256": manifest["matrix"]["sha256"], "effective_config_sha256": manifest["effective_config"]["sha256"], "counts": counts, "live_claim": state["live_claim"], "test_access_count": 0}


__all__ = ["claim_next_fit", "materialize_run", "record_fit_failed", "record_fit_succeeded", "recover_claim", "status_run"]
