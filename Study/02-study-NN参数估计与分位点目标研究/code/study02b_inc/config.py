"""Frozen configuration for the Study02 B incremental experiment.

This file IS the frozen post-benchmark matrix. Any change to these constants
changes ``CONFIG_HASH`` and therefore requires a new run-id.

Estimand (frozen, see task contract): paired relative RMSE improvement
I = (RMSE_P - RMSE_D) / RMSE_P for x_{0.95}, unchanged from B4.

Per-route training rules are kept exactly as the approved B runs:
- P:      A-E1 core_continuous distribution (log-uniform beta/eta, uniform rho),
          100 k train rows, joint m12 [256,128,64], SiLU, dropout 0.1,
          loss transformed_train_z_huber, 100/50/40 epoch contract, 10 seeds.
- D:      B3 distribution (uniform beta/eta/rho), 100 k train rows,
          selected [64,32], SiLU, dropout 0.1, huber, 500/50/40, 10 seeds.
- Dctrl:  same as D but [256,128,64] (A's m12 backbone), 5 seeds.

Existing checkpoints (n in {5,7,10,15,20}) are reused read-only; only missing
n values are trained. Test/evaluation uses the exact B4 seed scheme for the
shared n so the dense-n core reproduces B4 numbers on those n.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[4]
EXTERNAL_ROOT = Path("C:/weibull-runs/study02/b-inc")

# The first incremental run (BINC-20260802-01) is SUPERSEDED by the corrected
# run: its P evidence is invalid (missing the A-E1 input scaler). Its D/Dctrl
# checkpoints and eval row-level D/traditional outputs are reused read-only.
SUPERSEDED_RUNS = [Path("C:/weibull-runs/study02/b-inc/BINC-20260802-01")]

# Existing (approved, read-only) artifacts
P_CHECKPOINT_BASE = Path(
    "C:/weibull-runs/study02/artifacts/A-E1/A-E1-formal-r5-20260727-222417"
)
P_PLAN_PATH = P_CHECKPOINT_BASE / "plan.jsonl"
P_OUTPUTS = P_CHECKPOINT_BASE / "outputs"
B3_MANIFEST_PATH = Path(
    "C:/weibull-runs/study02/formal-b/B3-training-20260731-121958/manifest.json"
)
B4_CORE_MANIFEST_PATH = Path(
    "C:/weibull-runs/study02/formal-b/B4-core-20260801-051119/manifest.json"
)

# ----------------------------------------------------------------------------
# n grid
# ----------------------------------------------------------------------------
N_VALUES = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 25, 30]
N_EXISTING = [5, 7, 10, 15, 20]  # frozen checkpoints exist for these
N_MISSING = [n for n in N_VALUES if n not in N_EXISTING]

# ----------------------------------------------------------------------------
# Training data rules (per route)
# ----------------------------------------------------------------------------
N_TRAIN = 100_000
N_VAL = 20_000

# P follows the A-E1 design EXACTLY (see study02b_inc.a_data): scrambled-Sobol
# parameter points (design ns 220201 train / 220202 val), sample ns
# 320201 train / 320202 val, 100k train rows, 256x50 validation rows, and
# training-only per-position input scaler (zero-sd -> 0). A-E1 ranges below.
P_BETA_RANGE = (1.2, 4.0)
P_ETA_RANGE = (100.0, 10000.0)
P_RHO_RANGE = (0.0, 1.0)
P_A_TRAIN_DESIGN_NS = 220201
P_A_TRAIN_SAMPLE_NS = 320201
P_A_VAL_DESIGN_NS = 220202
P_A_VAL_SAMPLE_NS = 320202
P_A_VAL_POINTS = 256
P_A_VAL_REPEATS = 50

# D / Dctrl (B3): uniform beta/eta/rho. Seed scheme identical to B3.
D_PARAM_SEED_BASE = 100            # per-n: n * 100 + 1  (B3 scheme)
D_SAMPLE_NS_TRAIN = 4000
D_SAMPLE_NS_VAL = 5000

# Fit seed namespaces (identical to the approved runs).
P_FIT_SEEDS = list(range(420101, 420111))   # 10 seeds, matches A-E1
D_FIT_SEEDS = list(range(101, 111))         # 10 seeds, matches B3 selected
DCTRL_FIT_SEEDS = list(range(201, 206))     # 5 seeds, matches B3 controlled

# Architectures / training hyperparameters (identical to approved runs).
P_WIDTHS = [256, 128, 64]
D_SELECTED_WIDTHS = [64, 32]
DCTRL_WIDTHS = [256, 128, 64]
ACTIVATION = "silu"
DROPOUT = 0.1
P_EPOCHS = dict(max_epochs=100, min_epochs=50, patience=40)   # approved A-E1
D_EPOCHS = dict(max_epochs=500, min_epochs=50, patience=40)   # approved B3
LOSS_P = "transformed_train_z_huber"
LOSS_D = "huber"
LR = 1e-3
WEIGHT_DECAY = 1e-4
BATCH_SIZE = 512

# ----------------------------------------------------------------------------
# Dense-n core evaluation (reuses the exact B4 core design)
# ----------------------------------------------------------------------------
CORE_N_CLUSTERS = 64
CORE_N_REPLICATES = 20
CORE_SOBOL_SCRAMBLE = 42
CORE_SOBOL_M = 6
CORE_SAMPLE_NS = 6000
CORE_BETA_RANGE = (1.2, 4.0)
CORE_ETA_RANGE = (100.0, 10000.0)
CORE_RHO_RANGE = (0.0, 1.0)

# ----------------------------------------------------------------------------
# Parameter grid (transition surface), within/boundary of training support
# ----------------------------------------------------------------------------
# beta: log-spaced inside support + a few near-boundary points.
PG_BETA = [0.9, 1.1, 1.2, 1.35, 1.5, 1.7, 1.9, 2.1, 2.4, 2.7, 3.0, 3.3, 3.6, 4.0, 4.4]
PG_RHO = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
PG_ETA = 1000.0
PG_N = [5, 6, 7, 8, 9, 10, 12, 15, 20]
# Frozen post-benchmark value: 15 beta x 6 rho x 9 n x 360 draws = 291,600
# datasets (plus eta-sweep cells). Sizes the total run to ~20 sequential
# hours given measured eval throughput ~132 ms/dataset and training ~7.5 h.
PG_DRAWS = 360
PG_SAMPLE_NS = 7000           # common-random-numbers draw namespace (seed = 7000 + d)

# eta scale-equivalence validity check cells (beta x rho x n x eta).
PG_ETA_SWEEP = {
    "beta": [1.5, 3.0],
    "rho": [0.5],
    "n": [5, 10],
    "eta": [100.0, 1000.0, 10000.0],
}

# ----------------------------------------------------------------------------
# Bootstrap / analysis
# ----------------------------------------------------------------------------
N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = 42

# ----------------------------------------------------------------------------
# Config hash (the frozen matrix fingerprint)
# ----------------------------------------------------------------------------
def config_hash() -> str:
    payload = {
        "n_values": N_VALUES,
        "n_existing": N_EXISTING,
        "n_train": N_TRAIN,
        "n_val": N_VAL,
        "p": {
            "widths": P_WIDTHS, "activation": ACTIVATION, "dropout": DROPOUT,
            "epochs": P_EPOCHS, "loss": LOSS_P, "lr": LR,
            "weight_decay": WEIGHT_DECAY, "batch_size": BATCH_SIZE,
            "fit_seeds": P_FIT_SEEDS,
            "a_data": {
                "train_design_ns": P_A_TRAIN_DESIGN_NS,
                "train_sample_ns": P_A_TRAIN_SAMPLE_NS,
                "val_design_ns": P_A_VAL_DESIGN_NS,
                "val_sample_ns": P_A_VAL_SAMPLE_NS,
                "val_points": P_A_VAL_POINTS,
                "val_repeats": P_A_VAL_REPEATS,
                "scaler": "per-position mean/sd ddof=0, zero-sd->0, training-only",
            },
        },
        "d": {
            "widths": D_SELECTED_WIDTHS, "epochs": D_EPOCHS, "loss": LOSS_D,
            "fit_seeds": D_FIT_SEEDS, "param_seed_base": D_PARAM_SEED_BASE,
            "sample_ns_train": D_SAMPLE_NS_TRAIN, "sample_ns_val": D_SAMPLE_NS_VAL,
        },
        "dctrl": {"widths": DCTRL_WIDTHS, "epochs": D_EPOCHS, "loss": LOSS_D,
                  "fit_seeds": DCTRL_FIT_SEEDS},
        "core": {
            "n_clusters": CORE_N_CLUSTERS, "n_replicates": CORE_N_REPLICATES,
            "sob_scramble": CORE_SOBOL_SCRAMBLE, "sob_m": CORE_SOBOL_M,
            "sample_ns": CORE_SAMPLE_NS,
        },
        "param_grid": {
            "beta": PG_BETA, "rho": PG_RHO, "eta": PG_ETA, "n": PG_N,
            "draws": PG_DRAWS, "sample_ns": PG_SAMPLE_NS,
            "eta_sweep": PG_ETA_SWEEP,
        },
        "bootstrap": {"n": N_BOOTSTRAP, "seed": BOOTSTRAP_SEED},
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


CONFIG_HASH = config_hash()
