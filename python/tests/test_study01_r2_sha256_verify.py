"""
Auto-verification: R2 manifest SHA256 must match git blobs.

Reads expected SHA256 values from manifest.json, then confirms each
matches the SHA256 of the corresponding git blob.

Run:  pytest python/tests/test_study01_r2_sha256_verify.py -v
"""
import hashlib, json, subprocess, os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ART = "Study/01-study-MDM最小偏移量优化研究/artifacts/formal/delta_upper_bound_audit"
CHUNK_DIR = "Study/01-study-MDM最小偏移量优化研究/artifacts/formal/shared_data/chunks"


def _load_manifest():
    mpath = PROJECT_ROOT / ART / "manifest.json"
    with open(mpath, encoding="utf-8") as f:
        return json.load(f)


def _git_blob_sha256(commit, repo_path):
    """SHA256 of git blob at commit:repo_path."""
    blob = subprocess.run(
        ["git", "show", f"{commit}:{repo_path}"],
        capture_output=True, cwd=str(PROJECT_ROOT)
    ).stdout
    return hashlib.sha256(blob).hexdigest()


def test_manifest_does_not_list_itself():
    """manifest.json must NOT include itself in the 'files' section."""
    m = _load_manifest()
    for fname in m.get("files", {}):
        assert "manifest" not in fname.lower(), (
            f"manifest.json should not list itself under 'files', found: {fname}"
        )


def test_cohort_summary_sha256():
    m = _load_manifest()
    stored = m["files"]["cohort_summary.csv"]["sha256"]
    actual = _git_blob_sha256("HEAD", f"{ART}/cohort_summary.csv")
    assert actual == stored, f"cohort_summary.csv: manifest={stored} actual={actual}"


def test_extended_results_sha256():
    m = _load_manifest()
    stored = m["files"]["extended_results.csv"]["sha256"]
    actual = _git_blob_sha256("HEAD", f"{ART}/extended_results.csv")
    assert actual == stored, f"extended_results: manifest={stored} actual={actual}"


def test_merged_curves_sha256():
    m = _load_manifest()
    stored = m["files"]["merged_curves.csv"]["sha256"]
    actual = _git_blob_sha256("HEAD", f"{ART}/merged_curves.csv")
    assert actual == stored, f"merged_curves: manifest={stored} actual={actual}"


def test_run_log_sha256():
    m = _load_manifest()
    stored = m["files"]["run_log.txt"]["sha256"]
    actual = _git_blob_sha256("HEAD", f"{ART}/run_log.txt")
    assert actual == stored, f"run_log: manifest={stored} actual={actual}"


def test_input_chunks_sha256():
    """Verify input chunks hash from git blobs via blob OIDs (avoid path encoding)."""
    m = _load_manifest()
    stored = m["input_chunks"]["sha256"]
    chunks_commit = m["input_chunks"]["commit"]

    result = subprocess.run(
        ["git", "ls-tree", chunks_commit, CHUNK_DIR + "/"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT)
    )
    # git ls-tree format: <mode> blob <oid>\t<path>
    entries = []
    for line in result.stdout.strip().split('\n'):
        parts = line.split()
        if len(parts) >= 3 and parts[1] == 'blob':
            path = line.split('\t')[1] if '\t' in line else ''
            entries.append((path, parts[2]))
    entries = sorted([(p, oid) for p, oid in entries
                      if 'chunk_' in p and '_mdm.csv' in p],
                     key=lambda x: x[0])
    assert len(entries) == 45, f"Expected 45 chunks, got {len(entries)}"

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
        f"input_chunks SHA256: manifest={stored} actual={actual}"
    )


def test_all_sha256_stored_are_64_hex_chars():
    """No 40-char git blob OIDs mistakenly stored under 'sha256'."""
    m = _load_manifest()
    for fname, info in m.get("files", {}).items():
        sha = info.get("sha256", "")
        assert len(sha) == 64, f"{fname}: sha256 must be 64 hex, got {len(sha)} chars"
        assert all(c in "0123456789abcdef" for c in sha), f"{fname}: sha256 not hex"
    ic = m.get("input_chunks", {})
    sha = ic.get("sha256", "")
    assert len(sha) == 64, f"input_chunks sha256 must be 64 hex, got {len(sha)} chars"


def test_file_bytes_match_git_blob_size():
    """Manifest 'bytes' must match git blob byte count, not disk file size."""
    m = _load_manifest()
    for fname in m.get("files", {}):
        stored_bytes = m["files"][fname]["bytes"]
        path = f"{ART}/{fname}"
        blob = subprocess.run(
            ["git", "show", f"HEAD:{path}"],
            capture_output=True, cwd=str(PROJECT_ROOT)
        ).stdout
        actual_bytes = len(blob)
        assert actual_bytes == stored_bytes, (
            f"{fname}: manifest bytes={stored_bytes} git blob bytes={actual_bytes}"
        )


def test_sha256_source_description():
    """manifest.sha256_source must describe SHA256, not git hash-object (SHA-1)."""
    m = _load_manifest()
    src = m.get("sha256_source", "")
    assert "SHA256" in src or "sha256" in src, (
        f"sha256_source must mention SHA256, got: {src!r}"
    )
    assert "hash-object" not in src.lower(), (
        f"sha256_source must not say 'git hash-object' (that produces SHA-1), got: {src!r}"
    )


def test_tie_breaking_rule_field():
    """Tie-breaking rule must be present and reference the actual threshold."""
    m = _load_manifest()
    rule = m.get("tie_breaking_rule", "")
    assert "1e-12" in rule or "1e-12" in m.get("tie_breaking", ""), (
        f"tie_breaking_rule must mention 1e-12 threshold, got: {rule!r}"
    )
