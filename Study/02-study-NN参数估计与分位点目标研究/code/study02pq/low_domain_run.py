"""Train P, Q and QCP on the current low-beta/low-gamma research domain."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np

from . import config as CFG
from . import data as DATA
from . import training as TR


ROOT = Path(CFG.STUDY02_ROOT)
CONFIG_PATH = ROOT / "configs" / "qcp-low-domain-v1.json"
PROTOCOL_PATH = ROOT / "protocols" / "21-低形状低位置比研究域合同.md"


def _cfg() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() in {".json", ".csv", ".py", ".md", ".txt"}:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _json(path: Path, value: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def _paths(cfg: dict) -> tuple[Path, Path, Path, Path]:
    out = ROOT / cfg["artifact_namespace"]
    return out, out / "evidence", out / "fit_metadata", out / "analysis"


def _fit_name(n: int, fold: int, seed: int, route: str) -> str:
    return f"n{n}_f{fold}_s{seed}_r{route}"


def build_master(cfg: dict, *, repeats: int | None = None) -> DATA.Master:
    domain = cfg["research_domain"]
    eta = float(domain["eta"])
    gamma = [eta * float(x) for x in domain["gamma_over_eta_grid"]]
    return DATA.build_master(
        beta_grid=list(map(float, domain["beta_grid"])),
        gamma_grid=gamma,
        n_grid=list(map(int, domain["n_grid"])),
        repeats=int(repeats if repeats is not None else domain["repeats_per_combo"]),
        seed_namespace=cfg["data"]["seed_namespace"],
    )


def _save(result: dict, cfg: dict) -> None:
    _, evidence_dir, metadata_dir, _ = _paths(cfg)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    meta = dict(result["meta"])
    fit = meta["fit_id"]
    pred = result["predictions"]
    keys = pred["keys"]
    evidence_path = evidence_dir / f"{fit}.npz"
    np.savez_compressed(
        evidence_path,
        keys_beta=np.ascontiguousarray(keys[:, 0], dtype=np.float64),
        keys_gamma_over_eta=np.ascontiguousarray(keys[:, 1], dtype=np.float64),
        keys_n=np.ascontiguousarray(keys[:, 2], dtype=np.int32),
        keys_repeat_id=np.ascontiguousarray(keys[:, 3], dtype=np.int32),
        beta_hat=np.asarray(pred["beta_hat"], dtype=np.float32),
        eta_hat=np.asarray(pred["eta_hat"], dtype=np.float32),
        gamma_hat=np.asarray(pred["gamma_hat"], dtype=np.float32),
        x95_hat=np.asarray(pred["x95_hat"], dtype=np.float32),
        x95_true=np.asarray(pred["x95_true"], dtype=np.float32),
        min_x=np.asarray(pred["min_x"], dtype=np.float32),
        rel_err=np.asarray(pred["rel_err"], dtype=np.float32),
        rel_err_sq=np.asarray(pred["rel_err_sq"], dtype=np.float32),
    )
    meta.update({
        "research_domain_protocol": cfg["protocol_id"],
        "data_seed_namespace": cfg["data"]["seed_namespace"],
        "evidence_sha256": _sha(evidence_path),
    })
    _json(metadata_dir / f"{fit}.json", meta)


def _complete(cfg: dict, fit: str) -> bool:
    _, evidence_dir, metadata_dir, _ = _paths(cfg)
    ep = evidence_dir / f"{fit}.npz"
    mp = metadata_dir / f"{fit}.json"
    if not ep.exists() or not mp.exists():
        return False
    meta = json.loads(mp.read_text(encoding="utf-8"))
    return meta.get("evidence_sha256") == _sha(ep)


def _meta(cfg: dict, fit: str) -> dict:
    _, _, metadata_dir, _ = _paths(cfg)
    return json.loads((metadata_dir / f"{fit}.json").read_text(encoding="utf-8"))


def _validate_pair(left: dict, right: dict) -> None:
    for field in ("n", "fold", "seed", "init_param_sha", "batch_order_sha",
                  "network_sha", "scaler_sha", "train_rows_sha", "val_rows_sha",
                  "test_rows_sha", "split_strategy"):
        if left.get(field) != right.get(field):
            raise RuntimeError(f"pairing mismatch for {field}")


def run(cfg: dict, *, selected_seeds: set[int] | None = None,
        selected_ns: set[int] | None = None,
        selected_folds: set[int] | None = None,
        resume: bool = True) -> None:
    master = build_master(cfg)
    domain = cfg["research_domain"]
    budget = cfg["training"]
    constraint = cfg["qcp_constraint"]
    for seed in map(int, budget["seeds"]):
        if selected_seeds is not None and seed not in selected_seeds:
            continue
        for n in map(int, domain["n_grid"]):
            if selected_ns is not None and n not in selected_ns:
                continue
            for fold in map(int, budget["folds_1based"]):
                if selected_folds is not None and fold not in selected_folds:
                    continue
                for route in ("P", "Q"):
                    fit = _fit_name(n, fold, seed, route)
                    if resume and _complete(cfg, fit):
                        print(f"[resume] {fit}", flush=True)
                        continue
                    result = TR.train_one_fit(
                        n, fold - 1, seed, route, master,
                        max_epochs=int(budget["max_epochs"]),
                        patience=int(budget["patience"]),
                        split_strategy="repeat_stratified",
                        evaluate_test=True,
                    )
                    _save(result, cfg)
                    print(f"[fit] {fit}: rrmse={result['meta']['rrmse_x95']:.6f}",
                          flush=True)

                qcp_fit = _fit_name(n, fold, seed, "QCP")
                if not (resume and _complete(cfg, qcp_fit)):
                    p_meta = _meta(cfg, _fit_name(n, fold, seed, "P"))
                    p_limit = float(constraint["slack_multiplier"]) * \
                        float(p_meta["best_val_loss"])
                    result = TR.train_one_fit(
                        n, fold - 1, seed, "QCP", master,
                        max_epochs=int(budget["max_epochs"]),
                        patience=int(budget["patience"]),
                        split_strategy="repeat_stratified",
                        p_constraint_limit=p_limit,
                        constraint_rho=float(constraint["rho"]),
                        evaluate_test=True,
                    )
                    if not result["meta"].get("constraint_feasible_at_checkpoint", False):
                        raise RuntimeError(f"infeasible QCP checkpoint: {qcp_fit}")
                    _validate_pair(result["meta"], p_meta)
                    _validate_pair(result["meta"],
                                   _meta(cfg, _fit_name(n, fold, seed, "Q")))
                    _save(result, cfg)
                    print(f"[fit] {qcp_fit}: rrmse={result['meta']['rrmse_x95']:.6f}",
                          flush=True)
                else:
                    print(f"[resume] {qcp_fit}", flush=True)


def _load_evidence(cfg: dict, fit: str) -> dict[str, np.ndarray]:
    _, evidence_dir, _, _ = _paths(cfg)
    with np.load(evidence_dir / f"{fit}.npz") as z:
        return {name: np.asarray(z[name]) for name in z.files}


def paired_crossed_bootstrap(target: np.ndarray, comparator: np.ndarray, *,
                             replicates: int, seed: int) -> dict:
    """Paired bootstrap over folds within n and training seeds globally."""
    if target.shape != comparator.shape or target.ndim != 3:
        raise ValueError("target and comparator must share [n, fold, seed] shape")
    n_count, fold_count, seed_count = target.shape
    rng = np.random.default_rng(seed)
    mse_difference = np.empty(replicates, dtype=np.float64)
    relative_improvement = np.empty(replicates, dtype=np.float64)
    chunk = 2000
    for start in range(0, replicates, chunk):
        size = min(chunk, replicates - start)
        seed_idx = rng.integers(0, seed_count, size=(size, seed_count))
        target_mean = np.zeros(size, dtype=np.float64)
        comparator_mean = np.zeros(size, dtype=np.float64)
        for ni in range(n_count):
            fold_idx = rng.integers(0, fold_count, size=(size, fold_count))
            target_sample = target[ni][fold_idx[:, :, None], seed_idx[:, None, :]]
            comparator_sample = comparator[ni][fold_idx[:, :, None],
                                                seed_idx[:, None, :]]
            target_mean += target_sample.mean(axis=(1, 2)) / n_count
            comparator_mean += comparator_sample.mean(axis=(1, 2)) / n_count
        mse_difference[start:start + size] = target_mean - comparator_mean
        relative_improvement[start:start + size] = (
            np.sqrt(comparator_mean) - np.sqrt(target_mean)
        ) / np.sqrt(comparator_mean)
    return {
        "mse_difference_95ci":
            np.quantile(mse_difference, [0.025, 0.975]).tolist(),
        "relative_rmsre_improvement_95ci":
            np.quantile(relative_improvement, [0.025, 0.975]).tolist(),
    }


def analyze(cfg: dict) -> dict:
    routes = ("P", "Q", "QCP")
    domain = cfg["research_domain"]
    training = cfg["training"]
    all_rel = {route: [] for route in routes}
    cell_rel: dict[tuple, list[float]] = defaultdict(list)
    model_rows = []
    for n in map(int, domain["n_grid"]):
        for fold in map(int, training["folds_1based"]):
            for seed in map(int, training["seeds"]):
                loaded = {r: _load_evidence(cfg, _fit_name(n, fold, seed, r))
                          for r in routes}
                key_names = ("keys_beta", "keys_gamma_over_eta", "keys_n",
                             "keys_repeat_id")
                for name in key_names:
                    if any(not np.array_equal(loaded["P"][name], loaded[r][name])
                           for r in ("Q", "QCP")):
                        raise RuntimeError(f"held-out key mismatch: {n=} {fold=} {seed=}")
                row = {"n": n, "fold": fold, "seed": seed}
                for route in routes:
                    rel = np.asarray(loaded[route]["rel_err"], dtype=np.float64)
                    if not np.isfinite(rel).all():
                        raise RuntimeError(f"nonfinite evidence: {route} {n=} {fold=} {seed=}")
                    all_rel[route].append(rel)
                    row[f"mse_{route.lower()}"] = float(np.mean(rel ** 2))
                    for b, g, e in zip(loaded[route]["keys_beta"],
                                       loaded[route]["keys_gamma_over_eta"], rel):
                        cell_rel[(route, n, float(b), float(g))].append(float(e))
                model_rows.append(row)

    diagnostics = {}
    for route in routes:
        rel = np.concatenate(all_rel[route])
        abs_rel = np.abs(rel)
        cell_means = []
        cell_vars = []
        for key, values in cell_rel.items():
            if key[0] != route:
                continue
            x = np.asarray(values, dtype=np.float64)
            cell_means.append(float(x.mean()))
            cell_vars.append(float(np.mean((x - x.mean()) ** 2)))
        diagnostics[route] = {
            "rmsre": float(np.sqrt(np.mean(rel ** 2))),
            "signed_relative_bias": float(rel.mean()),
            "mae": float(abs_rel.mean()),
            "q95_absolute_relative_error": float(np.quantile(abs_rel, 0.95)),
            "rms_truth_cell_bias": float(np.sqrt(np.mean(np.square(cell_means)))),
            "within_truth_cell_sd": float(np.sqrt(np.mean(cell_vars))),
        }
    ns = list(map(int, domain["n_grid"]))
    folds = list(map(int, training["folds_1based"]))
    seeds = list(map(int, training["seeds"]))
    cubes = {route: np.empty((len(ns), len(folds), len(seeds)), dtype=np.float64)
             for route in routes}
    for row in model_rows:
        ni = ns.index(int(row["n"]))
        fi = folds.index(int(row["fold"]))
        si = seeds.index(int(row["seed"]))
        for route in routes:
            cubes[route][ni, fi, si] = float(row[f"mse_{route.lower()}"])

    contrasts = {}
    replicates = int(cfg["evaluation"]["bootstrap_replicates"])
    bootstrap_seed = int(cfg["evaluation"]["bootstrap_seed"])
    for offset, (target, comparator) in enumerate(
            (("Q", "P"), ("QCP", "Q"), ("QCP", "P"))):
        t = diagnostics[target]["rmsre"]
        c = diagnostics[comparator]["rmsre"]
        diff = cubes[target] - cubes[comparator]
        boot = paired_crossed_bootstrap(
            cubes[target], cubes[comparator], replicates=replicates,
            seed=bootstrap_seed + offset)
        seed_means = diff.mean(axis=(0, 1))
        contrasts[f"{target}_vs_{comparator}"] = {
            "absolute_rmsre_change": t - c,
            "relative_rmsre_improvement": (c - t) / c,
            **boot,
            "favorable_model_cells": int(np.sum(diff < 0.0)),
            "total_model_cells": int(diff.size),
            "favorable_seeds": int(np.sum(seed_means < 0.0)),
            "total_seeds": int(seed_means.size),
        }
    summary = {
        "protocol_id": cfg["protocol_id"],
        "status": "COMPLETE",
        "research_domain": domain,
        "diagnostics": diagnostics,
        "contrasts": contrasts,
    }
    out, _, _, analysis_dir = _paths(cfg)
    analysis_dir.mkdir(parents=True, exist_ok=True)
    _json(analysis_dir / "summary.json", summary)
    with (analysis_dir / "model_cells.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(model_rows[0]))
        writer.writeheader()
        writer.writerows(model_rows)
    manifest = {
        "protocol_id": cfg["protocol_id"],
        "status": "COMPLETE",
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=CFG.PROJECT_ROOT, text=True).strip(),
        "config_sha256": _sha(CONFIG_PATH),
        "protocol_sha256": _sha(PROTOCOL_PATH),
        "run_code_sha256": _sha(Path(__file__)),
        "fit_count": len(model_rows) * len(routes),
        "artifact_namespace": cfg["artifact_namespace"],
    }
    _json(out / "manifest.json", manifest)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="append", type=int)
    parser.add_argument("--n", action="append", type=int)
    parser.add_argument("--fold", action="append", type=int)
    parser.add_argument("--analyze-only", action="store_true")
    parser.add_argument("--run-only", action="store_true")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    if CFG.PROTOCOL_ID != "iid-v1":
        raise RuntimeError("set PQ_PROTOCOL=iid-v1 for the low-domain run")
    cfg = _cfg()
    selected = set(args.seed) if args.seed else None
    frozen = set(map(int, cfg["training"]["seeds"]))
    if selected is not None and not selected <= frozen:
        raise ValueError(f"seed outside design: {sorted(selected - frozen)}")
    selected_ns = set(args.n) if args.n else None
    frozen_ns = set(map(int, cfg["research_domain"]["n_grid"]))
    if selected_ns is not None and not selected_ns <= frozen_ns:
        raise ValueError(f"n outside design: {sorted(selected_ns - frozen_ns)}")
    selected_folds = set(args.fold) if args.fold else None
    frozen_folds = set(map(int, cfg["training"]["folds_1based"]))
    if selected_folds is not None and not selected_folds <= frozen_folds:
        raise ValueError(
            f"fold outside design: {sorted(selected_folds - frozen_folds)}")
    if not args.analyze_only:
        run(cfg, selected_seeds=selected, selected_ns=selected_ns,
            selected_folds=selected_folds, resume=not args.no_resume)
    if not args.run_only:
        summary = analyze(cfg)
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
