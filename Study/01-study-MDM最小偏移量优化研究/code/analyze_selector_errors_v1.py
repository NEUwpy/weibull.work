"""Bounded old-data diagnosis of AMDM selection errors; no fitting or new sampling.

Phase-one probes were fixed before inspecting full-design results. Explicitly
labelled phase-two probes follow the observed large-delta/disagreement groups.
These are reused-OOF exploratory comparisons, not independent confirmation.
"""
from pathlib import Path
from itertools import product
import hashlib
import json
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from run_E6b_dimensional_raw_specialist import compute_per_sample_loss
from paper_support import j1_from_loss

SOURCE = ROOT / "artifacts/formal/E5_normalized_raw"
OUT = ROOT / "artifacts/exploratory/selector_error_diagnosis_20260922"
KEYS = ["beta", "eta", "gamma", "gamma_over_eta", "n", "repeat_id"]
SEEDS = [42, 2026, 3407]
DELTAS = np.round(np.arange(26) * .02, 2)
BASE = 5


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    sources = list(sorted((SOURCE / "shared_data/chunks").glob("*_mdm.csv")))
    assert len(sources) == 160
    scan = compute_per_sample_loss(pd.concat([pd.read_csv(p) for p in sources], ignore_index=True))
    assert len(scan) == 48000 * 26 and scan.status.eq("success").all()
    assert np.isfinite(scan.loss).all() and not scan.duplicated(KEYS + ["delta"]).any()
    scan = scan.set_index(KEYS + ["delta"]).sort_index()
    truth = scan.loss.unstack("delta").sort_index()
    np.testing.assert_allclose(truth.columns, DELTAS)
    keys = truth.index.to_frame(index=False)
    actual = truth.to_numpy()
    rows = np.arange(len(keys))
    default = actual[:, BASE]
    pred_list, selected_list = [], []
    sealed_path = SOURCE / "specialist/raw_specialist_results.csv"
    sealed = pd.read_csv(sealed_path)
    sources.append(sealed_path)
    for seed in SEEDS:
        paths = sorted((SOURCE / "specialist/predictions").glob(f"*_seed{seed}.csv"))
        assert len(paths) == 20
        sources.extend(paths)
        parts = []
        for p in paths:
            part = pd.read_csv(p)
            part["fold"] = int(p.stem.split("_fold")[1].split("_")[0])
            parts.append(part)
        frame = pd.concat(parts).set_index(KEYS).sort_index()
        assert frame.index.equals(truth.index) and len(frame) == 48000
        saved = sealed[sealed.seed == seed].set_index(KEYS).sort_index()
        assert saved.index.equals(truth.index)
        np.testing.assert_array_equal(frame.fold, saved.fold)
        fold_lookup = {cell: i % 5 + 1 for i, cell in enumerate(product(
            sorted(keys.beta.unique()), sorted(keys.gamma_over_eta.unique()), sorted(keys.n.unique())))}
        expected_fold = [fold_lookup[(r.beta, r.gamma_over_eta, r.n)] for r in keys.itertuples()]
        np.testing.assert_array_equal(frame.fold, expected_fold)
        np.testing.assert_allclose(frame.selected_delta, saved.selected_delta)
        cols = sorted([c for c in frame if c.startswith("pred_d")], key=lambda x: float(x[6:]))
        np.testing.assert_allclose([float(c[6:]) for c in cols], DELTAS)
        pred = frame[cols].to_numpy()
        assert np.isfinite(pred).all()
        chosen = np.argmin(pred, axis=1)
        np.testing.assert_allclose(DELTAS[chosen], frame.selected_delta)
        np.testing.assert_allclose(actual[rows, chosen], frame.true_loss, atol=1e-10)
        np.testing.assert_allclose(actual[rows, chosen], saved.true_loss, atol=1e-10)
        np.testing.assert_allclose(actual.min(axis=1), frame.oracle_min_loss, atol=1e-10)
        pred_list.append(pred)
        selected_list.append(chosen)
    predictions = np.stack(pred_list)
    selected = np.stack(selected_list)
    p = predictions[0]
    chosen = selected[0]
    mean_pred = predictions.mean(axis=0)
    mean_choice = mean_pred.argmin(axis=1)
    smooth = lambda x: (np.pad(x, ((0, 0), (1, 1)), mode="edge")[:, :-2]
                        + 2*x + np.pad(x, ((0, 0), (1, 1)), mode="edge")[:, 2:]) / 4
    gain = p[:, BASE] - p[rows, chosen]
    tied = np.isclose(p, p.min(axis=1)[:, None], atol=1e-12, rtol=0)
    tie_nearest = np.where(tied, np.abs(DELTAS-.1)[None, :], np.inf).argmin(axis=1)
    shrink_target = .1 + .5*(DELTAS[chosen]-.1)
    # Nearest existing grid point; deterministic first (lower delta) on equal distance.
    shrink_choice = np.round(np.abs(DELTAS[None, :]-shrink_target[:, None]), 10).argmin(axis=1)
    policies = {"fixed_010": np.full(len(keys), BASE),
                **{f"seed_{s}": selected[i] for i, s in enumerate(SEEDS)},
                "mean_prediction_3seed": mean_choice,
                "median_prediction_3seed": np.median(predictions, axis=0).argmin(axis=1),
                "smooth_seed42": smooth(p).argmin(axis=1),
                "smooth_mean_3seed": smooth(mean_pred).argmin(axis=1),
                "tie_nearest_default": tie_nearest,
                "half_delta_adjustment": shrink_choice,
                "exact_consensus_else_default": np.where((selected == selected[0]).all(axis=0), chosen, BASE)}
    for threshold in (.01, .05, .10):
        policies[f"gain_gt_{threshold:.2f}_else_default"] = np.where(gain > threshold, chosen, BASE)
    all_gain = predictions[:, :, BASE] - predictions[:, rows, mean_choice]
    policies["all_seeds_predict_gain_else_default"] = np.where(all_gain.min(axis=0) > 0, mean_choice, BASE)
    # Post-hoc follow-ups to phase one, not independent validation or a tuned winner.
    phase_two = {
        "p2_seed42_large_delta_fallback": np.where(DELTAS[chosen] > .20, BASE, chosen),
        "p2_seed42_restrict_grid_020": p[:, :11].argmin(axis=1),
        "p2_seed42_cap_delta_020": np.minimum(chosen, 10),
        "p2_mean_large_delta_fallback": np.where(DELTAS[mean_choice] > .20, BASE, mean_choice),
        "p2_mean_restrict_grid_020": mean_pred[:, :11].argmin(axis=1),
        "p2_mean_disagreement_fallback": np.where(
            DELTAS[selected].max(axis=0)-DELTAS[selected].min(axis=0) > .12+1e-10, BASE, mean_choice),
    }
    for index, seed in enumerate(SEEDS[1:], 1):
        phase_two[f"p2_seed{seed}_large_delta_fallback"] = np.where(
            DELTAS[selected[index]] > .20, BASE, selected[index])
    policies.update(phase_two)

    def stats(loss, baseline):
        change = loss-baseline
        j1 = j1_from_loss(pd.Series(loss))
        base_j1 = j1_from_loss(pd.Series(baseline))
        return dict(count=len(loss), J1=j1,
                    improvement_pct=100*(1-j1/base_j1),
                    mean_loss=float(loss.mean()), loss_p95=float(np.quantile(loss, .95)),
                    loss_p99=float(np.quantile(loss, .99)),
                    improved=int((change < -1e-10).sum()), worsened=int((change > 1e-10).sum()),
                    equal=int((np.abs(change) <= 1e-10).sum()),
                    gross_harm=float(change.clip(min=0).sum()),
                    gross_benefit=float((-change).clip(min=0).sum()))

    result, by_n, by_cell, by_block = [], [], [], []
    for name, choice in policies.items():
        loss = actual[rows, choice]
        result.append(dict(policy=name, **stats(loss, default), switch_rate=float((choice != BASE).mean())))
        for n in sorted(keys.n.unique()):
            mask = keys.n.to_numpy() == n
            by_n.append(dict(policy=name, n=int(n), **stats(loss[mask], default[mask])))
        for cell, indices in keys.groupby(KEYS[:-1]).groups.items():
            idx = np.asarray(indices)
            by_cell.append(dict(policy=name, **dict(zip(KEYS[:-1], cell)), **stats(loss[idx], default[idx])))
        for lo, hi in ((0, 99), (100, 199), (200, 299)):
            mask = keys.repeat_id.between(lo, hi).to_numpy()
            by_block.append(dict(policy=name, repeat_block=f"{lo}-{hi}", **stats(loss[mask], default[mask])))
    results = pd.DataFrame(result)
    cells = pd.DataFrame(by_cell)
    results["cells_worse"] = results.policy.map(cells.groupby("policy").improvement_pct.apply(lambda x: int((x < -1e-10).sum())))
    results.to_csv(OUT / "policy_comparison.csv", index=False)
    pd.DataFrame(by_n).to_csv(OUT / "policy_by_n.csv", index=False)
    cells.to_csv(OUT / "policy_by_cell.csv", index=False)
    pd.DataFrame(by_block).to_csv(OUT / "policy_by_repeat_block.csv", index=False)

    details = keys.copy()
    details["selected_delta"] = DELTAS[chosen]
    details["predicted_gain"] = gain
    details["default_loss"] = default
    details["adaptive_loss"] = actual[rows, chosen]
    details["excess_loss"] = actual[rows, chosen]-default
    details["prediction_min_zero"] = p.min(axis=1) == 0
    details["minimum_tied"] = tied.sum(axis=1) > 1
    details["seed_delta_range"] = DELTAS[selected].max(axis=0)-DELTAS[selected].min(axis=0)
    details["selected_large_delta"] = DELTAS[chosen] > .20
    components = []
    for param, scale in (("beta", "beta"), ("eta", "eta"), ("gamma", "eta")):
        est = scan[f"{param}_hat"].unstack("delta").reindex(truth.index).to_numpy()
        error = ((est-keys[param].to_numpy()[:, None])/keys[scale].to_numpy()[:, None])**2
        details[f"{param}_se_change"] = error[rows, chosen]-error[:, BASE]
        for name, choice in policies.items():
            components.append(dict(policy=name, parameter=param, normalized_MSE=float(error[rows, choice].mean())))
    pd.DataFrame(components).to_csv(OUT / "parameter_mse.csv", index=False)
    details.nlargest(30, "excess_loss").to_csv(OUT / "largest_30_errors.csv", index=False)
    diagnostics = []
    for col in ("n", "beta", "gamma_over_eta", "selected_delta", "selected_large_delta", "prediction_min_zero", "minimum_tied"):
        for value, group in details.groupby(col):
            diagnostics.append(dict(group=col, value=str(value),
                                    predicted_gain_mean=float(group.predicted_gain.mean()),
                                    realized_gain_mean=float(-group.excess_loss.mean()),
                                    **stats(group.adaptive_loss.to_numpy(), group.default_loss.to_numpy())))
    for col in ("predicted_gain", "seed_delta_range"):
        bins = pd.qcut(details[col], 5, duplicates="drop")
        for value, group in details.groupby(bins, observed=True):
            diagnostics.append(dict(group=col+"_quintile", value=str(value),
                                    predicted_gain_mean=float(group.predicted_gain.mean()),
                                    realized_gain_mean=float(-group.excess_loss.mean()),
                                    **stats(group.adaptive_loss.to_numpy(), group.default_loss.to_numpy())))
    pd.DataFrame(diagnostics).to_csv(OUT / "error_groups.csv", index=False)
    excess = details.excess_loss.to_numpy()
    harm = np.maximum(excess, 0)
    summary = dict(
        samples=48000, cells=160, seeds=SEEDS,
        metric="J1=sqrt(mean(per-sample sum of three normalized squared parameter errors))",
        evaluation="Exploratory reuse of old OOF data; repeat blocks are stability summaries, not new held-out tests",
        prediction_zero_rate=float(details.prediction_min_zero.mean()),
        prediction_tie_rate=float(details.minimum_tied.mean()),
        top_one_percent_sample_share_of_gross_harm=float(np.sort(harm)[-480:].sum()/harm.sum()),
        seed_exact_agreement_rate=float((selected == selected[0]).all(axis=0).mean()),
        mean_pairwise_delta_range=float(details.seed_delta_range.mean()),
        zero_tie_nearest_changes=int((tie_nearest != chosen).sum()),
        policies=results.to_dict(orient="records"),
        post_hoc_phase_two_policies=list(phase_two),
        limitations=["No new model training or MDM evaluations", "No policy chosen by truth at inference",
                     "Thresholds and shrinkage are fixed probes, not tuned production recommendations",
                     "Ensemble uses three models per n/fold; extra model and inference cost",
                     "Clipped predictions cannot recover raw negative outputs"],
        source_hashes={str(p.relative_to(ROOT)).replace("\\", "/"): digest(p) for p in sources},
        code_sha256=digest(Path(__file__)),
        dependency_sha256={p.name: digest(p) for p in (
            HERE / "paper_support.py", HERE / "run_E6b_dimensional_raw_specialist.py")},
    )
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(results[["policy", "J1", "improvement_pct", "cells_worse", "loss_p99"]].to_string(index=False))
    print(json.dumps({k:v for k,v in summary.items() if k not in ("policies", "source_hashes")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
