"""P0 audit: mechanically classify E4d generalization data by axis."""
import pandas as pd
from pathlib import Path

artifact_dir = Path("Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E4_robustness")
df = pd.read_csv(artifact_dir / "E4d_selector_extrapolation.csv")

TRAIN_BETAS = {1.5, 2.0, 2.5, 4.0, 5.0}
TRAIN_GAMMAS = {0.1, 0.5, 1.0}
TRAIN_NS = {7, 10, 20}


def classify(row):
    beta, ge, n = row["beta"], row["gamma_over_eta"], row["n"]

    beta_in_domain = 1.5 <= beta <= 5.0
    ge_in_domain = 0.1 <= ge <= 1.0
    n_in_domain = 7 <= n <= 20

    on_beta_grid = beta in TRAIN_BETAS
    on_ge_grid = ge in TRAIN_GAMMAS
    on_n_grid = n in TRAIN_NS
    on_param_grid = on_beta_grid and on_ge_grid and on_n_grid

    # Parameter interpolation
    if beta_in_domain and ge_in_domain and n_in_domain and not on_param_grid and n in TRAIN_NS:
        return "p_interp"

    # Sample size interpolation
    if on_beta_grid and on_ge_grid and 7 <= n <= 20 and n not in TRAIN_NS:
        return "n_interp"

    p_extrap = not beta_in_domain or not ge_in_domain
    n_extrap = n < 7 or n > 20

    if p_extrap and n_extrap:
        return "multi_extrap"
    if p_extrap:
        return "p_extrap"
    if n_extrap:
        return "n_extrap"

    if on_param_grid:
        return "on_grid"
    return "p_interp"


df["gen_label"] = df.apply(classify, axis=1)

labels_order = ["p_interp", "n_interp", "p_extrap", "n_extrap", "multi_extrap", "on_grid"]
print("=== Generalization Label Distribution ===")
counts = df["gen_label"].value_counts()
for label in labels_order:
    c = counts.get(label, 0)
    print(f"  {label}: {c:>8} ({c / len(df) * 100:.1f}%)")
print(f"\nTotal: {len(df)}")

print("\n=== Per-track breakdown ===")
for track in ["E4b_boundary", "E4c_offgrid"]:
    print(f"\n--- {track} ---")
    td = df[df["track"] == track]
    for label in labels_order:
        c = len(td[td["gen_label"] == label])
        if c > 0:
            print(f"  {label}: {c:>8} ({c / len(td) * 100:.1f}%)")

print("\n=== Axis coverage analysis ===")
combos = df.groupby(["beta", "gamma_over_eta", "n", "gen_label"]).size().reset_index(name="count")
print(f"Unique (beta,ge,n) per label:")
print(combos.groupby("gen_label").size().to_string())

pi = df[df["gen_label"] == "p_interp"]
if len(pi) > 0:
    print(f"\nP-interp unique betas: {sorted(pi.beta.unique())}")
    print(f"P-interp unique ge: {sorted(pi.gamma_over_eta.unique())}")
    pc = pi.groupby(["beta", "gamma_over_eta", "n"])
    print(f"P-interp unique combos: {len(pc)}")

ni = df[df["gen_label"] == "n_interp"]
if len(ni) > 0:
    print(f"\nN-interp unique n: {sorted(ni.n.unique())}")
    nc = ni.groupby(["beta", "n"])
    print(f"N-interp unique (beta,n): {len(nc)}")

pe = df[df["gen_label"] == "p_extrap"]
if len(pe) > 0:
    print(f"\nP-extrap unique betas: {sorted(pe.beta.unique())}")
    print(f"P-extrap unique ge: {sorted(pe.gamma_over_eta.unique())}")
    print(f"P-extrap combos: {len(pe.groupby(['beta','gamma_over_eta','n']))}")

ne = df[df["gen_label"] == "n_extrap"]
if len(ne) > 0:
    print(f"\nN-extrap unique n: {sorted(ne.n.unique())}")
    print(f"N-extrap combos: {len(ne.groupby(['beta','gamma_over_eta','n']))}")

me = df[df["gen_label"] == "multi_extrap"]
if len(me) > 0:
    print(f"\nMulti-extrap combos: {len(me.groupby(['beta','gamma_over_eta','n']))}")
