"""B6 evidence verification: all SHA256 hashes and key numbers quoted in
04-B / 05-B recomputed from disk, plus figure artifacts and their inputs.

Reads only accepted run manifests under C:/weibull-runs/study02/formal-b and
the tracked artifacts/lean figures. No fits, no inference reruns.
"""
import csv, hashlib, json, sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY = REPO_ROOT / "Study/02-study-NN参数估计与分位点目标研究"
EXTERNAL = Path("C:/weibull-runs/study02/formal-b")

def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def _load(rel):
    return json.loads((EXTERNAL / rel / "manifest.json").read_text(encoding="utf-8"))


# ---- accepted run manifests and their SHAs ----

B1 = "B1-pilot-20260731-113742"
B2 = "B2-search-20260731-114219"
B3 = "B3-training-20260731-121958"
B4_CORE = "B4-core-20260801-051119"
B4_ANALYZE = "B4-analyze-20260801-053046"
B5_V3 = "B5-v3-20260801-062647"
B5_V4 = "B5-v4-20260801-063558"
B5_V6 = "B5-v6-20260801-073535"


def test_manifest_hashes_match_disk():
    expected = {
        B1: "ecf788fb59b1668b76cde448f90f4f57eb6a8f010b01953e50451f7ad285b692",
        B2: "ecee58a9433cbbbdf630e9dcf2399e21dab650cd36056952b6762a4e41838c89",
        B3: "5fcddbcf0bc405b30ac1d50a2ac120352b145e42623c72e7d4eef60ba7a24307",
        B4_CORE: "f331c91d750055e4ea0c03f3dc24be876cb563cbe3bb394ee85b47a6579334fb",
        B4_ANALYZE: "45bd50d0ac5cf39445b28836e0150c9df6b2136fe56b72598ea306553bd51142",
        B5_V3: "046e51434616eca82fb6091f7f2c58bc62c7f109aded66d8aa79bda724414c40",
        B5_V4: "fa4823ecf5064c536071eff569792c8efc4c096407cb65c37f117a08b79492d5",
        B5_V6: "317b4ed16a687ad60f14deb53d206ef036831039cd5121a69c1bd3f346ffd782",
    }
    for rel, sha in expected.items():
        assert _sha(EXTERNAL / rel / "manifest.json") == sha, f"{rel} manifest hash mismatch"


def test_b4_primary_conclusion():
    b4 = _load(B4_ANALYZE)
    p = b4["primary"]
    assert p["improvement_I"] == 0.3926
    assert p["ci_95_lower"] == 0.34437788520680845
    assert p["ci_95_upper"] == 0.4347393498309549
    assert p["verdict"] == "supported and material"


def test_b4_per_n_and_bh():
    b4 = _load(B4_ANALYZE)
    assert b4["per_n"]["5"]["bh_support"] == "supported (BH)"
    assert b4["per_n"]["7"]["bh_support"] == "not significant (BH)"
    assert b4["per_n"]["10"]["bh_support"] == "not significant (BH)"
    assert b4["per_n"]["15"]["bh_support"] == "supported (BH)"
    assert b4["per_n"]["20"]["bh_support"] == "supported (BH)"
    assert b4["bh_adjustment"]["support"] == {
        "5": "supported (BH)", "15": "supported (BH)", "20": "supported (BH)",
        "7": "not significant (BH)", "10": "not significant (BH)"}


def test_b4_d_vs_traditional():
    b4 = _load(B4_CORE)
    dvt = b4["d_vs_traditional"]
    assert dvt["MDM"]["t_better"] is True and dvt["MDM"]["d_better"] is False
    assert dvt["MLE"]["t_better"] is False and dvt["MLE"]["d_better"] is False
    assert dvt["LRE"]["t_better"] is True and dvt["LRE"]["d_better"] is False


def test_b4_controlled_attribution():
    """B3 controlled attribution: P vs Dctrl (matched m12 backbone); D (selected
    [64,32]) explains little beyond Dctrl. Values quoted in 04-B/05-B."""
    b4 = _load(B4_CORE)
    pr = b4["per_route"]
    assert abs(pr["P"]["rmse"] - 0.6943) < 0.0005
    assert abs(pr["Dctrl"]["rmse"] - 0.3296) < 0.0005
    assert abs(pr["D"]["rmse"] - 0.3290) < 0.0005
    # Dctrl (m12 [256,128,64], 5 seeds) vs D selected ([64,32], 10 seeds)
    b3 = _load(B3)
    groups = {}
    for e in b3["d_checkpoints"]:
        groups.setdefault(e["group"], {"widths": set(), "seeds": set()})
        groups[e["group"]]["widths"].add(tuple(e["widths"]))
        groups[e["group"]]["seeds"].add(e["seed"])
    assert groups["controlled"]["widths"] == {(256, 128, 64)}
    assert groups["selected"]["widths"] == {(64, 32)}
    assert len(groups["controlled"]["seeds"]) == 5
    assert len(groups["selected"]["seeds"]) == 10


def test_b5_v6_stress_bh_corrected():
    b5 = _load(B5_V6)
    bh = b5["stress"]["_bh"]
    # the cells the reviewer flagged must NOT be q=0 or supported
    assert bh["q_values"]["low_n7"] > 0.05      # p=.1789
    assert bh["q_values"]["low_n15"] > 0.05     # p=.4238
    assert bh["q_values"]["loc_n10"] > 0.05     # p=.5607
    assert bh["support"]["low_n7"].startswith("not significant")
    assert bh["support"]["low_n15"].startswith("not significant")
    assert bh["support"]["loc_n10"].startswith("not significant")
    n_supported = sum(1 for v in bh["support"].values() if v.startswith("supported"))
    assert n_supported == 10


def test_b5_v6_nist_500_and_exactness():
    b5 = _load(B5_V6)
    for n in ["5", "7", "10", "15", "20"]:
        assert b5["nist"][n]["exact_500"] is True
        assert b5["nist"][n]["n_unique_splits"] == 500


def test_b5_v3_p_diagnostics():
    v3 = _load(B5_V3)
    pd = v3["p_diagnostics"]
    assert pd["legal_rate"] == 1.0
    assert pd["gamma_violations"] == 0
    assert pd["n_total"] == 64000
    # pooled beta/eta/gamma rmse quoted in 05-B
    assert abs(pd["pooled"]["beta"]["rmse"] - 0.325) < 0.001
    assert abs(pd["pooled"]["eta"]["rmse"] - 2.466) < 0.001
    assert abs(pd["pooled"]["gamma"]["rmse"] - 0.880) < 0.001


def test_figures_and_sha256sums_tracked():
    b6 = STUDY / "artifacts" / "b6"
    sums = json.loads((b6 / "SHA256SUMS").read_text(encoding="utf-8"))
    for name, sha in sums["outputs"].items():
        assert _sha(b6 / name) == sha, f"figure {name} hash mismatch"
    assert list(sums["outputs"].keys()) == ["core_error_vs_n.png", "core_effect_by_n.png", "stress_tradeoff.png"]
    # inputs bound to accepted manifests
    assert sums["inputs"][f"{B4_ANALYZE}/manifest.json"] == _sha(EXTERNAL / B4_ANALYZE / "manifest.json")
    assert sums["inputs"][f"{B5_V6}/manifest.json"] == _sha(EXTERNAL / B5_V6 / "manifest.json")
