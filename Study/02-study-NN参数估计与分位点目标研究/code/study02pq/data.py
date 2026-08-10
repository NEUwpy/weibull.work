"""Study/02 P-Q 数据：确定性样本重建、五折留出、validation 切分、逐位置 scaler。

样本契约：python/studies/common/sample.py 的 generate_sample(...,
seed=SEED_NAMESPACE)，与 Study01 Dimensional-RAW 完全一致。
折定义：combo_idx % 5 == fold_idx（combos = product(beta, gamma_over_eta, n)），
与 Study01 split_report.csv 一致。
"""

from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass
from typing import Optional

import numpy as np

STUDY02_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
# study02pq -> code -> 02-study-NN... -> Study -> 仓库根
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    STUDY02_CODE_DIR))))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "python"))

from studies.common.sample import generate_sample  # noqa: E402

from . import config as CFG  # noqa: E402


@dataclass
class Master:
    """48,000 样本的确定性主表。"""

    keys: np.ndarray            # (N, 4): [beta, gamma_over_eta, n, repeat_id]
    X: np.ndarray               # (N,) object: 每个 (n,) 升序原始样本 float64
    true_params: np.ndarray     # (N, 3): [beta, eta, gamma]
    x0_95: np.ndarray           # (N,)

    def idx_of(self, beta: float, goe: float, n: int, rid: int) -> int:
        m = (self.keys[:, 0] == beta) & (self.keys[:, 1] == goe) \
            & (self.keys[:, 2] == n) & (self.keys[:, 3] == rid)
        return int(np.flatnonzero(m)[0])


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_rows(row_indices: np.ndarray) -> str:
    """样本键行的规范 SHA256。"""
    return sha_bytes(row_indices.astype(np.int64).tobytes())


def sha_float_array(a: np.ndarray) -> str:
    return sha_bytes(np.ascontiguousarray(a, dtype=np.float64).tobytes())


def build_master(beta_grid=None, gamma_grid=None, n_grid=None, repeats=None,
                 seed_namespace=None) -> Master:
    """确定性重建全部样本。默认使用冻结配置。"""
    beta_grid = beta_grid or CFG.BETA_GRID
    gamma_grid = gamma_grid or CFG.GAMMA_GRID
    n_grid = n_grid or CFG.N_GRID
    repeats = repeats if repeats is not None else CFG.REPEATS
    seed_ns = seed_namespace or CFG.SEED_NAMESPACE
    eta = CFG.ETA

    keys, X_list, true_params, x0_95 = [], [], [], []
    for beta in beta_grid:
        for gamma in gamma_grid:
            goe = gamma / eta
            for n in n_grid:
                for rid in range(repeats):
                    sample = generate_sample(float(beta), float(eta), float(gamma),
                                             int(n), int(rid), seed=seed_ns)
                    s = np.asarray(sample, dtype=np.float64)
                    assert np.all(np.diff(s) >= 0), "not ascending-sorted"
                    assert len(s) == n
                    keys.append((float(beta), float(goe), float(n), int(rid)))
                    X_list.append(s)
                    true_params.append((float(beta), float(eta), float(gamma)))
                    x0_95.append(_x0_95(float(beta), float(eta), float(gamma)))
    keys = np.asarray(keys, dtype=np.float64)
    X = np.empty(len(X_list), dtype=object)
    for i, s in enumerate(X_list):
        X[i] = s
    return Master(keys=keys, X=X,
                  true_params=np.asarray(true_params, dtype=np.float64),
                  x0_95=np.asarray(x0_95, dtype=np.float64))


def _x0_95(beta: float, eta: float, gamma: float, R: float = CFG.X0_95_R) -> float:
    return gamma + eta * (-np.log(R)) ** (1.0 / beta)


def fold_combos_for_n(n: int) -> list[list[tuple]]:
    """每个 fold 的 (train_combos, test_combos) for 给定 n（combos 枚举与 Study01 一致）。"""
    combos = CFG.combos()
    per_fold = []
    for fold_idx in range(CFG.N_FOLDS):
        tr = [c for i, c in enumerate(combos) if i % CFG.N_FOLDS != fold_idx and c[2] == n]
        te = [c for i, c in enumerate(combos) if i % CFG.N_FOLDS == fold_idx and c[2] == n]
        assert len(te) == len(CFG.BETA_GRID)  # 1 goe level x all beta
        assert len(tr) == (CFG.N_FOLDS - 1) * len(CFG.BETA_GRID)
        per_fold.append((tr, te))
    return per_fold


def _match(master: Master, combos) -> np.ndarray:
    """返回 master 行索引，属于给定 (beta, goe, n) combo 列表。"""
    beta_v = np.array([c[0] for c in combos])
    goe_v = np.array([c[1] for c in combos])
    n_v = np.array([c[2] for c in combos])
    idx = []
    for b, g, nn in zip(beta_v, goe_v, n_v):
        m = (master.keys[:, 0] == b) & (master.keys[:, 1] == g) & (master.keys[:, 2] == nn)
        idx.append(np.flatnonzero(m))
    return np.concatenate(idx) if idx else np.array([], dtype=np.int64)


