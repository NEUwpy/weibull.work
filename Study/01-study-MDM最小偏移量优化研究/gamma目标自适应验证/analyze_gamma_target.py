"""Check the gamma-target hypothesis on the sealed candidate scan; no training.

Primary tie rule: exact minimum, nearest delta=0.1, then smaller delta.
Hindsight selectors use true parameters and are explicitly not deployable.
"""
from pathlib import Path
import hashlib
import json
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
sys.path.insert(0, str(STUDY / "code"))
from run_E6b_dimensional_raw_specialist import compute_per_sample_loss
from paper_support import j1_from_loss

OUT = HERE / "results"
SOURCE = STUDY / "artifacts/formal/E5_normalized_raw"
KEYS = ["beta", "eta", "gamma", "gamma_over_eta", "n", "repeat_id"]
GRID = np.round(np.arange(26)*.02, 2)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def min_near_default(values):
    ties = values == values.min(axis=1)[:, None]
    distances = np.round(abs(GRID-.1), 10)
    return np.where(ties, distances[None, :], np.inf).argmin(axis=1)


def run():
    OUT.mkdir(exist_ok=True)
    paths = sorted((SOURCE / "shared_data/chunks").glob("*_mdm.csv"))
    assert len(paths) == 160
    frame = compute_per_sample_loss(pd.concat([pd.read_csv(p) for p in paths], ignore_index=True))
    assert len(frame) == 48000*26 and frame.status.eq("success").all()
    assert not frame.duplicated(KEYS+["delta"]).any()
    frame = frame.set_index(KEYS+["delta"]).sort_index()
    truth = frame.loss.unstack("delta").sort_index()
    np.testing.assert_allclose(truth.columns, GRID)
    keys = truth.index.to_frame(index=False)
    loss = truth.to_numpy()
    assert np.isfinite(loss).all()
    estimates, se = {}, {}
    for name, scale in (("beta", "beta"), ("eta", "eta"), ("gamma", "eta")):
        estimates[name] = frame[f"{name}_hat"].unstack("delta").reindex(truth.index).to_numpy()
        se[name] = ((estimates[name]-keys[name].to_numpy()[:, None])/keys[scale].to_numpy()[:, None])**2
    np.testing.assert_allclose(sum(se.values()), loss, atol=1e-12)
    prediction_path = SOURCE / "specialist/raw_specialist_results.csv"
    paths.append(prediction_path)
    pred = pd.read_csv(prediction_path)
    pred = pred[pred.seed == 42].set_index(KEYS).sort_index()
    assert pred.index.equals(truth.index)
    rows = np.arange(len(keys))
    current = pred.selected_delta_idx.to_numpy(int)
    np.testing.assert_allclose(GRID[current], pred.selected_delta)
    np.testing.assert_allclose(loss[rows, current], pred.true_loss)
    gamma_choice = min_near_default(se["gamma"])
    joint_choice = min_near_default(loss)
    ties = se["gamma"] == se["gamma"].min(axis=1)[:, None]
    choices = {
        "fixed_010": np.full(len(keys), 5),
        "current_joint_AMDM_seed42": current,
        "gamma_oracle": gamma_choice,
        "joint_oracle": joint_choice,
        "gamma_oracle_tie_low_delta": se["gamma"].argmin(axis=1),
        "gamma_oracle_tie_joint_loss": min_near_default(np.where(ties, loss, np.inf)),
    }
    np.testing.assert_array_less(se["gamma"][rows,gamma_choice], se["gamma"][:,5]+1e-12)
    np.testing.assert_array_less(loss[rows,joint_choice], loss[rows,gamma_choice]+1e-12)
    def metrics(indices, choice):
        selected_loss = loss[indices,choice[indices]]
        base_loss = loss[indices,5]
        result = dict(count=len(indices), J1=j1_from_loss(pd.Series(selected_loss)),
                      improvement_vs_fixed_pct=100*(1-np.sqrt(selected_loss.mean()/base_loss.mean())),
                      joint_improved=int((selected_loss<base_loss-1e-12).sum()),
                      joint_worsened=int((selected_loss>base_loss+1e-12).sum()),
                      joint_equal=int((abs(selected_loss-base_loss)<=1e-12).sum()),
                      loss_p99=float(np.quantile(selected_loss,.99)))
        for name in se:
            mse = se[name][indices,choice[indices]].mean()
            base_mse = se[name][indices,5].mean()
            result[name+"_RMSE"] = float(np.sqrt(mse))
            result[name+"_RMSE_improvement_pct"] = float(100*(1-np.sqrt(mse/base_mse)))
        return result
    overall = pd.DataFrame([dict(rule=name, **metrics(rows, choice)) for name,choice in choices.items()])
    overall.to_csv(OUT / "comparison.csv",index=False)
    grouped = []
    for grouping in (["n"], ["beta"], ["gamma_over_eta"], KEYS[:-1]):
        for key, index in keys.groupby(grouping).groups.items():
            index = np.asarray(index)
            values = key if isinstance(key, tuple) else (key,)
            for name, choice in choices.items():
                grouped.append(dict(group="cell" if len(grouping)>1 else grouping[0],
                                    **dict(zip(grouping,values)),rule=name,**metrics(index,choice)))
    pd.DataFrame(grouped).to_csv(OUT / "by_group.csv",index=False)
    gamma_better = se["gamma"][rows,gamma_choice] < se["gamma"][:,5]-1e-12
    joint_worse = loss[rows,gamma_choice] > loss[:,5]+1e-12
    higher_beta = se["beta"][rows,gamma_choice] > se["beta"][:,5]+1e-12
    higher_eta = se["eta"][rows,gamma_choice] > se["eta"][:,5]+1e-12
    cases = keys.copy()
    cases["delta_fixed"] = .1
    for name, choice in choices.items():
        cases[name+"_delta"] = GRID[choice]
        cases[name+"_loss"] = loss[rows,choice]
        for parameter in se:
            cases[name+"_"+parameter+"_hat"] = estimates[parameter][rows,choice]
    # Fixed first examples illustrate both directions, never replace full summaries.
    examples = pd.concat([cases[gamma_better & joint_worse].head(5).assign(case="gamma_better_joint_worse"),
                          cases[gamma_better & ~joint_worse].head(5).assign(case="gamma_better_joint_not_worse")])
    examples.to_csv(OUT / "examples.csv",index=False)
    selections = pd.DataFrame({name:GRID[choice] for name,choice in choices.items()})
    selections.apply(pd.Series.value_counts).fillna(0).astype(int).sort_index().to_csv(OUT / "delta_counts.csv",index_label="delta")
    # Can the true gamma be bracketed by this sample's evaluated candidate estimates?
    reachable = ((estimates["gamma"].min(axis=1)<=keys.gamma.to_numpy())
                 & (estimates["gamma"].max(axis=1)>=keys.gamma.to_numpy()))
    summary = dict(
        design_cells=160, samples=48000, candidates=26,
        purpose="Gamma-target hindsight potential and cross-parameter tradeoff; no learned gamma-target model",
        primary_tie_rule="Exact gamma loss minimum; nearest delta 0.1; then smaller delta",
        gamma_improved_count=int(gamma_better.sum()),
        gamma_improved_but_joint_worse=int((gamma_better & joint_worse).sum()),
        gamma_improved_but_beta_worse=int((gamma_better & higher_beta).sum()),
        gamma_improved_but_eta_worse=int((gamma_better & higher_eta).sum()),
        exact_gamma_minimum_ties=int((ties.sum(axis=1)>1).sum()),
        near_gamma_minimum_ties_1e_12=int((np.isclose(se["gamma"],se["gamma"].min(axis=1)[:,None],atol=1e-12,rtol=0).sum(axis=1)>1).sum()),
        gamma_joint_same_delta=int((gamma_choice==joint_choice).sum()),
        true_gamma_within_candidate_gamma_range=int(reachable.sum()),
        comparison=overall.to_dict(orient="records"),
        inputs={str(p.relative_to(STUDY)).replace("\\","/"):digest(p) for p in paths},
        code_sha256=digest(Path(__file__)),
        dependency_sha256={p.name:digest(p) for p in (STUDY/"code/paper_support.py",STUDY/"code/run_E6b_dimensional_raw_specialist.py")},
    )
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(overall.to_string(index=False))
    print(json.dumps({k:v for k,v in summary.items() if k not in ("comparison","inputs","dependency_sha256")},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    run()
