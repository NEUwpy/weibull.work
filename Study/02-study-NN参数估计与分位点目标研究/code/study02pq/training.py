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


def fit_id(n: int, fold_idx: int, seed: int, route: str, suffix: str = "") -> str:
    return f"n{n}_f{fold_idx + 1}_s{seed}_r{route.upper()}{suffix}"


def _tensor(x: np.ndarray) -> torch.Tensor:
    return torch.tensor(np.ascontiguousarray(x), dtype=torch.float64)


def _xR_from_params(params: np.ndarray, R: float) -> np.ndarray:
    """从真参数 (beta, eta, gamma) 计算 x_R = gamma + eta*(-ln R)^(1/beta)。"""
    beta, eta, gamma = params[:, 0], params[:, 1], params[:, 2]
    return gamma + eta * (-np.log(float(R))) ** (1.0 / beta)


def _epoch_perm(n_rows: int, generator: torch.Generator) -> np.ndarray:
    return torch.randperm(n_rows, generator=generator).numpy()


def train_one_fit(n: int, fold_idx: int, seed: int, route: str, master: DATA.Master,
                  max_epochs=None, batch_size=None, patience=None,
                  initial_state=None, include_initial=False, return_state=False,
                  learning_rate=None, split_strategy="gamma_holdout",
                  target_R=None, hidden=None, fit_suffix="", split_rows=None,
                  lambda_p=None, p_constraint_limit=None, constraint_rho=None,
                  record_history=False, evaluate_test=True):
    """训练一个 (n, fold, seed, route) 模型并在 held-out 折上评价。

    S3 扩展（缺省保持 S1/iid 行为不变）：
      - target_R：Q 路由的目标可靠度水平（None → CFG.X0_95_R）；'Q90'/'Q99' 等 route
        由调用方与 target_R 一起传入；
      - hidden：网络隐藏层（None → CFG.HIDDEN_LAYERS，容量实验用）；
      - fit_suffix：fit_id 后缀（容量实验，如 '_sm64'；None/'' 保持 S1 fit_id）。

    返回 dict（指标、预测 numpy、配对 SHA、元数据）。不写盘；由调用方负责 checkpoint。
    """
    route = route.upper()
    max_epochs = max_epochs or CFG.MAX_EPOCHS
    batch_size = batch_size or CFG.BATCH_SIZE
    patience = patience or CFG.PATIENCE
    fit_suffix = fit_suffix or ""

    # ---- 确定性种子（初始参数 + batch 顺序共用） ----
    torch.manual_seed(seed)
    gen = torch.Generator().manual_seed(seed)

    # ---- 数据行（与 seed/route 无关） ----
    if split_rows is not None:
        if len(split_rows) != 3:
            raise ValueError("split_rows must be (train_rows, val_rows, test_rows)")
        train_rows, val_rows, test_rows = (
            np.asarray(rows, dtype=np.int64) for rows in split_rows
        )
    elif split_strategy == "gamma_holdout":
        train_rows, val_rows, test_rows = DATA.split_fold(master, n, fold_idx)
    elif split_strategy == "repeat_stratified":
        train_rows, val_rows, test_rows = DATA.split_repeat_fold(master, n, fold_idx)
    elif split_strategy == "continuous_sobol":
        train_rows, val_rows, test_rows = DATA.split_continuous_fold(master, n, fold_idx)
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
    model = MODEL.build_model(n, seed, hidden=hidden)
    if initial_state is not None:
        model.load_state_dict(copy.deepcopy(initial_state))
    init_sha = MODEL.params_sha(model)
    net_sha = MODEL.structure_signature(n, hidden=hidden)
    loss_fn, target_kind = LOSS.build_route_loss(
        route, target_R=target_R, lambda_p=lambda_p)
    selection_loss_fn, selection_target_kind = LOSS.build_selection_loss(
        route, target_R=target_R, lambda_p=lambda_p)
    if selection_target_kind != target_kind:
        raise RuntimeError("route objective and checkpoint target kinds must match")
    if route == "QCP":
        if p_constraint_limit is None or not np.isfinite(float(p_constraint_limit)) \
                or float(p_constraint_limit) <= 0.0:
            raise ValueError("QCP requires a finite positive p_constraint_limit")
        if constraint_rho is None or not np.isfinite(float(constraint_rho)) \
                or float(constraint_rho) <= 0.0:
            raise ValueError("QCP requires a finite positive constraint_rho")
        p_constraint_limit = float(p_constraint_limit)
        constraint_rho = float(constraint_rho)
    elif p_constraint_limit is not None or constraint_rho is not None:
        raise ValueError("constraint arguments are only valid for route='QCP'")

    if target_kind == "params":
        y_tr = _tensor(P_tr); y_val = _tensor(P_val)
    elif target_R is None or target_R == CFG.X0_95_R:
        # S1/iid 默认：x0.95（make_arrays 预计算的 x0_95 目标；行为不变）
        y_tr = _tensor(X95_tr); y_val = _tensor(X95_val)
    else:
        # S3 E1：目标特异可靠度水平 x_R，从真参数解析计算（与 data.x0_95 同式）
        y_tr = _tensor(_xR_from_params(P_tr, target_R))
        y_val = _tensor(_xR_from_params(P_val, target_R))

    X_tr_t = _tensor(X_tr_s); X_val_t = _tensor(X_val_s)
    P_tr_t = _tensor(P_tr); P_val_t = _tensor(P_val)
    min_x_tr_t = _tensor(min_x_tr); min_x_val_t = _tensor(min_x_val)

    # ---- batch 顺序（epoch 1 的置换 SHA，确定性） ----
    perm = _epoch_perm(len(X_tr), gen)
    batch_order_sha = DATA.sha_bytes(perm.astype(np.int64).tobytes())

    lr = CFG.LR if learning_rate is None else float(learning_rate)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=CFG.WEIGHT_DECAY)
    best_val = float("inf")
    best_state = None
    best_epoch = 0
    best_val_objective = float("inf")
    patience_counter = 0
    stopped_epoch = 0
    nan_flag = False
    t0 = time.time()
    last_epoch_loss = float("nan")
    history = []
    dual_multiplier = 0.0
    last_train_q = float("nan")
    last_train_p = float("nan")
    best_constraint_feasible = route != "QCP"
    best_val_p_loss = float("nan")
    best_constraint_violation = float("inf")

    # 续训实验把共同起点作为 epoch 0 候选，避免目标切换把已有模型训练坏。
    if include_initial:
        model.eval()
        with torch.no_grad():
            val_out = model(X_val_t)
            best_val_objective = float(loss_fn(val_out, y_val, min_x_val_t))
            best_val = float(selection_loss_fn(val_out, y_val, min_x_val_t))
        best_state = copy.deepcopy(model.state_dict())
        model.train()

    for epoch in range(1, max_epochs + 1):
        if epoch > 1:
            perm = _epoch_perm(len(X_tr), gen)
        model.train()
        epoch_loss_sum = 0.0
        epoch_q_sum = 0.0
        epoch_p_sum = 0.0
        n_seen = 0
        for b0 in range(0, len(perm), batch_size):
            idx = perm[b0:b0 + batch_size]
            xb = X_tr_t[idx]
            yb = y_tr[idx]
            mxb = min_x_tr_t[idx]
            optimizer.zero_grad()
            out = model(xb)
            if route == "QCP":
                q_loss, p_loss = LOSS.parameter_target_loss_components(
                    out, yb, mxb,
                    CFG.X0_95_R if target_R is None else float(target_R))
                violation = p_loss - p_constraint_limit
                dual_t = torch.as_tensor(
                    dual_multiplier, dtype=q_loss.dtype, device=q_loss.device)
                active = torch.clamp(
                    dual_t + constraint_rho * violation, min=0.0)
                loss = q_loss + (active ** 2 - dual_t ** 2) / (2.0 * constraint_rho)
                epoch_q_sum += float(q_loss.detach()) * len(idx)
                epoch_p_sum += float(p_loss.detach()) * len(idx)
            else:
                loss = loss_fn(out, yb, mxb)
            if not torch.isfinite(loss):
                nan_flag = True
                break
            loss.backward()
            optimizer.step()
            epoch_loss_sum += float(loss.detach()) * len(idx)
            n_seen += len(idx)
        last_epoch_loss = epoch_loss_sum / max(n_seen, 1)
        if route == "QCP" and n_seen:
            last_train_q = epoch_q_sum / n_seen
            last_train_p = epoch_p_sum / n_seen
            dual_multiplier = max(
                0.0, dual_multiplier + constraint_rho *
                (last_train_p - p_constraint_limit))

        model.eval()
        with torch.no_grad():
            val_out = model(X_val_t)
            if route == "QCP":
                val_q_constraint, val_p_constraint = \
                    LOSS.parameter_target_loss_components(
                        val_out, P_val_t, min_x_val_t,
                        CFG.X0_95_R if target_R is None else float(target_R))
                val_objective = float(val_q_constraint)
                val_loss = float(val_q_constraint)
                current_val_p = float(val_p_constraint)
            else:
                val_objective = float(loss_fn(val_out, y_val, min_x_val_t))
                val_loss = float(selection_loss_fn(val_out, y_val, min_x_val_t))
                current_val_p = float("nan")
            if record_history:
                train_out = model(X_tr_t)
                train_q, train_p = LOSS.parameter_target_loss_components(
                    train_out, P_tr_t, min_x_tr_t,
                    CFG.X0_95_R if target_R is None else float(target_R))
                if route == "QCP":
                    val_q, val_p = val_q_constraint, val_p_constraint
                else:
                    val_q, val_p = LOSS.parameter_target_loss_components(
                        val_out, P_val_t, min_x_val_t,
                        CFG.X0_95_R if target_R is None else float(target_R))
                history_row = {
                    "epoch": int(epoch),
                    "train_objective": float(last_epoch_loss),
                    "val_objective": val_objective,
                    "train_q_loss": float(train_q),
                    "val_q_loss": float(val_q),
                    "train_p_loss": float(train_p),
                    "val_p_loss": float(val_p),
                }
                if route == "QCP":
                    history_row.update({
                        "p_constraint_limit": p_constraint_limit,
                        "constraint_violation": float(val_p) - p_constraint_limit,
                        "dual_multiplier": dual_multiplier,
                    })
                history.append(history_row)
        model.train()
        stopped_epoch = epoch

        if route == "QCP":
            current_violation = current_val_p - p_constraint_limit
            current_feasible = current_violation <= 1e-12
            if current_feasible and (
                    not best_constraint_feasible or val_loss < best_val - 1e-12):
                best_constraint_feasible = True
                best_val = val_loss
                best_val_objective = val_objective
                best_val_p_loss = current_val_p
                best_constraint_violation = current_violation
                best_state = copy.deepcopy(model.state_dict())
                best_epoch = epoch
                patience_counter = 0
            elif not current_feasible and not best_constraint_feasible:
                if current_violation < best_constraint_violation:
                    best_constraint_violation = current_violation
                    best_val = val_loss
                    best_val_objective = val_objective
                    best_val_p_loss = current_val_p
                    best_state = copy.deepcopy(model.state_dict())
                    best_epoch = epoch
                patience_counter = 0
            else:
                patience_counter += 1
                if best_constraint_feasible and patience_counter >= patience:
                    break
        elif val_loss < best_val - 1e-12:
            best_val = val_loss
            best_val_objective = val_objective
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

    common_meta = {
        "fit_id": fit_id(n, fold_idx, seed, route, fit_suffix),
        "n": int(n), "fold": int(fold_idx + 1), "seed": int(seed), "route": route,
        "target_R": (float(target_R) if target_R is not None and route != "P" else None),
        "lambda_p": (float(lambda_p) if route == "QP" and lambda_p is not None else
                     0.0 if route == "QP" else None),
        "p_constraint_limit": (p_constraint_limit if route == "QCP" else None),
        "constraint_rho": (constraint_rho if route == "QCP" else None),
        "final_dual_multiplier": (dual_multiplier if route == "QCP" else None),
        "last_train_q_loss": (last_train_q if route == "QCP" else None),
        "last_train_p_loss": (last_train_p if route == "QCP" else None),
        "constraint_feasible_at_checkpoint": (best_constraint_feasible
                                              if route == "QCP" else None),
        "best_val_p_loss": (best_val_p_loss if route == "QCP" else None),
        "best_constraint_violation": (best_constraint_violation
                                      if route == "QCP" else None),
        "hidden_layers": list(hidden) if hidden is not None else list(CFG.HIDDEN_LAYERS),
        "converged": bool(converged), "nan_flag": bool(nan_flag),
        "best_epoch": int(best_epoch), "stopped_epoch": int(stopped_epoch),
        "best_val_loss": float(best_val),
        "best_val_objective": float(best_val_objective),
        "checkpoint_loss": "Q" if route in {"QP", "QCP"} else route,
        "last_train_loss": float(last_epoch_loss),
        "runtime_s": float(runtime_s),
        "init_param_sha": init_sha,
        "batch_order_sha": batch_order_sha,
        "network_sha": net_sha,
        "scaler_sha": scaler.params_sha(),
        "train_rows_sha": DATA.sha_rows(train_rows),
        "val_rows_sha": DATA.sha_rows(val_rows),
        "test_rows_sha": DATA.sha_rows(test_rows),
        "n_train": int(len(train_rows)), "n_val": int(len(val_rows)),
        "route_loss": ("P" if route == "P" else
                       "P_matrix_truth" if route.startswith("M") else
                       "Q_plus_lambda_P" if route == "QP" else "Q"),
        "constraint_form": ("Q_min_subject_to_P_limit" if route == "QCP" else None),
        "warm_started": bool(initial_state is not None),
        "learning_rate": lr,
        "split_strategy": split_strategy,
        "history_recorded": bool(record_history),
        "test_evaluated": bool(evaluate_test),
    }
    if not evaluate_test:
        result = {"meta": common_meta}
        if record_history:
            result["history"] = history
        if return_state:
            result["model_state"] = copy.deepcopy(model.state_dict())
        return result

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
        **common_meta,
        "rrmse_x95": rrmse,
        "n_test": int(len(test_rows)),
        "n_nonfinite": n_nonfinite, "n_illegal": n_illegal,
        "n_support_viol": n_support_viol,
        "support_legality_ok": bool(n_support_viol == 0),
        "sample_bytes_sha": DATA.sample_bytes_sha(master, test_rows),
    }
    result = {"meta": meta, "predictions": predictions}
    if record_history:
        result["history"] = history
    if return_state:
        result["model_state"] = copy.deepcopy(model.state_dict())
    return result
