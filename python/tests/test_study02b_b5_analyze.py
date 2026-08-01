"""Tests for B5 v4: split-conformal quantile, CSV schema, NIST split count."""
import sys, csv
from pathlib import Path
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in [str(REPO_ROOT/"Study/02-study-NN参数估计与分位点目标研究/code"),str(REPO_ROOT/"python")]:
    if p not in sys.path: sys.path.insert(0, p)

from study02b.analyze_b5 import split_conformal_quantile, _N_VALUES, _bh_qvalues, _cluster_bootstrap_paired


def test_bh_qvalues_known_vector():
    """Standard BH: p=[.001,.01,.04,.20] -> q≈[.004,.020,.053333,.20]."""
    q=_bh_qvalues({"a":.001,"b":.01,"c":.04,"d":.20})
    assert abs(q["a"]-0.004)<1e-6
    assert abs(q["b"]-0.020)<1e-6
    assert abs(q["c"]-(0.04*4/3))<1e-9
    assert abs(q["d"]-0.20)<1e-9

def test_bh_qvalues_zero_cannot_drag_large_p():
    """A zero/small p must not force a later large p to q=0 (reverse cumulative min)."""
    q=_bh_qvalues({"low_n5":0.0,"low_n7":.178,"low_n15":.423,"loc_n10":.56})
    assert q["low_n5"]==0.0
    assert q["low_n7"]>0.05     # .178 -> .356, not supported
    assert q["low_n15"]>0.05    # .423 -> .56, not supported
    assert q["loc_n10"]>0.05    # .56 -> .56, not supported
    # q-values must be monotone non-increasing in sorted-p order
    ps=sorted([.0,.178,.423,.56]); qs=sorted([q["low_n5"],q["low_n7"],q["low_n15"],q["loc_n10"]])
    assert qs==[q["low_n5"],q["low_n7"],q["low_n15"],q["loc_n10"]]

def test_plus_one_pvalue_no_exact_zero():
    """Bootstrap p-value must use plus-one correction: never exactly 0 from finite draws."""
    paired={0:[-1.0,-2.0],1:[-1.5,-2.5]}
    r=_cluster_bootstrap_paired(paired,2,n_boot=2000,seed=1)
    assert r["p"]>0.0
    assert r["p"]<=1.0


def test_split_conformal_alpha_0_1():
    """For alpha=0.1, q = ceil((n+1)*0.9) order statistic."""
    residuals=np.abs(np.random.default_rng(42).standard_normal(1000))
    q=split_conformal_quantile(residuals,0.1)
    expected_idx=int(np.ceil(1001*0.9))-1
    assert q==float(np.sort(residuals)[expected_idx])

def test_split_conformal_alpha_0_05():
    residuals=np.abs(np.random.default_rng(42).standard_normal(1000))
    q=split_conformal_quantile(residuals,0.05)
    expected_idx=int(np.ceil(1001*0.95))-1
    assert q==float(np.sort(residuals)[expected_idx])

def test_split_conformal_edge_cases():
    assert np.isnan(split_conformal_quantile(np.array([]),0.1))
    q=split_conformal_quantile(np.array([1.0,2.0,3.0]),0.1)
    assert q==3.0  # ceil(4*0.9)-1=ceil(3.6)-1=4-1=3, index 2 → 3.0

def test_stress_csv_schema():
    """v3 stress CSVs must have required columns."""
    v3=Path("C:/weibull-runs/study02/formal-b/B5-v3-20260801-062647")
    with open(v3/"stress_low.csv",newline="",encoding="utf-8") as f:
        reader=csv.DictReader(f)
        cols=reader.fieldnames
        for c in ["cluster","replicate","n","domain","true_x095","P_pred","P_valid","D_pred","D_valid"]:
            assert c in cols, f"Missing column {c}"
        rows=list(reader)
    assert len(rows)==1600

def test_nist_500_splits():
    """v3 nist_splits.csv must have exactly 500 unique splits per n."""
    v3=Path("C:/weibull-runs/study02/formal-b/B5-v3-20260801-062647")
    with open(v3/"nist_splits.csv",newline="",encoding="utf-8") as f:
        rows=list(csv.DictReader(f))
    for n_val in [5,7,10,15,20]:
        subset=[r for r in rows if int(r["n"])==n_val]
        splits=set(int(r["split"]) for r in subset)
        assert len(splits)==500, f"n={n_val}: expected 500 splits, got {len(splits)}"

