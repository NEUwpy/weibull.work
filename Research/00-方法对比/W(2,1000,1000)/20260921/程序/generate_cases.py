from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import numpy as np

PROGRAM_DIR = Path(__file__).resolve().parent
WORK_DIR = PROGRAM_DIR.parent / '结果' / '复算输出'
REPO_ROOT = next(p for p in PROGRAM_DIR.parents if (p / 'python' / 'methods').is_dir())
PYTHON_DIR = PROGRAM_DIR / "依赖快照" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from studies.common.runner import run_method
from studies.common.sample import generate_sample

SHAPE = 2.0
SCALE = 1000.0
LOCATION = 1000.0
SAMPLE_SIZES = (7, 15, 30)
REPEATS = 50
OFFSETS = (0.10, 0.15, 0.20)
SEED_NAMESPACE = 20260921
GAMMA_STEPS = 240
METHODS = (("lse", "LS"), ("lre", "LRE"), ("wmle", "WMLM"), ("mle", "MLM"))
Y_RANGE = (-0.8, 1.6)


def git_version() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()


def clean_result(result: dict) -> dict:
    extra = result.get("extra") or {}
    solution = extra.get("solution_info") or {}
    return {
        "shape_hat": result.get("beta_hat"),
        "scale_hat": result.get("eta_hat"),
        "location_hat": result.get("gamma_hat"),
        "r_squared": result.get("r_squared"),
        "converged": bool(result.get("converged")),
        "status": solution.get("solution_strategy") or solution.get("status") or extra.get("raw_status") or ("ok" if result.get("converged") else extra.get("error", "failed")),
        "root_solver": solution.get("root_solver"),
        "gradient_at_zero": solution.get("probe_gradient_at_zero"),
    }


def configure_style() -> None:
    mpl.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "Times", "DejaVu Serif"], "font.size": 8, "axes.linewidth": 0.8, "xtick.major.width": 0.8, "ytick.major.width": 0.8, "xtick.minor.width": 0.6, "ytick.minor.width": 0.6, "axes.unicode_minus": True})


def plot_curves(case_dir: Path, curves: list[list[dict]], n: int, offset: float) -> None:
    configure_style()
    fig, ax = plt.subplots(figsize=(130 / 25.4, 92 / 25.4))
    for rows in curves:
        points = sorted(rows, key=lambda row: float(row["gamma"]))
        ax.plot([float(row["gamma"]) for row in points], [float(row["gradient"]) for row in points], color="black", linewidth=0.48, alpha=0.82, solid_capstyle="round")
    ax.axhline(offset, color="#b2182b", linewidth=0.85, linestyle="-.", zorder=5)
    ax.set_xlim(0.0, LOCATION + SCALE)
    ax.set_ylim(*Y_RANGE)
    ax.spines["bottom"].set_position(("data", 0.0))
    ax.spines["left"].set_position(("data", 0.0))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.xaxis.set_ticks_position("bottom")
    ax.yaxis.set_ticks_position("left")
    ax.set_xticks(np.arange(0.0, LOCATION + SCALE + 0.1, 500.0))
    ax.set_yticks(np.arange(-0.8, 1.6001, 0.4))
    ax.xaxis.set_minor_locator(MultipleLocator(100.0))
    ax.yaxis.set_minor_locator(MultipleLocator(0.1))
    ax.tick_params(which="major", direction="in", length=4.2, pad=3)
    ax.tick_params(which="minor", direction="in", length=2.4)
    ax.set_ylabel("Std gradient", labelpad=8)
    fig.text(0.56, 0.055, "Location parameter value adopted", ha="center", va="center")
    fig.subplots_adjust(left=0.14, right=0.985, bottom=0.18, top=0.975)
    fig.savefig(case_dir / f"样本量{n}_偏移量{offset:.2f}.png", dpi=600, facecolor="white")
    plt.close(fig)


def run_case() -> dict:
    label = "W(2,1000,1000)"
    case_dir = WORK_DIR / "outputs" / label
    case_dir.mkdir(parents=True, exist_ok=True)
    samples, results, diagnostics = {}, {}, {}
    for n in SAMPLE_SIZES:
        samples[str(n)] = []
        results[str(n)] = {f"{offset:.2f}": [] for offset in OFFSETS}
        curves_for_n = []
        other_cache = {}
        for repeat_id in range(REPEATS):
            sample = generate_sample(SHAPE, SCALE, LOCATION, n, repeat_id, seed=SEED_NAMESPACE)
            sample_id = repeat_id + 1
            samples[str(n)].append([float(value) for value in sample])
            other_cache[sample_id] = {display_name: clean_result(run_method(method_id, sample)) for method_id, display_name in METHODS}
            for offset_index, offset in enumerate(OFFSETS):
                mdm_raw = run_method("mdm", sample, variant=f"mdm-delta-{offset:.2f}", offset=offset, gamma_steps=GAMMA_STEPS, trace=(offset_index == 0))
                mdm = clean_result(mdm_raw)
                results[str(n)][f"{offset:.2f}"].append({"sample_id": sample_id, "MDM": mdm, **other_cache[sample_id]})
                if offset_index == 0:
                    trace_data = mdm_raw.get("trace_data") or {}
                    curve = [{"gamma": float(point["gamma"]), "gradient": float(point["gradient"])} for point in trace_data.get("grad_gamma_curve", []) if point.get("source") == "trace_grid" and not point.get("virtual", False) and math.isfinite(float(point["gradient"]))]
                    if len(curve) < GAMMA_STEPS - 2:
                        raise RuntimeError(f"{label}, n={n}, sample={sample_id}: too few finite curve points, got {len(curve)}")
                    curves_for_n.append(curve)
            print(f"{label} n={n} sample={sample_id}/50", flush=True)
        for offset in OFFSETS:
            plot_curves(case_dir, curves_for_n, n, offset)
        diagnostics[str(n)] = {"mdm": {key: {"valid": sum(row["MDM"]["converged"] for row in rows), "gamma_zero": sum(row["MDM"]["converged"] and abs(float(row["MDM"]["location_hat"])) < 1e-12 for row in rows), "right_edge_fallback": sum(row["MDM"].get("root_solver") == "right_edge_fit" for row in rows)} for key, rows in results[str(n)].items()}, "other_methods": {display_name: {"valid": sum(other_cache[sample_id][display_name]["converged"] for sample_id in other_cache), "gamma_zero": sum(other_cache[sample_id][display_name]["converged"] and abs(float(other_cache[sample_id][display_name]["location_hat"])) < 1e-12 for sample_id in other_cache)} for _, display_name in METHODS}}
    return {"label": label, "shape": SHAPE, "scale": SCALE, "location": LOCATION, "samples": samples, "results": results, "diagnostics": diagnostics}


WORK_DIR.mkdir(parents=True, exist_ok=False)
payload = {"protocol": {"seed_namespace": SEED_NAMESPACE, "sample_sizes": list(SAMPLE_SIZES), "repeats": REPEATS, "offsets": list(OFFSETS), "gamma_steps": GAMMA_STEPS, "code_version": git_version()}, "cases": [run_case()]}
(WORK_DIR / "payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print("payload complete", flush=True)
