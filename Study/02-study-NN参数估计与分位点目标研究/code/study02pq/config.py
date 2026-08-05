"""Study/02 P-Q v2 冻结配置加载与路径。

加载 configs/pq-protocol-v2.json（FROZEN）。路径全部由本文件绝对位置派生，
不假设 C/D 盘。v1（preliminary/superseded）产物保留于 artifacts/pq/；
v2 产物写入 artifacts/pq_v2/。
"""

from __future__ import annotations

import json
import os

# .../Study/02-study-NN.../code/study02pq/config.py
STUDY02_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY02_ROOT))  # 仓库根

PROTOCOL_VERSION = "v3"
CONFIG_PATH = os.path.join(STUDY02_ROOT, "configs", "pq-protocol-v3.json")
PROTOCOL_PATH = os.path.join(STUDY02_ROOT, "01-PQ-冻结协议.md")

# r4 primary 产物目录（v1 保留于 artifacts/pq/，preliminary；
# v2/P_loggap 保留于 artifacts/pq_v2/，sensitivity，不覆盖）
ARTIFACT_DIR = os.path.join(STUDY02_ROOT, "artifacts", "pq_v3")
PREDICTIONS_DIR = os.path.join(ARTIFACT_DIR, "predictions")
CHECKPOINTS_DIR = os.path.join(ARTIFACT_DIR, "fit_metadata")   # 无模型 state，故称 fit metadata
EVIDENCE_DIR = os.path.join(ARTIFACT_DIR, "evidence")          # 压缩逐样本证据（npz，tracked）
SPLITS_MANIFEST_PATH = os.path.join(ARTIFACT_DIR, "splits_manifest.json")


def load_frozen_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


CFG = load_frozen_config()

# 便捷引用
DESIGN = CFG["design"]
SPLIT = CFG["split"]
VAL = CFG["validation"]
TRAINING = CFG["training"]
SEEDS = list(CFG["seeds"])
ROUTES = list(CFG["routes"])

BETA_GRID = list(DESIGN["beta_grid"])
ETA = float(DESIGN["eta"])
GAMMA_GRID = [float(g) for g in DESIGN["gamma_grid"]]
GAMMA_OVER_ETA_GRID = [round(g / ETA, 6) for g in GAMMA_GRID]
N_GRID = list(DESIGN["n_grid"])
REPEATS = int(DESIGN["repeats_per_combo"])
SEED_NAMESPACE = CFG["study01_alignment"]["seed_namespace"]

N_FOLDS = int(SPLIT["n_folds"])
VAL_FRACTION = float(VAL["fraction"])
X0_95_R = 0.95

EPS_PARAM = 1e-6

# 网络
HIDDEN_LAYERS = tuple(TRAINING["hidden_layers"])
LR = float(TRAINING["learning_rate"])
WEIGHT_DECAY = float(TRAINING["weight_decay"])
BATCH_SIZE = int(TRAINING["batch_size"])
MAX_EPOCHS = int(TRAINING["max_epochs"])
PATIENCE = int(TRAINING["patience"])

# Study01 权威输入（协议 §0）
STUDY01_ALIGN = CFG["study01_alignment"]


def study01_abs_path(rel: str) -> str:
    return os.path.join(PROJECT_ROOT, rel)


def combos() -> list[tuple[float, float, int]]:
    """product(beta, gamma_over_eta, n)，与 Study01 get_combo_split 枚举一致。"""
    from itertools import product
    return list(product(BETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID))


def combo_fold_of(combo: tuple[float, float, int]) -> int:
    idx = combos().index(combo)
    return idx % N_FOLDS
