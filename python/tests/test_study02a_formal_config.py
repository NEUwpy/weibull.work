from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))


def _copy_config_study(tmp_path: Path) -> Path:
    copied_root = tmp_path / "study"
    copied_configs = copied_root / "configs"
    copied_configs.mkdir(parents=True)
    for name in (
        "A-g2-configs.sha256",
        "A-g2-protocol-v1.json",
        "A-g2-search-v1.json",
        "A-g3-pilot-amendment-v4.json",
        "A-g3-pilot-amendment-v4.sha256",
    ):
        shutil.copy2(STUDY_ROOT / "configs" / name, copied_configs / name)
    return copied_root


def _rewrite_json(path: Path, mutate) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def test_effective_formal_config_exposes_the_approved_contract():
    from study02a.formal_config import load_effective_formal_config

    config = load_effective_formal_config(STUDY_ROOT)

    assert config.base_protocol_id == "A-G2-v1"
    assert config.base_protocol_sha256 == "f82e078051d760d7c9c11ece54b8fae7360c6db1aef3229a97b4fcd92ae01a11"
    assert config.base_search_id == "A-G2-search-v1"
    assert config.base_search_sha256 == "abd6d17b1d2467e1253e0154adba0b6582a3feeb83ed889534ed4f6ab5e0ca13"
    assert config.amendment_id == "A-G3-pilot-amendment-v4"
    assert config.amendment_sha256 == "164e72658669dbb57f6dab8b1fc80099bd319f1fa327d5dda60cb61cb929ee38"
    assert (config.max_epochs, config.min_epochs, config.patience) == (100, 50, 40)
    assert config.base_max_epochs == 500
    assert config.approved_override_paths == ("search.training.max_epochs",)
    assert len(config.effective_config_sha256) == 64
    int(config.effective_config_sha256, 16)
    with pytest.raises(FrozenInstanceError):
        config.max_epochs = 500


def test_effective_hash_is_canonical_and_deterministic(tmp_path):
    from study02a.formal_config import load_effective_formal_config

    copied_root = _copy_config_study(tmp_path)
    first = load_effective_formal_config(copied_root)
    second = load_effective_formal_config(copied_root)

    protocol = json.loads((copied_root / "configs" / "A-g2-protocol-v1.json").read_text(encoding="utf-8"))
    search = json.loads((copied_root / "configs" / "A-g2-search-v1.json").read_text(encoding="utf-8"))
    search["training"]["max_epochs"] = 100
    canonical = json.dumps(
        {"protocol": protocol, "search": search},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    expected = hashlib.sha256(canonical).hexdigest()

    assert first.effective_config_sha256 == second.effective_config_sha256 == expected


@pytest.mark.parametrize("missing_name", ["A-g3-pilot-amendment-v4.json", "A-g3-pilot-amendment-v4.sha256"])
def test_missing_amendment_or_sha_manifest_rejects(tmp_path, missing_name):
    from study02a.formal_config import load_effective_formal_config

    copied_root = _copy_config_study(tmp_path)
    (copied_root / "configs" / missing_name).unlink()

    with pytest.raises(ValueError, match="amendment"):
        load_effective_formal_config(copied_root)


def test_amendment_sha_mismatch_rejects(tmp_path):
    from study02a.formal_config import load_effective_formal_config

    copied_root = _copy_config_study(tmp_path)
    amendment = copied_root / "configs" / "A-g3-pilot-amendment-v4.json"
    amendment.write_bytes(amendment.read_bytes() + b"\n")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_effective_formal_config(copied_root)


@pytest.mark.parametrize(
    ("case", "mutate"),
    [
        ("amendment ID", lambda doc: doc.__setitem__("amendment_id", "wrong")),
        ("base search ID", lambda doc: doc["protocol_revision"].__setitem__("base_search_id", "wrong")),
        ("override path", lambda doc: doc["protocol_revision"].__setitem__("override", "search.training.min_epochs")),
        ("old value", lambda doc: doc["protocol_revision"].__setitem__("old_value", 499)),
        ("new value", lambda doc: doc["protocol_revision"].__setitem__("new_value", 500)),
        ("additional override", lambda doc: doc["protocol_revision"].__setitem__("additional_override", "search.training.min_epochs")),
    ],
)
def test_amendment_contract_tampering_rejects_before_use(tmp_path, case, mutate):
    from study02a.formal_config import load_effective_formal_config

    copied_root = _copy_config_study(tmp_path)
    amendment = copied_root / "configs" / "A-g3-pilot-amendment-v4.json"
    _rewrite_json(amendment, mutate)

    with pytest.raises(ValueError, match=case):
        load_effective_formal_config(copied_root)


@pytest.mark.parametrize("requested", [99, 101, 500])
def test_unapproved_requested_max_epochs_rejects(requested):
    from study02a.formal_config import load_effective_formal_config

    with pytest.raises(ValueError, match="requested_max_epochs"):
        load_effective_formal_config(STUDY_ROOT, requested_max_epochs=requested)


def test_exact_requested_ceiling_is_only_a_validation_request():
    from study02a.formal_config import load_effective_formal_config

    default = load_effective_formal_config(STUDY_ROOT)
    requested = load_effective_formal_config(STUDY_ROOT, requested_max_epochs=100)

    assert requested == default
    assert requested.max_epochs == 100
    assert requested.max_epochs != requested.base_max_epochs


def test_loader_performs_no_writes(tmp_path):
    from study02a.formal_config import load_effective_formal_config

    copied_root = _copy_config_study(tmp_path)
    before = {
        path.relative_to(copied_root): path.read_bytes()
        for path in copied_root.rglob("*")
        if path.is_file()
    }

    load_effective_formal_config(copied_root)

    after = {
        path.relative_to(copied_root): path.read_bytes()
        for path in copied_root.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not (copied_root / "artifacts").exists()
