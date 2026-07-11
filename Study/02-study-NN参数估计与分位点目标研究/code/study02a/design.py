"""Frozen parameter designs and row allocation for Study/02 research A."""

from __future__ import annotations

from itertools import product
from typing import Any, Mapping

import numpy as np
import pandas as pd
from scipy.stats import qmc

from studies.common.sample import generate_sample

from .config import FrozenConfig


def _role_seed(role: str, config: FrozenConfig) -> int:
    seeds = config.protocol["seeds"]
    if role in seeds["design"]:
        return int(seeds["design"][role])
    if role in seeds["module_test_design"]:
        return int(seeds["module_test_design"][role])
    raise ValueError(f"Unknown design role: {role}")


def _range_spec(layer: str, config: FrozenConfig) -> tuple[float, float, float, float, float, float]:
    parameterization = config.protocol["parameterization"]
    if layer == "core":
        spec = parameterization["core"]
        return (
            float(spec["beta"]["min"]), float(spec["beta"]["max"]),
            float(spec["eta"]["min"]), float(spec["eta"]["max"]),
            float(spec["rho"]["min"]), float(spec["rho"]["max"]),
        )

    stress_key = layer.replace("-", "_")
    stress = parameterization["stress_layers"].get(stress_key)
    if stress is not None:
        return (*map(float, stress["beta"]), *map(float, stress["eta"]), *map(float, stress["rho"]))

    distribution = parameterization["training_distributions"].get(layer)
    if distribution and isinstance(distribution.get("beta"), dict):
        return (
            float(distribution["beta"]["min"]), float(distribution["beta"]["max"]),
            float(distribution["eta"]["min"]), float(distribution["eta"]["max"]),
            float(distribution["rho"]["min"]), float(distribution["rho"]["max"]),
        )
    raise ValueError(f"Unknown continuous parameter layer: {layer}")


def generate_parameter_points(
    role: str,
    layer: str,
    count: int,
    config: FrozenConfig,
) -> pd.DataFrame:
    if count <= 0:
        raise ValueError("count must be positive")
    beta_min, beta_max, eta_min, eta_max, rho_min, rho_max = _range_spec(layer, config)
    exponent = int(np.ceil(np.log2(count)))
    raw = qmc.Sobol(d=3, scramble=True, seed=_role_seed(role, config)).random_base2(exponent)[:count]
    beta = np.exp(np.log(beta_min) + raw[:, 0] * np.log(beta_max / beta_min))
    eta = np.exp(np.log(eta_min) + raw[:, 1] * np.log(eta_max / eta_min))
    rho = rho_min + raw[:, 2] * (rho_max - rho_min)
    return pd.DataFrame({
        "point_id": [f"{role}:{layer}:{i:07d}" for i in range(count)],
        "beta": beta,
        "eta": eta,
        "rho": rho,
        "gamma": rho * eta,
    })


def _legacy_parameter_cells(config: FrozenConfig) -> list[dict[str, Any]]:
    grid = config.protocol["parameterization"]["training_distributions"]["legacy_grid"]
    cells = []
    for index, (beta, eta, gamma) in enumerate(product(grid["beta"], grid["eta"], grid["gamma"])):
        cells.append({
            "parameter_cell_id": f"legacy-{index:03d}",
            "beta": float(beta),
            "eta": float(eta),
            "gamma": float(gamma),
            "rho": float(gamma) / float(eta),
        })
    return cells


def _expand_cells(cells: list[dict[str, Any]], count: int) -> pd.DataFrame:
    if count < 0:
        raise ValueError("count cannot be negative")
    if not cells and count:
        raise ValueError("cannot allocate rows without cells")
    quotient, remainder = divmod(count, len(cells)) if cells else (0, 0)
    rows: list[dict[str, Any]] = []
    for index, cell in enumerate(cells):
        repeats = quotient + (1 if index < remainder else 0)
        for repeat_id in range(repeats):
            rows.append({**cell, "repeat_id": repeat_id})
    return pd.DataFrame(rows)


def allocate_historical_rows(role: str, count: int, config: FrozenConfig) -> pd.DataFrame:
    if role not in {"training", "validation"}:
        raise ValueError("historical rows support training or validation roles")
    wants_validation = role == "validation"
    parameter_cells = [
        cell for index, cell in enumerate(_legacy_parameter_cells(config))
        if (index % 5 == 0) == wants_validation
    ]
    cells: list[dict[str, Any]] = []
    for cell in parameter_cells:
        for n in config.protocol["sample_sizes"]["core"]:
            cells.append({**cell, "n": int(n), "cell_id": f"{cell['parameter_cell_id']}:n{n}"})
    return _expand_cells(cells, count)


def allocate_training_rows(
    distribution: str,
    n_mode: str,
    count: int,
    config: FrozenConfig,
    *,
    fixed_n: int | None = None,
) -> pd.DataFrame:
    if n_mode not in {"fixed_n", "shared_n"}:
        raise ValueError("n_mode must be fixed_n or shared_n")
    core_n = [int(n) for n in config.protocol["sample_sizes"]["core"]]
    if n_mode == "fixed_n" and fixed_n not in core_n:
        raise ValueError(f"fixed_n must be one of {core_n}")

    if distribution == "legacy_grid":
        parameter_cells = _legacy_parameter_cells(config)
        n_values = [int(fixed_n)] if n_mode == "fixed_n" else core_n
        cells = [
            {**cell, "n": n, "cell_id": f"{cell['parameter_cell_id']}:n{n}"}
            for cell in parameter_cells
            for n in n_values
        ]
        return _expand_cells(cells, count)

    points = generate_parameter_points("training", distribution, count, config)
    points["parameter_cell_id"] = points["point_id"]
    if n_mode == "fixed_n":
        points["n"] = int(fixed_n)
    else:
        points["n"] = [core_n[index % len(core_n)] for index in range(count)]
    points["cell_id"] = points["point_id"] + ":n" + points["n"].astype(str)
    points["repeat_id"] = 0
    return points


def generate_lifetime_sample(row: Mapping[str, Any], namespace: int) -> np.ndarray:
    return generate_sample(
        float(row["beta"]),
        float(row["eta"]),
        float(row["gamma"]),
        int(row["n"]),
        int(row["repeat_id"]),
        seed=int(namespace),
    )
