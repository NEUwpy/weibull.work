from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))

from study02a.config import load_frozen_config
from study02a.matrix import expand_module_matrix


def test_all_frozen_matrix_rules_expand_with_sealed_tests():
    cfg = load_frozen_config(STUDY_ROOT)
    matrix = expand_module_matrix(cfg)
    expected_rules = set(cfg.search["module_matrix_rules"])
    assert set(matrix["rule_id"]) == expected_rules
    assert matrix["fit_id"].is_unique
    assert set(matrix["test_state"]) == {"sealed"}


def test_historical_and_total_fit_caps_are_exact():
    cfg = load_frozen_config(STUDY_ROOT)
    matrix = expand_module_matrix(cfg)
    historical = matrix[matrix["rule_id"] == "A-E1_historical"]
    assert len(historical) == 30
    assert len(matrix) == 820
    assert len(matrix) <= cfg.search["fit_caps"]["G3"]
