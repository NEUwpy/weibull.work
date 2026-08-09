"""Study02 S5B major-revision experiment.

Narrow additions only:
1) seven new seeds for the frozen-grid iid P_equal/Q_param contrast;
2) continuous-within-Study01-range P_equal/Q_param/Q_direct validation;
3) crossed fold x seed inference for relative rRMSE improvement.

Existing S1-S4 artifacts are read-only.  New files live below
``artifacts/pq_s5b_revision`` and are resumable per fit.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from scipy.stats import qmc

from . import config as CFG
from . import data as DATA
from . import losses as LOSS
from . import model as MODEL
from . import training as TR

torch.set_num_threads(1)

ROOT = Path(CFG.STUDY02_ROOT)
PROTOCOL_PATH = ROOT / "configs" / "pq-s5b-revision-v1.json"
ARTIFACT_ROOT = ROOT / "artifacts" / "pq_s5b_revision"
OLD_IID = ROOT / "artifacts" / "pq_iid_main"


def load_protocol() -> dict:
    with PROTOCOL_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=CFG.PROJECT_ROOT, text=True).strip()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path, canonical_text: bool = False) -> str:
    value = path.read_bytes()
    if canonical_text:
        value = value.replace(b"\r\n", b"\n")
    return _sha_bytes(value)


def build_continuous_master(points_per_n: int | None = None) -> DATA.Master:
    """Construct the frozen continuous Sobol design inside Study01 bounds."""
    cfg = load_protocol()
    design = cfg["continuous_within_range"]
    domain = cfg["study01_domain"]
    count = int(points_per_n or design["points_per_n"])
    if count <= 0:
        raise ValueError("points_per_n must be positive")

    m = int(np.ceil(np.log2(count)))
    raw = qmc.Sobol(d=2, scramble=True, seed=int(design["sobol_seed"])).random_base2(m)[:count]
    # Randomize the Sobol ordering before point_id % 5 split, while retaining exact balance.
    order = np.random.default_rng(int(design["sobol_seed"]) + 1).permutation(count)
    raw = raw[order]
    beta_lo, beta_hi = map(float, domain["beta_bounds"])
    goe_lo, goe_hi = map(float, domain["gamma_over_eta_bounds"])
    beta_points = beta_lo + (beta_hi - beta_lo) * raw[:, 0]
    goe_points = goe_lo + (goe_hi - goe_lo) * raw[:, 1]
    eta = float(domain["eta"])
    namespace = design["sample_namespace"]

    keys, samples, params, x_r = [], [], [], []
    R = float(cfg["target"]["reliability"])
    for n in map(int, domain["n_grid"]):
        for point_id, (beta, goe) in enumerate(zip(beta_points, goe_points)):
            gamma = eta * float(goe)
            sample = DATA.generate_sample(float(beta), eta, gamma, n, point_id,
                                          seed=namespace)
            keys.append((float(beta), float(goe), float(n), int(point_id)))
            samples.append(np.asarray(sample, dtype=np.float64))
            params.append((float(beta), eta, gamma))
            x_r.append(gamma + eta * (-np.log(R)) ** (1.0 / float(beta)))

    x_obj = np.empty(len(samples), dtype=object)
    for i, sample in enumerate(samples):
        x_obj[i] = sample
    return DATA.Master(
        keys=np.asarray(keys, dtype=np.float64),
        X=x_obj,
        true_params=np.asarray(params, dtype=np.float64),
        x0_95=np.asarray(x_r, dtype=np.float64),
    )


def _fit_name(n: int, fold_idx: int, seed: int, route: str) -> str:
    return f"n{n}_f{fold_idx + 1}_s{seed}_r{route}"


def _contract_dir(contract: str) -> Path:
    if contract not in {"grid_extra", "continuous"}:
        raise ValueError(contract)
    return ARTIFACT_ROOT / contract


def _paths(contract: str, fit: str) -> tuple[Path, Path]:
    base = _contract_dir(contract)
    return base / "fit_metadata" / f"{fit}.json", base / "evidence" / f"{fit}.npz"


def _ensure_contract_dirs(contract: str) -> None:
    meta, evidence = _paths(contract, "placeholder")
    meta.parent.mkdir(parents=True, exist_ok=True)
    evidence.parent.mkdir(parents=True, exist_ok=True)


def fit_complete(contract: str, fit: str) -> bool:
    meta_path, evidence_path = _paths(contract, fit)
    if not meta_path.is_file() or not evidence_path.is_file():
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        with np.load(evidence_path) as ev:
            return (meta.get("fit_id") == fit and len(ev["rel_err_sq"]) == meta["n_test"]
                    and np.isfinite(ev["rel_err_sq"]).all())
    except Exception:
        return False


def _save_result(contract: str, fit: str, result: dict) -> None:
    _ensure_contract_dirs(contract)
    meta_path, evidence_path = _paths(contract, fit)
    p = result["predictions"]
    keys = np.asarray(p["keys"], dtype=np.float64)
    arrays = {
        "keys_beta": keys[:, 0].astype(np.float64),
        "keys_gamma_over_eta": keys[:, 1].astype(np.float64),
        "keys_n": keys[:, 2].astype(np.int32),
        "keys_point_or_repeat_id": keys[:, 3].astype(np.int32),
        "xR_hat": np.asarray(p["x95_hat"], dtype=np.float32),
        "xR_true": np.asarray(p["x95_true"], dtype=np.float32),
        "rel_err": np.asarray(p["rel_err"], dtype=np.float32),
        "rel_err_sq": np.asarray(p["rel_err_sq"], dtype=np.float32),
    }
    for key in ("beta_hat", "eta_hat", "gamma_hat", "min_x"):
        if key in p:
            arrays[key] = np.asarray(p[key], dtype=np.float32)
    np.savez_compressed(evidence_path, **arrays)
    meta = dict(result["meta"])
    meta.update({
        "fit_id": fit,
        "contract": contract,
        "evidence_sha256": _sha_file(evidence_path),
        "runtime_git_sha": _head(),
        "protocol_sha256": _sha_file(PROTOCOL_PATH, canonical_text=True),
    })
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8", newline="\n")


def _direct_scale(X: np.ndarray) -> np.ndarray:
    scale = np.std(np.asarray(X, dtype=np.float64), axis=1, ddof=0)
    if np.any(~np.isfinite(scale)) or np.any(scale <= 0):
        raise RuntimeError("Q_direct encountered a non-positive sample scale")
    return scale


def train_one_direct_fit(n: int, fold_idx: int, seed: int, master: DATA.Master,
                         max_epochs: int | None = None,
                         patience: int | None = None) -> dict:
    """Train the same hidden trunk with a one-scalar direct x_R head."""
    train_rows, val_rows, test_rows = DATA.split_continuous_fold(master, n, fold_idx)
    X_tr, _, y_tr = DATA.make_arrays(master, train_rows)
    X_va, _, y_va = DATA.make_arrays(master, val_rows)
    X_te, _, y_te = DATA.make_arrays(master, test_rows)
    min_tr, min_va, min_te = (DATA.sample_min(master, rows)
                              for rows in (train_rows, val_rows, test_rows))
    s_tr, s_va, s_te = map(_direct_scale, (X_tr, X_va, X_te))
    scaler = DATA.PerPositionScaler().fit(X_tr)
    X_tr = scaler.transform(X_tr)
    X_va = scaler.transform(X_va)
    X_te = scaler.transform(X_te)

    torch.manual_seed(seed)
    generator = torch.Generator().manual_seed(seed)
    model = MODEL.build_scalar_model(n, seed)
    init_sha = MODEL.params_sha(model)
    trunk_sha = MODEL.trunk_params_sha(model)
    optimizer = torch.optim.Adam(model.parameters(), lr=CFG.LR,
                                 weight_decay=CFG.WEIGHT_DECAY)
    max_epochs = int(max_epochs or CFG.MAX_EPOCHS)
    patience = int(patience or CFG.PATIENCE)

    Xtr = TR._tensor(X_tr); Xva = TR._tensor(X_va); Xte = TR._tensor(X_te)
    ytr = TR._tensor(y_tr); yva = TR._tensor(y_va)
    mtr = TR._tensor(min_tr); mva = TR._tensor(min_va); mte = TR._tensor(min_te)
    str_ = TR._tensor(s_tr); sva = TR._tensor(s_va); ste = TR._tensor(s_te)

    perm = TR._epoch_perm(len(X_tr), generator)
    batch_sha = DATA.sha_bytes(perm.astype(np.int64).tobytes())
    best_val, best_epoch, stale, best_state = float("inf"), 0, 0, None
    stopped_epoch, last_loss, nan_flag = 0, float("nan"), False
    t0 = time.time()
    for epoch in range(1, max_epochs + 1):
        if epoch > 1:
            perm = TR._epoch_perm(len(X_tr), generator)
        model.train()
        total = 0.0
        seen = 0
        for b0 in range(0, len(perm), CFG.BATCH_SIZE):
            idx = perm[b0:b0 + CFG.BATCH_SIZE]
            optimizer.zero_grad()
            xhat = mtr[idx] + str_[idx] * model(Xtr[idx])
            loss = LOSS.loss_q(xhat, ytr[idx])
            if not torch.isfinite(loss):
                nan_flag = True
                break
            loss.backward()
            optimizer.step()
            total += float(loss.detach()) * len(idx)
            seen += len(idx)
        last_loss = total / max(seen, 1)
        model.eval()
        with torch.no_grad():
            val_loss = float(LOSS.loss_q(mva + sva * model(Xva), yva))
        stopped_epoch = epoch
        if not np.isfinite(val_loss):
            nan_flag = True
        if nan_flag:
            break
        if val_loss < best_val - 1e-12:
            best_val, best_epoch = val_loss, epoch
            best_state = copy.deepcopy(model.state_dict())
            stale = 0
        else:
            stale += 1
            if stale >= patience:
                break
    if best_state is None:
        raise RuntimeError("Q_direct produced no finite validation checkpoint")
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        xhat = (mte + ste * model(Xte)).numpy()
    if not np.isfinite(xhat).all():
        raise RuntimeError("Q_direct produced non-finite held-out predictions")
    rel = (xhat - y_te) / y_te
    fit = _fit_name(n, fold_idx, seed, "QD")
    return {
        "meta": {
            "fit_id": fit, "n": n, "fold": fold_idx + 1, "seed": seed,
            "route": "QD", "route_label": "Q_direct",
            "converged": True, "nan_flag": nan_flag,
            "best_epoch": best_epoch, "stopped_epoch": stopped_epoch,
            "best_val_loss": best_val, "last_train_loss": last_loss,
            "rrmse_xR": float(np.sqrt(np.mean(rel ** 2))),
            "n_test": len(test_rows), "n_nonfinite": 0,
            "runtime_s": time.time() - t0,
            "init_param_sha": init_sha, "trunk_init_sha": trunk_sha,
            "batch_order_sha": batch_sha,
            "network_sha": MODEL.scalar_structure_signature(n),
            "scaler_sha": scaler.params_sha(),
            "train_rows_sha": DATA.sha_rows(train_rows),
            "val_rows_sha": DATA.sha_rows(val_rows),
            "test_rows_sha": DATA.sha_rows(test_rows),
            "sample_bytes_sha": DATA.sample_bytes_sha(master, test_rows),
            "split_strategy": "continuous_sobol",
            "direct_decode": "xR_hat=min(X)+sample_sd_ddof0*raw_scalar",
        },
        "predictions": {
            "keys": master.keys[test_rows], "x95_hat": xhat,
            "x95_true": y_te, "min_x": min_te,
            "rel_err": rel, "rel_err_sq": rel ** 2,
        },
    }


def _decorate_param_result(result: dict, n: int, seed: int, label: str) -> dict:
    init_model = MODEL.build_model(n, seed)
    result["meta"]["trunk_init_sha"] = MODEL.trunk_params_sha(init_model)
    result["meta"]["route_label"] = label
    result["meta"]["rrmse_xR"] = result["meta"].pop("rrmse_x95")
    return result


def run_grid(seeds: list[int] | None = None, max_epochs: int | None = None) -> None:
    cfg = load_protocol()
    seeds = list(map(int, seeds or cfg["seeds"]["new"]))
    allowed = set(map(int, cfg["seeds"]["new"]))
    if not set(seeds) <= allowed:
        raise ValueError("grid_extra may only contain the seven preregistered new seeds")
    master = DATA.build_master()
    for seed in seeds:
        for n in map(int, cfg["study01_domain"]["n_grid"]):
            for fold_idx in range(CFG.N_FOLDS):
                for route, label in (("P", "P_equal"), ("Q", "Q_param")):
                    fit = _fit_name(n, fold_idx, seed, route)
                    if fit_complete("grid_extra", fit):
                        continue
                    print(f"[S5B grid] {fit}", flush=True)
                    result = TR.train_one_fit(
                        n, fold_idx, seed, route, master,
                        max_epochs=max_epochs, split_strategy="repeat_stratified")
                    _save_result("grid_extra", fit,
                                 _decorate_param_result(result, n, seed, label))


def run_continuous(seeds: list[int] | None = None, max_epochs: int | None = None,
                   points_per_n: int | None = None) -> None:
    cfg = load_protocol()
    seeds = list(map(int, seeds or cfg["seeds"]["all"]))
    if not set(seeds) <= set(map(int, cfg["seeds"]["all"])):
        raise ValueError("continuous run contains an unregistered seed")
    master = build_continuous_master(points_per_n=points_per_n)
    for seed in seeds:
        for n in map(int, cfg["study01_domain"]["n_grid"]):
            for fold_idx in range(CFG.N_FOLDS):
                for route, label in (("P", "P_equal"), ("Q", "Q_param")):
                    fit = _fit_name(n, fold_idx, seed, route)
                    if not fit_complete("continuous", fit):
                        print(f"[S5B continuous] {fit}", flush=True)
                        result = TR.train_one_fit(
                            n, fold_idx, seed, route, master, max_epochs=max_epochs,
                            split_strategy="continuous_sobol")
                        _save_result("continuous", fit,
                                     _decorate_param_result(result, n, seed, label))
                fit = _fit_name(n, fold_idx, seed, "QD")
                if not fit_complete("continuous", fit):
                    print(f"[S5B continuous] {fit}", flush=True)
                    _save_result("continuous", fit, train_one_direct_fit(
                        n, fold_idx, seed, master, max_epochs=max_epochs))


def _evidence_path(contract: str, n: int, fold_idx: int, seed: int,
                   route: str) -> Path:
    fit = _fit_name(n, fold_idx, seed, route)
    if contract == "grid" and seed in {42, 2026, 3407}:
        return OLD_IID / "evidence" / f"{TR.fit_id(n, fold_idx, seed, route)}.npz"
    mapped = "grid_extra" if contract == "grid" else "continuous"
    return _paths(mapped, fit)[1]


def _cell_mse(contract: str, n: int, fold_idx: int, seed: int, route: str) -> float:
    path = _evidence_path(contract, n, fold_idx, seed, route)
    with np.load(path) as ev:
        values = np.asarray(ev["rel_err_sq"], dtype=np.float64)
    if not np.isfinite(values).all():
        raise RuntimeError(f"non-finite evidence: {path}")
    return float(values.mean())


def _matrix(contract: str, routes: list[str]) -> tuple[np.ndarray, list[dict]]:
    cfg = load_protocol()
    ns = list(map(int, cfg["study01_domain"]["n_grid"]))
    seeds = list(map(int, cfg["seeds"]["all"]))
    matrix = np.empty((len(ns), CFG.N_FOLDS, len(seeds), len(routes)), dtype=np.float64)
    rows = []
    for ni, n in enumerate(ns):
        for f in range(CFG.N_FOLDS):
            for si, seed in enumerate(seeds):
                row = {"contract": contract, "n": n, "fold": f + 1, "seed": seed}
                for ri, route in enumerate(routes):
                    value = _cell_mse(contract, n, f, seed, route)
                    matrix[ni, f, si, ri] = value
                    row[f"mse_{route}"] = value
                rows.append(row)
    return matrix, rows


def crossed_bootstrap(a: np.ndarray, b: np.ndarray, n_boot: int,
                      seed: int) -> dict:
    """Paired crossed fold-within-n x global-seed bootstrap on cell MSE."""
    if a.shape != b.shape or a.ndim != 3:
        raise ValueError("expected matched (n, fold, seed) arrays")
    n_n, n_f, n_s = a.shape
    rng = np.random.default_rng(seed)
    rel, diff = np.empty(n_boot), np.empty(n_boot)
    batch = 2000
    for start in range(0, n_boot, batch):
        stop = min(start + batch, n_boot)
        size = stop - start
        seed_idx = rng.integers(0, n_s, size=(size, n_s))
        fold_idx = rng.integers(0, n_f, size=(size, n_n, n_f))
        ma = np.zeros(size)
        mb = np.zeros(size)
        for ni in range(n_n):
            ma += a[ni][fold_idx[:, ni, :, None], seed_idx[:, None, :]].mean(axis=(1, 2))
            mb += b[ni][fold_idx[:, ni, :, None], seed_idx[:, None, :]].mean(axis=(1, 2))
        ma /= n_n
        mb /= n_n
        rel[start:stop] = (np.sqrt(ma) - np.sqrt(mb)) / np.sqrt(ma)
        diff[start:stop] = mb - ma
    point_ma, point_mb = float(a.mean()), float(b.mean())
    return {
        "baseline_rrmse": float(np.sqrt(point_ma)),
        "comparison_rrmse": float(np.sqrt(point_mb)),
        "relative_improvement": float((np.sqrt(point_ma) - np.sqrt(point_mb)) /
                                      np.sqrt(point_ma)),
        "relative_improvement_ci95": np.quantile(rel, [0.025, 0.975]).tolist(),
        "mean_mse_difference_comparison_minus_baseline": point_mb - point_ma,
        "mean_mse_difference_ci95": np.quantile(diff, [0.025, 0.975]).tolist(),
        "n_boot": int(n_boot), "bootstrap_seed": int(seed),
    }


def analyze(n_boot: int | None = None) -> dict:
    cfg = load_protocol()
    n_boot = int(n_boot or cfg["inference"]["replicates"])
    boot_seed = int(cfg["inference"]["seed"])
    grid, rows_g = _matrix("grid", ["P", "Q"])
    cont, rows_c = _matrix("continuous", ["P", "Q", "QD"])
    primary = crossed_bootstrap(grid[..., 0], grid[..., 1], n_boot, boot_seed)
    continuous_pq = crossed_bootstrap(cont[..., 0], cont[..., 1], n_boot, boot_seed + 1)
    continuous_q_qd = crossed_bootstrap(cont[..., 1], cont[..., 2], n_boot, boot_seed + 2)

    ns = list(map(int, cfg["study01_domain"]["n_grid"]))
    per_n = {}
    for ni, n in enumerate(ns):
        per_n[str(n)] = {
            "grid_P_vs_Q": crossed_bootstrap(
                grid[ni:ni + 1, ..., 0], grid[ni:ni + 1, ..., 1],
                n_boot, boot_seed + 10 + ni),
            "continuous_P_vs_Q": crossed_bootstrap(
                cont[ni:ni + 1, ..., 0], cont[ni:ni + 1, ..., 1],
                n_boot, boot_seed + 20 + ni),
        }
    direction = {
        "grid_Q_better_cells": int(np.sum(grid[..., 1] < grid[..., 0])),
        "grid_total_cells": int(grid[..., 0].size),
        "continuous_Q_better_cells": int(np.sum(cont[..., 1] < cont[..., 0])),
        "continuous_total_cells": int(cont[..., 0].size),
        "continuous_Qdirect_better_than_Qparam_cells": int(np.sum(cont[..., 2] < cont[..., 1])),
    }
    mdm_source = (ROOT.parent / "01-study-MDM最小偏移量优化研究" / "artifacts" /
                  "formal" / "E6_dimensional_raw" / "quantiles" / "summary.csv")
    summary = {
        "protocol": cfg["protocol_id"], "generated_at_git_sha": _head(),
        "confirmatory": {"grid_P_equal_vs_Q_param": primary},
        "exploratory": {
            "continuous_P_equal_vs_Q_param": continuous_pq,
            "continuous_Q_param_vs_Q_direct": continuous_q_qd,
            "per_n": per_n,
            "direction_counts": direction,
            "study01_MDM_Default_same_grid_rrmse": cfg["classical_reference"]["reported_xR_rrmse"],
        },
        "contract_separation": cfg["inference"]["separate_contracts"],
        "classical_reference_source": str(mdm_source.relative_to(CFG.PROJECT_ROOT)).replace("\\", "/"),
        "classical_reference_sha256": _sha_file(mdm_source, canonical_text=True),
        "notes": [
            "Only frozen-grid pooled P_equal-Q_param is confirmatory.",
            "Continuous, per-n, Q_direct and MDM comparisons are exploratory.",
            "Q_param outputs are a latent parameterization; parameter accuracy is not claimed.",
        ],
    }
    out = ARTIFACT_ROOT / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary_s5b.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")
    pd.DataFrame(rows_g + rows_c).to_csv(out / "cell_mse.csv", index=False,
                                         lineterminator="\n")
    return summary


def verify() -> dict:
    cfg = load_protocol()
    expected = {"grid_extra": 280, "continuous": 600}
    result = {"protocol_sha256": _sha_file(PROTOCOL_PATH, canonical_text=True),
              "contracts": {}}
    for contract, count in expected.items():
        base = _contract_dir(contract)
        metas = sorted((base / "fit_metadata").glob("*.json"))
        evidence = sorted((base / "evidence").glob("*.npz"))
        failures = []
        for meta_path in metas:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            ev_path = base / "evidence" / f"{meta_path.stem}.npz"
            if not ev_path.is_file() or _sha_file(ev_path) != meta["evidence_sha256"]:
                failures.append(meta_path.stem)
        result["contracts"][contract] = {
            "expected_fits": count, "metadata": len(metas), "evidence": len(evidence),
            "valid": len(metas) == count == len(evidence) and not failures,
            "failures": failures,
        }
    result["all_valid"] = all(x["valid"] for x in result["contracts"].values())
    return result


def write_manifest() -> None:
    verification = verify()
    if not verification["all_valid"]:
        raise RuntimeError(f"S5B evidence incomplete: {verification}")
    analysis_dir = ARTIFACT_ROOT / "analysis"
    required_analysis = [analysis_dir / "summary_s5b.json", analysis_dir / "cell_mse.csv"]
    if not all(p.is_file() for p in required_analysis):
        raise RuntimeError("analysis outputs missing")
    files = [PROTOCOL_PATH, Path(__file__), Path(DATA.__file__), Path(MODEL.__file__),
             Path(TR.__file__), Path(LOSS.__file__), *required_analysis]
    for contract in ("grid_extra", "continuous"):
        files.extend(sorted((_contract_dir(contract) / "fit_metadata").glob("*.json")))
        files.extend(sorted((_contract_dir(contract) / "evidence").glob("*.npz")))
    manifest = {
        "protocol": load_protocol()["protocol_id"], "git_sha": _head(),
        "verification": verification,
        "sha_rule": "text files canonicalized to LF; npz raw bytes",
        "files": len(files),
    }
    manifest_path = ARTIFACT_ROOT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8", newline="\n")
    files.append(manifest_path)
    lines = []
    for path in sorted(files, key=lambda p: str(p)):
        canonical = path.suffix.lower() in {".json", ".csv", ".py", ".md", ".txt", ".log"}
        rel = path.relative_to(ROOT).as_posix()
        lines.append(f"{_sha_file(path, canonical_text=canonical)}  {rel}")
    (ARTIFACT_ROOT / "SHA256SUMS").write_text("\n".join(lines) + "\n",
                                               encoding="utf-8", newline="\n")


def main() -> None:
    if CFG.PROTOCOL_VERSION != "iid-v1":
        raise RuntimeError("S5B must run with PQ_PROTOCOL=iid-v1")
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["grid", "continuous", "analyze", "verify", "seal"],
                        required=True)
    parser.add_argument("--seed", action="append", type=int)
    parser.add_argument("--n-boot", type=int)
    args = parser.parse_args()
    if args.phase == "grid":
        run_grid(args.seed)
    elif args.phase == "continuous":
        run_continuous(args.seed)
    elif args.phase == "analyze":
        analyze(args.n_boot)
    elif args.phase == "verify":
        print(json.dumps(verify(), ensure_ascii=False, indent=2))
    else:
        write_manifest()


if __name__ == "__main__":
    main()
