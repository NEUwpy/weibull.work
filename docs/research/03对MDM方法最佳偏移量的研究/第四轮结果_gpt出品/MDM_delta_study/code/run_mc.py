"""
run_mc.py — Monte Carlo driver for the MDM gradient-offset (delta) study.

Runs one sample size n per invocation (keeps each run bounded on a 1-CPU box):

    python run_mc.py <n> [R]

For each (beta, gamma/eta) scenario it draws R Weibull samples and, from a
single profiled sigma_min(gamma) curve per sample, reads off the estimates
for every delta. Saves:
    ../data/raw_n{n}.npz   raw per-replication estimates
    ../data/agg_n{n}.csv   aggregated metrics, one row per (n,beta,gr,delta)

eta is fixed at 100 (scale invariance verified separately).
"""
import sys, time, json
import numpy as np
import pandas as pd
from mdm_core import sample_weibull3, estimate_mdm

ETA = 100.0
BETAS = np.array([0.8, 1.2, 2.0, 3.0, 5.0])
GRS = np.array([0.0, 0.05, 0.1, 0.2, 0.5])          # gamma/eta
DELTAS = np.array([0.0, 0.01, 0.03, 0.05, 0.08, 0.10,
                   0.15, 0.20, 0.30, 0.50, 0.70, 1.00])
N_GAMMA = 220
NE_CAP = 3.0
BETA_LO, BETA_HI = 0.105, 28.5   # rails of the inner beta grid [0.1, 30]


def normalized_error(bh, eh, gh, beta, eta, gamma):
    return np.sqrt(((bh - beta) / beta) ** 2
                   + ((eh - eta) / eta) ** 2
                   + ((gh - gamma) / eta) ** 2)


def is_anomaly(bh, eh, gh, ne, t_min, eta):
    bad = ~np.isfinite(bh) | ~np.isfinite(eh) | ~np.isfinite(gh)
    bad |= (bh <= BETA_LO) | (bh >= BETA_HI)
    bad |= (eh <= 0) | (eh > 10 * eta)
    bad |= (gh >= t_min)
    bad |= ~np.isfinite(ne) | (ne > 5.0)
    return bad


def run_for_n(n: int, R: int, seed0: int = 20240):
    nb, ng, nd = BETAS.size, GRS.size, DELTAS.size
    ghat = np.full((nb, ng, nd, R), np.nan)
    bhat = np.full((nb, ng, nd, R), np.nan)
    ehat = np.full((nb, ng, nd, R), np.nan)
    strict = np.zeros((nb, ng, nd, R), dtype=bool)
    tmin = np.full((nb, ng, R), np.nan)
    span = np.full((nb, ng, R), np.nan)
    gamma0 = np.full((nb, ng, R), np.nan)
    has_flank = np.zeros((nb, ng, R), dtype=bool)

    t0 = time.time()
    for ib, beta in enumerate(BETAS):
        for ig, gr in enumerate(GRS):
            gamma = gr * ETA
            # independent stream per scenario; reproducible
            rng = np.random.default_rng((seed0, n, ib, ig))
            for r in range(R):
                t = sample_weibull3(beta, ETA, gamma, n, rng)
                tmin[ib, ig, r] = t[0]
                span[ib, ig, r] = t[-1] - t[0]
                try:
                    res = estimate_mdm(t, DELTAS, n_gamma=N_GAMMA)
                    gamma0[ib, ig, r] = res.get("gamma0", np.nan)
                    has_flank[ib, ig, r] = res.get("has_right_flank", False)
                    for idl, d in enumerate(DELTAS):
                        rr = res[float(d)]
                        ghat[ib, ig, idl, r] = rr["gamma_hat"]
                        bhat[ib, ig, idl, r] = rr["beta_hat"]
                        ehat[ib, ig, idl, r] = rr["eta_hat"]
                        strict[ib, ig, idl, r] = rr["strict_root"]
                except Exception:
                    pass
        print(f"  n={n} beta={beta:g} done  ({time.time()-t0:.1f}s)", flush=True)

    np.savez_compressed(
        f"../data/raw_n{n}.npz",
        n=n, R=R, eta=ETA, betas=BETAS, grs=GRS, deltas=DELTAS,
        ghat=ghat, bhat=bhat, ehat=ehat, strict=strict,
        tmin=tmin, span=span, gamma0=gamma0, has_flank=has_flank,
    )

    # ---- aggregate ----
    rows = []
    for ib, beta in enumerate(BETAS):
        for ig, gr in enumerate(GRS):
            gamma = gr * ETA
            tm = tmin[ib, ig]              # (R,)
            sp = span[ib, ig]
            for idl, d in enumerate(DELTAS):
                bh = bhat[ib, ig, idl]
                eh = ehat[ib, ig, idl]
                gh = ghat[ib, ig, idl]
                ne = normalized_error(bh, eh, gh, beta, ETA, gamma)
                anom = is_anomaly(bh, eh, gh, ne, tm, ETA)
                clean = ~anom
                nclean = int(clean.sum())

                def cstat(arr, fn):
                    a = arr[clean]
                    return float(fn(a)) if a.size else np.nan

                ne_capped = np.where(np.isfinite(ne), np.minimum(ne, NE_CAP), NE_CAP)
                hug = (tm - gh) / np.where(sp > 0, sp, np.nan)

                row = dict(
                    n=n, beta=beta, gamma_over_eta=gr, gamma=gamma, eta=ETA,
                    delta=float(d), R=R, n_anom=int(anom.sum()),
                    anom_rate=float(anom.mean()),
                    strict_rate=float(strict[ib, ig, idl].mean()),
                    has_flank_rate=float(has_flank[ib, ig].mean()),
                    # gamma
                    gamma_bias=cstat(gh, lambda a: np.mean(a - gamma)),
                    gamma_mae=cstat(gh, lambda a: np.mean(np.abs(a - gamma))),
                    gamma_rmse=cstat(gh, lambda a: np.sqrt(np.mean((a - gamma) ** 2))),
                    gamma_std=cstat(gh, lambda a: np.std(a, ddof=1) if a.size > 1 else np.nan),
                    gamma_medae=cstat(gh, lambda a: np.median(np.abs(a - gamma))),
                    # beta
                    beta_bias=cstat(bh, lambda a: np.mean(a - beta)),
                    beta_mae=cstat(bh, lambda a: np.mean(np.abs(a - beta))),
                    beta_rmse=cstat(bh, lambda a: np.sqrt(np.mean((a - beta) ** 2))),
                    # eta
                    eta_bias=cstat(eh, lambda a: np.mean(a - ETA)),
                    eta_mae=cstat(eh, lambda a: np.mean(np.abs(a - ETA))),
                    eta_rmse=cstat(eh, lambda a: np.sqrt(np.mean((a - ETA) ** 2))),
                    # normalized error
                    NE_mean_clean=cstat(ne, np.mean),
                    NE_mean_capped=float(np.mean(ne_capped)),
                    NE_median=float(np.nanmedian(ne)),
                    NE_p90=float(np.nanpercentile(ne, 90)),
                    # t_min hugging
                    hug_rate=float(np.nanmean(hug < 0.02)),
                    hug_median=float(np.nanmedian(hug)),
                    n_clean=nclean,
                )
                rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(f"../data/agg_n{n}.csv", index=False)
    print(f"n={n}: saved raw + agg ({len(df)} rows) in {time.time()-t0:.1f}s")
    return df


if __name__ == "__main__":
    n = int(sys.argv[1])
    R = int(sys.argv[2]) if len(sys.argv) > 2 else 250
    run_for_n(n, R)
