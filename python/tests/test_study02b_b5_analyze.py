"""Tests for B5 v4: split-conformal quantile, CSV schema, NIST split count."""
import sys, csv
from pathlib import Path
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in [str(REPO_ROOT/"Study/02-study-NN参数估计与分位点目标研究/code"),str(REPO_ROOT/"python")]:
    if p not in sys.path: sys.path.insert(0, p)

from study02b.analyze_b5 import split_conformal_quantile, _N_VALUES


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
