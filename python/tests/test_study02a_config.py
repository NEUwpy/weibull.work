from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))

from study02a.config import load_frozen_config


def test_load_frozen_config_verifies_hashes():
    config = load_frozen_config(STUDY_ROOT)
    assert config.protocol["status"] == "frozen_oracle_approved"
    assert config.protocol_sha256 == "f82e078051d760d7c9c11ece54b8fae7360c6db1aef3229a97b4fcd92ae01a11"
    assert config.search_sha256 == "abd6d17b1d2467e1253e0154adba0b6582a3feeb83ed889534ed4f6ab5e0ca13"


def test_screening_and_formal_seeds_are_disjoint():
    config = load_frozen_config(STUDY_ROOT)
    screening = set(config.protocol["seeds"]["nn_screening"])
    formal = set(config.protocol["seeds"]["nn_formal"])
    assert screening.isdisjoint(formal)
    assert len(screening) == 3
    assert len(formal) == 10
