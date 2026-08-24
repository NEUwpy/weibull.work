"""从 Word 附件提取样本并绘制 MDM 梯度-位置参数曲线。

画法参考文献 182-046 的图 5：每个样本量叠加 30 条黑色梯度曲线，
并绘制 delta=0.1 的红色点划判据线。梯度和参数估计均调用项目当前
生产实现 ``python/methods/mdm.py``，不使用手工构造曲线。
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
DEFAULT_DOCX = HERE.parent / "两组样本-画图.docx"
DEFAULT_OUTPUT_DIR = HERE

sys.path.insert(0, str(REPO_ROOT / "python"))
from methods.mdm import MDM  # noqa: E402


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": WORD_NS}
OFFSET = 0.1
GAMMA_STEPS = 240
EXPECTED_TABLE_SHAPES = [(7, 15), (7, 15), (15, 15), (15, 15)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docx", type=Path, default=DEFAULT_DOCX)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--gamma-steps", type=int, default=GAMMA_STEPS)
    return parser.parse_args()


def _cell_text(cell: ET.Element) -> str:
    return "".join(node.text or "" for node in cell.findall(".//w:t", NS)).strip()


def read_numeric_tables(docx_path: Path) -> list[np.ndarray]:
    """Read numeric Word tables directly from OOXML with no Office dependency."""
    with zipfile.ZipFile(docx_path) as archive:
        document_xml = archive.read("word/document.xml")
    root = ET.fromstring(document_xml)

    tables: list[np.ndarray] = []
    for table_index, table in enumerate(root.findall(".//w:tbl", NS), start=1):
        rows: list[list[float]] = []
        for row_index, row in enumerate(table.findall("./w:tr", NS), start=1):
            values: list[float] = []
            for column_index, cell in enumerate(row.findall("./w:tc", NS), start=1):
                raw = _cell_text(cell)
                try:
                    values.append(float(raw))
                except ValueError as exc:
                    raise ValueError(
                        f"表 {table_index} 第 {row_index} 行第 {column_index} 列不是数值: {raw!r}"
                    ) from exc
            rows.append(values)

        widths = {len(row) for row in rows}
        if len(widths) != 1:
            raise ValueError(f"表 {table_index} 的列数不一致: {sorted(widths)}")
        tables.append(np.asarray(rows, dtype=float))

    shapes = [tuple(table.shape) for table in tables]
    if shapes != EXPECTED_TABLE_SHAPES:
        raise ValueError(f"附件表格结构已变化，实际为 {shapes}，预期为 {EXPECTED_TABLE_SHAPES}")
    return tables


def assemble_sample_groups(tables: list[np.ndarray]) -> dict[int, np.ndarray]:
    """Combine the two 15-group blocks for each sample size into n x 30 matrices."""
    groups = {
        7: np.hstack((tables[0], tables[1])),
        15: np.hstack((tables[2], tables[3])),
    }
    for sample_size, matrix in groups.items():
        if matrix.shape != (sample_size, 30):
            raise AssertionError(f"n={sample_size} 数据形状错误: {matrix.shape}")
        if not np.isfinite(matrix).all() or np.any(matrix <= 0):
            raise ValueError(f"n={sample_size} 包含非有限值或非正寿命值")
    return groups


def run_mdm(groups: dict[int, np.ndarray], gamma_steps: int):
    curves: list[dict[str, object]] = []
    estimates: list[dict[str, object]] = []

    for sample_size, matrix in groups.items():
        for group_index in range(matrix.shape[1]):
            sample = matrix[:, group_index].astype(float)
            model = MDM(sample.tolist())
            beta_hat, eta_hat, gamma_hat, r_squared, status = model.run(
                trace=True,
                offset=OFFSET,
                gamma_steps=gamma_steps,
            )
            solution = model.last_solution_info
            estimates.append(
                {
                    "sample_size": sample_size,
                    "group_id": group_index + 1,
                    "beta_hat": beta_hat,
                    "eta_hat": eta_hat,
                    "gamma_hat": gamma_hat,
                    "r_squared": r_squared,
                    "status": bool(status),
                    "solution_strategy": solution["solution_strategy"],
                    "gradient_at_zero": solution["probe_gradient_at_zero"],
                    "sample_min": float(np.min(sample)),
                    "offset": OFFSET,
                }
            )

            for point in model.trace_data["grad_gamma_curve"]:
                gradient = float(point["gradient"])
                if not math.isfinite(gradient):
                    continue
                curves.append(
                    {
                        "sample_size": sample_size,
                        "group_id": group_index + 1,
                        "gamma": float(point["gamma"]),
                        "gradient": gradient,
                        "sigma_min": float(point["sigma_min"]),
                        "best_beta": float(point["best_beta"]),
                        "best_eta": float(point["best_eta"]),
                        "source": point.get("source", "trace_grid"),
                        "virtual": bool(point.get("virtual", False)),
                    }
                )
    return curves, estimates


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"没有可写入 {path.name} 的数据")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_input_samples(path: Path, groups: dict[int, np.ndarray]) -> None:
    rows: list[dict[str, object]] = []
    for sample_size, matrix in groups.items():
        for group_index in range(matrix.shape[1]):
            for observation_index, value in enumerate(matrix[:, group_index], start=1):
                rows.append(
                    {
                        "sample_size": sample_size,
                        "group_id": group_index + 1,
                        "observation_index": observation_index,
                        "value": float(value),
                    }
                )
    write_csv(path, rows)


def configure_plot_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Microsoft YaHei",
                "SimHei",
                "Arial Unicode MS",
                "DejaVu Sans",
            ],
            "axes.unicode_minus": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 8,
            "axes.linewidth": 0.8,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
        }
    )


def grouped_curves(curves: list[dict[str, object]], sample_size: int):
    for group_id in range(1, 31):
        rows = [
            row
            for row in curves
            if row["sample_size"] == sample_size
            and row["group_id"] == group_id
            and not row["virtual"]
        ]
        rows.sort(key=lambda row: float(row["gamma"]))
        yield group_id, rows


def draw_panel(ax: mpl.axes.Axes, curves: list[dict[str, object]], sample_size: int) -> None:
    for _, rows in grouped_curves(curves, sample_size):
        ax.plot(
            [float(row["gamma"]) for row in rows],
            [float(row["gradient"]) for row in rows],
            color="black",
            linewidth=0.55,
            alpha=0.72,
            solid_capstyle="round",
        )

    ax.axhline(OFFSET, color="#d62728", linewidth=0.9, linestyle="-.", zorder=5)
    ax.set_xlim(0, 1800)
    ax.set_ylim(-0.8, 1.6)
    ax.set_xticks(np.arange(0, 1801, 200))
    ax.set_yticks(np.arange(-0.8, 1.61, 0.4))
    ax.set_xlabel("位置参数")
    ax.set_ylabel("尺度参数估计值标准差梯度")
    ax.text(
        0.03,
        0.94,
        f"n = {sample_size}（30组）",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8,
    )
    ax.spines["top"].set_visible(True)
    ax.spines["right"].set_visible(True)
    ax.tick_params(direction="out", length=3.0, pad=2)


def save_figure(fig: mpl.figure.Figure, stem: Path) -> None:
    fig.savefig(stem.with_suffix(".png"), dpi=600, bbox_inches="tight", facecolor="white")
    fig.savefig(stem.with_suffix(".svg"), bbox_inches="tight", facecolor="white")
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")


def make_figures(output_dir: Path, curves: list[dict[str, object]]) -> None:
    configure_plot_style()

    for sample_size in (7, 15):
        fig, ax = plt.subplots(figsize=(120 / 25.4, 82 / 25.4), constrained_layout=True)
        draw_panel(ax, curves, sample_size)
        save_figure(fig, output_dir / f"mdm_gradient_gamma_n{sample_size}")
        plt.close(fig)

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(183 / 25.4, 76 / 25.4),
        sharey=True,
        constrained_layout=True,
    )
    for panel_label, ax, sample_size in zip(("a", "b"), axes, (7, 15), strict=True):
        draw_panel(ax, curves, sample_size)
        ax.text(
            -0.15,
            1.04,
            panel_label,
            transform=ax.transAxes,
            fontsize=9,
            fontweight="bold",
            ha="left",
            va="bottom",
        )
    axes[1].set_ylabel("")
    save_figure(fig, output_dir / "mdm_gradient_gamma_comparison")
    plt.close(fig)


def validate_outputs(
    groups: dict[int, np.ndarray],
    curves: list[dict[str, object]],
    estimates: list[dict[str, object]],
    output_dir: Path,
    gamma_steps: int,
) -> None:
    assert sum(matrix.size for matrix in groups.values()) == 660
    assert len(estimates) == 60
    assert {(row["sample_size"], row["group_id"]) for row in estimates} == {
        (sample_size, group_id)
        for sample_size in (7, 15)
        for group_id in range(1, 31)
    }
    assert len(curves) >= 60 * gamma_steps

    expected = [
        "input_samples.csv",
        "mdm_gradient_curves.csv",
        "mdm_parameter_estimates.csv",
        "mdm_gradient_gamma_n7.png",
        "mdm_gradient_gamma_n7.svg",
        "mdm_gradient_gamma_n7.pdf",
        "mdm_gradient_gamma_n15.png",
        "mdm_gradient_gamma_n15.svg",
        "mdm_gradient_gamma_n15.pdf",
        "mdm_gradient_gamma_comparison.png",
        "mdm_gradient_gamma_comparison.svg",
        "mdm_gradient_gamma_comparison.pdf",
    ]
    missing = [name for name in expected if not (output_dir / name).is_file()]
    if missing:
        raise AssertionError(f"缺少输出文件: {missing}")


def main() -> None:
    args = parse_args()
    docx_path = args.docx.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    tables = read_numeric_tables(docx_path)
    groups = assemble_sample_groups(tables)
    write_input_samples(output_dir / "input_samples.csv", groups)

    curves, estimates = run_mdm(groups, gamma_steps=args.gamma_steps)
    write_csv(output_dir / "mdm_gradient_curves.csv", curves)
    write_csv(output_dir / "mdm_parameter_estimates.csv", estimates)
    make_figures(output_dir, curves)
    validate_outputs(groups, curves, estimates, output_dir, args.gamma_steps)

    for sample_size in (7, 15):
        subset = [row for row in estimates if row["sample_size"] == sample_size]
        gamma_values = np.asarray([float(row["gamma_hat"]) for row in subset])
        print(
            f"n={sample_size}: 30 groups; gamma_hat range="
            f"[{gamma_values.min():.6f}, {gamma_values.max():.6f}]"
        )
    print(f"Outputs written to: {output_dir}")


if __name__ == "__main__":
    main()
