"""Study/02 P-Q 训练：单 fit（P/Q 共用），确定性、可续接、含配对 SHA。

对固定 (n, fold, seed, route)：
  - torch.manual_seed(seed) + torch.Generator(seed) 决定初始化与 batch 顺序；
  - scaler 仅 fit 训练折（train+val，共 9600 行），test 折不参与；
  - early stopping 用 validation loss（同 route 的损失），patience=20；
  - checkpoint 选择 validation loss 最低的 epoch；
  - 输出 fit 指标、逐样本 held-out 预测、配对 SHA（初始参数/batch 顺序）。
"""

from __future__ import annotations

import copy
import json
import os
import time

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

from . import config as CFG
from . import data as DATA
from . import losses as LOSS
from . import model as MODEL

torch.set_num_threads(1)


def fit_id(n: int, fold_idx: int, seed: int, route: str) -> str:
    return f"n{n}_f{fold_idx + 1}_s{seed}_r{route.upper()}"


def _tensor(x: np.ndarray) -> torch.Tensor:
    return torch.tensor(np.ascontiguousarray(x), dtype=torch.float64)


def _epoch_perm(n_rows: int, generator: torch.Generator) -> np.ndarray:
    return torch.randperm(n_rows, generator=generator).numpy()


def train_one_fit(n: int, fold_idx: int, seed: int, route: str, master: DATA.Master,
                  max_epochs=None, batch_size=None, patience=None,
                  initial_state=None, include_initial=False, return_state=False,
                  learning_rate=None, split_strategy="gamma_holdout"):
    """训练一个 (n, fold, seed, route) 模型并在 held-out 折上评价。

    返回 dict（指标、预测 numpy、配对 SHA、元数据）。不写盘；由调用方负责 checkpoint。
    """
    route = route.upper()
    max_epochs = max_epochs or CFG.MAX_EPOCHS
    batch_size = batch_size or CFG.BATCH_SIZE
    patience = patience or CFG.PATIENCE

    # ---- 确定性种子（初始参数 + batch 顺序共用） ----
    torch.manual_seed(seed)
    gen = torch.Generator().manual_seed(seed)

    # ---- 数据行（与 seed/route 无关） ----
    if split_strategy == "gamma_holdout":
        train_rows, val_rows, test_rows = DATA.split_fold(master, n, fold_idx)
    elif split_strategy == "repeat_stratified":
        train_rows, val_rows, test_rows = DATA.split_repeat_fold(master, n, fold_idx)
    else:
        raise ValueError(f"unknown split_strategy {split_strategy!r}")
    X_tr, P_tr, X95_tr = DATA.make_arrays(master, train_rows)
    X_val, P_val, X95_val = DATA.make_arrays(master, val_rows)
    X_te, P_te, X95_te = DATA.make_arrays(master, test_rows)
    min_x_tr = DATA.sample_min(master, train_rows)
    min_x_val = DATA.sample_min(master, val_rows)
    min_x_te = DATA.sample_min(master, test_rows)

    # ---- scaler：仅训练折（train+val）拟合；test 折绝不参与 ----
    # 历史 r4 保持原合同；纠偏后的同分布主实验严格只用 train 拟合 scaler。
    scaler_fit_X = np.vstack([X_tr, X_val]) if split_strategy == "gamma_holdout" else X_tr
    scaler = DATA.PerPositionScaler().fit(scaler_fit_X)
    X_tr_s = scaler.transform(X_tr)
    X_val_s = scaler.transform(X_val)
    X_te_s = scaler.transform(X_te)

    # ---- 模型与损失 ----
    model = MODEL.build_model(n, seed)
    if initial_state is not None:
        model.load_state_dict(copy.deepcopy(initial_state))
    init_sha = MODEL.params_sha(model)
    net_sha = MODEL.structure_signature(n)
    loss_fn, target_kind = LOSS.build_route_loss(route)

    if target_kind == "params":
        y_tr = _tensor(P_tr); y_val = _tensor(P_val)
    else:
        y_tr = _tensor(X95_tr); y_val = _tensor(X95_val)

    X_tr_t = _tensor(X_tr_s); X_val_t = _tensor(X_val_s)
    min_x_tr_t = _tensor(min_x_tr); min_x_val_t = _tensor(min_x_val)

    # ---- batch 顺序（epoch 1 的置换 SHA，确定性） ----
    perm = _epoch_perm(len(X_tr), gen)
    batch_order_sha = DATA.sha_bytes(perm.astype(np.int64).tobytes())

    lr = CFG.LR if learning_rate is None else float(learning_rate)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=CFG.WEIGHT_DECAY)
    best_val = float("inf")
    best_state = None
    best_epoch = 0
    patience_counter = 0
    stopped_epoch = 0
    nan_flag = False
    t0 = time.time()
    last_epoch_loss = float("nan")

    # 续训实验把共同起点作为 epoch 0 候选，避免目标切换把已有模型训练坏。
    if include_initial:
        model.eval()
        with torch.no_grad():
            val_out = model(X_val_t)
            best_val = float(loss_fn(val_out, y_val, min_x_val_t))
        best_state = copy.deepcopy(model.state_dict())
        model.train()

    for epoch in range(1, max_epochs + 1):
        if epoch > 1:
            perm = _epoch_perm(len(X_tr), gen)
        model.train()
        epoch_loss_sum = 0.0
        n_seen = 0
        for b0 in range(0, len(perm), batch_size):
            idx = perm[b0:b0 + batch_size]
            xb = X_tr_t[idx]
            yb = y_tr[idx]
            mxb = min_x_tr_t[idx]
            optimizer.zero_grad()
            out = model(xb)
            loss = loss_fn(out, yb, mxb)
            if not torch.isfinite(loss):
                nan_flag = True
                break
            loss.backward()
            optimizer.step()
            epoch_loss_sum += float(loss.detach()) * len(idx)
            n_seen += len(idx)
        last_epoch_loss = epoch_loss_sum / max(n_seen, 1)

        model.eval()
        with torch.no_grad():
            val_out = model(X_val_t)
            val_loss = float(loss_fn(val_out, y_val, min_x_val_t))
        model.train()
        stopped_epoch = epoch

        if val_loss < best_val - 1e-12:
            best_val = val_loss
            best_state = copy.deepcopy(model.state_dict())
            best_epoch = epoch
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                break
        if nan_flag:
            break

    runtime_s = time.time() - t0
    converged = not nan_flag and best_state is not None
    model.load_state_dict(best_state if best_state is not None else model.state_dict())

    # ---- held-out 评价 ----
    model.eval()
    with torch.no_grad():
        min_x_te_t = _tensor(min_x_te)
        out_te = model(_tensor(X_te_s))
        b_hat, e_hat, g_hat = LOSS.decode_params(out_te, min_x_te_t)
        x95_hat = LOSS.weibull_quantile(b_hat, e_hat, g_hat)
        x95_hat_np = x95_hat.numpy()
        b_hat_np = b_hat.numpy(); e_hat_np = e_hat.numpy(); g_hat_np = g_hat.numpy()

    rel_err = (x95_hat_np - X95_te) / X95_te
    rrmse = float(np.sqrt(np.mean(rel_err ** 2)))
    n_nonfinite = int(np.sum(~np.isfinite(x95_hat_np)))
    n_illegal = int(np.sum(~(b_hat_np > 0) | ~(e_hat_np > 0) | ~np.isfinite(g_hat_np)))
    # 支撑合法性（production test，结构性保证）：gamma_hat < min(X) 必须对所有 held-out 样本成立
    n_support_viol = int(np.sum(g_hat_np >= min_x_te - 1e-9))
    assert n_support_viol == 0, \
        f"support legality violated for {n_support_viol} held-out samples (gamma_hat >= min(X))"
    # 参数相对误差诊断（非成功标准）
    rel_b = (b_hat_np - P_te[:, 0]) / P_te[:, 0]
    rel_e = (e_hat_np - P_te[:, 1]) / P_te[:, 1]
    rel_g = (g_hat_np - P_te[:, 2]) / P_te[:, 2]

    predictions = {
        "keys": master.keys[test_rows],
        "beta_hat": b_hat_np, "eta_hat": e_hat_np, "gamma_hat": g_hat_np,
        "x95_hat": x95_hat_np, "x95_true": X95_te,
        "min_x": min_x_te,
        "rel_err": rel_err, "rel_err_sq": rel_err ** 2,
        "rel_b": rel_b, "rel_e": rel_e, "rel_g": rel_g,
        "n_support_viol": n_support_viol,
    }

    meta = {
        "fit_id": fit_id(n, fold_idx, seed, route),
        "n": int(n), "fold": int(fold_idx + 1), "seed": int(seed), "route": route,
        "converged": bool(converged), "nan_flag": bool(nan_flag),
        "best_epoch": int(best_epoch), "stopped_epoch": int(stopped_epoch),
        "best_val_loss": float(best_val),
        "last_train_loss": float(last_epoch_loss),
        "rrmse_x95": rrmse,
        "n_test": int(len(test_rows)),
        "n_nonfinite": n_nonfinite, "n_illegal": n_illegal,
        "n_support_viol": n_support_viol,
        "support_legality_ok": bool(n_support_viol == 0),
        "sample_bytes_sha": DATA.sample_bytes_sha(master, test_rows),
        "runtime_s": float(runtime_s),
        "init_param_sha": init_sha,
        "batch_order_sha": batch_order_sha,
        "network_sha": net_sha,
        "scaler_sha": scaler.params_sha(),
        "train_rows_sha": DATA.sha_rows(train_rows),
        "val_rows_sha": DATA.sha_rows(val_rows),
        "test_rows_sha": DATA.sha_rows(test_rows),
        "route_loss": "P" if route == "P" else "Q",
        "warm_started": bool(initial_state is not None),
        "learning_rate": lr,
        "split_strategy": split_strategy,
    }
    result = {"meta": meta, "predictions": predictions}
    if return_state:
        result["model_state"] = copy.deepcopy(model.state_dict())
    return result
