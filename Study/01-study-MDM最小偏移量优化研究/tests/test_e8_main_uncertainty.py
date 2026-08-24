import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


STUDY_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = STUDY_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

import analyze_e8_main_uncertainty as uncertainty
import paper_support as PS


OUTPUT_DIR = (
    STUDY_ROOT / "artifacts" / "formal" /
    "E8_mean_normalized_selector" / "main_uncertainty"
)


def test_bootstrap_is_paired_deterministic_and_reports_j1_scale():
    adaptive = np.array([1.0, 4.0, 9.0, 16.0])
    default = np.array([4.0, 9.0, 16.0, 25.0])
    first = uncertainty.bootstrap_from_units(
        adaptive, default, n_bootstrap=2_000, rng_seed=123
    )
    second = uncertainty.bootstrap_from_units(
        adaptive, default, n_bootstrap=2_000, rng_seed=123
    )

    assert first == second
    assert first["adaptive_J1"] == pytest.approx(np.sqrt(adaptive.mean()))
    assert first["default_J1"] == pytest.approx(np.sqrt(default.mean()))
    assert first["delta_J1_ci95_high"] < 0
    assert first["relative_improvement_ci95_low"] > 0


def test_bootstrap_rejects_unpaired_inputs():
    with pytest.raises(ValueError, match="paired"):
        uncertainty.bootstrap_from_units(
            np.array([1.0, 2.0]), np.array([1.0]),
            n_bootstrap=10, rng_seed=1,
        )


def test_formal_uncertainty_outputs_match_primary_result_and_ledger():
    summary = json.loads(
        (OUTPUT_DIR / "summary.json").read_text(encoding="utf-8")
    )
    primary = summary["primary_result"]
    monte_carlo = summary["conditional_monte_carlo_uncertainty"]
    design = summary["design_composition_sensitivity"]
    cells = pd.read_csv(OUTPUT_DIR / "cell_effects.csv")

    assert primary["adaptive_J1"] == pytest.approx(0.5845531935428129)
    assert primary["default_J1"] == pytest.approx(0.6304091999323665)
    assert primary["relative_improvement"] == pytest.approx(0.07274006533291921)
    assert monte_carlo["relative_improvement_ci95"][0] > 0
    assert monte_carlo["relative_improvement_ci95"][0] < primary["relative_improvement"]
    assert monte_carlo["relative_improvement_ci95"][1] > primary["relative_improvement"]
    assert design["relative_improvement_resampling_range95"][0] > 0
    assert len(cells) == 160
    assert int((cells["delta_J1"] < -1e-12).sum()) == 125
    assert int((cells["delta_J1"] > 1e-12).sum()) == 35

    ledger = (OUTPUT_DIR / "SHA256SUMS").read_text(encoding="ascii").splitlines()
    assert len(ledger) == 4
    for line in ledger:
        expected, name = line.split("  ", 1)
        assert PS.sha256_file_lf(OUTPUT_DIR / name) == expected
