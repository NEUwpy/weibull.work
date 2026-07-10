from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
FIGURE_CODE = REPO_ROOT / "Study" / "01-study-MDM最小偏移量优化研究" / "code"
if str(FIGURE_CODE) not in sys.path:
    sys.path.insert(0, str(FIGURE_CODE))

import plot_fig1 as framework_module


def test_framework_spec_is_a_result_free_final_manuscript_roadmap():
    spec = framework_module.build_framework_spec()
    rendered_contract = repr(spec).lower()

    for forbidden in [
        "j1",
        "%",
        "improvement",
        "upper bound",
        "requires nn",
        "pending",
        "completed",
        "e3a",
        "e3b",
        "e3c",
    ]:
        assert forbidden not in rendered_contract

    layers = {layer["id"]: layer for layer in spec["layers"]}
    assert layers["L1"]["kind"] == "deployable"
    assert layers["L2"]["kind"] == "deployable"
    assert layers["L3"]["available_information"] == "true beta"
    assert layers["L4"]["available_information"] == "true beta + n"
    assert layers["L5"]["available_information"] == "true beta + true gamma/eta + n"
    assert layers["L6"]["kind"] == "hindsight benchmark"

    assert spec["adaptive_bridge"] == [
        "observable sample features",
        "26-point risk curve",
        "selected delta",
    ]
    assert [item["id"] for item in spec["validation_path"]] == [
        "E1",
        "E2",
        "E3",
        "E4",
        "Real data",
    ]
