import json
from pathlib import Path

import numpy as np

from . import low_domain_run as RUN


def test_low_domain_config_is_dense_and_bounded():
    cfg = json.loads(RUN.CONFIG_PATH.read_text(encoding="utf-8"))
    domain = cfg["research_domain"]
    assert domain["beta_grid"] == [1.0, 1.25, 1.5, 1.75, 2.0]
    assert domain["gamma_over_eta_grid"] == [0.05, 0.10, 0.15, 0.20, 0.25]
    assert cfg["training"]["max_epochs"] == 600
    assert cfg["training"]["patience"] == 60
    assert cfg["training"]["routes"] == ["P", "Q", "QCP"]


def test_small_master_uses_new_domain_and_namespace():
    cfg = RUN._cfg()
    master = RUN.build_master(cfg, repeats=1)
    domain = cfg["research_domain"]
    expected = (len(domain["beta_grid"]) * len(domain["gamma_over_eta_grid"])
                * len(domain["n_grid"]))
    assert len(master.keys) == expected
    assert np.array_equal(np.unique(master.keys[:, 0]), np.asarray(domain["beta_grid"]))
    assert np.allclose(np.unique(master.keys[:, 1]),
                       np.asarray(domain["gamma_over_eta_grid"]))
    assert Path(RUN.PROTOCOL_PATH).exists()


def test_paired_bootstrap_preserves_clear_direction():
    comparator = np.full((2, 3, 4), 0.04, dtype=np.float64)
    target = np.full((2, 3, 4), 0.0324, dtype=np.float64)
    result = RUN.paired_crossed_bootstrap(
        target, comparator, replicates=1000, seed=7)
    assert result["mse_difference_95ci"][1] < 0.0
    assert np.allclose(result["relative_rmsre_improvement_95ci"], [0.1, 0.1])
