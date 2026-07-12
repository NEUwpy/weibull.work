from pathlib import Path
import sys

import pytest
import torch


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))

from study02a.models import build_deepsets, build_mlp, decode_model_output
from study02a.training import compute_loss, select_independent_capacity


def test_deepsets_is_permutation_invariant():
    torch.manual_seed(4)
    model = build_deepsets((32, 32), "mean", (64, 32), "relu")
    x = torch.tensor([[[0.0], [0.5], [2.0], [4.0]]])
    mask = torch.ones(1, 4, dtype=torch.bool)
    n = torch.tensor([4.0])
    assert torch.allclose(model(x, mask, n), model(x[:, [2, 0, 3, 1], :], mask, n), atol=1e-6)


def test_deepsets_has_explicit_n_channel_not_a_fake_set_element():
    model = build_deepsets((8, 8), "mean", (8,), "relu")
    x = torch.tensor([[[0.0], [1.0], [2.0], [0.0]]])
    mask = torch.tensor([[True, True, True, False]])
    assert model(x, mask, torch.tensor([3.0])).shape == (1, 3)
    with pytest.raises(TypeError):
        model(x, mask)


def test_decode_is_always_legal():
    decoded = decode_model_output(
        torch.tensor([[0.0, 0.0, 0.0]]),
        location=torch.tensor([100.0]),
        scale=torch.tensor([20.0]),
    )[0]
    beta, eta, gamma = decoded.tolist()
    assert beta > 0 and eta > 0 and gamma < 100.0
    assert decoded.tolist() == pytest.approx([1.0, 20.0, 80.0])


def test_mlp_output_shape():
    model = build_mlp(input_dim=15, widths=(64, 32), activation="silu", dropout=0.1)
    assert model(torch.ones(8, 15)).shape == (8, 3)


@pytest.mark.parametrize(
    "loss_id",
    ["raw_train_z_mse", "transformed_unscaled_mse", "transformed_train_z_mse", "transformed_train_z_huber"],
)
def test_frozen_losses_are_finite_and_zero_on_exact_prediction(loss_id):
    target = torch.tensor([[1.0, 2.0, 3.0], [2.0, 4.0, 8.0]])
    stats = {"mean": torch.tensor([1.5, 3.0, 5.5]), "sd": torch.tensor([0.5, 1.0, 2.5])}
    loss = compute_loss(loss_id, target, target, stats)
    assert torch.isfinite(loss)
    assert loss.item() == pytest.approx(0.0)


def test_independent_capacity_never_exceeds_joint_by_more_than_five_percent():
    selected = select_independent_capacity(joint_count=1000, candidate_counts={"a": 700, "b": 980, "c": 1040, "d": 1100})
    assert selected == ("b", 980)
    assert selected[1] <= 1050
