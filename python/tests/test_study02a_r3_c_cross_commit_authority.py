"""R3-C versioned cross-commit authority tests.

Tests the content-addressed historical verifier (``verify_historical_authority``)
against:

1. The real A-E1 r5 sealed run (read-only, never modified) at commit d2a056f.
2. Forged / missing git objects (fail-closed).
3. Forged scoped_code_files hashes (fail-closed).
4. The version-dispatched predecessor schema (v1 7-key vs v2 13-key).

Constraints: no real sealed run directory is modified; the r5 manifest is read
exactly once and its bytes are never written.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))
if str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

from study02a.formal_scheduler import (  # noqa: E402
    _git_commit_exists,
    _verify_scoped_code_against_git,
    verify_historical_authority,
)


# Real A-E1 r5 sealed run directory and commit (immutable, read-only).
_R5_RUN_DIR = Path(r"C:\weibull-runs\study02\artifacts\A-E1\A-E1-formal-r5-20260727-222417")
_R5_CACHE_ROOT = Path(r"C:\weibull-runs\study02\cache")
_R5_COMMIT = "d2a056fdfe650af9f2992f8ea85f8b2daab2fbb3"
_MISSING_COMMIT = "0" * 40  # syntactically valid but does not exist in the object db.


def _r5_available() -> bool:
    return (_R5_RUN_DIR / "manifest.json").is_file()


# ============================================================================
# 1. Real r5 read-only historical verification (content-addressed).
# ============================================================================


@pytest.mark.skipif(not _r5_available(), reason="real r5 sealed run not available")
def test_r3_c_historical_verifier_accepts_real_r5_at_d2a056f():
    """The content-addressed historical verifier accepts the real A-E1 r5 sealed
    run at commit d2a056f. Scoped code blobs are read from the git object
    database (no checkout); the full journal (plan, events, anchors, receipts,
    output SHAs) is replayed; the run is terminal sealed (no live claim)."""

    manifest, plan, state, events = verify_historical_authority(
        _R5_RUN_DIR, _R5_CACHE_ROOT,
    )

    assert manifest["module_id"] == "A-E1"
    assert manifest["code_commit"] == _R5_COMMIT
    assert manifest["scheduler"]["authority"]["code_commit"] == _R5_COMMIT
    assert state["live_claim"] is None
    # r5 sealed 349 fits, all succeeded, 699 events (genesis + 2*349 terminal).
    assert manifest["scheduler"]["fit_count"] == len(plan)
    assert len(events) == 699
    fit_states = set(state["fit_states"].values())
    assert fit_states == {"succeeded"}, f"unexpected non-succeeded states: {fit_states}"


# ============================================================================
# 2. Missing / forged git commit object (fail-closed).
# ============================================================================


def test_r3_c_git_commit_exists_rejects_missing_commit():
    """``_git_commit_exists`` rejects a commit SHA that is not in the git object
    database. No checkout is attempted; the check reads only object metadata."""
    repo_root = STUDY_ROOT.parents[1]
    with pytest.raises(ValueError, match="not a reachable git commit"):
        _git_commit_exists(repo_root, _MISSING_COMMIT)


def test_r3_c_git_commit_exists_accepts_d2a056f():
    """``_git_commit_exists`` accepts the real r5 sealed commit d2a056f."""
    repo_root = STUDY_ROOT.parents[1]
    _git_commit_exists(repo_root, _R5_COMMIT)  # no exception.


# ============================================================================
# 3. Forged scoped_code_files / path-set drift (fail-closed).
# ============================================================================


@pytest.mark.skipif(not _r5_available(), reason="real r5 sealed run not available")
def test_r3_c_verify_scoped_code_rejects_forged_hash():
    """``_verify_scoped_code_against_git`` rejects a forged scoped_code_sha256
    that doesn't match any blob at the sealed commit."""

    r5_manifest = json.loads((_R5_RUN_DIR / "manifest.json").read_bytes().decode("utf-8"))
    sealed_files = dict(r5_manifest["scheduler"]["authority"]["scoped_code_files"])
    # Forge a wrong aggregate SHA (flip one character).
    forged_sha = ("1" if r5_manifest["scheduler"]["authority"]["scoped_code_sha256"][0] != "1"
                  else "2") + r5_manifest["scheduler"]["authority"]["scoped_code_sha256"][1:]
    with pytest.raises(ValueError, match="scoped_code_sha256 mismatch"):
        _verify_scoped_code_against_git(
            STUDY_ROOT, _R5_COMMIT, sealed_files, forged_sha,
        )


@pytest.mark.skipif(not _r5_available(), reason="real r5 sealed run not available")
def test_r3_c_verify_scoped_code_rejects_path_set_drift():
    """``_verify_scoped_code_against_git`` rejects when the sealed path set
    doesn't match the git tree at the sealed commit (added/removed file)."""

    r5_manifest = json.loads((_R5_RUN_DIR / "manifest.json").read_bytes().decode("utf-8"))
    sealed_files = dict(r5_manifest["scheduler"]["authority"]["scoped_code_files"])
    sealed_sha = r5_manifest["scheduler"]["authority"]["scoped_code_sha256"]
    # Add a fictitious path to the sealed set (path-set drift).
    forged_files = dict(sealed_files)
    forged_files["study02/nonexistent/forged.py"] = "a" * 64
    with pytest.raises(ValueError, match="path-set drift"):
        _verify_scoped_code_against_git(
            STUDY_ROOT, _R5_COMMIT, forged_files, sealed_sha,
        )


