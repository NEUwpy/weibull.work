"""
analyze.py — turn the Monte Carlo output into the study's conclusions.

Produces (in ../data):
  agg_master.csv          all aggregated cells
  best_per_scenario.csv   argmin-delta per (n,beta,gamma/eta)
  best_per_n.csv          one delta per n
  best_per_beta.csv       one delta per beta
  strategy_compare.csv    overall + per-n NE of each strategy
  adaptive_rule.csv       the fitted delta(n, beta-hat bin) lookup
  headline.json           numbers quoted in the report
"""
import glob, json
import numpy as np
import pandas as pd

ETA = 100.0
DELTAS = np.array([0.0, 0.01, 0.03, 0.05, 0.08, 0.10,
                   0.15, 0.20, 0.30, 0.50, 0.70, 1.00])
NE_CAP = 3.0
BASE = 0.10
D_IDX = {round(float(d), 3): i for i, d in enumerate(DELTAS)}
PILOT_DELTA = 0.10
# beta-hat bins for the adaptive rule (observable proxy for the regime)
BHAT_EDGES = np.array([0, 1.0, 1.5, 2.5, 4.0, np.inf])
BHAT_LABELS = ["<1.0", "1.0-1.5", "1.5-2.5", "2.5-4.0", ">4.0"]


def ne(bh, eh, gh, beta, eta, gamma):
    return np.sqrt(((bh - beta) / beta) ** 2 + ((eh - eta) / eta) ** 2
                   + ((gh - gamma) / eta) ** 2)


def load_raw_long():
    """Per-replication long table with capped NE at every delta + pilot beta-hat."""
    recs = []
    for f in sorted(glob.glob("../data/raw_n*.npz")):
        z = np.load(f)
        n = int(z["n"]); betas = z["betas"]; grs = z["grs"]; R = int(z["R"])
        bhat = z["bhat"]; ehat = z["ehat"]; ghat = z["ghat"]
        tmin = z["tmin"]; span = z["span"]
        ip = D_IDX[round(PILOT_DELTA, 3)]
        for ib, beta in enumerate(betas):
            for ig, gr in enumerate(grs):
                gamma = gr * ETA
                bp = bhat[ib, ig, ip, :]          # pilot beta-hat (R,)
                NEs = np.empty((DELTAS.size, R))
                for idl in range(DELTAS.size):
                    val = ne(bhat[ib, ig, idl], ehat[ib, ig, idl],
                             ghat[ib, ig, idl], beta, ETA, gamma)
                    val = np.where(np.isfinite(val), np.minimum(val, NE_CAP), NE_CAP)
                    NEs[idl] = val
                for r in range(R):
                    rec = dict(n=n, beta=float(beta), gr=float(gr),
                               beta_pilot=float(bp[r]) if np.isfinite(bp[r]) else np.nan,
                               tmin=float(tmin[ib, ig, r]), span=float(span[ib, ig, r]))
                    for idl, d in enumerate(DELTAS):
                        rec[f"NE_{idl}"] = float(NEs[idl, r])
                    recs.append(rec)
    return pd.DataFrame(recs)


