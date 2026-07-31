import importlib.util
import gzip
import json
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).with_name("E2-comparison-generalization.py")
SPEC = importlib.util.spec_from_file_location("e2", SCRIPT)
E2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(E2)
CONFIG = json.loads((SCRIPT.parent.parent / "configs" / "E2-comparison-generalization.json").read_text(encoding="utf-8"))


def test_parameter_points_are_deterministic_and_in_range():
    spec = CONFIG["layers"]["location_stress"]
    first = E2.parameter_points("x", spec, 8, 123)
    second = E2.parameter_points("x", spec, 8, 123)
    assert first == second
    assert all(spec["beta"][0] <= p["beta"] <= spec["beta"][1] for p in first)
    assert all(spec["eta"][0] <= p["eta"] <= spec["eta"][1] for p in first)
    assert all(np.isclose(p["gamma"], p["rho"] * p["eta"]) for p in first)


def test_sample_build_is_deterministic_and_legal_truth():
    rows, samples = E2.build_samples("core", CONFIG["layers"]["core"], [5, 7], 3, 2, 4, 5)
    rows2, samples2 = E2.build_samples("core", CONFIG["layers"]["core"], [5, 7], 3, 2, 4, 5)
    assert rows == rows2 and len(rows) == 12
    assert all(np.array_equal(a, b) for a, b in zip(samples, samples2))
    assert all(row["gamma"] < sample.min() for row, sample in zip(rows, samples))


def test_row_metrics_penalizes_illegal():
    base = {"legal": False, "beta": 2.0, "eta": 3.0, "gamma": 1.0,
            "beta_hat": np.nan, "eta_hat": np.nan, "gamma_hat": np.nan}
    result = E2.row_metrics(base, 10.0)
    assert result["row_loss"] == 100.0
    assert result["e_beta"] == result["e_eta"] == result["e_gamma"] == 10.0


def test_plan_cohort_is_exact():
    fixed, shared = E2.load_plan_rows(Path(CONFIG["source_run"]), CONFIG)
    assert len(fixed) == 50 and len(shared) == 10
    assert {row["fixed_n"] for row in fixed} == {5, 7, 10, 15, 20}
    assert {row["seed"] for row in shared} == set(range(420101, 420111))


def test_paired_comparison_detects_clear_nn_gain():
    nn = []
    traditional = []
    for point in ("p0", "p1", "p2"):
        for seed in (1, 2):
            nn.append({
                "point_id": point, "seed": seed, "row_loss": 0.25,
                "e_beta": 0.5, "e_eta": 0.5, "e_gamma": 0.5, "legal": True,
            })
        traditional.append({
            "point_id": point, "seed": 0, "row_loss": 1.0,
            "e_beta": 1.0, "e_eta": 1.0, "e_gamma": 1.0, "legal": True,
        })
    result = E2.paired_comparison(nn, traditional, n_boot=50, seed=7)
    assert result["l_param_relative_improvement"]["effect"] == 0.5
    assert result["global_better"] is True


def test_source_writer_accepts_union_of_record_fields(tmp_path):
    target = tmp_path / "source.csv.gz"
    E2.write_source(target, [{"a": 1}, {"a": 2, "b": 3}])
    with gzip.open(target, "rt", encoding="utf-8") as handle:
        assert handle.readline().strip() == "a,b"


def test_seed_stability_uses_same_scale_variance_and_rank():
    records = []
    for point, base in (("p0", 0.1), ("p1", 0.4), ("p2", 0.9)):
        for seed, delta in ((1, 0.0), (2, 0.01)):
            records.append({"n": 5, "point_id": point, "seed": seed, "row_loss": (base + delta) ** 2})
    result = E2.seed_stability(records)[0]
    assert 0.0 <= result["seed_variance_share"] < 0.01
    assert result["point_difficulty_rank_spearman_min"] == 1.0
