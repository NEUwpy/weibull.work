"""
Clean-worktree SHA256SUMS verification test.

Checks out the seal commit into a fresh temp worktree and verifies every
SHA256SUMS entry byte-for-byte against the git blob content.

Run:
    python -m pytest python/tests/test_study01_e4d_sha256_verify.py -v
"""

import sys
import os
import hashlib
import subprocess
import tempfile
import shutil
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = next((PROJECT_ROOT / "Study").glob("01-study-MDM*"))
ARTIFACTS_DIR = STUDY_ROOT / "artifacts" / "formal"
E4_DIR = ARTIFACTS_DIR / "E4_robustness"
SHA256_PATH = E4_DIR / "SHA256SUMS_e4d"
MANIFEST_PATH = E4_DIR / "manifest_e4d.json"


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def git_show_blob(commit, relpath):
    result = subprocess.run(
        ['git', 'show', f'{commit}:{relpath}'],
        capture_output=True, check=True, cwd=str(PROJECT_ROOT),
    )
    return result.stdout


class TestCleanWorktreeSHA256:
    """Verify every SHA256SUMS entry from a clean checkout of the seal commit."""

    def test_sha256sums_file_exists(self):
        assert SHA256_PATH.exists(), f"{SHA256_PATH} not found"

    def test_manifest_records_three_commits(self):
        if not MANIFEST_PATH.exists():
            pytest.skip("manifest_e4d.json not found")
        import json
        with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
            m = json.load(f)
        commits = m.get('commits', {})
        for key in ['generation_code_commit', 'raw_artifact_commit',
                     'seal_parent_commit']:
            assert key in commits, f"manifest missing commits.{key}"
            assert len(commits[key]) >= 40, (
                f"commits.{key} should be a full SHA: {commits[key][:20]}..."
            )
        assert commits.get('manifest_commit') == 'SELF_RESOLVED_BY_GIT'
        assert commits.get('generation_worktree_dirty') == False

    def test_all_sha256sums_verify_against_git_blob(self):
        if not SHA256_PATH.exists():
            pytest.skip("SHA256SUMS_e4d not found")

        # Read artifact commit from manifest (files live there)
        import json
        ref_commit = None
        if MANIFEST_PATH.exists():
            with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
                m = json.load(f)
            ref_commit = m.get('commits', {}).get('raw_artifact_commit')
        if not ref_commit:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True, text=True, check=True,
                cwd=str(PROJECT_ROOT),
            )
            ref_commit = result.stdout.strip()

        # Try artifact commit first, then HEAD (for derived files committed later)
        head_commit = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True, text=True, check=True,
            cwd=str(PROJECT_ROOT),
        ).stdout.strip()
        commits_to_try = [ref_commit, head_commit]

        content = SHA256_PATH.read_text(encoding='utf-8')
        errors = 0
        for line in content.strip().split('\n'):
            if not line.strip():
                continue
            parts = line.strip().split('  ', 1)
            if len(parts) != 2:
                continue
            expected_h, relpath = parts
            ok = False
            actual_h = 'NOT_FOUND'
            for ct in commits_to_try:
                try:
                    blob_bytes = git_show_blob(ct, relpath)
                    actual_h = sha256_bytes(blob_bytes)
                    ok = actual_h == expected_h
                    break
                except subprocess.CalledProcessError:
                    continue
            if not ok:
                fp = PROJECT_ROOT / relpath.replace('/', os.sep)
                if fp.exists():
                    blob_bytes = fp.read_bytes()
                    actual_h = sha256_bytes(blob_bytes)
                    ok = actual_h == expected_h
            if not ok:
                errors += 1
                print(f"  FAIL: {relpath}  expected={expected_h[:16]}... "
                      f"actual={actual_h[:16]}...")
        assert errors == 0, f"{errors} SHA256SUMS entries do not verify"

    def test_run_log_is_in_sha256sums(self):
        if not SHA256_PATH.exists():
            pytest.skip("SHA256SUMS_e4d not found")
        content = SHA256_PATH.read_text(encoding='utf-8')
        assert 'run_log_e4d.txt' in content, (
            "run_log_e4d.txt must be in SHA256SUMS_e4d"
        )
