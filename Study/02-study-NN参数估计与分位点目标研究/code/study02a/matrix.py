"""Deterministic expansion of the frozen G3 training-fit matrix."""

from __future__ import annotations

from itertools import product
from typing import Any

import pandas as pd

from .config import FrozenConfig


def expand_module_matrix(config: FrozenConfig) -> pd.DataFrame:
    protocol = config.protocol
    search = config.search
    screening = [int(seed) for seed in search["screening_seeds"]]
    formal = [int(seed) for seed in search["formal_seeds"]]
    core_n = [int(n) for n in protocol["sample_sizes"]["core"]]
    architecture_ids = [str(item["id"]) for item in search["mlp_stage1_architectures"]]
    optimizer_ids = [str(item["id"]) for item in search["stage2_rule"]["optimizer_candidates"]]
    rows: list[dict[str, Any]] = []

    def add(rule_id: str, module: str, route: str, n: int | str, loss: str, architecture: str,
            optimizer: str, training_size: int, seed: int, fit_kind: str) -> None:
        index = len(rows)
        rows.append({
            "fit_id": f"G3-fit-{index:04d}",
            "rule_id": rule_id,
            "module": module,
            "route": route,
            "n": n,
            "loss": loss,
            "architecture": architecture,
            "optimizer": optimizer,
            "training_size": int(training_size),
            "seed": int(seed),
            "fit_kind": fit_kind,
            "test_state": "sealed",
        })

    for route, seed in product(["H0_hsm", "H0_kde_scott1024", "H1"], formal):
        add("A-E1_historical", "A-E1", route, "shared", "raw_train_z_mse", "historical_128_64_32", "adam_historical", 7000, seed, "historical")

    controlled_routes = search["module_matrix_rules"]["A-E1_controlled"]["routes"]
    for route, n, seed in product(controlled_routes, core_n, screening):
        add("A-E1_controlled", "A-E1", route, n, "transformed_train_z_huber", "m05", "stage1", 100000, seed, "controlled")

    for route in ["F2", "V"]:
        _add_search_rows(add, "A-E1_optimized_supplement", "A-E1", route, 10, 100000, screening, architecture_ids, optimizer_ids)
        for n, seed in product(core_n, formal):
            add("A-E1_optimized_supplement", "A-E1", route, n, "selected:A-E1_loss", "selected:A-E1_architecture", "selected:A-E1_optimizer", 100000, seed, "winner_retrain")

    for loss, seed in product([item["id"] for item in search["losses"]], screening):
        add("A-E3_loss", "A-E3", "selected:F2_or_V", 10, loss, "m05", "stage1", 100000, seed, "loss_screen")

    _add_search_rows(add, "A-E3_architecture", "A-E3", "selected:F2_or_V", 10, 100000, screening, architecture_ids, optimizer_ids)

    for output_form, n, seed in product(["joint", "independent_capacity_matched"], core_n, formal):
        add("A-E3_joint_independent", "A-E3", f"selected:F2_or_V:{output_form}", n, "selected:A-E3_loss", "selected:A-E3_architecture", "selected:A-E3_optimizer", 100000, seed, "output_form")

    deep_ids = [str(item["id"]) for item in search["deepsets_stage1_architectures"]]
    _add_search_rows(add, "A-E3_fixed_shared", "A-E3", "S", "shared", 100000, screening, deep_ids, optimizer_ids)
    for seed in formal:
        add("A-E3_fixed_shared", "A-E3", "S", "shared", "selected:A-E3_loss", "selected:S_architecture", "selected:S_optimizer", 100000, seed, "shared_winner_retrain")

    for size, n, seed in product(protocol["training_sizes"], core_n, screening):
        add("A-E2_training_size", "A-E2", "selected:A-E3_baseline", n, "selected:A-E3_loss", "selected:A-E3_architecture", "selected:A-E3_optimizer", int(size), seed, "size_screen")
    for n, seed in product(core_n, formal):
        add("A-E2_training_size", "A-E2", "selected:A-E3_baseline", n, "selected:A-E3_loss", "selected:A-E3_architecture", "selected:A-E3_optimizer", -1, seed, "selected_size_retrain")

    distributions = ["legacy_grid", "core_continuous", "extended_wide"]
    for distribution, n, seed in product(distributions, core_n, screening):
        add("A-E2_distribution", "A-E2", f"selected:A-E3_baseline:{distribution}", n, "selected:A-E3_loss", "selected:A-E3_architecture", "selected:A-E3_optimizer", -1, seed, "distribution_screen")
    for n, seed in product(core_n, formal):
        add("A-E2_distribution", "A-E2", "selected:A-E2_distribution", n, "selected:A-E3_loss", "selected:A-E3_architecture", "selected:A-E3_optimizer", -1, seed, "selected_distribution_retrain")

    matrix = pd.DataFrame(rows)
    frozen_rules = set(search["module_matrix_rules"])
    if set(matrix["rule_id"]) != frozen_rules:
        raise ValueError("Expanded matrix does not cover exactly the frozen module rules")
    if len(matrix) > int(search["fit_caps"]["G3"]):
        raise ValueError("Expanded G3 matrix exceeds the frozen fit cap")
    return matrix


def _add_search_rows(add, rule_id, module, route, n, training_size, seeds, architecture_ids, optimizer_ids):
    for architecture, seed in product(architecture_ids, seeds):
        add(rule_id, module, route, n, "transformed_train_z_huber", architecture, "stage1", training_size, seed, "search_stage1")
    for top_slot, optimizer, seed in product(range(1, 5), optimizer_ids, seeds):
        add(rule_id, module, route, n, "transformed_train_z_huber", f"selected_top_{top_slot}", optimizer, training_size, seed, "search_stage2")
