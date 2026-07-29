"""R3-C / R4-5 versioned cross-commit authority tests.

Tests the content-addressed historical verifier (``verify_historical_authority``)
against:

1. The real A-E1 r5 sealed run (read-only, never modified) at commit d2a056f.
2. Forged / missing git objects (fail-closed).
3. Forged scoped_code_files hashes (fail-closed).
4. The version-dispatched predecessor schema (v1 7-key vs v2 13-key).
5. R4-5 sealed-bytes verification (authority_sha256 self-hash, frozen config/matrix
   cross-consistency, plan SHA, matrix-row binding, terminal condition).

R4-5 STOP CONDITION: the real r5 run has 3 scoped code files whose sealed SHA-256
was computed over bytes with MIXED line endings (neither pure LF nor pure CRLF).
Git stores LF-normalized blobs, so these cannot be reconstructed from git objects
without a working-tree fallback (which R4-5 forbids). The historical verifier
fail-closes at the scoped-code gate and reports the exact path + hashes.

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
    _canonical,
    _crlf_normalize,
    _git_commit_exists,
    _git_list_py_blobs,
    _git_read_paths_batch,
    _sha,
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


def _load_r5_manifest() -> dict:
    return json.loads((_R5_RUN_DIR / "manifest.json").read_bytes().decode("utf-8"))


def _build_lf_scoped_files_from_git() -> dict[str, str]:
    """Build a ``scoped_code_files`` dict where every per-file hash is the LF form
    of the git blob at ``_R5_COMMIT``. Used to isolate aggregate-level tests from
    the 3 mixed-line-ending files whose sealed hash is neither LF nor CRLF."""

    repo_root = STUDY_ROOT.parents[1]
    code_tree_posix = (STUDY_ROOT.relative_to(repo_root) / "code").as_posix()
    shared_tree_posix = "python/studies"
    scoped_to_repo: dict[str, str] = {}
    all_repo_paths: list[str] = []
    seen: set[str] = set()
    for scoped_prefix, tree_posix in (
        ("study02", code_tree_posix),
        ("studies", shared_tree_posix),
    ):
        for relative_posix, _blob_sha in _git_list_py_blobs(repo_root, _R5_COMMIT, tree_posix):
            scoped_key = f"{scoped_prefix}/{relative_posix}"
            repo_path = f"{tree_posix}/{relative_posix}"
            scoped_to_repo[scoped_key] = repo_path
            if repo_path not in seen:
                seen.add(repo_path)
                all_repo_paths.append(repo_path)
    contents = _git_read_paths_batch(repo_root, _R5_COMMIT, all_repo_paths)
    return {key: _sha(contents[path]) for key, path in scoped_to_repo.items()}


def _list_unrecoverable_scoped_files(sealed_files: dict[str, str]) -> list[str]:
    """Return the scoped keys whose sealed hash matches neither the LF git blob
    nor its deterministic CRLF reconstruction at ``_R5_COMMIT``."""

    repo_root = STUDY_ROOT.parents[1]
    code_tree_posix = (STUDY_ROOT.relative_to(repo_root) / "code").as_posix()
    shared_tree_posix = "python/studies"
    scoped_to_repo: dict[str, str] = {}
    all_repo_paths: list[str] = []
    seen: set[str] = set()
    for scoped_prefix, tree_posix in (
        ("study02", code_tree_posix),
        ("studies", shared_tree_posix),
    ):
        for relative_posix, _blob_sha in _git_list_py_blobs(repo_root, _R5_COMMIT, tree_posix):
            scoped_key = f"{scoped_prefix}/{relative_posix}"
            repo_path = f"{tree_posix}/{relative_posix}"
            scoped_to_repo[scoped_key] = repo_path
            if repo_path not in seen:
                seen.add(repo_path)
                all_repo_paths.append(repo_path)
    contents = _git_read_paths_batch(repo_root, _R5_COMMIT, all_repo_paths)
    unrecoverable: list[str] = []
    for scoped_key, sealed_hash in sealed_files.items():
        content = contents[scoped_to_repo[scoped_key]]
        if _sha(content) == sealed_hash:
            continue
        if _sha(_crlf_normalize(content)) == sealed_hash:
            continue
        unrecoverable.append(scoped_key)
    return unrecoverable


# ============================================================================
# 1. Real r5 read-only historical verification (R4-5 stop condition).
# ============================================================================


@pytest.mark.skipif(not _r5_available(), reason="real r5 sealed run not available")
def test_r4_5_historical_verifier_rejects_r5_mixed_line_endings():
    """R4-5 STOP CONDITION: the real A-E1 r5 sealed run at d2a056f has 3 scoped
    code files whose sealed SHA-256 was computed over bytes with MIXED line
    endings (a mix of CRLF and lone LF). Git stores LF-normalized blobs, so
    neither the LF form (git blob as-is) nor the CRLF form (LF->CRLF) can
    deterministically reconstruct the sealed bytes.

    The historical verifier fail-closes at the scoped-code gate and reports the
    exact path + sealed/LF/CRLF hashes. Per R4-5, no working-tree fallback is
    permitted -- sealed bytes cannot be substituted from the current file."""

    with pytest.raises(ValueError, match="scoped blob hash mismatch") as exc_info:
        verify_historical_authority(_R5_RUN_DIR, _R5_CACHE_ROOT)
    message = str(exc_info.value)
    # The failure must name one of the 3 known unrecoverable files.
    assert (
        "studies/mdm_delta/generate_curve_study_data.py" in message
        or "studies/mle/simulate.py" in message
        or "studies/wmle/simulate.py" in message
    ), f"unexpected mismatch path in error: {message}"


@pytest.mark.skipif(not _r5_available(), reason="real r5 sealed run not available")
def test_r4_5_r5_has_exactly_3_unrecoverable_scoped_files():
    """Exactly 3 r5 scoped files cannot be recovered from d2a056f git blobs via
    LF or CRLF. Documents the stop-condition path set for audit."""

    r5_manifest = _load_r5_manifest()
    sealed_files = r5_manifest["scheduler"]["authority"]["scoped_code_files"]
    unrecoverable = _list_unrecoverable_scoped_files(sealed_files)
    assert set(unrecoverable) == {
        "studies/mdm_delta/generate_curve_study_data.py",
        "studies/mle/simulate.py",
        "studies/wmle/simulate.py",
    }


@pytest.mark.skipif(not _r5_available(), reason="real r5 sealed run not available")
def test_r4_5_r5_authority_sha256_self_hash_is_valid():
    """The r5 sealed authority_sha256 matches the self-hash of the authority dict
    (minus authority_sha256). This is the sealed-bytes integrity guarantee that
    R4-5 uses in place of re-running _authority/_plan_rows."""

    from study02a.formal_scheduler import _canonical, _sha

    r5_manifest = _load_r5_manifest()
    authority = r5_manifest["scheduler"]["authority"]
    authority_without_sha = {k: v for k, v in authority.items() if k != "authority_sha256"}
    assert authority["authority_sha256"] == _sha(_canonical(authority_without_sha))


@pytest.mark.skipif(not _r5_available(), reason="real r5 sealed run not available")
def test_r4_5_r5_frozen_config_matrix_cross_consistency():
    """The r5 sealed authority's matrix_sha256 and effective_config_sha256 agree
    with the manifest block AND with the frozen repository constants."""

    from study02a.formal_contracts import (
        APPROVED_EFFECTIVE_CONFIG_SHA256,
        FROZEN_MATRIX_SHA256,
    )

    r5_manifest = _load_r5_manifest()
    authority = r5_manifest["scheduler"]["authority"]
    assert authority["matrix_sha256"] == r5_manifest["matrix"]["sha256"]
    assert authority["matrix_sha256"] == FROZEN_MATRIX_SHA256
    assert authority["effective_config_sha256"] == r5_manifest["effective_config"]["sha256"]
    assert authority["effective_config_sha256"] == APPROVED_EFFECTIVE_CONFIG_SHA256


@pytest.mark.skipif(not _r5_available(), reason="real r5 sealed run not available")
def test_r4_5_r5_plan_sha_and_matrix_row_binding():
    """The r5 sealed plan bytes hash to the authority's plan_sha256, and every
    plan row's matrix_row_sha256 matches the frozen matrix row for its fit_id.
    No _plan_rows / _authority re-derivation is needed."""

    r5_manifest = _load_r5_manifest()
    authority = r5_manifest["scheduler"]["authority"]
    plan_bytes = (_R5_RUN_DIR / "plan.jsonl").read_bytes()
    assert _sha(plan_bytes) == authority["plan_sha256"]
    plan = [json.loads(line) for line in plan_bytes.decode("utf-8").splitlines()]
    assert r5_manifest["scheduler"]["fit_count"] == len(plan)

    from study02a.formal_contracts import _open_verified_matrix_evidence

    matrix_evidence = _open_verified_matrix_evidence(Path(authority["matrix_path"]))
    matrix_rows_by_fit = {row["fit_id"]: row for row in matrix_evidence.rows}
    for row in plan:
        matrix_row = matrix_rows_by_fit[row["fit_id"]]
        assert row["matrix_row_sha256"] == _sha(_canonical(matrix_row))


@pytest.mark.skipif(not _r5_available(), reason="real r5 sealed run not available")
def test_r4_5_r5_scheduler_state_is_terminal():
    """The r5 scheduler state is terminal: no live_claim and every fit state is
    succeeded (no pending/claimed). The R4-5 terminal condition would accept
    this state (the only reason historical verify fails is the scoped-code gate)."""

    state_bytes = (_R5_RUN_DIR / "scheduler_state.json").read_bytes()
    state = json.loads(state_bytes.decode("utf-8"))
    assert state["live_claim"] is None
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
# 3. Forged scoped_code_files / path-set drift / aggregate SHA (fail-closed).
# ============================================================================


def test_r3_c_verify_scoped_code_rejects_forged_aggregate_sha():
    """``_verify_scoped_code_against_git`` rejects a forged scoped_code_sha256
    that doesn't match the per-file hashes. Uses LF hashes from git blobs so that
    all per-file checks pass and only the aggregate check is isolated."""

    correct_files = _build_lf_scoped_files_from_git()
    correct_sha = _sha(_canonical(correct_files))
    forged_sha = ("1" if correct_sha[0] != "1" else "2") + correct_sha[1:]
    with pytest.raises(ValueError, match="scoped_code_sha256 mismatch"):
        _verify_scoped_code_against_git(
            STUDY_ROOT, _R5_COMMIT, correct_files, forged_sha,
        )


def test_r3_c_verify_scoped_code_accepts_correct_lf_hashes():
    """``_verify_scoped_code_against_git`` accepts the git-blob LF hashes with
    the correctly recomputed aggregate. This proves the LF-only path works when
    no mixed-line-ending files are present."""

    correct_files = _build_lf_scoped_files_from_git()
    correct_sha = _sha(_canonical(correct_files))
    _verify_scoped_code_against_git(
        STUDY_ROOT, _R5_COMMIT, correct_files, correct_sha,
    )  # no exception.


@pytest.mark.skipif(not _r5_available(), reason="real r5 sealed run not available")
def test_r3_c_verify_scoped_code_rejects_path_set_drift():
    """``_verify_scoped_code_against_git`` rejects when the sealed path set
    doesn't match the git tree at the sealed commit (added/removed file)."""

    r5_manifest = _load_r5_manifest()
    sealed_files = dict(r5_manifest["scheduler"]["authority"]["scoped_code_files"])
    sealed_sha = r5_manifest["scheduler"]["authority"]["scoped_code_sha256"]
    # Add a fictitious path to the sealed set (path-set drift).
    forged_files = dict(sealed_files)
    forged_files["study02/nonexistent/forged.py"] = "a" * 64
    with pytest.raises(ValueError, match="path-set drift"):
        _verify_scoped_code_against_git(
            STUDY_ROOT, _R5_COMMIT, forged_files, sealed_sha,
        )


