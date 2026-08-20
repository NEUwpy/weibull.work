import json
import sys
from pathlib import Path

import pytest


STUDY_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = STUDY_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

import derive_e8_seed42_primary as seed42


def test_seed42_primary_derivation_uses_existing_e8_outputs(tmp_path):
    summary = seed42.derive(tmp_path)

    assert summary["primary_seed"] == 42
    assert summary["sensitivity_seeds"] == [2026, 3407]
    assert summary["main"]["adaptive_J1"] == pytest.approx(0.5845531935428129)
    assert summary["main"]["relative_improvement_vs_default"] == pytest.approx(
        0.07274006533291955
    )
    assert summary["unseen_beta"]["adaptive_J1"] == pytest.approx(0.5840909185338468)
    assert summary["unseen_beta"]["relative_improvement_vs_default"] == pytest.approx(
        0.07347335889687057
    )
    assert summary["quantile_relative_rmse"] == pytest.approx({
        "x0.90": 0.16084078678729685,
        "x0.95": 0.21356179696558647,
        "x0.99": 0.37533347522054533,
    })

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["derivation_only"] is True
    assert set(manifest["derived_files_sha256_lf"]) == {
        "main_results.csv", "unseen_beta.csv", "quantiles.csv", "summary.json"
    }
    assert (tmp_path / "SHA256SUMS").is_file()
    assert not (tmp_path / "SHA256SUMS.local_not_in_git").exists()
