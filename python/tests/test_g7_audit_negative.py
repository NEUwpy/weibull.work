"""Regression tests for the production G7 manuscript audit.

Every negative test mutates a temporary fixture and invokes the same
``audit_manuscript`` function used by the command-line audit.  Formal evidence
and manuscript files in the repository are never modified.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "01-study-MDM最小偏移量优化研究"
AUDIT_DIR = STUDY_ROOT / "manuscript" / "audit"
AUDIT_SCRIPT = AUDIT_DIR / "auto_audit.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("study01_g7_auto_audit", AUDIT_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


AUDIT = _load_audit_module()


def _copy(tmp_path: Path, source: Path) -> Path:
    destination = tmp_path / source.name
    shutil.copy2(source, destination)
    return destination


def _assert_rejected(fragment: str, **overrides) -> list[str]:
    errors = AUDIT.audit_manuscript(run_git_check=False, **overrides)
    assert errors, "corrupted fixture unexpectedly passed the production audit"
    assert any(fragment in error for error in errors), (
        f"expected an error containing {fragment!r}; got:\n"
        + "\n".join(errors)
    )
    return errors


def test_current_package_passes_production_audit():
    assert AUDIT.audit_manuscript(run_git_check=False) == []


def test_corrupt_c002_expected_value_is_rejected(tmp_path):
    claims_path = _copy(tmp_path, AUDIT_DIR / "claims-to-data.csv")
    claims = pd.read_csv(claims_path, dtype=str, keep_default_na=False)
    claims.loc[claims["claim_id"] == "C002", "expected_value"] = "0.632540558"
    claims.to_csv(claims_path, index=False)

    _assert_rejected("C002 value mismatch", claims_csv=claims_path)


def test_delete_required_claim_is_rejected(tmp_path):
    claims_path = _copy(tmp_path, AUDIT_DIR / "claims-to-data.csv")
    claims = pd.read_csv(claims_path, dtype=str, keep_default_na=False)
    claims = claims[claims["claim_id"] != "C001"]
    claims.to_csv(claims_path, index=False)

    _assert_rejected("claims registry missing IDs: C001", claims_csv=claims_path)


def test_add_unregistered_claim_is_rejected(tmp_path):
    claims_path = _copy(tmp_path, AUDIT_DIR / "claims-to-data.csv")
    claims = pd.read_csv(claims_path, dtype=str, keep_default_na=False)
    extra = claims.iloc[[0]].copy()
    extra.loc[:, "claim_id"] = "C999"
    claims = pd.concat([claims, extra], ignore_index=True)
    claims.to_csv(claims_path, index=False)

    _assert_rejected("claims registry has unexpected IDs: C999", claims_csv=claims_path)


def test_stale_source_path_is_rejected(tmp_path):
    claims_path = _copy(tmp_path, AUDIT_DIR / "claims-to-data.csv")
    claims = pd.read_csv(claims_path, dtype=str, keep_default_na=False)
    claims.loc[claims["claim_id"] == "C017", "source_file"] = "R2产物"
    claims.to_csv(claims_path, index=False)

    _assert_rejected("C017 source_file mismatch", claims_csv=claims_path)


def test_figure_index_pending_status_is_rejected(tmp_path):
    index_path = _copy(tmp_path, STUDY_ROOT / "manuscript" / "figure-index.md")
    index_path.write_text(
        index_path.read_text(encoding="utf-8") + "\nS9 | **需生成**\n",
        encoding="utf-8",
    )

    _assert_rejected(
        'figure-index contains stale status "需生成"', figure_index_md=index_path
    )


def test_submission_checklist_pending_figures_are_rejected(tmp_path):
    checklist_path = _copy(tmp_path, AUDIT_DIR / "submission-checklist.md")
    checklist_path.write_text(
        checklist_path.read_text(encoding="utf-8") + "\n- [ ] S1-S8需生成\n",
        encoding="utf-8",
    )

    _assert_rejected(
        'submission-checklist contains stale status "需生成"',
        submission_checklist_md=checklist_path,
    )


def test_delete_reference_7_is_rejected(tmp_path):
    references_path = _copy(tmp_path, AUDIT_DIR / "reference-checklist.csv")
    references = pd.read_csv(references_path, dtype=str, keep_default_na=False)
    references = references[references["ref_number"] != "[7]"]
    references.to_csv(references_path, index=False)

    _assert_rejected(
        "reference [7] must appear exactly once",
        reference_checklist_csv=references_path,
    )


def test_wrong_supplementary_beta_count_is_rejected(tmp_path):
    supplementary_path = _copy(
        tmp_path, STUDY_ROOT / "manuscript" / "supplementary.md"
    )
    text = supplementary_path.read_text(encoding="utf-8")
    corrected = text.replace("5×3×20=300", "每个beta各300个")
    assert corrected != text, "fixture setup did not replace the frozen beta count"
    supplementary_path.write_text(corrected, encoding="utf-8")

    _assert_rejected(
        "supplementary contains stale per-beta count",
        supplementary_md=supplementary_path,
    )


def test_delete_figure_7_citation_is_rejected(tmp_path):
    paper_path = _copy(tmp_path, STUDY_ROOT / "manuscript" / "paper.md")
    text = paper_path.read_text(encoding="utf-8")
    corrected = text.replace("Figure 7", "the boundary/off-grid panel")
    assert corrected != text, "fixture setup did not remove the Figure 7 citation"
    paper_path.write_text(corrected, encoding="utf-8")

    _assert_rejected("paper does not cite Figure 7", paper_md=paper_path)
