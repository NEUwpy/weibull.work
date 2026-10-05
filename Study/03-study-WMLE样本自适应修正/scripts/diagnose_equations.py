"""Descriptive equation diagnostics; truth-dependent quantities are not deployable inputs."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
STUDY = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(STUDY.parents[1] / "python")]
from methods.wmle import get_weight_j1, get_weight_j2, get_weight_j3
from studies.common.sample import generate_sample


def quantities(x, b, g):
    z = x-g
    logz = np.log(z)
    weights = np.exp(b*(logz-logz.max()))
    term1 = get_weight_j2(len(x))/b + logz.mean() - np.sum(weights*logz)/weights.sum()
    required_j3 = np.mean(1/z)*weights.sum()/np.sum(weights/z)
    term2 = required_j3-get_weight_j3(len(x), b)
    scale = np.exp((np.log(np.mean(np.exp(b*(logz-logz.max())))/get_weight_j1(len(x))))/b+logz.max())
    return dict(term1=term1, term2=term2, required_j3=required_j3,
                tabulated_j3=get_weight_j3(len(x),b), scale_from_equation=scale,
                objective_recomputed=term1**2+term2**2)


def main():
    dest = STUDY / "results/analysis_v1"
    data = pd.read_csv(dest / "all_case_rows.csv")
    rows = []
    for r in data.itertuples():
        x = generate_sample(float(r.beta), float(r.eta), float(r.gamma),
                            int(r.sample_size), int(r.repeat_id), seed=int(r.seed_namespace))
        assert abs(x.min()-r.sample_min) < 1e-7
        truth = quantities(x, r.beta, r.gamma)
        row = {name:getattr(r,name) for name in ["cohort","beta","eta","gamma","sample_size","repeat_id","valid","E"]}
        row.update({"truth_"+k:v for k,v in truth.items()})
        row.update(gap1_over_range=(x[1]-x[0])/np.ptp(x),
                   gap2_over_range=(x[2]-x[1])/np.ptp(x),
                   largest_gap_over_range=np.diff(x).max()/np.ptp(x))
        if r.valid:
            fitted = quantities(x, r.beta_hat, r.gamma_hat)
            assert fitted["objective_recomputed"] <= 1.01e-8
            assert np.isclose(fitted["scale_from_equation"],r.eta_hat,rtol=1e-9)
            row.update({"fit_"+k:v for k,v in fitted.items()})
        rows.append(row)
    d = pd.DataFrame(rows)
    d.to_csv(dest / "equation_diagnostics.csv",index=False,encoding="utf-8-sig")
    groups = []
    for key,g in d.groupby(["cohort","beta","eta","gamma","sample_size"]):
        groups.append(dict(zip(["cohort","beta","eta","gamma","sample_size"],key)) |
                      dict(required_j3_p05=g.truth_required_j3.quantile(.05),
                           required_j3_median=g.truth_required_j3.median(),
                           required_j3_p95=g.truth_required_j3.quantile(.95),
                           tabulated_j3=g.truth_tabulated_j3.iloc[0],
                           term1_truth_sd=g.truth_term1.std()))
    pd.DataFrame(groups).to_csv(dest / "equation_summary.csv",index=False,encoding="utf-8-sig")
    target = d[d.cohort.eq("historical_complete") & d.beta.eq(2) & d.eta.eq(1000) &
               d.gamma.eq(500) & d.sample_size.eq(7)]
    example=target[target.repeat_id.eq(46)].iloc[0]
    percentile={f:float((target[f]<=example[f]).mean()) for f in
                ["gap1_over_range","gap2_over_range","largest_gap_over_range","truth_required_j3"]}
    print("example",example.to_dict())
    print("within-50 empirical percentiles",percentile)
    print("same-cell J3 truth quantiles",target.truth_required_j3.quantile([.05,.5,.95]).to_dict())
    v=data[data.valid]
    cor=[]
    for k,g in v.groupby(["cohort","beta","eta","gamma","sample_size"]):
        cor.append(dict(zip(["cohort","beta","eta","gamma","sample_size"],k)) |
                   dict(beta_eta=g.e_beta.corr(g.e_eta,method="spearman"),
                        eta_gamma=g.e_eta.corr(g.e_gamma,method="spearman"),
                        beta_gamma=g.e_beta.corr(g.e_gamma,method="spearman")))
    c=pd.DataFrame(cor)
    c.to_csv(dest / "parameter_error_correlations.csv",index=False,encoding="utf-8-sig")
    print("controlled median within-cell error correlations",c[c.cohort.eq("controlled_20260922")][["beta_eta","eta_gamma","beta_gamma"]].median().to_dict())


if __name__ == "__main__":
    main()