def _val_salt(n: int, fold_idx: int) -> int:
    h = hashlib.sha256(f"pq_val|{n}|{fold_idx}".encode()).hexdigest()[:8]
    return int(h, 16)


def split_fold(master: Master, n: int, fold_idx: int, val_fraction=None):
    """返回 (train_rows, val_rows, test_rows)（行索引，与 seed/route 无关）。

    - test_rows: 该折留出的 1 个 γ/η 水平 × 8 beta × repeats
    - train_rows: 其余 4 个 γ/η 水平 × 8 beta × repeats
    - val_rows: train_rows 的确定性 15% 子集（盐 = pq_val|n|fold）
    """
    val_fraction = val_fraction if val_fraction is not None else CFG.VAL_FRACTION
    tr_combos, te_combos = fold_combos_for_n(n)[fold_idx]
    train_rows = _match(master, tr_combos)
    test_rows = _match(master, te_combos)
    # 确定性 validation 切分（盐 = pq_val|n|fold；与 seed/route 无关）
    order = np.arange(len(train_rows))
    rng = np.random.default_rng(_val_salt(n, fold_idx))
    rng.shuffle(order)
    n_val = int(round(len(train_rows) * val_fraction))
    assert n_val > 0
    val_rows = train_rows[order[:n_val]]
    tr_final = train_rows[order[n_val:]]
    assert not set(tr_final.tolist()) & set(val_rows.tolist())
    return tr_final, val_rows, test_rows


def split_repeat_fold(master: Master, n: int, fold_idx: int):
    """同分布五折：每个参数组合都按 repeat_id 分到 train/val/test。

    test 使用 ``repeat_id % 5 == fold_idx``，validation 使用下一余数，其余为
    train。对正式 300 repeats，每个组合分别得到 180/60/60 行。
    """
    assert 0 <= fold_idx < CFG.N_FOLDS
    n_mask = master.keys[:, 2].astype(np.int64) == int(n)
    repeat_mod = master.keys[:, 3].astype(np.int64) % CFG.N_FOLDS
    test_mask = n_mask & (repeat_mod == fold_idx)
    val_mask = n_mask & (repeat_mod == ((fold_idx + 1) % CFG.N_FOLDS))
    train_mask = n_mask & ~test_mask & ~val_mask
    train_rows = np.flatnonzero(train_mask)
    val_rows = np.flatnonzero(val_mask)
    test_rows = np.flatnonzero(test_mask)
    assert not set(train_rows) & set(val_rows)
    assert not set(train_rows) & set(test_rows)
    assert not set(val_rows) & set(test_rows)
    return train_rows, val_rows, test_rows


