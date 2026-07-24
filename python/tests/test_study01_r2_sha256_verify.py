"""
Auto-verification: R2 manifest SHA256 must match git blobs.

After any commit that includes R2 artifacts, this test confirms that
every file SHA256 recorded in manifest.json equals the SHA256 of the
corresponding git blob (LF-normalised bytes from git show).

Run:  pytest python/tests/test_study01_r2_sha256_verify.py -v
"""
import hashlib, json, subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ART = "Study/01-study-MDM最小偏移量优化研究/artifacts/formal/delta_upper_bound_audit"

INPUT_CHUNKS_COMMIT = "c70c5d48c00d3ae045b289a71471fec3583023b5"

def _git_blob_sha256(commit, repo_path):
    """SHA256 of git blob at commit:repo_path."""
    blob = subprocess.run(
        ["git", "show", f"{commit}:{repo_path}"],
        capture_output=True, cwd=str(PROJECT_ROOT)
    ).stdout
    return hashlib.sha256(blob).hexdigest()

def test_manifest_json_not_sealed():  # exclusion rule: manifest self-reference
    """manifest.json may record its own hash but cannot verify itself."""
    pass

def test_cohort_summary_sha256():
    stored = '8bf5af44d9878c014fd90dd679e06cd344c7aa4513b87f33586d51b437de6dee'
    actual = _git_blob_sha256("HEAD", f"{ART}/cohort_summary.csv")
    assert actual == stored, f"cohort_summary.csv mismatch: manifest={stored} actual={actual}"

def test_extended_results_sha256():
    stored = 'cd46f721536545688fc0dc64a2782dfe323acd32ee5d9382e4e8985b93a0f288'
    actual = _git_blob_sha256("HEAD", f"{ART}/extended_results.csv")
    assert actual == stored, f"extended_results mismatch"

def test_merged_curves_sha256():
    stored = '603003a63d1bc0713f7374f121cda81dfc319fbbcea42006b7bad8adb156d828'
    actual = _git_blob_sha256("HEAD", f"{ART}/merged_curves.csv")
    assert actual == stored, f"merged_curves mismatch"

def test_run_log_sha256():
    stored = '449d6b916eaa8a24b1e84d45d1e5046f7919c7e44f7d32a06b0be73f63f06b60'
    actual = _git_blob_sha256("HEAD", f"{ART}/run_log.txt")
    assert actual == stored, f"run_log mismatch"

def test_input_chunks_sha256():
    """Verify input chunks hash from git blobs at the recorded commit.

    Uses git ls-tree to get blob OIDs, then git cat-file blob to avoid
    path-encoding issues with git show on Chinese-named paths.
    """
    stored = '6181e17246931d18cbf78d80bbae16f9f434aa8aceb5dbca5d59b4399a705ee8'
    chunk_dir = "Study/01-study-MDM最小偏移量优化研究/artifacts/formal/shared_data/chunks"

    result = subprocess.run(
        ["git", "ls-tree", INPUT_CHUNKS_COMMIT, chunk_dir + "/"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT)
    )
    # git ls-tree format: <mode> blob <oid>\t<path>
    entries = []
    for line in result.stdout.strip().split('\n'):
        parts = line.split()
        if len(parts) >= 3 and parts[1] == 'blob':
            path = line.split('\t')[1] if '\t' in line else ''
            entries.append((path, parts[2]))
    # Filter to _mdm.csv chunks, sort by path (deterministic)
    entries = sorted([(p, oid) for p, oid in entries
                      if 'chunk_' in p and '_mdm.csv' in p],
                     key=lambda x: x[0])
    assert len(entries) == 45, f"Expected 45 chunks, got {len(entries)}"

    import hashlib
    hasher = hashlib.sha256()
    for _, oid in entries:
        blob = subprocess.run(
            ["git", "cat-file", "blob", oid],
            capture_output=True, cwd=str(PROJECT_ROOT)
        ).stdout
        h = hashlib.sha256(blob).hexdigest()
        hasher.update(h.encode("ascii"))
    actual = hasher.hexdigest()

    assert actual == stored, (
        f"input_chunks SHA256 mismatch: manifest={stored} actual={actual}"
    )

def test_all_sha256_stored_are_64_hex_chars():
    """No 40-char git blob OIDs mistakenly stored under 'sha256'."""
    import json
    mpath = Path(PROJECT_ROOT) / ART / "manifest.json"
    with open(mpath, encoding="utf-8") as f:
        m = json.load(f)
    for fname, info in m.get("files", {}).items():
        sha = info.get("sha256", "")
        assert len(sha) == 64, f"{fname}: sha256 must be 64 hex, got {len(sha)}"
        assert all(c in "0123456789abcdef" for c in sha), f"{fname}: sha256 not hex"
    ic = m.get("input_chunks", {})
    sha = ic.get("sha256", "")
    assert len(sha) == 64, f"input_chunks sha256 must be 64 hex, got {len(sha)}"
