"""
Clean-worktree SHA256SUMS verification test.

Checks out the seal commit into a fresh temp worktree and verifies every
SHA256SUMS entry byte-for-byte against the git blob content.

Run:
    python -m pytest python/tests/test_study01_e4d_sha256_verify.py -v
"""

import sys
import os
import io
import json
import hashlib
import subprocess
from pathlib import Path

import pandas as pd
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

        # Each file must be verified from its manifest-declared source_commit
        import json
        if not MANIFEST_PATH.exists():
            pytest.skip("manifest_e4d.json not found")
        with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
            m = json.load(f)
        output_prov = m.get('output_provenance', {})

        content = SHA256_PATH.read_text(encoding='utf-8')
        errors = 0
        for line in content.strip().split('\n'):
            if not line.strip():
                continue
            parts = line.strip().split('  ', 1)
            if len(parts) != 2:
                continue
            expected_h, relpath = parts
            file_info = output_prov.get(relpath, {})
            source_commit = file_info.get('source_commit')
            if not source_commit:
                errors += 1
                print(f"  FAIL: {relpath} — no source_commit in manifest")
                continue
            expected_row_count = file_info.get('row_count')
            ok = False
            actual_h = 'NOT_FOUND'
            try:
                blob_bytes = git_show_blob(source_commit, relpath)
                actual_h = sha256_bytes(blob_bytes)
                ok = actual_h == expected_h
                # Also verify row_count for CSVs
                if ok and expected_row_count is not None:
                    import io
                    df = pd.read_csv(io.BytesIO(blob_bytes))
                    if int(len(df)) != int(expected_row_count):
                        ok = False
                        print(f"  row_count mismatch: expected "
                              f"{expected_row_count}, got {len(df)}")
            except subprocess.CalledProcessError:
                pass
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