def test_r3_c_verify_scoped_code_rejects_forged_blob_hash():
    """``_verify_scoped_code_against_git`` rejects when a single file's sealed
    hash is forged (doesn't match the git blob's LF or CRLF form). Uses LF hashes
    from git blobs as the base so only the forged file fails."""

    correct_files = _build_lf_scoped_files_from_git()
    first_key = next(iter(correct_files))
    forged_files = dict(correct_files)
    forged_files[first_key] = "f" * 64
    forged_aggregate = _sha(_canonical(forged_files))
    with pytest.raises(ValueError, match="blob hash mismatch"):
        _verify_scoped_code_against_git(
            STUDY_ROOT, _R5_COMMIT, forged_files, forged_aggregate,
        )


@pytest.mark.skipif(not _r5_available(), reason="real r5 sealed run not available")
def test_r4_5_no_working_tree_fallback_in_scoped_verifier():
    """R4-5: ``_verify_scoped_code_against_git`` does NOT read the working tree.
    Even though the 3 unrecoverable files exist in the working tree and their WT
    hash matches the sealed hash, the verifier must fail closed (no fallback).
    This test confirms the source code contains no working-tree read path."""

    import inspect

    source = inspect.getsource(_verify_scoped_code_against_git)
    assert "wt_path" not in source, "working-tree path leak in scoped verifier"
    assert "_read_identity_snapshot" not in source, "working-tree read in scoped verifier"
    assert "_scoped_key_to_working_tree_path" not in source, "working-tree helper in scoped verifier"


