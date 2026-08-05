"""
BP 神经网络模型
- BPNet: 基础全连接网络，支持排序样本输入和统计特征输入
- 训练/评估工具函数
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from typing import Dict, List, Tuple, Optional


class JParamLoss(nn.Module):
    """J_param 损失函数。

    J_param = sqrt( mean( ((β̂-β)/β)² + ((η̂-η)/η)² + ((γ̂-γ)/η)² ) )

    使用 eta 归一化 gamma，因为两者与寿命同量纲。
    """

    def forward(self, y_pred: torch.Tensor, y_true: torch.Tensor) -> torch.Tensor:
        """
        Args:
            y_pred: shape (batch, 3) 预测值 [β̂, η̂, γ̂]
            y_true: shape (batch, 3) 真值 [β, η, γ]
        """
        beta_hat, eta_hat, gamma_hat = y_pred[:, 0], y_pred[:, 1], y_pred[:, 2]
        beta, eta, gamma = y_true[:, 0], y_true[:, 1], y_true[:, 2]

        # 相对误差（gamma 用 eta 归一化）
        err_beta = (beta_hat - beta) / beta
        err_eta = (eta_hat - eta) / eta
        err_gamma = (gamma_hat - gamma) / eta

        # J_param
        j_param_sq = err_beta ** 2 + err_eta ** 2 + err_gamma ** 2
        j_param = torch.sqrt(torch.mean(j_param_sq))

        return j_param


class BPNet(nn.Module):
    """BP 神经网络，用于三参数 Weibull 直接估计。

    支持两种输入模式：
    - raw: 排序样本输入，维度 = n_samples
    - feature: 统计特征输入，维度 = n_features (默认12)
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dims: List[int] = [64, 32],
        output_dim: int = 3,
        dropout: float = 0.1,
    ):
        super().__init__()

        layers = []
        prev_dim = input_dim

        for h_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, h_dim),
                nn.BatchNorm1d(h_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
            ])
            prev_dim = h_dim

        layers.append(nn.Linear(prev_dim, output_dim))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class BPTrainer:
    """BP 网络训练器。"""

    def __init__(
        self,
        input_dim: int,
        hidden_dims: List[int] = [64, 32],
        lr: float = 1e-3,
        weight_decay: float = 1e-4,
        dropout: float = 0.1,
        device: str = "cpu",
    ):
        self.device = torch.device(device)
        self.model = BPNet(
            input_dim=input_dim,
            hidden_dims=hidden_dims,
            dropout=dropout,
        ).to(self.device)

        self.optimizer = optim.Adam(
            self.model.parameters(),
            lr=lr,
            weight_decay=weight_decay,
        )
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="min", factor=0.5, patience=10
        )
        self.criterion = JParamLoss()  # 使用 J_param 损失

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        epochs: int = 200,
        batch_size: int = 64,
        patience: int = 30,
        verbose: bool = True,
    ) -> Dict[str, List[float]]:
        """训练模型。

        Returns:
            训练历史：{"train_loss": [...], "val_loss": [...]}
        """
        # 转换为 tensor
        X_train_t = torch.FloatTensor(X_train).to(self.device)
        y_train_t = torch.FloatTensor(y_train).to(self.device)

        train_dataset = TensorDataset(X_train_t, y_train_t)
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

        if X_val is not None:
            X_val_t = torch.FloatTensor(X_val).to(self.device)
            y_val_t = torch.FloatTensor(y_val).to(self.device)

        history = {"train_loss": [], "val_loss": []}
        best_val_loss = float("inf")
        best_model_state = None
        patience_counter = 0

        for epoch in range(epochs):
            # 训练
            self.model.train()
            train_losses = []

            for X_batch, y_batch in train_loader:
                self.optimizer.zero_grad()
                y_pred = self.model(X_batch)
                loss = self.criterion(y_pred, y_batch)
                loss.backward()
                self.optimizer.step()
                train_losses.append(loss.item())

            avg_train_loss = np.mean(train_losses)
            history["train_loss"].append(avg_train_loss)

            # 验证
            if X_val is not None:
                self.model.eval()
                with torch.no_grad():
                    y_val_pred = self.model(X_val_t)
                    val_loss = self.criterion(y_val_pred, y_val_t).item()
                history["val_loss"].append(val_loss)

                self.scheduler.step(val_loss)

                # 早停
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    best_model_state = self.model.state_dict().copy()
                    patience_counter = 0
                else:
                    patience_counter += 1

                if patience_counter >= patience:
                    if verbose:
                        print(f"早停于 epoch {epoch+1}, val_loss={val_loss:.6f}")
                    break

                if verbose and (epoch + 1) % 20 == 0:
                    print(f"Epoch {epoch+1}/{epochs}: train_loss={avg_train_loss:.6f}, val_loss={val_loss:.6f}")
            else:
                if verbose and (epoch + 1) % 20 == 0:
                    print(f"Epoch {epoch+1}/{epochs}: train_loss={avg_train_loss:.6f}")

        # 恢复最佳模型
        if best_model_state is not None:
            self.model.load_state_dict(best_model_state)

        return history

    def predict(self, X: np.ndarray) -> np.ndarray:
        """预测参数。

        Returns:
            shape (n, 3) 数组 [beta_hat, eta_hat, gamma_hat]
        """
        self.model.eval()
        with torch.no_grad():
            X_t = torch.FloatTensor(X).to(self.device)
            y_pred = self.model(X_t).cpu().numpy()
        return y_pred

    def save(self, path: str):
        """保存模型。"""
        torch.save({
            "model_state": self.model.state_dict(),
            "optimizer_state": self.optimizer.state_dict(),
        }, path)

    def load(self, path: str):
        """加载模型。"""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state"])


def create_bp_feature_model(
    n_features: int = 12,
    hidden_dims: List[int] = [64, 32],
    **kwargs,
) -> BPTrainer:
    """创建统计特征输入的 BP 模型。"""
    return BPTrainer(input_dim=n_features, hidden_dims=hidden_dims, **kwargs)


def create_bp_raw_model(
    n_samples: int,
    hidden_dims: List[int] = [128, 64, 32],
    **kwargs,
) -> BPTrainer:
    """创建排序样本输入的 BP 模型。"""
    return BPTrainer(input_dim=n_samples, hidden_dims=hidden_dims, **kwargs)


if __name__ == "__main__":
    # 测试模型创建
    print("测试 BP 模型...")

    # 特征输入模型
    trainer_feat = create_bp_feature_model(n_features=12)
    print(f"特征模型参数量: {sum(p.numel() for p in trainer_feat.model.parameters()):,}")

    # 排序样本输入模型（n=10）
    trainer_raw = create_bp_raw_model(n_samples=10)
    print(f"排序样本模型参数量: {sum(p.numel() for p in trainer_raw.model.parameters()):,}")

    # 测试前向传播
    X_test = np.random.randn(5, 12).astype(np.float32)
    y_pred = trainer_feat.predict(X_test)
    print(f"预测输出形状: {y_pred.shape}")
    print(f"预测值示例: {y_pred[0]}")
