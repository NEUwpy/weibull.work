"""P2 formal frozen configuration — minimal orthogonal generalization fill.

All values freeze the P2 design from 07-剩余实验目标与规划.md §P2.
Do NOT modify without authorization — this is the sole config authority for P2.
"""

# P2-NI: pure sample-size interpolation (n=15, training-grid params)
P2_NI_BETAS = [1.5, 2.0, 2.5, 4.0, 5.0]
P2_NI_GAMMA_OVER_ETA = [0.1, 0.5, 1.0]
P2_NI_N = [15]

# P2-PI: pure parameter interpolation (non-grid params, training n)
P2_PI_BETAS = [1.75, 2.25, 3.25, 4.50]
P2_PI_GAMMA_OVER_ETA = [0.30, 0.75]
P2_PI_N = [7, 10, 20]

# Shared
ETA = 1.0
REPEATS = 1000

# Delta grid (identical to existing 26-point grid from config.py)
DELTA_GRID = [round(0.00 + 0.02 * i, 2) for i in range(26)]

# Seed namespace
SEED_NAMESPACE = "study01_p2_v1"

# Output.  The original ``p2_generalization`` directory is a preserved,
# invalid v1 run produced with Python's process-randomized ``hash()``.
OUTPUT_DIR_NAME = "extended_validation/p2_generalization_v2"
INVALID_V1_OUTPUT_DIR_NAME = "extended_validation/p2_generalization"

# Formal execution remains sealed until Codex binds an exact clean commit.
P2_FORMAL_AUTHORIZED = True
P2_APPROVED_PARENT_COMMIT = "5156fd31604a805f4ddfa793ad08fa348f7b1923"
P2_RUN_ID = "study01-p2-v2"

# Vector-MLP reconstruction
VECTOR_MLP_FOLDS = 5
VECTOR_MLP_SEEDS = [42, 2026, 3407]

# Expected counts
P2_NI_COMBOS = len(P2_NI_BETAS) * len(P2_NI_GAMMA_OVER_ETA) * len(P2_NI_N)  # 15
P2_PI_COMBOS = len(P2_PI_BETAS) * len(P2_PI_GAMMA_OVER_ETA) * len(P2_PI_N)  # 24
P2_TOTAL_COMBOS = P2_NI_COMBOS + P2_PI_COMBOS  # 39
P2_TOTAL_SAMPLES = P2_TOTAL_COMBOS * REPEATS  # 39,000
P2_TOTAL_DELTA_EVALS = P2_TOTAL_SAMPLES * len(DELTA_GRID)  # 1,014,000


def build_p2_combos():
    """Build complete P2 combo list: [(track, beta, gamma_over_eta, n), ...]"""
    combos = []
    for beta in P2_NI_BETAS:
        for ge in P2_NI_GAMMA_OVER_ETA:
            for n_ in P2_NI_N:
                combos.append(("P2-NI", beta, ge, n_))
    for beta in P2_PI_BETAS:
        for ge in P2_PI_GAMMA_OVER_ETA:
            for n_ in P2_PI_N:
                combos.append(("P2-PI", beta, ge, n_))
    return combos


def validate_p2_counts():
    """Fail-closed: verify exact P2 counts."""
    combos = build_p2_combos()
    ni = [c for c in combos if c[0] == "P2-NI"]
    pi = [c for c in combos if c[0] == "P2-PI"]
    assert len(ni) == P2_NI_COMBOS, f"P2-NI: {len(ni)} != {P2_NI_COMBOS}"
    assert len(pi) == P2_PI_COMBOS, f"P2-PI: {len(pi)} != {P2_PI_COMBOS}"
    assert len(combos) == P2_TOTAL_COMBOS, f"total: {len(combos)} != {P2_TOTAL_COMBOS}"
    assert P2_TOTAL_SAMPLES == 39000
    assert P2_TOTAL_DELTA_EVALS == 1014000
    assert REPEATS == 1000
    assert len(DELTA_GRID) == 26
    assert SEED_NAMESPACE == "study01_p2_v1"
    return True


# J1 formula (from 02-实验协议.md §4.1):
# J1 = sqrt(mean_i[(beta_hat_i-beta_i)/beta_i)^2 + ((eta_hat_i-eta_i)/eta_i)^2 + ((gamma_hat_i-gamma_i)/eta_i)^2])
# NO division by 3. Pooled from all per-sample squared errors.


def compute_j1(loss_components):
    """Compute J1 from per-sample squared error components.
    
    loss_components: array of e_b^2 + e_e^2 + e_g^2 per sample
    Returns J1 = sqrt(mean(loss_components))
    """
    import numpy as np
    return float(np.sqrt(np.mean(loss_components)))


def compute_j1_squared(bh, beta, eh, eta_val, gh, gamma):
    """Compute per-sample squared error component for J1."""
    e_b = (bh - beta) / beta
    e_e = (eh - eta_val) / eta_val
    e_g = (gh - gamma) / eta_val
    return e_b**2 + e_e**2 + e_g**2


# Default and L1 delta values for reference comparison
DEFAULT_DELTA = 0.1
L1_DELTA = 0.08
