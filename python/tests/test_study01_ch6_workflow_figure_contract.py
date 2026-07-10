from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
FIGURE_CODE = REPO_ROOT / "Study" / "01-study-MDM最小偏移量优化研究" / "code"
if str(FIGURE_CODE) not in sys.path:
    sys.path.insert(0, str(FIGURE_CODE))

import plot_ch6_workflow as workflow_module


def test_workflow_spec_keeps_deployment_inputs_observable():
    spec = workflow_module.build_workflow_spec()

    assert spec["deployable_inputs"] == [
        "n",
        "x_(1)",
        "x_(n)",
        "range",
        "Q1",
        "median",
        "Q3",
        "IQR",
        "mean",
        "sd",
        "CV",
        "g1",
        "g2",
    ]
    assert set(spec["excluded_inputs"]) == {
        "true beta",
        "true gamma/eta",
        "configuration ID",
        "seed",
        "repeat_id",
        "candidate delta",
    }


def test_workflow_spec_distinguishes_vector_prediction_from_offline_evaluation():
    spec = workflow_module.build_workflow_spec()

    assert spec["model"] == "vector-output MLP"
    assert spec["output_dimensions"] == 26
    assert spec["delta_grid"] == {
        "min": 0.0,
        "max": 0.5,
        "step": 0.02,
    }
    assert spec["selection"] == "argmin predicted loss"
    assert spec["training_label"] == "raw per-sample 26-point loss curve"
    assert spec["evaluation"] == "true selected-loss aggregated as J1"


def test_workflow_figure_is_one_schematic_panel():
    fig = workflow_module.plot_workflow(save=False)
    try:
        assert len(fig.axes) == 1
        assert fig.get_size_inches()[0] > fig.get_size_inches()[1]
    finally:
        workflow_module.plt.close(fig)
