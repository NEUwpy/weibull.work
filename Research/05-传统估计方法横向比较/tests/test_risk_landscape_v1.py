"""Independent artifact checks for risk_landscape_v1."""

import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts" / "risk_landscape_v1"
CODE = ROOT / "code" / "run_risk_landscape_v1.py"

spec = importlib.util.spec_from_file_location("risk_landscape_v1", CODE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def test_expected_artifacts_exist():
    expected = {
        "per_sample_losses.csv.gz",
        "method_summary.csv",
        "cell_summary.csv",
        "selector_summary.csv",
        "fold_choices.csv",
        "winner_stability.csv",
        "bootstrap_summary.csv",
        "subgroup_summary.csv",
        "scale_sensitivity.csv",
        "result.json",
        "manifest.json",
        "run_log.txt",
    }
    assert expected <= {p.name for p in ART.iterdir()}


def test_raw_identity_and_coverage():
    raw = pd.read_csv(ART / "per_sample_losses.csv.gz")
    assert len(raw) == 48_000 * 5
    assert raw[module.SAMPLE_KEYS].drop_duplicates().shape[0] == 48_000
    assert not raw.duplicated(module.SAMPLE_KEYS + ["method"]).any()
    assert set(raw["method"]) == set(module.ALL_METHODS)
    counts = raw.groupby(module.SAMPLE_KEYS)["method"].nunique()
    assert (counts == 5).all()
    assert np.isfinite(raw["loss_primary"]).all()


def test_method_summary_independent_recompute():
    raw = pd.read_csv(ART / "per_sample_losses.csv.gz")
    reported = pd.read_csv(ART / "method_summary.csv").set_index("method")
    for method, group in raw.groupby("method"):
        j1 = math.sqrt(float(group["loss_primary"].mean()))
        assert abs(j1 - reported.loc[method, "J1_primary"]) < 1e-12
        assert int(group["failed"].sum()) == int(reported.loc[method, "failure_count"])


def test_primary_failure_gate_is_computable():
    reported = pd.read_csv(ART / "method_summary.csv").set_index("method")
    assert set(module.PRIMARY_METHODS) <= set(reported.index)
    assert reported.loc[module.PRIMARY_METHODS, "failure_rate"].notna().all()


def test_crossfit_coverage_and_no_test_fold_in_training_decision():
    raw = pd.read_csv(ART / "per_sample_losses.csv.gz")
    evaluations, choices = module.build_crossfit(raw)
    for selector in list(module.SELECTORS) + ["sample_hindsight"]:
        selected = evaluations[evaluations["selector"] == selector]
        assert len(selected) == 48_000
        assert selected[module.SAMPLE_KEYS].drop_duplicates().shape[0] == 48_000
    fixed = choices[choices["selector"] == "Fixed"]
    assert set(fixed["fold"]) == set(range(5))
    cell = choices[choices["selector"] == "cell"]
    assert len(cell) == 160 * 5
    assert not cell.duplicated(module.CELL_KEYS + ["fold"]).any()


def test_selector_summary_independent_recompute():
    raw = pd.read_csv(ART / "per_sample_losses.csv.gz")
    evaluations, _ = module.build_crossfit(raw)
    reported = pd.read_csv(ART / "selector_summary.csv").set_index("selector")
    for selector, group in evaluations.groupby("selector"):
        j1 = math.sqrt(float(group["loss_primary"].mean()))
        assert abs(j1 - reported.loc[selector, "J1"]) < 1e-12


def test_bootstrap_contract():
    boot = pd.read_csv(ART / "bootstrap_summary.csv").set_index("selector")
    assert set(module.SELECTORS) | {"sample_hindsight"} == set(boot.index)
    assert (boot["n_cells"] == 160).all()
    assert (boot["n_bootstrap"] == 5000).all()
    assert (boot["ci95_low"] <= boot["relative_J1_improvement_point"]).all()
    assert (boot["relative_J1_improvement_point"] <= boot["ci95_high"]).all()


def test_decision_recomputes_from_reported_tables():
    summary = pd.read_csv(ART / "method_summary.csv")
    selectors = pd.read_csv(ART / "selector_summary.csv")
    bootstrap = pd.read_csv(ART / "bootstrap_summary.csv")
    stability = pd.read_csv(ART / "winner_stability.csv")
    subgroups = pd.read_csv(ART / "subgroup_summary.csv")
    expected = module.make_decision(summary, selectors, bootstrap, stability, subgroups)
    result = json.loads((ART / "result.json").read_text(encoding="utf-8"))
    actual = result["decision"]
    assert expected["decision"] == actual["decision"]
    assert expected["criteria"] == actual["criteria"]
    assert expected["positive_n_groups"] == actual["positive_n_groups"]
    assert expected["stable_region_counts"] == actual["stable_region_counts"]
    assert expected["methods_with_replicated_regions"] == actual["methods_with_replicated_regions"]
    assert np.isclose(expected["cell_relative_J1_improvement"], actual["cell_relative_J1_improvement"])
    assert np.allclose(expected["cell_bootstrap_ci95"], actual["cell_bootstrap_ci95"])


def test_manifest_hashes():
    manifest = json.loads((ART / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["run_id"] == "risk_landscape_v1"
    for name, expected in manifest["output_hashes"].items():
        path = ART / name
        assert path.exists(), name
        assert sha256(path) == expected, name