def split_data_scale_fixed_eval(master: Master, n: int, fold_idx: int,
                                train_repeats: int, base_repeats: int = 300):
    """数据量学习曲线拆分：固定原 300 repeats 的 validation/test，只扩训练集。

    基线块 ``repeat_id < base_repeats`` 完全沿用 iid-v1 的五折规则。若需要超过
    基线每组合 180 条训练行，则从 ``repeat_id >= base_repeats`` 的独立新块中继续
    选取同一 fold 的三个训练余数类；新块只进入训练，不改变固定 validation/test。

    ``train_repeats`` 是每个 (beta, gamma/eta, n) 组合的目标训练行数；当前冻结
    pilot 使用 180/360/720，均能由完整五元组块精确构造。
    """
    assert 0 <= fold_idx < CFG.N_FOLDS
    base_train = base_repeats * (CFG.N_FOLDS - 2) // CFG.N_FOLDS
    if base_repeats % CFG.N_FOLDS != 0:
        raise ValueError("base_repeats must be divisible by n_folds")
    if train_repeats < base_train:
        raise ValueError(f"train_repeats must be >= baseline {base_train}")

    extra_needed = int(train_repeats) - int(base_train)
    train_classes = CFG.N_FOLDS - 2
    if extra_needed * CFG.N_FOLDS % train_classes != 0:
        raise ValueError("extra train repeats must correspond to complete fold blocks")
    extra_pool_size = extra_needed * CFG.N_FOLDS // train_classes
    extra_end = int(base_repeats + extra_pool_size)

    n_mask = master.keys[:, 2].astype(np.int64) == int(n)
    repeat_id = master.keys[:, 3].astype(np.int64)
    repeat_mod = repeat_id % CFG.N_FOLDS
    test_class = int(fold_idx)
    val_class = int((fold_idx + 1) % CFG.N_FOLDS)
    is_train_class = (repeat_mod != test_class) & (repeat_mod != val_class)

    base_mask = n_mask & (repeat_id < base_repeats)
    test_rows = np.flatnonzero(base_mask & (repeat_mod == test_class))
    val_rows = np.flatnonzero(base_mask & (repeat_mod == val_class))
    train_rows = np.flatnonzero(
        n_mask & is_train_class & (repeat_id < extra_end)
    )

    n_combos_for_n = len(CFG.BETA_GRID) * len(CFG.GAMMA_GRID)
    assert len(train_rows) == n_combos_for_n * int(train_repeats)
    assert len(val_rows) == n_combos_for_n * (base_repeats // CFG.N_FOLDS)
    assert len(test_rows) == n_combos_for_n * (base_repeats // CFG.N_FOLDS)
    assert not set(train_rows) & set(val_rows)
    assert not set(train_rows) & set(test_rows)
    assert not set(val_rows) & set(test_rows)
    return train_rows, val_rows, test_rows


def split_continuous_fold(master: Master, n: int, fold_idx: int):
    """S5B 连续参数五折：按预先随机排列后的 point_id 取模。

    ``build_continuous_master`` 把 Sobol 参数点按冻结随机排列写入，键的第四列是
    point_id/rank。因每个参数点只对应一个样本，本拆分不是“同参数重复”的 iid 拆分；
    train/validation/test 都是从同一连续参数分布独立覆盖的域内样本。
    """
    assert 0 <= fold_idx < CFG.N_FOLDS
    n_mask = master.keys[:, 2].astype(np.int64) == int(n)
    point_mod = master.keys[:, 3].astype(np.int64) % CFG.N_FOLDS
    test_rows = np.flatnonzero(n_mask & (point_mod == fold_idx))
    val_rows = np.flatnonzero(n_mask & (point_mod == ((fold_idx + 1) % CFG.N_FOLDS)))
    train_rows = np.flatnonzero(n_mask & ~(point_mod == fold_idx)
                                & ~(point_mod == ((fold_idx + 1) % CFG.N_FOLDS)))
    assert not set(train_rows) & set(val_rows)
    assert not set(train_rows) & set(test_rows)
    assert not set(val_rows) & set(test_rows)
    return train_rows, val_rows, test_rows


def make_arrays(master: Master, rows: np.ndarray):
    """按行索引返回 (X, params, x0_95)。X 为 (len(rows), n)。"""
    n = int(master.keys[rows[0]][2]) if len(rows) else 0
    X = np.zeros((len(rows), n), dtype=np.float64)
    for i, r in enumerate(rows):
        X[i] = master.X[int(r)]
    params = master.true_params[rows]
    x95 = master.x0_95[rows]
    return X, params, x95


def sample_min(master: Master, rows: np.ndarray) -> np.ndarray:
    """逐行 min(X)（location-scale decode 的 location 锚点）。"""
    return np.array([master.X[int(r)].min() for r in rows], dtype=np.float64)


def sample_bytes_sha(master: Master, rows: np.ndarray) -> str:
    """给定行集合的原始样本字节流 SHA256（主样本字节契约）。"""
    buf = np.concatenate([master.X[int(r)] for r in rows])
    return sha_bytes(np.ascontiguousarray(buf, dtype=np.float64).tobytes())


class PerPositionScaler:
    """逐位置 StandardScaler；fit 仅用训练折（含其内部 validation 行），
    test 折绝不参与。P/Q 共用同一实例，故参数 SHA 一致。"""

    def __init__(self):
        self.mean_ = None
        self.scale_ = None

    def fit(self, X: np.ndarray):
        X = np.asarray(X, dtype=np.float64)
        self.mean_ = X.mean(axis=0)
        self.scale_ = X.std(axis=0)
        self.scale_ = np.where(self.scale_ == 0.0, 1.0, self.scale_)
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        return (np.asarray(X, dtype=np.float64) - self.mean_) / self.scale_

    def params_sha(self) -> str:
        return sha_bytes(self.mean_.tobytes() + self.scale_.tobytes())


def verify_integrity(master: Master):
    """规模自检（协议 §2.2）。"""
    assert len(master.keys) == CFG.DESIGN["n_samples"] == 48000
    assert len(master.X) == 48000
    n_combos = len({(k[0], k[1], k[2]) for k in master.keys})
    assert n_combos == 160, n_combos
    # 每组合 repeats 计数
    rep_counts = {}
    for k in master.keys:
        rep_counts[(k[0], k[1], k[2])] = rep_counts.get((k[0], k[1], k[2]), 0) + 1
    assert all(c == CFG.REPEATS for c in rep_counts.values())
    # must-include 组合 (beta=2, eta=1000, gamma=1000) → goe=1.0
    mi = CFG.DESIGN["must_include_combo"]
    assert np.any((master.keys[:, 0] == mi["beta"]) &
                  (np.isclose(master.keys[:, 1], mi["gamma"] / CFG.ETA)))
    return {
        "n_samples": int(len(master.keys)),
        "n_combos": int(n_combos),
        "repeats_ok": True,
    }