def test_contamination_conditions():
    """contamination.csv must have exactly 5 conditions."""
    v3=Path("C:/weibull-runs/study02/formal-b/B5-v3-20260801-062647")
    with open(v3/"contamination.csv",newline="",encoding="utf-8") as f:
        rows=list(csv.DictReader(f))
    conds=set(r["condition"] for r in rows)
    assert conds=={"clean","high3","high10","low_end","two_sided"}
    # Each condition: 32×10=320 rows
    for c in conds:
        assert sum(1 for r in rows if r["condition"]==c)==320


# ---- B5 v5 derived-analysis tests (synthetic fixtures) ----

def _write_csv(path, fieldnames, rows):
    with open(path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fieldnames); w.writeheader()
        for r in rows: w.writerow(r)


def _stress_fixture(tmp_path):
    """3 domains x (2 clusters x 2 reps at n=5); D sqre loss < P sqre loss."""
    fieldnames=["cluster","replicate","n","true_x095","P_pred","P_valid","D_pred","D_valid"]
    rows=[]
    for ci in [0,1]:
        for ri in [0,1]:
            rows.append({"cluster":ci,"replicate":ri,"n":5,"true_x095":100,
                         "P_pred":50,"P_valid":1,"D_pred":101,"D_valid":1})
    for dom in ["low","high","loc"]:
        _write_csv(tmp_path/f"stress_{dom}.csv", fieldnames, rows)
    return tmp_path


def test_analyze_stress_uses_paired_sqre_loss(tmp_path):
    """Direction must come from paired squared-relative-error loss, not signed bias."""
    from study02b.analyze_b5 import analyze_stress
    res=analyze_stress(_stress_fixture(tmp_path))
    cell=res["low"]["n5"]
    # Corrected estimand: D has the smaller squared relative error
    assert cell["paired_loss"]["direction"]=="D better"
    assert cell["paired_loss"]["mean_sqre_diff"]<0
    # Signed bias is descriptive only and can point the other way (D rel err -0.5 vs P ... )
    assert cell["signed_bias_diff"]["mean"]>0
    assert "note" in cell["signed_bias_diff"]
    # Per-route total/valid/failure reported separately
    assert cell["route_stats"]["D"]["n_valid"]==4
    assert cell["route_stats"]["D"]["n_total"]==4
    assert cell["route_stats"]["D"]["n_failure"]==0
    # BH secondary family across domain x n
    assert res["_bh"]["m"]==3
    assert "bh" in cell and "support" in cell["bh"]


def test_analyze_stress_bh_family_and_common_valid(tmp_path):
    from study02b.analyze_b5 import analyze_stress
    res=analyze_stress(_stress_fixture(tmp_path))
    assert res["_bh"]["method"]=="Benjamini-Hochberg"
    assert res["_bh"]["m"]==3  # 3 domains x 1 n
    for dom in ["low","high","loc"]:
        for key in res["_bh"]["p_values"]:
            if key.startswith(dom+"_n"):
                assert key.split("_n")[1] in {"5","7","10","15","20"}
    # common-valid counts reported
    assert res["low"]["n5"]["common_valid"]["n_rows"]==4


def test_analyze_contamination_paired_and_pv_d_degradation(tmp_path):
    """Each condition vs its paired clean row, plus explicit 4-way common-valid P-vs-D estimand."""
    from study02b.analyze_b5 import analyze_contamination
    fieldnames=["cluster","replicate","condition","true_x095","P_pred","P_valid","D_pred","D_valid"]
    rows=[]
    for ci in [0,1]:
        for ri in [0,1]:
            rows.append({"cluster":ci,"replicate":ri,"condition":"clean","true_x095":100,
                         "P_pred":101,"P_valid":1,"D_pred":101,"D_valid":1})
            rows.append({"cluster":ci,"replicate":ri,"condition":"high3","true_x095":100,
                         "P_pred":150,"P_valid":1,"D_pred":102,"D_valid":1})
    p=tmp_path/"contamination.csv"
    _write_csv(p, fieldnames, rows)
    res=analyze_contamination(p)
    hp=res["high3"]["P"]
    # paired with clean rows: 4 common-valid pairs, all 4 validity states counted
    assert hp["validity_changes"]["clean_valid_cond_valid"]==4
    assert hp["common_valid"]["n_rows"]==4
    assert hp["paired_sqre_change"]["mean"]>0  # degraded under high3
    assert hp["clean_rmse"] is not None and hp["cond_rmse"] is not None
    # P-vs-D degradation on explicit 4-way common-valid estimand
    pd=res["high3"]["P_vs_D_degradation"]
    assert pd["common_valid_4way"]==4
    assert pd["direction"]=="D degrades less"
    assert pd["paired_diff_D_minus_P"]["mean"]<0


