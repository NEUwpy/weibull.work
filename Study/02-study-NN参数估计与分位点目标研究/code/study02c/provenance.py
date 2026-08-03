"""Provenance helpers for C2/C3C4 runners.

Verifies the study02c code subtree matches HEAD before a final manifest is
emitted (fail closed), and records the exact code tip + tree-clean status.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_CODE_SUBTREE = Path(__file__).resolve().parent


def git_tip() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True, cwd=str(_REPO_ROOT)).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _git_subtree_status(subtree: Path) -> str:
    """git status --porcelain for the code subtree, relative to repo root."""
    rel = subtree.relative_to(_REPO_ROOT).as_posix()
    out = subprocess.run(["git", "status", "--porcelain", "--", rel],
                         capture_output=True, text=True, cwd=str(_REPO_ROOT)).stdout
    return out.strip()


def code_tree_clean() -> bool:
    """True iff the study02c code subtree has no staged/unstaged changes.

    Untracked files inside the subtree also count as dirty (they would not be
    covered by a commit of tracked files). __pycache__/.pyc are excluded.
    """
    lines = _git_subtree_status(_CODE_SUBTREE)
    if not lines:
        return True
    for line in lines.splitlines():
        path = line[3:].strip()
        if path.endswith(("__pycache__", ".pyc")) or "__pycache__/" in path:
            continue
        return False
    return True


def require_code_clean(tip: str) -> bool:
    """Fail-closed gate: only emit a final manifest when the code subtree is
    clean and its committed tip equals the working-tree HEAD tip."""
    if not code_tree_clean():
        print("  [provenance] FAIL: code/study02c subtree is dirty; refusing final manifest.")
        return False
    head = git_tip()
    if head != tip:
        print(f"  [provenance] FAIL: tip changed during run ({tip} -> {head}); "
              f"refusing final manifest.")
        return False
    print(f"  [provenance] OK: code subtree clean at {head[:12]}")
    return True


def add_output_dir_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-dir", default=None,
                        help="explicit output directory (used to rebuild/overwrite a "
                             "current authoritative artifact dir)")
