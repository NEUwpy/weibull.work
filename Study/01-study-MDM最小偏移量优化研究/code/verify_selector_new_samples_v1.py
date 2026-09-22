"""Frozen-model confirmation on fresh samples. No tuning or training.

Prepare records and fixes the contract; run uses four worker processes by default.
Each cell is checkpointed. All policies share samples and duplicate deltas are
evaluated only once. Use --stage prepare, --stage smoke, then --stage run.
"""
from __future__ import annotations
import os
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
from pathlib import Path
from itertools import product
from concurrent.futures import ProcessPoolExecutor, as_completed
import argparse
import hashlib
import json
import subprocess
import sys
import time

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
sys.path[:0] = [str(HERE), str(REPO / "python")]
import dim_raw_config as CFG
from studies.common.sample import generate_sample
from studies.common.runner import run_method
from check_mean_normalized_e2e_scale import predict_curve, normalized_joint_loss
from paper_support import j1_from_loss

OUT = ROOT / "artifacts/exploratory/selector_new_sample_confirmation_20260922"
MODEL_DIR = "Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E5_normalized_raw/specialist/final_models"
COMMIT = "ddc75754"
NAMESPACE = "study01_selector_confirmation_20260922_v1"
SEEDS = [42, 2026, 3407]
POLICIES = ["fixed_010", "frozen_final_seed1", "large_delta_fallback"]
CELLS = list(product(CFG.BETA_GRID, CFG.GAMMA_OVER_ETA_GRID, CFG.N_GRID))
REPEATS = 100
MODELS = {}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_models():
    hashes = {}
    for n in CFG.N_GRID:
        name = f"n{n}_final"
        raw = subprocess.check_output(["git", "show", f"{COMMIT}:{MODEL_DIR}/{name}.json"], cwd=REPO)
        model = json.loads(raw)
        assert model["n"] == n and model["seed"] == 1
        assert model["normalization"].startswith("Z_n = sorted(x)/mean(x)")
        assert model["delta_grid"] == CFG.DELTA_GRID and "mlp_weights" in model
        # Arrays cached once; same forward function as the existing scale check.
        for key in ("coefs_", "intercepts_"):
            model["mlp_weights"][key] = [np.asarray(v) for v in model["mlp_weights"][key]]
        MODELS[n] = model
        hashes[name] = sha(raw)
    return hashes


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    hashes = load_models()
    checks = []
    for n, model in MODELS.items():
        from sklearn.neural_network import MLPRegressor
        # Independent sklearn forward pass verifies the JSON inference conversion.
        mlp = MLPRegressor()
        mlp.coefs_ = model["mlp_weights"]["coefs_"]
        mlp.intercepts_ = model["mlp_weights"]["intercepts_"]
        mlp.n_layers_ = len(mlp.coefs_)+1
        mlp.n_outputs_ = 26
        mlp.out_activation_ = "identity"
        mlp.n_features_in_ = n
        diffs = []
        for rid in (0, 50, 99):
            sample = generate_sample(2., 1000., 1000., n, rid, seed=CFG.SEED_NAMESPACE)
            z = sample/sample.mean()
            x = ((z-np.asarray(model["input_scaler_mean"]))/np.asarray(model["input_scaler_std"]))[None, :]
            expected = np.maximum(mlp.predict(x)[0]*model["target_scaler_std"]+model["target_scaler_mean"],0)
            predicted = predict_curve(sample, model)
            np.testing.assert_allclose(predicted,expected,rtol=1e-10,atol=1e-10)
            diffs.append(float(np.max(abs(predicted-expected))))
        checks.append(dict(model=model["model_id"], checked_rows=3, max_abs_difference=max(diffs),
                           kind="numpy forward vs sklearn forward with same historical weights"))
    # Bridge today's MDM to the saved candidate estimates before new samples.
    bridges = []
    for n in CFG.N_GRID:
        cell_id = CELLS.index((2., 1., n))
        path = ROOT / f"artifacts/formal/E5_normalized_raw/shared_data/chunks/chunk_{cell_id:04d}_mdm.csv"
        frame = pd.read_csv(path)
        sample = generate_sample(2., 1000., 1000., n, 0, seed=CFG.SEED_NAMESPACE)
        for delta in (.02, .1, .3):
            result = run_method("mdm", sample, offset=delta, gamma_steps=60, trace=False)
            assert result["converged"]
            old = frame[(frame.repeat_id == 0) & np.isclose(frame.delta, delta)].iloc[0]
            np.testing.assert_allclose([result[k] for k in ("beta_hat", "eta_hat", "gamma_hat")],
                                       old[["beta_hat", "eta_hat", "gamma_hat"]].to_numpy(float), rtol=1e-6, atol=1e-5)
            bridges.append(dict(n=n, delta=delta, matched=True))
    contract = dict(version=1, namespace=NAMESPACE, cells=CELLS, repeats=REPEATS,
                    samples=len(CELLS)*REPEATS, eta=CFG.ETA, model_commit=COMMIT,
                    model_hashes=hashes, model_checks=checks, solver_bridge=bridges,
                    policies=POLICIES, delta_grid=CFG.DELTA_GRID,
                    fallback="If frozen final seed1 selected delta > 0.20, select 0.10; otherwise unchanged",
                    model_assignment="Select the single full-development frozen model by observed n; no true-parameter routing",
                    failure="Nonconverged or nonfinite results scored by at least the corresponding frozen full-development p99 penalty; report all failures and complete-case sensitivity",
                    metric="J1=sqrt(mean joint standardized squared error))",
                    scope="New independent sample realizations on existing discrete design, conditional on frozen full-development models; not exact OOF-model replication or new parameter-domain proof",
                    bootstrap="2000 paired resamples within each cell; fixed design and fixed models; seed 20260922",
                    threshold_frozen_before_new_outcomes=True,
                    solver_sha256=sha((REPO / "python/methods/mdm.py").read_bytes()),
                    code_sha256=sha(Path(__file__).read_bytes()))
    contract_path = OUT / "contract.json"
    if contract_path.exists():
        assert json.loads(contract_path.read_text(encoding="utf-8")) == contract, "Existing frozen contract differs"
    else:
        contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"PREPARE PASS: 4 full-development models, 12 forward checks, 12 solver bridges. {len(CELLS)*REPEATS} new samples fixed.", flush=True)


