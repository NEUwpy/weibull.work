"""Draw the manuscript's AMDM training/inference flow, with editable text.

Diagram only: no fabricated numerical examples. Its graph and provenance are
exported as a numbered JSON file alongside PNG/SVG/PDF.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
STEM = "F02_AMDM训练与估计流程"

# Share typography with F01, without rerunning its numerical calculation.
spec = importlib.util.spec_from_file_location("mdm_figure_style", Path(__file__).with_name("F01_MDM原理联图.py"))
style_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(style_module)
style_module.style()

NODES = {
    "truth": (2, 77, 17, 11, "模拟真参数\n" + r"$(\beta,\eta,\gamma)$", "grey"),
    "sim": (26, 77, 17, 11, "模拟样本\n" + r"$\boldsymbol{t}_n$", "grey"),
    "scan": (50, 77, 18, 11, "MDM候选求解\n" + r"$\delta_1,\ldots,\delta_{26}$", "grey"),
    "target": (76, 77, 22, 11, "联合损失向量\n" + r"$\boldsymbol{\ell}$", "orange"),
    "train_input": (26, 55, 17, 11, "排序 · 均值归一化\n输入标准化", "blue"),
    "fit": (50, 55, 18, 11, "多输出回归训练\n按样本量分别拟合", "blue"),
    "model": (76, 55, 22, 11, "模型与变换参数\n训练后保存", "blue"),
    "obs": (2, 22, 17, 12, "当前观测样本\n" + r"$\boldsymbol{t}_n$", "grey"),
    "input": (26, 22, 17, 12, "排序 · 均值归一化\n输入标准化", "blue"),
    "predict": (50, 22, 18, 12, "预测候选损失\n逆标准化 · 非负截断", "blue"),
    "select": (76, 22, 22, 12, "选择预测损失最低的候选\n" + r"$\hat{\delta}(\boldsymbol{t}_n)$", "orange"),
    "mdm": (50, 1, 18, 12, "MDM三参数求解\n使用所选偏移", "grey"),
    "output": (76, 1, 22, 12, "AMDM估计结果\n" + r"$(\hat{\beta},\hat{\eta},\hat{\gamma})$", "grey"),
}
EDGES = [
    ("truth", "sim", [(19, 82.5), (26, 82.5)], "solid"),
    ("sim", "scan", [(43, 82.5), (50, 82.5)], "solid"),
    ("scan", "target", [(68, 82.5), (76, 82.5)], "solid"),
    ("truth", "target", [(10.5, 88), (10.5, 92), (87, 92), (87, 88)], "solid"),
    ("sim", "train_input", [(34.5, 77), (34.5, 66)], "solid"),
    ("train_input", "fit", [(43, 60.5), (50, 60.5)], "solid"),
    ("target", "fit", [(87, 77), (87, 71), (59, 71), (59, 66)], "solid"),
    ("fit", "model", [(68, 60.5), (76, 60.5)], "solid"),
    ("model", "predict", [(87, 55), (87, 45), (59, 45), (59, 34)], "dashed"),
    ("obs", "input", [(19, 28), (26, 28)], "solid"),
    ("input", "predict", [(43, 28), (50, 28)], "solid"),
    ("predict", "select", [(68, 28), (76, 28)], "solid"),
    ("select", "mdm", [(87, 22), (87, 17), (59, 17), (59, 13)], "solid"),
    ("obs", "mdm", [(10.5, 22), (10.5, 7), (50, 7)], "solid"),
    ("mdm", "output", [(68, 7), (76, 7)], "solid"),
]
PALETTE = {
    "grey": ("#F5F6F7", "#7D858C"),
    "blue": ("#EDF5FA", "#0072B2"),
    "orange": ("#FFF3E9", "#C96D24"),
}

def main():
    fig, ax = plt.subplots(figsize=(183 / 25.4, 128 / 25.4))
    fig.subplots_adjust(left=.015, right=.985, bottom=.035, top=.97)
    ax.set(xlim=(0, 100), ylim=(-1, 101))
    ax.axis("off")
    for key, (x, y, w, h, label, family) in NODES.items():
        face, edge = PALETTE[family]
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=0.6",
                                   facecolor=face, edgecolor=edge, linewidth=.85, zorder=3))
        ax.text(x+w/2, y+h/2, label, ha="center", va="center", fontsize=7.1,
                linespacing=1.7, color="#263746", zorder=4)
    for source, target, points, ls in EDGES:
        color = "#0072B2" if ls == "dashed" else "#697783"
        xs, ys = zip(*points)
        if len(points) > 2:
            ax.plot(xs[:-1], ys[:-1], color=color, lw=.85,
                    ls="--" if ls == "dashed" else "-", zorder=1)
        ax.annotate("", xy=points[-1], xytext=points[-2],
                    arrowprops={"arrowstyle": "-|>", "lw": .85, "color": color,
                                "linestyle": "--" if ls == "dashed" else "-",
                                "shrinkA": 0, "shrinkB": 2, "mutation_scale": 8}, zorder=2)
    ax.text(1, 98, "a", fontsize=11, fontweight="bold")
    ax.text(6, 98, "离线训练", fontsize=9)
    ax.text(1, 41, "b", fontsize=11, fontweight="bold")
    ax.text(6, 41, "实际估计", fontsize=9)
    ax.text(49, 93.1, "真参数用于计算训练目标", fontsize=6.8, ha="center", color="#697783")
    ax.text(61, 72.4, "目标标准化", fontsize=6.8, color="#C96D24")
    ax.text(88, 46.5, "复用", fontsize=6.8, color="#0072B2")
    ax.text(26, 9, "原始寿命样本", fontsize=7, color="#697783")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for label in fig.findobj(matplotlib.text.Text):
        if label.get_visible() and label.get_text():
            bb = label.get_window_extent(renderer)
            assert bb.x0 >= -1 and bb.y0 >= -1 and bb.x1 <= fig.bbox.x1+1 and bb.y1 <= fig.bbox.y1+1, label.get_text()
    for suffix in ("png", "svg", "pdf"):
        fig.savefig(ROOT / f"{STEM}.{suffix}", dpi=400)
    svg = ROOT / f"{STEM}.svg"
    svg.write_text("\n".join(l.rstrip() for l in svg.read_text(encoding="utf-8").splitlines())+"\n", encoding="utf-8")
    plt.close(fig)
    metadata = {
        "figure": "F02", "revision": 1, "type": "method information-flow diagram",
        "size_mm": [183, 128], "quantitative_data": False,
        "nodes": NODES, "edges": EDGES,
        "sources": [
            "Study/Study 01 New/Study01论文初稿-v0.1.md sections 2.4-2.5",
            "Study/01-study-MDM最小偏移量优化研究/code/check_mean_normalized_e2e_scale.py:predict_curve",
            "Study/01-study-MDM最小偏移量优化研究/code/run_E6b_dimensional_raw_specialist.py:train_specialist",
        ],
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "checks": {"text_inside_canvas": True, "training_and_inference_separated": True,
                   "raw_sample_goes_to_MDM": True, "truth_used_only_in_training": True},
    }
    (ROOT / "数据" / f"{STEM}.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"F02 exported: {len(NODES)} nodes, {len(EDGES)} edges.")

if __name__ == "__main__":
    main()
