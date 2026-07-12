from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_DIR = REPO_ROOT / "Study" / "01-study-MDM最小偏移量优化研究"
LADDER_CSV = STUDY_DIR / "artifacts" / "formal" / "E2_oracle_layers" / "ladder_L1_L6.csv"
FIGURE_SCRIPT = STUDY_DIR / "code" / "plot_fig3_fig4.py"


def test_figure5_panel_b_uses_stepwise_relative_j1_reductions():
    ladder = pd.read_csv(LADDER_CSV).set_index("layer")
    order = ["Default", "L1", "L2", "L3", "L4", "L5", "L6"]
    j1 = [float(ladder.loc[layer, "J1_global"]) for layer in order]
    stepwise = [
        (previous - current) / previous * 100
        for previous, current in zip(j1[:-1], j1[1:])
    ]

    assert stepwise[2] == pytest.approx(7.505140, abs=1e-6)
    assert stepwise[5] == pytest.approx(13.418178, abs=1e-6)

    source = FIGURE_SCRIPT.read_text(encoding="utf-8")
    assert "stepwise_reductions" in source
    assert "Stepwise $J_1$ reduction vs previous layer (%)" in source
    assert "Cumulative improvement vs Default (%)" not in source
    assert "delta_imp = improvements" not in source
    assert 'f"+{imp:.1f}%"' not in source
    assert 'f"{reduction:.2f}%" if reduction < 0.1 else' in source
    assert "hindsight gap" in source
    assert "two major jumps" not in source