def evaluate_cell(cell_id, count=REPEATS):
    beta, ratio, n = CELLS[cell_id]
    eta, gamma = float(CFG.ETA), float(CFG.ETA*ratio)
    fold = cell_id % 5 + 1
    model = MODELS[n]
    penalty = float(model["dev_failure_penalty"])
    output = []
    start = time.perf_counter()
    for rid in range(count):
        sample = generate_sample(beta, eta, gamma, n, rid, seed=NAMESPACE)
        prediction = predict_curve(sample, model)
        original = float(CFG.DELTA_GRID[int(prediction.argmin())])
        deltas = [.1, original, .1 if original > .20 else original]
        estimates = {d: run_method("mdm", sample, offset=d, gamma_steps=60, trace=False) for d in set(deltas)}
        for policy, delta in zip(POLICIES, deltas):
            result = estimates[delta]
            finite = all(np.isfinite(result[k]) for k in ("beta_hat", "eta_hat", "gamma_hat"))
            valid = bool(result["converged"]) and finite
            raw_loss = normalized_joint_loss(result, beta, eta, gamma) if finite else np.nan
            loss = raw_loss if valid else max(penalty, raw_loss) if finite else penalty
            output.append(dict(cell_id=cell_id, beta=beta, eta=eta, gamma=gamma,
                               gamma_over_eta=ratio, n=n, model_seed=1, repeat_id=rid, policy=policy,
                               delta=delta, beta_hat=result["beta_hat"], eta_hat=result["eta_hat"],
                               gamma_hat=result["gamma_hat"], valid=valid, loss=loss,
                               sample_sha256=sha(sample.astype("<f8").tobytes())))
    return output, time.perf_counter()-start


def worker_init():
    load_models()