def test_analyze_conformal_recomputes_from_thresholds(tmp_path):
    """Coverage must be recomputed from pred/true_x095 + v4 thresholds (not the v3 covered_* columns)."""
    from study02b.analyze_b5 import analyze_conformal_coverage
    core_f=["cluster","replicate","n","route","pred","true_x095"]
    core=[{"cluster":0,"replicate":0,"n":5,"route":"P","pred":100,"true_x095":90},
          {"cluster":0,"replicate":0,"n":5,"route":"D","pred":100,"true_x095":95}]
    _write_csv(tmp_path/"conformal_core.csv", core_f, core)
    st_f=["cluster","replicate","n","true_x095","P_pred","P_valid","D_pred","D_valid"]
    st=[{"cluster":0,"replicate":0,"n":5,"true_x095":95,"P_pred":100,"P_valid":1,"D_pred":100,"D_valid":1},
        {"cluster":0,"replicate":1,"n":5,"true_x095":95,"P_pred":100,"P_valid":1,"D_pred":100,"D_valid":0}]
    for dom in ["low","high","loc"]:
        _write_csv(tmp_path/f"stress_{dom}.csv", st_f, st)
    thresholds={"5":{"P_q90":8,"P_q95":12,"D_q90":4,"D_q95":6}}
    res=analyze_conformal_coverage(thresholds, tmp_path, core_path=tmp_path/"conformal_core.csv")
    p5=res["core"]["P_n5"]
    assert p5["cov90"]==0.0 and p5["cov95"]==1.0       # |100-90|=10: <=8 false, <=12 true
    assert p5["abs_width90"]==16.0 and p5["abs_width95"]==24.0
    assert p5["spearman"]=="undefined (constant width per route x n)"
    assert p5["n_total"]==1 and p5["n_valid"]==1 and p5["n_invalid"]==0
    # Stress reports conditional-on-valid coverage plus availability, never unconditional
    sd=res["stress_degradation"]["low_D_n5"]
    assert sd["n_total"]==2 and sd["n_valid"]==1
    assert sd["availability"]==0.5
    assert sd["cov95_cond_valid"]==1.0


def test_analyze_nist_paired_exceedance_cis(tmp_path):
    """NIST must report paired exceedance-effect CIs and route failure rates."""
    from study02b.analyze_b5 import analyze_nist
    fieldnames=["n","split"]+[f"{r}_{m}" for r in ["P","D","MDM","MLE","LRE"]
                              for m in ["valid","pinball","exceed"]]
    rows=[]
    for s in [0,1,2]:
        row={"n":5,"split":s}
        for r in ["P","D","MDM","MLE","LRE"]:
            row[f"{r}_valid"]=1
            row[f"{r}_pinball"]=10.0+s
            row[f"{r}_exceed"]=0.90+0.01*s
        rows.append(row)
    p=tmp_path/"nist_splits.csv"
    _write_csv(p, fieldnames, rows)
    res=analyze_nist(p)
    n5=res["5"]
    assert n5["n_unique_splits"]==3
    assert n5["route_stats"]["P"]["split_failure_rate"]==0.0
    pd=n5["paired"]["P_vs_D"]
    assert pd["n_common_splits"]==3
    assert "exceedance_effect" in pd
    assert "pinball_effect" in pd
    assert "mean" in pd["exceedance_effect"] and "ci_lo" in pd["exceedance_effect"]


def test_run_analyze_binds_v3_csvs_and_v4_calibration(tmp_path):
    """v5 manifest must bind frozen v3 CSV hashes and the accepted v4 calibration artifact/hash."""
    import hashlib
    from study02b import analyze_b5 as a
    out=str(tmp_path/"run")
    m=a.run_analyze(output_dir=out)
    assert m["version"]=="6.0"
    # v3 manifest + 6 CSV hashes bound
    v3_mf_sha=hashlib.sha256((a._V3_DIR/"manifest.json").read_bytes()).hexdigest()
    assert m["input_hashes"]["b5_v3_manifest"]==v3_mf_sha
    assert len(m["input_hashes"]["b5_v3_csvs"])==6
    for f in sorted(a._V3_DIR.glob("*.csv")):
        assert m["input_hashes"]["b5_v3_csvs"][f.name]==hashlib.sha256(f.read_bytes()).hexdigest()
    # accepted v4 calibration manifest bound
    v4_sha=hashlib.sha256(a._V4_MANIFEST.read_bytes()).hexdigest()
    assert m["input_hashes"]["b5_v4_calibration_manifest"]["sha256"]==v4_sha
    # corrected estimand + BH present in the persisted manifest
    assert m["stress"]["low"]["n5"]["paired_loss"]["direction"] in ("D better","P better","no difference")
    assert "_bh" in m["stress"]
    assert m["nist"]["5"]["n_unique_splits"]==500 and m["nist"]["5"]["exact_500"]