@pytest.mark.skipif(not _r5_available(), reason="real r5 sealed run not available")
def test_r3_c_verify_scoped_code_rejects_forged_blob_hash():
    """``_verify_scoped_code_against_git`` rejects when a single file's sealed
    hash is forged (doesn't match the git blob's LF or CRLF form)."""

    r5_manifest = json.loads((_R5_RUN_DIR / "manifest.json").read_bytes().decode("utf-8"))
    sealed_files = dict(r5_manifest["scheduler"]["authority"]["scoped_code_files"])
    # Forge one file's hash.
    first_key = next(iter(sealed_files))
    forged_files = dict(sealed_files)
    forged_files[first_key] = "f" * 64
    # Recompute the aggregate to isolate the failure to the per-file check.
    import hashlib
    from study02a.formal_scheduler import _sha, _canonical
    forged_aggregate = _sha(_canonical(forged_files))
    with pytest.raises(ValueError, match="blob hash mismatch"):
        _verify_scoped_code_against_git(
            STUDY_ROOT, _R5_COMMIT, forged_files, forged_aggregate,
        )


# ============================================================================
# 4. Version-dispatched predecessor schema (v1 r5 vs v2 new).
# ============================================================================


def test_r3_c_v1_predecessor_fields_are_the_r5_sealed_7_key_set():
    """The v1 predecessor schema is exactly the 7-key set that r5 sealed at
    d2a056f. This is a regression guard: adding or removing a v1 field would
    break r5 replay."""

    from study02a.formal_contracts import _PREDECESSOR_SCHEMA_V1_FIELDS

    assert _PREDECESSOR_SCHEMA_V1_FIELDS == frozenset({
        "module_id", "run_id",
        "selection_trace_path", "selection_trace_sha256",
        "selection_receipt_path", "selection_receipt_sha256",
        "selection_ledger_path",
    })


def test_r3_c_v2_predecessor_fields_include_authority_triple():
    """The v2 predecessor schema includes the 10 C1 keys PLUS the authority
    triple (code_commit, scoped_code_sha256, authority_sha256)."""

    from study02a.formal_contracts import _PREDECESSOR_SCHEMA_V2_FIELDS

    authority_triple = {"code_commit", "scoped_code_sha256", "authority_sha256"}
    assert authority_triple.issubset(_PREDECESSOR_SCHEMA_V2_FIELDS), (
        f"v2 predecessor must include the authority triple; got {_PREDECESSOR_SCHEMA_V2_FIELDS}"
    )
    # v2 is a strict superset of v1.
    from study02a.formal_contracts import _PREDECESSOR_SCHEMA_V1_FIELDS
    assert _PREDECESSOR_SCHEMA_V1_FIELDS.issubset(_PREDECESSOR_SCHEMA_V2_FIELDS)
    assert len(_PREDECESSOR_SCHEMA_V2_FIELDS) == 13


def test_r3_c_build_formal_manifest_emits_v2():
    """``build_formal_manifest`` always emits ``study02-formal-v2`` for new
    runs (A-E1 r5 stays v1; never rewritten)."""

    from study02a.formal_config import load_effective_formal_config
    from study02a.formal_contracts import build_formal_manifest

    frozen_matrix = STUDY_ROOT / "artifacts" / "pilot" / "G3-matrix" / "experiment_matrix.csv"
    effective = load_effective_formal_config(STUDY_ROOT)
    manifest = build_formal_manifest(
        effective_config=effective,
        module_id="A-E1",
        run_id="G3-AE1-formal-test",
        code_commit="a" * 40,
        matrix_path=frozen_matrix,
        rule_ids=("A-E1_historical",),
        fit_ids=("G3-fit-0000",),
        role_namespaces={"training": "study02/formal/t", "validation": "study02/formal/v"},
        screening_seeds=(420001, 420002, 420003),
        formal_seeds=tuple(range(420101, 420111)),
        predecessor=None,
    )
    assert manifest["manifest_version"] == "study02-formal-v2"


@pytest.mark.skipif(not _r5_available(), reason="real r5 sealed run not available")
def test_r3_c_real_r5_manifest_is_v1_with_7_key_predecessor():
    """The real A-E1 r5 manifest is v1 with the 7-key predecessor段. This is a
    read-only regression guard: R3-C must never rewrite r5's bytes."""

    r5_manifest = json.loads((_R5_RUN_DIR / "manifest.json").read_bytes().decode("utf-8"))
    assert r5_manifest["manifest_version"] == "study02-formal-v1"
    from study02a.formal_contracts import _PREDECESSOR_SCHEMA_V1_FIELDS
    assert set(r5_manifest["predecessor"]) == _PREDECESSOR_SCHEMA_V1_FIELDS