def main():
    df = pd.concat([pd.read_csv(f) for f in sorted(glob.glob("../data/agg_n*.csv"))],
                   ignore_index=True)
    df.to_csv("../data/agg_master.csv", index=False)
    key = ["n", "beta", "gamma_over_eta"]

    # ---------- best delta per full scenario ----------
    idx = df.groupby(key)["NE_mean_capped"].idxmin()
    best = df.loc[idx, key + ["delta", "NE_mean_capped"]].rename(
        columns={"delta": "best_delta", "NE_mean_capped": "NE_best"})
    best = best.merge(df[df.delta == BASE][key + ["NE_mean_capped"]]
                      .rename(columns={"NE_mean_capped": "NE_base01"}), on=key)
    best["impr_vs01_pct"] = 100 * (best.NE_base01 - best.NE_best) / best.NE_base01
    best.to_csv("../data/best_per_scenario.csv", index=False)

    # ---------- best delta per n (one delta, averaged over scenarios) ----------
    def best_single(group_keys):
        g = (df.groupby(group_keys + ["delta"])["NE_mean_capped"]
             .mean().reset_index())
        gi = g.groupby(group_keys)["NE_mean_capped"].idxmin()
        return g.loc[gi].rename(columns={"delta": "best_delta",
                                         "NE_mean_capped": "NE_at_best"})

    best_n = best_single(["n"]).sort_values("n")
    best_n.to_csv("../data/best_per_n.csv", index=False)
    best_beta = best_single(["beta"]).sort_values("beta")
    best_beta.to_csv("../data/best_per_beta.csv", index=False)
    best_gr = best_single(["gamma_over_eta"]).sort_values("gamma_over_eta")

    # global best single delta
    g_all = df.groupby("delta")["NE_mean_capped"].mean()
    global_delta = float(g_all.idxmin()); global_ne = float(g_all.min())

    # ---------- per-rep long for adaptive evaluation ----------
    raw = load_raw_long()
    raw["bhat_bin"] = pd.cut(raw["beta_pilot"], BHAT_EDGES, labels=BHAT_LABELS,
                             right=False)
    rng = np.random.default_rng(7)
    raw["fold"] = rng.integers(0, 2, size=len(raw))   # 0=train,1=test
    NEcols = [f"NE_{i}" for i in range(DELTAS.size)]

    train = raw[raw.fold == 0]
    test = raw[raw.fold == 1]

    # Strategy NE on the TEST fold -------------------------------------------
    def test_ne_fixed(delta):
        i = D_IDX[round(float(delta), 3)]
        return float(test[f"NE_{i}"].mean())

    # per-n best learned on train, applied on test
    pern_map = {}
    for n, gtr in train.groupby("n"):
        means = gtr[NEcols].mean().values
        pern_map[n] = int(np.argmin(means))
    pern_test = np.array([test[f"NE_{pern_map[n]}"][test.n == n].sum()
                          for n in sorted(test.n.unique())]).sum() / len(test)

    # adaptive rule delta(n, bhat_bin) learned on train ----------------------
    rule_rows = []
    rule = {}
    for (n, b), gtr in train.groupby(["n", "bhat_bin"], observed=True):
        if len(gtr) < 20:
            continue
        means = gtr[NEcols].mean().values
        bi = int(np.argmin(means))
        rule[(n, b)] = bi
        rule_rows.append(dict(n=n, bhat_bin=str(b), best_delta=float(DELTAS[bi]),
                              n_train=len(gtr), NE_train=float(means[bi])))
    rule_df = pd.DataFrame(rule_rows).sort_values(["n", "bhat_bin"])
    rule_df.to_csv("../data/adaptive_rule.csv", index=False)

    # fallback for (n,bin) cells unseen in train: per-n best
    def adaptive_idx(row):
        bi = rule.get((row.n, row.bhat_bin))
        if bi is None:
            bi = pern_map.get(row.n, D_IDX[round(BASE, 3)])
        return bi

    test_idx = test.apply(adaptive_idx, axis=1).values
    adaptive_test = float(np.mean([test.iloc[k][NEcols[test_idx[k]]]
                                   for k in range(len(test))]))

    # per-scenario oracle on test (optimistic lower bound)
    oracle_rows = []
    for (n, b, gr), gte in test.groupby(["n", "beta", "gr"]):
        means = gte[NEcols].mean().values
        oracle_rows.append(means.min())
    oracle_test = float(np.mean(oracle_rows))

    base_test = test_ne_fixed(BASE)
    strat = pd.DataFrame([
        dict(strategy="fixed delta=0.1 (baseline)", NE=base_test, impr_pct=0.0),
        dict(strategy=f"global fixed delta={global_delta:g}",
             NE=test_ne_fixed(global_delta),
             impr_pct=100 * (base_test - test_ne_fixed(global_delta)) / base_test),
        dict(strategy="per-n best delta", NE=pern_test,
             impr_pct=100 * (base_test - pern_test) / base_test),
        dict(strategy="adaptive delta(n, beta-hat)", NE=adaptive_test,
             impr_pct=100 * (base_test - adaptive_test) / base_test),
        dict(strategy="per-scenario oracle (upper bound)", NE=oracle_test,
             impr_pct=100 * (base_test - oracle_test) / base_test),
    ])
    strat.to_csv("../data/strategy_compare.csv", index=False)

    # per-n strategy comparison (test fold)
    pern_rows = []
    for n in sorted(test.n.unique()):
        tn = test[test.n == n]
        b = float(tn[f"NE_{D_IDX[round(BASE,3)]}"].mean())
        pn = float(tn[f"NE_{pern_map[n]}"].mean())
        ti = tn.apply(adaptive_idx, axis=1).values
        ad = float(np.mean([tn.iloc[k][NEcols[ti[k]]] for k in range(len(tn))]))
        orac = np.mean([g[NEcols].mean().values.min()
                        for _, g in tn.groupby(["beta", "gr"])])
        pern_rows.append(dict(n=n, base01=b, per_n=pn, adaptive=ad,
                              oracle=float(orac),
                              best_delta_n=float(DELTAS[pern_map[n]])))
    pd.DataFrame(pern_rows).to_csv("../data/strategy_by_n.csv", index=False)

    headline = dict(
        n_scenarios=int(len(best)), R=int(df.R.iloc[0]),
        deltas=[float(x) for x in DELTAS],
        best_delta_counts={str(k): int(v) for k, v in
                           best.best_delta.value_counts().sort_index().items()},
        median_best_delta_by_beta={str(k): float(v) for k, v in
                                   best.groupby("beta").best_delta.median().items()},
        median_best_delta_by_n={str(int(k)): float(v) for k, v in
                                best.groupby("n").best_delta.median().items()},
        median_best_delta_by_gr={str(k): float(v) for k, v in
                                 best.groupby("gamma_over_eta").best_delta.median().items()},
        global_best_delta=global_delta, global_best_NE=global_ne,
        per_n_best={str(int(r.n)): float(r.best_delta) for r in best_n.itertuples()},
        per_beta_best={str(r.beta): float(r.best_delta) for r in best_beta.itertuples()},
        strategy_overall={r.strategy: dict(NE=float(r.NE), impr_pct=float(r.impr_pct))
                          for r in strat.itertuples()},
        mean_impr_per_scenario_pct=float(best.impr_vs01_pct.mean()),
        median_impr_per_scenario_pct=float(best.impr_vs01_pct.median()),
    )
    with open("../data/headline.json", "w") as fh:
        json.dump(headline, fh, indent=2)

    pd.set_option("display.width", 200)
    print("=== best delta per n (averaged over scenarios) ===")
    print(best_n[["n", "best_delta", "NE_at_best"]].to_string(index=False))
    print("\n=== best delta per beta ===")
    print(best_beta[["beta", "best_delta", "NE_at_best"]].to_string(index=False))
    print("\n=== best delta per gamma/eta ===")
    print(best_gr[["gamma_over_eta", "best_delta", "NE_at_best"]].to_string(index=False))
    print(f"\nglobal best single delta = {global_delta:g}  (mean cappedNE {global_ne:.4f})")
    print("\n=== strategy comparison (TEST fold) ===")
    print(strat.to_string(index=False))
    print("\n=== adaptive rule delta(n, beta-hat bin) ===")
    print(rule_df.to_string(index=False))
    print("\nper-scenario mean improvement vs 0.1: "
          f"{headline['mean_impr_per_scenario_pct']:.1f}%  "
          f"(median {headline['median_impr_per_scenario_pct']:.1f}%)")


if __name__ == "__main__":
    main()