def test_r4_5_scoped_key_to_working_tree_helper_is_removed():
    """R4-5: the ``_scoped_key_to_working_tree_path`` helper has been removed
    from ``formal_scheduler`` (it was only used by the working-tree fallback)."""

    import study02a.formal_scheduler as fs

    assert not hasattr(fs, "_scoped_key_to_working_tree_path")


# ============================================================================
# 4. R4-5: verify_historical_authority does NOT call _authority/_plan_rows.
# ============================================================================


def test_r4_5_historical_verifier_source_has_no_authority_call():
    """R4-5: ``verify_historical_authority`` source code does not call
    ``_authority`` or ``_plan_rows`` (current production code must not be used
    to re-derive or "execute" historical state)."""

    import inspect

    source = inspect.getsource(verify_historical_authority)
    # The function may reference these names in comments/docstrings; check that
    # it does not *call* them (no parenthesised invocation as a statement).
    assert "= _authority(" not in source, "verify_historical_authority calls _authority()"
    assert "_plan_rows(" not in source, "verify_historical_authority calls _plan_rows()"


def test_r4_5_historical_verifier_source_verifies_sealed_bytes():
    """R4-5: ``verify_historical_authority`` source code contains the sealed-bytes
    verification checks required by R4-5."""

    import inspect

    source = inspect.getsource(verify_historical_authority)
    assert "authority_sha256" in source and "self-hash" in source.lower() or "self_hash" in source.lower()
    assert "FROZEN_MATRIX_SHA256" in source
    assert "APPROVED_EFFECTIVE_CONFIG_SHA256" in source
    assert "matrix_row_sha256" in source
    assert "non_terminal" in source
    assert "live_claim" in source


# ============================================================================
# 5. Version-dispatched predecessor schema (v1 r5 vs v2 new).
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

    r5_manifest = _load_r5_manifest()
    assert r5_manifest["manifest_version"] == "study02-formal-v1"
    from study02a.formal_contracts import _PREDECESSOR_SCHEMA_V1_FIELDS
    assert set(r5_manifest["predecessor"]) == _PREDECESSOR_SCHEMA_V1_FIELDS