def summarize():
    df = pd.concat([pd.read_csv(OUT / "cells" / f"cell_{i:03d}.csv") for i in range(len(CELLS))], ignore_index=True)
    assert len(df) == len(CELLS)*REPEATS*len(POLICIES)
    assert not df.duplicated(["cell_id", "repeat_id", "policy"]).any()
    assert df.groupby(["cell_id", "repeat_id"]).sample_sha256.nunique().eq(1).all()
    matrix = df.pivot(index=["cell_id", "repeat_id"], columns="policy", values="loss").sort_index()[POLICIES]
    cube = matrix.to_numpy().reshape(len(CELLS), REPEATS, len(POLICIES))
    rng = np.random.default_rng(20260922)
    boot = np.empty((2000, len(POLICIES)))
    for b in range(len(boot)):
        picks = rng.integers(REPEATS, size=(len(CELLS), REPEATS))
        boot[b] = np.sqrt(cube[np.arange(len(CELLS))[:, None], picks].mean(axis=(0, 1)))
    rows = []
    base = matrix.fixed_010.to_numpy()
    current = matrix.frozen_final_seed1.to_numpy()
    for i, name in enumerate(POLICIES):
        values = matrix[name].to_numpy()
        change = values-base
        vsbase = 100*(1-boot[:, i]/boot[:, 0])
        vscurrent = 100*(1-boot[:, i]/boot[:, 1])
        sub = df[df.policy == name]
        rows.append(dict(policy=name, J1=j1_from_loss(pd.Series(values)),
                         improvement_vs_fixed_pct=100*(1-np.sqrt(values.mean()/base.mean())),
                         ci_vs_fixed_low=np.quantile(vsbase,.025), ci_vs_fixed_high=np.quantile(vsbase,.975),
                         improvement_vs_original_pct=100*(1-np.sqrt(values.mean()/current.mean())),
                         ci_vs_original_low=np.quantile(vscurrent,.025), ci_vs_original_high=np.quantile(vscurrent,.975),
                         improved=int((change < -1e-10).sum()), worsened=int((change > 1e-10).sum()),
                         equal=int((abs(change) <= 1e-10).sum()), failures=int((~sub.valid).sum()),
                         loss_p95=np.quantile(values,.95), loss_p99=np.quantile(values,.99)))
    result = pd.DataFrame(rows)
    result.to_csv(OUT / "comparison.csv", index=False)
    grouped = []
    for group in ("n", "beta", "gamma_over_eta", "cell_id"):
        for val, indices in df[df.policy==POLICIES[0]].groupby(group).groups.items():
            cells = df.loc[indices, "cell_id"].unique()
            subset = matrix.loc[matrix.index.get_level_values("cell_id").isin(cells)]
            for name in POLICIES:
                grouped.append(dict(group=group, value=val, policy=name, count=len(subset),
                                    J1=j1_from_loss(subset[name]),
                                    improvement_pct=100*(1-np.sqrt(subset[name].mean()/subset.fixed_010.mean()))))
    pd.DataFrame(grouped).to_csv(OUT / "by_group.csv", index=False)
    params = []
    for name, sub in df.groupby("policy"):
        for parameter, scale in (("beta", "beta"), ("eta", "eta"), ("gamma", "eta")):
            err = (sub[f"{parameter}_hat"]-sub[parameter])/sub[scale]
            params.append(dict(policy=name, parameter=parameter, MSE=float(np.mean(err**2)),
                               RMSE=float(np.sqrt(np.mean(err**2)))))
    pd.DataFrame(params).to_csv(OUT / "parameter_errors.csv", index=False)
    result_dict = dict(status="complete", samples=16000, design_cells=160,
                       failures=int((~df.valid).sum()), comparison=rows,
                       validity="Conditional on frozen full-development models and current discrete design; no policy retuning",
                       contract_sha256=sha((OUT / "contract.json").read_bytes()),
                       cell_sha256={f"cell_{i:03d}.csv":sha((OUT / "cells" / f"cell_{i:03d}.csv").read_bytes()) for i in range(160)})
    (OUT / "summary.json").write_text(json.dumps(result_dict,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(result.to_string(index=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["prepare", "smoke", "run", "summary"], required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.stage == "prepare":
        prepare()
        return
    contract = json.loads((OUT / "contract.json").read_text(encoding="utf-8"))
    assert contract["code_sha256"] == sha(Path(__file__).read_bytes())
    assert contract["solver_sha256"] == sha((REPO / "python/methods/mdm.py").read_bytes())
    if args.stage == "summary":
        summarize()
        return
    if args.stage == "smoke":
        load_models()
        total=0
        for i in range(4):
            output, seconds = evaluate_cell(i, count=2)
            assert len(output)==6 and all(r["valid"] for r in output)
            total += seconds
        print(f"SMOKE PASS: 8 new samples / 24 policy rows; elapsed {total:.2f}s",flush=True)
        return
    (OUT / "cells").mkdir(exist_ok=True)
    pending = [i for i in range(len(CELLS)) if not (OUT / "cells" / f"cell_{i:03d}.csv").exists()]
    done = len(CELLS)-len(pending)
    print(f"RUN: {len(pending)} cells pending, {args.workers} workers",flush=True)
    with ProcessPoolExecutor(max_workers=args.workers, initializer=worker_init) as pool:
        futures = {pool.submit(evaluate_cell,i):i for i in pending}
        for future in as_completed(futures):
            i=futures[future]
            output, seconds=future.result()
            frame=pd.DataFrame(output)
            assert len(frame)==REPEATS*len(POLICIES)
            target=OUT / "cells" / f"cell_{i:03d}.csv"
            temporary=target.with_suffix(".tmp")
            frame.to_csv(temporary,index=False)
            temporary.replace(target)
            done+=1
            print(f"{done}/160 cells complete; cell {i}; {seconds:.1f}s; failures {(~frame.valid).sum()}",flush=True)
    summarize()


if __name__ == "__main__":
    main()
