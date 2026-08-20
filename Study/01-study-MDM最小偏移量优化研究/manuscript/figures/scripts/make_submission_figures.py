"""Create submission-grade Study01 figures from sealed computed evidence.

Python/matplotlib is the exclusive rendering backend. The script reads the
machine-readable paths in ../figure_sources.json, writes compact source-data
tables to ../data/derived, and exports PNG/SVG/PDF/TIFF into ../main and
../supplementary. It never changes the sealed Study01 artifacts.
"""

from __future__ import annotations

import json
import hashlib
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


SCRIPT_DIR = Path(__file__).resolve().parent
FIGURE_DIR = SCRIPT_DIR.parent
CONFIG_PATH = FIGURE_DIR / "figure_sources.json"
MAIN_DIR = FIGURE_DIR / "main"
SUPP_DIR = FIGURE_DIR / "supplementary"
DERIVED_DIR = FIGURE_DIR / "data" / "derived"
TABLES_DIR = FIGURE_DIR / "tables"
PROVENANCE_DIR = FIGURE_DIR / "provenance"
PRIMARY_SEED = 42

MM = 1 / 25.4
COLORS = {
    "raw": "#1F4E79",
    "raw_light": "#9DB7D0",
    "default": "#777777",
    "l6": "#3A9D8F",
    "wmle": "#D97706",
    "lse": "#B65C7A",
    "accent": "#C44E52",
    "ink": "#202124",
    "muted": "#686868",
    "light": "#E7E7E7",
    "pale_blue": "#EAF1F7",
    "pale_grey": "#F5F5F3",
    "pale_teal": "#E8F4F1",
}


mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "Microsoft YaHei", "DejaVu Sans", "sans-serif"],
    "font.size": 7.2,
    "axes.labelsize": 7.5,
    "axes.titlesize": 8.0,
    "xtick.labelsize": 6.8,
    "ytick.labelsize": 6.8,
    "legend.fontsize": 6.7,
    "axes.linewidth": 0.75,
    "xtick.major.width": 0.65,
    "ytick.major.width": 0.65,
    "xtick.major.size": 3.0,
    "ytick.major.size": 3.0,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "axes.unicode_minus": False,
})


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def source_paths() -> dict[str, Path]:
    cfg = read_json(CONFIG_PATH)
    return {key: Path(value) for key, value in cfg["source_data"].items()}


def style_axis(ax, *, xgrid=False, ygrid=False):
    ax.spines["left"].set_color("#7A7A7A")
    ax.spines["bottom"].set_color("#7A7A7A")
    ax.tick_params(colors=COLORS["ink"])
    ax.set_axisbelow(True)
    if xgrid:
        ax.grid(axis="x", color=COLORS["light"], lw=0.55)
    if ygrid:
        ax.grid(axis="y", color=COLORS["light"], lw=0.55)


def panel_label(ax, label):
    ax.text(-0.12, 1.04, label, transform=ax.transAxes, weight="bold",
            fontsize=8.2, va="bottom", ha="left", color=COLORS["ink"])


def export_figure(fig, stem: str, folder: Path, *, tiff=True):
    folder.mkdir(parents=True, exist_ok=True)
    svg_path = folder / f"{stem}.svg"
    svg_temporary = folder / f"{stem}.new.svg"
    fig.savefig(svg_temporary, bbox_inches="tight", facecolor="white")
    # Matplotlib writes trailing spaces inside multi-line SVG path data.
    # Normalize text-only whitespace so generated figures pass git diff --check.
    svg_text = svg_temporary.read_text(encoding="utf-8")
    svg_temporary.write_text(
        "\n".join(line.rstrip() for line in svg_text.splitlines()) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    svg_temporary.replace(svg_path)
    for extension, kwargs in (
        ("pdf", {}),
        ("png", {"dpi": 300}),
    ):
        target = folder / f"{stem}.{extension}"
        temporary = folder / f"{stem}.new.{extension}"
        fig.savefig(temporary, bbox_inches="tight", facecolor="white", **kwargs)
        temporary.replace(target)
    if tiff:
        # Some Windows image viewers briefly retain a handle to the existing
        # TIFF.  Render to a sibling file and replace only after PIL closes it.
        target = folder / f"{stem}.tiff"
        temporary = folder / f"{stem}.new.tiff"
        fig.savefig(temporary, dpi=600, bbox_inches="tight",
                    facecolor="white", pil_kwargs={"compression": "tiff_lzw"})
        temporary.replace(target)
    plt.close(fig)


def save_source(df: pd.DataFrame, name: str):
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    target = DERIVED_DIR / name
    temporary = target.with_name(f"{target.stem}.new{target.suffix}")
    df.to_csv(
        temporary,
        index=False,
        encoding="utf-8",
        lineterminator="\n",
    )
    temporary.replace(target)


def normalize_generated_text_to_lf(path: Path) -> None:
    """Keep tracked text bytes identical before and after Git normalization."""
    if path.suffix.lower() not in {".csv", ".json", ".md", ".svg", ".txt"}:
        return
    raw = path.read_bytes()
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if normalized != raw:
        path.write_bytes(normalized)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_submission_provenance(paths: dict[str, Path]):
    """Bind the manuscript-side figures to their declared sealed sources."""
    output_files = []
    for folder in (MAIN_DIR, SUPP_DIR, DERIVED_DIR, TABLES_DIR):
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            normalize_generated_text_to_lf(path)
            output_files.append(path)

    source_files = {}
    for key, folder in paths.items():
        for name in ("manifest.json", "summary.json", "summary.csv"):
            path = folder / name
            if path.is_file():
                source_files[f"{key}/{name}"] = sha256_file(path)

    try:
        git_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=FIGURE_DIR, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        git_head = None

    manifest = {
        "schema_version": 2,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "generator": str(Path(__file__).resolve()),
        "generator_sha256": sha256_file(Path(__file__).resolve()),
        "figure_sources_sha256": sha256_file(CONFIG_PATH),
        "runtime_head_commit": git_head,
        "method": "Mean-normalized MLP: sort(X)/mean(X), then train-fold-only per-position StandardScaler",
        "sources": {key: str(folder) for key, folder in paths.items()},
        "source_file_sha256": source_files,
        "outputs": {
            str(path.relative_to(FIGURE_DIR)).replace("\\", "/"): sha256_file(path)
            for path in output_files
        },
        "notes": [
            "Paper main figures use the fixed primary seed 42; seeds 2026 and 3407 are sensitivity evidence only.",
            "E8 seed42_primary, specialist, unseen-beta, and quantile evidence support the formal mean-normalized route.",
            "E6 traditional_ref supplies unchanged WMLE/LSE comparison values.",
            "E5 selector_output supplies sealed out-of-fold mean-normalized selections bound by the E8 manifest.",
            "E11 supplies the bounded 20-cell profile-gradient mechanism diagnostic used in Figure 5.",
            "Tracked text outputs are normalized to LF before hashing so repository bytes reproduce the ledger on Windows and Unix checkouts.",
        ],
    }
    PROVENANCE_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = PROVENANCE_DIR / "manifest.json"
    manifest_temporary = PROVENANCE_DIR / "manifest.new.json"
    with manifest_temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    manifest_temporary.replace(manifest_path)
    checksum_lines = [
        f"{digest}  {name}" for name, digest in sorted(manifest["outputs"].items())
    ]
    checksum_path = PROVENANCE_DIR / "SHA256SUMS"
    checksum_temporary = PROVENANCE_DIR / "SHA256SUMS.new"
    with checksum_temporary.open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write("\n".join(checksum_lines) + "\n")
    checksum_temporary.replace(checksum_path)


def load_summary(paths):
    return read_json(paths["specialist"] / "summary.json")


def load_full_scan():
    code_dir = Path(read_json(CONFIG_PATH)["canonical_generator"]).parent
    if str(code_dir) not in sys.path:
        sys.path.insert(0, str(code_dir))
    import paper_support as paper_support

    _, df_full, _ = paper_support.load_scan(verbose=False)
    return paper_support, df_full


def draw_box(ax, xy, width, height, text, *, face, edge, fontsize=6.4,
             linewidth=0.9, radius=0.012):
    x, y = xy
    patch = FancyBboxPatch(
        (x, y), width, height,
        boxstyle=f"round,pad=0.006,rounding_size={radius}",
        facecolor=face, edgecolor=edge, linewidth=linewidth,
        transform=ax.transAxes,
    )
    ax.add_patch(patch)
    ax.text(x + width / 2, y + height / 2, text, ha="center", va="center",
            fontsize=fontsize, color=COLORS["ink"], transform=ax.transAxes,
            linespacing=1.25)
    return patch


def draw_arrow(ax, start, end, *, color="#666666", linestyle="-", lw=0.9,
               mutation=9):
    arrow = FancyArrowPatch(start, end, transform=ax.transAxes,
                            arrowstyle="-|>", mutation_scale=mutation,
                            linewidth=lw, color=color, linestyle=linestyle,
                            shrinkA=0, shrinkB=0)
    ax.add_patch(arrow)


def figure_1_method_structure():
    """Schematic-led method figure centred on loss-curve learning and selection."""
    fig = plt.figure(figsize=(178 * MM, 102 * MM))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def draw_mlp(x, y, width, height, *, trained=False):
        patch = FancyBboxPatch(
            (x, y), width, height,
            boxstyle="round,pad=0.006,rounding_size=0.012",
            facecolor=COLORS["pale_blue"], edgecolor=COLORS["raw"],
            linewidth=1.0, transform=ax.transAxes,
        )
        ax.add_patch(patch)
        ax.text(x + width / 2, y + height * 0.78,
                "Trained per-$n$ MLP" if trained else "Per-$n$ MLP",
                ha="center", va="center", fontsize=6.2, weight="bold",
                color=COLORS["raw"], transform=ax.transAxes)
        node_x = np.linspace(x + width * 0.31, x + width * 0.69, 3)
        node_counts = (3, 2, 3)
        node_y = []
        for xx, count in zip(node_x, node_counts):
            ys = np.linspace(y + height * 0.34, y + height * 0.56, count)
            node_y.append(ys)
        for j in range(2):
            for y1 in node_y[j]:
                for y2 in node_y[j + 1]:
                    ax.plot([node_x[j], node_x[j + 1]], [y1, y2],
                            color=COLORS["raw_light"], lw=0.35,
                            transform=ax.transAxes, zorder=2)
        for xx, ys in zip(node_x, node_y):
            ax.scatter(np.repeat(xx, len(ys)), ys, s=7.5,
                       facecolor="white", edgecolor=COLORS["raw"],
                       linewidth=0.55, transform=ax.transAxes, zorder=3)
        ax.text(x + width / 2, y + height * 0.15, "hidden: 256–128–64",
                ha="center", va="center", fontsize=5.1,
                color=COLORS["muted"], transform=ax.transAxes)

    def draw_curve_axes(bounds, *, show_actual, mark_minimum=False, title=None,
                        show_xlabel=True):
        curve_ax = ax.inset_axes(bounds)
        delta = np.linspace(0, 0.50, 26)
        actual = 0.44 + 2.05 * (delta - 0.22) ** 2 + 0.018 * np.cos(24 * delta)
        predicted = 0.455 + 1.92 * (delta - 0.235) ** 2 + 0.013 * np.sin(22 * delta)
        if show_actual:
            curve_ax.plot(delta, actual, color=COLORS["l6"], lw=1.55,
                          label="Actual loss")
        curve_ax.plot(delta, predicted, color=COLORS["raw"], lw=1.55,
                      linestyle=(0, (3, 1.5)) if show_actual else "-",
                      label="Predicted loss")
        if mark_minimum:
            idx = int(np.argmin(predicted))
            curve_ax.axvline(delta[idx], color=COLORS["wmle"], lw=0.9,
                             linestyle=(0, (2, 2)), alpha=0.9)
            curve_ax.scatter(delta[idx], predicted[idx], s=24,
                             facecolor=COLORS["wmle"], edgecolor="white",
                             linewidth=0.6, zorder=4)
            curve_ax.annotate(r"$\widehat{\delta}$",
                              xy=(delta[idx], predicted[idx]),
                              xytext=(delta[idx] + 0.055, predicted[idx] + 0.045),
                              color=COLORS["wmle"], fontsize=6.7, weight="bold",
                              arrowprops={"arrowstyle": "-", "lw": 0.7,
                                          "color": COLORS["wmle"]})
        curve_ax.set_xlim(-0.01, 0.51)
        curve_ax.set_ylim(0.40, 0.66)
        curve_ax.set_xticks([0, 0.5])
        curve_ax.set_xticklabels(["0", "0.5"], fontsize=5.2)
        curve_ax.set_yticks([])
        if show_xlabel:
            curve_ax.set_xlabel(r"Candidate offset $\delta$", fontsize=5.5, labelpad=-1)
        curve_ax.set_ylabel("Loss", fontsize=5.5, labelpad=1)
        curve_ax.spines["left"].set_color(COLORS["muted"])
        curve_ax.spines["bottom"].set_color(COLORS["muted"])
        curve_ax.tick_params(length=2, pad=1, colors=COLORS["muted"])
        if title:
            curve_ax.set_title(title, fontsize=6.2, weight="bold", pad=2,
                               color=COLORS["ink"])
        if show_actual:
            curve_ax.text(0.48, actual[-1] + 0.004, "actual",
                          color=COLORS["l6"], fontsize=5.4, ha="right")
            curve_ax.text(0.48, predicted[-1] - 0.025, "predicted",
                          color=COLORS["raw"], fontsize=5.4, ha="right")
        return curve_ax

    # Two panels: offline learning of the loss curve, then deployment on one sample.
    ax.add_patch(Rectangle((0.015, 0.53), 0.97, 0.43, transform=ax.transAxes,
                           facecolor=COLORS["pale_grey"], edgecolor="none"))
    ax.add_patch(Rectangle((0.015, 0.055), 0.97, 0.395, transform=ax.transAxes,
                           facecolor="white", edgecolor=COLORS["light"], lw=0.8))
    ax.text(0.028, 0.925, "a", fontsize=8.4, weight="bold",
            color=COLORS["ink"], transform=ax.transAxes)
    ax.text(0.053, 0.925, "Offline training: learn the 26-point loss curve",
            fontsize=7.5, weight="bold", color=COLORS["ink"],
            transform=ax.transAxes)
    ax.text(0.028, 0.415, "b", fontsize=8.4, weight="bold",
            color=COLORS["ink"], transform=ax.transAxes)
    ax.text(0.053, 0.415, "New-sample estimation: select an offset, then fit with MDM",
            fontsize=7.5, weight="bold", color=COLORS["ink"],
            transform=ax.transAxes)

    # Panel a: one simulated sample produces both the target and the prediction.
    draw_box(ax, (0.045, 0.695), 0.12, 0.105,
             "Known parameters\n" + r"$\beta,\eta,\gamma$" + "\nsample size " + r"$n$",
             face="#EFEFEF", edge="#9B9B9B", fontsize=5.9)
    ax.text(0.105, 0.825, "simulation only", ha="center", va="center",
            fontsize=5.3, color=COLORS["muted"], transform=ax.transAxes)
    draw_box(ax, (0.215, 0.695), 0.145, 0.105,
             "Monte Carlo sample\n" + r"$x_{(1)}\leq\cdots\leq x_{(n)}$",
             face="white", edge="#9B9B9B", fontsize=6.0)
    draw_box(ax, (0.415, 0.785), 0.135, 0.095,
             "26 MDM fits\n+ loss vs truth",
             face=COLORS["pale_teal"], edge=COLORS["l6"], fontsize=5.9)
    draw_mlp(0.415, 0.585, 0.135, 0.125)

    draw_arrow(ax, (0.165, 0.748), (0.215, 0.748), color=COLORS["muted"])
    draw_arrow(ax, (0.360, 0.748), (0.415, 0.833), color=COLORS["l6"])
    draw_arrow(ax, (0.360, 0.748), (0.415, 0.648), color=COLORS["raw"])
    ax.text(0.385, 0.675, "sample mean\n+ training scaler",
            fontsize=4.7, color=COLORS["raw"], ha="center", va="center",
            transform=ax.transAxes)
    draw_arrow(ax, (0.550, 0.833), (0.610, 0.790), color=COLORS["l6"])
    draw_arrow(ax, (0.550, 0.648), (0.610, 0.675), color=COLORS["raw"])
    draw_curve_axes([0.615, 0.640, 0.31, 0.200], show_actual=True,
                    title="Curve-level supervision", show_xlabel=False)
    ax.text(0.770, 0.573, "Fit the predicted curve to the actual curve",
            fontsize=5.7, color=COLORS["muted"], ha="center",
            transform=ax.transAxes)
    ax.text(0.949, 0.548, "schematic curves", fontsize=4.9,
            color="#8A8A8A", ha="right", transform=ax.transAxes)

    # Panel b: the selected minimum is passed to MDM; the MLP never outputs parameters.
    bottom_y, bh = 0.205, 0.105
    draw_box(ax, (0.045, bottom_y), 0.105, bh,
             "Current sample\n" + r"$x_1,\ldots,x_n$",
             face="white", edge=COLORS["raw"], fontsize=5.9)
    draw_box(ax, (0.185, bottom_y), 0.115, bh,
             "Sort values\n/ sample mean\n+ training scaler",
             face=COLORS["pale_blue"], edge=COLORS["raw"], fontsize=5.3)
    draw_mlp(0.335, 0.185, 0.135, 0.145, trained=True)
    draw_curve_axes([0.520, 0.145, 0.205, 0.18], show_actual=False,
                    mark_minimum=True, title="Predicted loss curve")
    draw_box(ax, (0.765, bottom_y), 0.085, bh,
             "MDM at\n" + r"$\widehat{\delta}$",
             face="white", edge=COLORS["ink"], fontsize=6.1, linewidth=1.0)
    draw_box(ax, (0.890, bottom_y), 0.085, bh,
             "Parameter\nestimates\n" + r"$\widehat{\beta},\widehat{\eta},\widehat{\gamma}$",
             face="white", edge=COLORS["ink"], fontsize=5.6, linewidth=1.0)
    draw_arrow(ax, (0.150, 0.258), (0.185, 0.258), color=COLORS["raw"])
    draw_arrow(ax, (0.300, 0.258), (0.335, 0.258), color=COLORS["raw"])
    draw_arrow(ax, (0.470, 0.258), (0.520, 0.258), color=COLORS["raw"])
    draw_arrow(ax, (0.725, 0.258), (0.765, 0.258), color=COLORS["wmle"], lw=1.2)
    ax.text(0.745, 0.288, r"select $\widehat{\delta}$", fontsize=5.2,
            color=COLORS["wmle"], ha="center", transform=ax.transAxes)
    draw_arrow(ax, (0.850, 0.258), (0.890, 0.258), color=COLORS["ink"])
    ax.text(0.402, 0.135, "predicts 26 losses", fontsize=5.2,
            color=COLORS["raw"], ha="center", transform=ax.transAxes)
    ax.text(0.813, 0.135, "estimates parameters", fontsize=5.2,
            color=COLORS["ink"], ha="center", transform=ax.transAxes)

    method_contract = {
        "core_conclusion": "the MLP predicts a candidate-loss curve and selects delta; MDM estimates the Weibull parameters",
        "archetype": "two-panel schematic-led method figure",
        "input": "sorted sample / sample mean, one network per n",
        "preprocessing": "position-wise StandardScaler fitted on training fold only",
        "network": "MLP 256-128-64, ReLU, Adam",
        "output": "predicted loss at 26 candidate delta values",
        "decision": "argmin predicted loss; MDM estimates beta, eta, gamma",
        "training_target": "actual 26-point loss curve computed from Monte Carlo truth and 26 MDM fits",
        "illustrative_curves": "schematic only; not numerical evidence",
    }
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    with (DERIVED_DIR / "fig1_method_contract.json").open("w", encoding="utf-8") as handle:
        json.dump(method_contract, handle, ensure_ascii=False, indent=2)
    export_figure(fig, "fig1_method_structure", MAIN_DIR)


def delta_risk_curve(paths):
    _, df_full = load_full_scan()
    loss = pd.to_numeric(df_full["loss"], errors="coerce")
    curve = (df_full.assign(loss=loss).groupby("delta", as_index=False)["loss"].mean())
    curve["J1"] = np.sqrt(curve["loss"])
    curve = curve[["delta", "J1"]].sort_values("delta").reset_index(drop=True)
    save_source(curve, "fig2_delta_risk.csv")
    return curve


def figure_2_delta_risk(paths):
    curve = delta_risk_curve(paths)
    d_min = float(curve.loc[curve["J1"].idxmin(), "delta"])
    j_min = float(curve["J1"].min())
    j_default = float(curve.loc[np.isclose(curve["delta"], 0.10), "J1"].iloc[0])

    layers = pd.read_csv(paths["specialist"] / "crossfit_layers.csv")
    layers["improvement_pct"] = 100 * (1 - layers["J1"] / layers.loc[0, "J1"])
    layers["condition_group"] = np.select(
        [layers["layer"].isin(["Default", "L1", "L2"]),
         layers["layer"].isin(["L3", "L4", "L5"])],
        ["fixed_or_n_conditioned", "parameter_conditioned_average"],
        default="sample_level_hindsight",
    )
    save_source(layers, "fig2_decision_conditions.csv")

    fig, (ax, zoom, ladder) = plt.subplots(
        1, 3, figsize=(183 * MM, 72 * MM),
        gridspec_kw={"width_ratios": [1.30, 0.92, 0.95], "wspace": 0.50},
    )
    for target in (ax, zoom):
        target.plot(curve["delta"], curve["J1"], color=COLORS["ink"],
                    lw=1.45, marker="o", ms=2.8, mfc="white", mew=0.8)
        style_axis(target)
        target.set_xlabel(r"Offset, $\delta$")
        target.set_ylabel(r"Pooled $J_1$")

    ax.scatter([d_min], [j_min], s=28, color=COLORS["raw"], zorder=5,
               label=f"Minimum ({d_min:.2f})")
    ax.scatter([0.10], [j_default], s=30, color=COLORS["accent"], marker="s",
               zorder=5, label="Default (0.10)")
    ax.set_xlim(-0.01, 0.51)
    ax.set_ylim(0.60, max(curve["J1"].max() + 0.015, 0.96))
    ax.legend(loc="upper right", handletextpad=0.5)
    ax.set_title("Full candidate grid", pad=4)
    panel_label(ax, "a")

    zoom_mask = curve["delta"].between(0.02, 0.16)
    zoom.lines[0].set_data(curve.loc[zoom_mask, "delta"], curve.loc[zoom_mask, "J1"])
    zoom.axvspan(0.06, 0.10, color=COLORS["pale_blue"], zorder=-1)
    zoom.scatter([d_min], [j_min], s=28, color=COLORS["raw"], zorder=5)
    zoom.scatter([0.10], [j_default], s=30, color=COLORS["accent"], marker="s", zorder=5)
    zoom.set_xlim(0.015, 0.165)
    local = curve.loc[zoom_mask, "J1"]
    zoom.set_ylim(local.min() - 0.004, local.max() + 0.006)
    zoom.set_xticks([0.02, 0.06, 0.10, 0.14])
    zoom.annotate(f"minimum\n{j_min:.4f}", (d_min, j_min),
                  xytext=(0.037, j_min + 0.027), fontsize=6.3,
                  arrowprops={"arrowstyle": "-", "lw": 0.7, "color": COLORS["muted"]})
    zoom.annotate(f"default\n{j_default:.4f}", (0.10, j_default),
                  xytext=(0.116, j_default + 0.012), fontsize=6.3,
                  arrowprops={"arrowstyle": "-", "lw": 0.7, "color": COLORS["muted"]})
    zoom.set_title("Low-risk region", pad=4)
    panel_label(zoom, "b")

    layer_colors = [COLORS["default"], "#AAB7C4", "#91A7BD", "#7696B3",
                    "#5A82A8", COLORS["raw"], COLORS["l6"]]
    y = np.arange(len(layers))
    ladder.axhspan(-0.45, 2.45, color=COLORS["pale_grey"], zorder=-3)
    ladder.axhspan(2.55, 5.45, color=COLORS["pale_blue"], alpha=0.65, zorder=-3)
    ladder.axhspan(5.55, 6.45, color=COLORS["pale_teal"], zorder=-3)
    ladder.hlines(y, layers["J1"].min() - 0.01, layers["J1"],
                  color="#D8D8D8", lw=1.0)
    ladder.scatter(layers["J1"], y, c=layer_colors, s=25, zorder=3)
    ladder.set_yticks(y, layers["layer"])
    ladder.invert_yaxis()
    ladder.set_xlabel(r"Pooled $J_1$")
    ladder.set_xlim(layers["J1"].min() - 0.016, layers["J1"].max() + 0.018)
    ladder.set_ylim(6.55, -0.55)
    style_axis(ladder)
    for yi, row in layers.iterrows():
        if row["layer"] in ("Default", "L3", "L5", "L6"):
            ladder.text(row["J1"] + 0.004, yi, f"{row['J1']:.3f}",
                        va="center", fontsize=5.7, color=COLORS["muted"])
    ladder.text(0.99, 0.965, "fixed / sample-size rules", transform=ladder.transAxes,
                ha="right", va="top", fontsize=5.5, color=COLORS["muted"])
    ladder.text(0.99, 0.545, "parameter-conditioned averages",
                transform=ladder.transAxes, ha="right", va="top",
                fontsize=5.5, color=COLORS["raw"])
    ladder.text(0.99, 0.105, "sample-level hindsight",
                transform=ladder.transAxes, ha="right", va="top",
                fontsize=5.5, color=COLORS["l6"])
    ladder.set_title("Decision and reference conditions", pad=4)
    panel_label(ladder, "c")
    fig.align_ylabels()
    export_figure(fig, "fig2_overall_delta_risk", MAIN_DIR)


def main_results_by_n(summary):
    ns = [7, 10, 15, 20]
    seeds = pd.DataFrame(summary["seed_table"])
    comp = pd.DataFrame(summary["model_comparison"])
    primary = seeds[seeds["seed"] == PRIMARY_SEED]
    if len(primary) != 1:
        raise AssertionError(f"Expected one primary-seed row, got {len(primary)}")
    primary = primary.iloc[0]
    rows = []
    for n in ns:
        raw_value = float(primary[f"J1_n{n}"])
        default = float(comp.loc[(comp["model"] == "Default") &
                                 (comp["seed"] == PRIMARY_SEED), f"J1_n{n}"].iloc[0])
        l6 = float(comp.loc[(comp["model"] == "L6-hindsight") &
                            (comp["seed"] == PRIMARY_SEED), f"J1_n{n}"].iloc[0])
        rows.append({
            "n": n,
            "adaptive": raw_value,
            "default": default,
            "l6": l6,
            "adaptive_improvement_pct": 100 * (1 - raw_value / default),
            "l6_improvement_pct": 100 * (1 - l6 / default),
            "observed_default_to_hindsight_J1_gap": default - l6,
        })
    out = pd.DataFrame(rows)
    save_source(out, "fig3_main_results_by_n.csv")
    return out


def sample_loss_difference_by_n(paths):
    """Summarize paired losses for the fixed primary training seed."""
    _, df_full = load_full_scan()
    diag = pd.read_csv(paths["selector_output"] / "diagnostics" /
                       "near_optimal_diagnostics.csv", low_memory=False)
    keys = ["beta", "gamma_over_eta", "n", "repeat_id"]
    default = df_full[np.isclose(pd.to_numeric(df_full["delta"]), 0.10)][
        keys + ["loss"]].rename(columns={"loss": "default_loss"})
    if default.duplicated(keys).any():
        raise AssertionError("Default sample losses are not unique")
    adaptive = diag[diag["seed"] == PRIMARY_SEED][keys + ["true_loss"]].copy()
    adaptive = adaptive.rename(columns={"true_loss": "adaptive_loss"})
    if adaptive.duplicated(keys).any():
        raise AssertionError("Primary-seed adaptive sample losses are not unique")
    paired = adaptive.merge(default, on=keys, how="left", validate="one_to_one")
    if paired["default_loss"].isna().any():
        raise AssertionError("Missing Default loss for a paired sample")
    paired["loss_difference"] = paired["default_loss"] - paired["adaptive_loss"]

    rows = []
    for n, group in paired.groupby("n"):
        quantiles = group["loss_difference"].quantile(
            [0.01, 0.05, 0.25, 0.50, 0.75, 0.95, 0.99])
        rows.append({
            "n": int(n),
            "n_samples": int(len(group)),
            "improved_pct": 100 * float((group["loss_difference"] > 1e-12).mean()),
            "unchanged_pct": 100 * float((group["loss_difference"].abs() <= 1e-12).mean()),
            "worsened_pct": 100 * float((group["loss_difference"] < -1e-12).mean()),
            **{f"q{int(q * 100):02d}": float(value)
               for q, value in quantiles.items()},
        })
    out = pd.DataFrame(rows).sort_values("n")
    save_source(out, "fig3_sample_loss_difference_quantiles.csv")
    write_parameter_error_decomposition(df_full, diag)
    return out


def write_parameter_error_decomposition(df_full, diag):
    """Write the three normalized error components behind the joint loss."""
    keys = ["beta", "gamma_over_eta", "n", "repeat_id"]
    estimate_cols = keys + ["delta", "eta", "gamma",
                            "beta_hat", "eta_hat", "gamma_hat"]
    default = df_full[np.isclose(pd.to_numeric(df_full["delta"]), 0.10)][
        estimate_cols].copy()
    adaptive = (diag[diag["seed"] == PRIMARY_SEED]
                .rename(columns={"selected_delta": "delta"})
                .merge(df_full[estimate_cols], on=keys + ["delta"],
                       how="left", validate="one_to_one"))
    if adaptive[["beta_hat", "eta_hat", "gamma_hat"]].isna().any().any():
        raise AssertionError("Missing selected parameter estimates")

    def summarize(frame):
        errors = {
            "beta": (frame["beta_hat"] - frame["beta"]) / frame["beta"],
            "eta": (frame["eta_hat"] - frame["eta"]) / frame["eta"],
            "gamma": (frame["gamma_hat"] - frame["gamma"]) / frame["eta"],
        }
        return {
            name: {
                "rmse": float(np.sqrt(np.mean(values ** 2))),
                "median_abs": float(np.median(np.abs(values))),
                "p95_abs": float(np.quantile(np.abs(values), 0.95)),
                "mse": float(np.mean(values ** 2)),
            }
            for name, values in errors.items()
        }

    default_metrics = summarize(default)
    adaptive_metrics_all = summarize(adaptive)
    rows = []
    for parameter in ("beta", "eta", "gamma"):
        adaptive_metrics = adaptive_metrics_all[parameter]
        rows.append({
            "parameter": parameter,
            "default_normalized_rmse": default_metrics[parameter]["rmse"],
            "adaptive_normalized_rmse": adaptive_metrics["rmse"],
            "mse_contribution_reduction_pct": 100 * (
                1 - adaptive_metrics["mse"] / default_metrics[parameter]["mse"]),
            "default_median_absolute_error": default_metrics[parameter]["median_abs"],
            "adaptive_median_absolute_error": adaptive_metrics["median_abs"],
            "default_p95_absolute_error": default_metrics[parameter]["p95_abs"],
            "adaptive_p95_absolute_error": adaptive_metrics["p95_abs"],
        })
    table = pd.DataFrame(rows)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(TABLES_DIR / "supp_table_parameter_error_decomposition.csv",
                 index=False, encoding="utf-8")
    labels = {"beta": r"$\beta$", "eta": r"$\eta$", "gamma": r"$\gamma$"}
    lines = [
        "**表 B3  联合损失的三参数误差分解。**",
        "",
        "| 参数 | Default 标准化 RMSE | 自适应标准化 RMSE | 均方误差贡献降幅 | Default 绝对误差中位数 | 自适应绝对误差中位数 | Default P95 | 自适应 P95 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in table.itertuples():
        lines.append(
            f"| {labels[row.parameter]} | {row.default_normalized_rmse:.4f} "
            f"| {row.adaptive_normalized_rmse:.4f} "
            f"| {row.mse_contribution_reduction_pct:.1f}% "
            f"| {row.default_median_absolute_error:.4f} "
            f"| {row.adaptive_median_absolute_error:.4f} "
            f"| {row.default_p95_absolute_error:.4f} "
            f"| {row.adaptive_p95_absolute_error:.4f} |")
    lines.append("")
    (TABLES_DIR / "supp_table_parameter_error_decomposition.md").write_text(
        "\n".join(lines), encoding="utf-8")


def figure_3_main_results(paths, summary):
    data = main_results_by_n(summary)
    paired = sample_loss_difference_by_n(paths)
    ns = data["n"].to_numpy()
    fig, (ax, gain) = plt.subplots(
        1, 2, figsize=(178 * MM, 76 * MM),
        gridspec_kw={"width_ratios": [1.28, 1.02], "wspace": 0.42},
    )

    ax.fill_between(ns, data["l6"], data["default"],
                    color=COLORS["pale_teal"], alpha=0.90, linewidth=0)
    ax.plot(ns, data["adaptive"], color=COLORS["raw"], lw=1.8,
            marker="o", ms=4.5)
    ax.plot(ns, data["default"], color=COLORS["default"], lw=1.35,
            marker="s", ms=3.8)
    ax.plot(ns, data["l6"], color=COLORS["l6"], lw=1.25,
            marker="^", ms=4.0, linestyle="--")
    for row in data.itertuples():
        ax.text(row.n, row.adaptive + 0.018,
                f"{row.adaptive_improvement_pct:.1f}%",
                ha="center", va="bottom", fontsize=6.2,
                color=COLORS["raw"], weight="bold")
    ax.text(0.02, 0.04, "shading: observed Default–hindsight gap",
            transform=ax.transAxes, ha="left", va="bottom", fontsize=5.6,
            color=COLORS["muted"])
    ax.text(0.02, 0.965, "% below Default", transform=ax.transAxes,
            ha="left", va="top", fontsize=5.6, color=COLORS["raw"])
    ax.text(20.55, data["default"].iloc[-1], "Default",
            color=COLORS["default"], fontsize=6.3, va="center")
    ax.text(20.55, data["adaptive"].iloc[-1], "Adaptive",
            color=COLORS["raw"], fontsize=6.3, va="center", weight="bold")
    ax.text(20.55, data["l6"].iloc[-1], "L6 hindsight",
            color=COLORS["l6"], fontsize=6.3, va="center")
    ax.set_xlabel(r"Sample size, $n$")
    ax.set_ylabel(r"Pooled $J_1$")
    ax.set_xticks(ns)
    ax.set_ylim(0.35, 0.80)
    ax.set_xlim(6.3, 23.0)
    style_axis(ax)
    panel_label(ax, "a")

    gain.axhspan(0, 1.06, color=COLORS["pale_teal"], alpha=0.65, zorder=-3)
    gain.axhspan(-0.62, 0, color="#F8ECEC", alpha=0.65, zorder=-3)
    gain.axhline(0, color="#555555", lw=0.8, linestyle="--", zorder=1)
    for row in paired.itertuples():
        gain.vlines(row.n, row.q01, row.q99, color=COLORS["raw_light"],
                    lw=1.15, zorder=2)
        gain.vlines(row.n, row.q05, row.q95, color=COLORS["raw"],
                    lw=2.5, zorder=3)
        gain.vlines(row.n, row.q25, row.q75, color=COLORS["raw"],
                    lw=7.0, zorder=4)
        gain.scatter(row.n, row.q50, s=19, color="white",
                     edgecolor=COLORS["raw"], lw=0.9, zorder=5)
        gain.text(row.n, min(row.q99 + 0.055, 0.98), f"{row.improved_pct:.1f}%",
                  ha="center", va="bottom", fontsize=6.1, color=COLORS["raw"])
    gain.text(0.98, 0.97, "Samples improved", transform=gain.transAxes,
              ha="right", va="top", fontsize=5.8, color=COLORS["muted"])
    gain.text(0.98, 0.90, "positive: adaptive better", transform=gain.transAxes,
              ha="right", va="top", fontsize=5.7, color=COLORS["l6"])
    gain.set_xticks(ns)
    gain.set_xlabel(r"Sample size, $n$")
    gain.set_ylabel(r"Paired loss difference, $\Delta\ell_i$")
    gain.set_ylim(-0.62, 1.06)
    style_axis(gain)
    gain.text(0.5, -0.19,
              "thin: 1st–99th   medium: 5th–95th   thick: IQR   dot: median",
              transform=gain.transAxes, ha="center", va="top", fontsize=5.5,
              color=COLORS["muted"], clip_on=False)
    panel_label(gain, "b")
    fig.subplots_adjust(bottom=0.20)
    export_figure(fig, "fig3_per_n_J1", MAIN_DIR)


def selector_mechanism_data(paths):
    """Derive a typical loss curve, delta-confusion matrix, and regret quantiles."""
    _, df_full = load_full_scan()
    diag = pd.read_csv(paths["selector_output"] / "diagnostics" /
                       "near_optimal_diagnostics.csv", low_memory=False)
    keys = ["beta", "gamma_over_eta", "n", "repeat_id"]
    valid = df_full[pd.to_numeric(df_full["loss"], errors="coerce").notna()].copy()
    oracle_idx = valid.groupby(keys)["loss"].idxmin()
    oracle = valid.loc[oracle_idx, keys + ["delta", "loss"]].rename(
        columns={"delta": "oracle_delta", "loss": "oracle_loss"})
    diag = diag[diag["seed"] == PRIMARY_SEED].copy()
    diag = diag.merge(oracle, on=keys, how="left", validate="one_to_one")
    if diag["oracle_delta"].isna().any():
        raise AssertionError("Missing hindsight delta for selector diagnostics")
    diag["regret"] = (diag["true_loss"] - diag["oracle_loss"]).clip(lower=0)

    median_regret = float(diag["regret"].median())
    typical = diag.iloc[(diag["regret"] - median_regret).abs().argmin()]
    prediction_path = paths["selector_output"] / "predictions" / f"{typical['model_id']}.csv"
    prediction = pd.read_csv(prediction_path, low_memory=False)
    mask = ((prediction["repeat_id"] == int(typical["repeat_id"])) &
            (prediction["n"] == int(typical["n"])) &
            np.isclose(prediction["beta"], float(typical["beta"])) &
            np.isclose(prediction["gamma_over_eta"], float(typical["gamma_over_eta"])))
    pred_row = prediction.loc[mask]
    if len(pred_row) != 1:
        raise AssertionError("Representative prediction row is not unique")
    pred_row = pred_row.iloc[0]
    pred_cols = sorted((c for c in prediction.columns if c.startswith("pred_d")),
                       key=lambda name: float(name.removeprefix("pred_d")))
    deltas = np.array([float(c.removeprefix("pred_d")) for c in pred_cols])
    sample_mask = ((valid["repeat_id"] == int(typical["repeat_id"])) &
                   (valid["n"] == int(typical["n"])) &
                   np.isclose(valid["beta"], float(typical["beta"])) &
                   np.isclose(valid["gamma_over_eta"], float(typical["gamma_over_eta"])))
    actual = valid.loc[sample_mask, ["delta", "loss"]].sort_values("delta")
    curve = pd.DataFrame({
        "delta": deltas,
        "observed_loss": actual.set_index("delta").loc[deltas, "loss"].to_numpy(),
        "predicted_loss": pred_row[pred_cols].to_numpy(dtype=float),
        "selected_delta": float(typical["selected_delta"]),
        "oracle_delta": float(typical["oracle_delta"]),
        "n": int(typical["n"]),
        "beta": float(typical["beta"]),
        "gamma_over_eta": float(typical["gamma_over_eta"]),
        "repeat_id": int(typical["repeat_id"]),
        "selection_rule": "closest to median regret among primary-seed test predictions",
    })
    save_source(curve, "fig4_representative_curve.csv")

    confusion = pd.crosstab(diag["oracle_delta"], diag["selected_delta"],
                            normalize="index").reindex(index=deltas, columns=deltas,
                                                       fill_value=0.0) * 100
    confusion_long = (confusion.rename_axis("oracle_delta").reset_index()
                      .melt(id_vars="oracle_delta", var_name="selected_delta",
                            value_name="row_percent"))
    save_source(confusion_long, "fig4_delta_confusion.csv")

    quantiles = []
    for n, group in diag.groupby("n"):
        for q in (0.50, 0.90, 0.99):
            quantiles.append({"n": int(n), "quantile": q,
                              "excess_loss": float(group["regret"].quantile(q))})
    regret = pd.DataFrame(quantiles)
    save_source(regret, "fig4_excess_loss_quantiles.csv")
    return curve, confusion, regret


def figure_4_selector_mechanism(paths):
    curve, confusion, regret = selector_mechanism_data(paths)
    fig = plt.figure(figsize=(183 * MM, 112 * MM))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 0.78],
                          width_ratios=[1.05, 1.0], hspace=0.42, wspace=0.38)
    ax_curve = fig.add_subplot(gs[0, 0])
    ax_heat = fig.add_subplot(gs[0, 1])
    ax_regret = fig.add_subplot(gs[1, :])

    ax_curve.plot(curve["delta"], curve["observed_loss"], color=COLORS["ink"],
                  lw=1.5, marker="o", ms=3, mfc="white", label="Observed loss")
    ax_curve.plot(curve["delta"], curve["predicted_loss"], color=COLORS["raw"],
                  lw=1.5, marker="o", ms=3, label="Predicted loss")
    selected = float(curve["selected_delta"].iloc[0])
    oracle = float(curve["oracle_delta"].iloc[0])
    ax_curve.axvline(selected, color=COLORS["raw"], lw=1.0, linestyle="--",
                     label=rf"Selected $\delta={selected:.2f}$")
    ax_curve.axvline(oracle, color=COLORS["l6"], lw=1.0, linestyle=":",
                     label=rf"Hindsight $\delta={oracle:.2f}$")
    ax_curve.set_xlabel(r"Candidate offset, $\delta$")
    ax_curve.set_ylabel("Single-sample loss")
    style_axis(ax_curve)
    ax_curve.legend(loc="upper right", ncol=2, columnspacing=0.8,
                    handletextpad=0.4)
    ax_curve.set_title("Rule-selected median-regret case", pad=4)
    panel_label(ax_curve, "a")

    delta_grid = confusion.index.to_numpy(dtype=float)
    edges = np.r_[delta_grid - 0.01, delta_grid[-1] + 0.01]
    mesh = ax_heat.pcolormesh(edges, edges, confusion.to_numpy(), cmap="Blues",
                              shading="flat", vmin=0,
                              vmax=max(10.0, float(np.nanpercentile(confusion, 99))))
    ax_heat.plot([0, 0.5], [0, 0.5], color=COLORS["accent"], lw=0.9,
                 linestyle="--")
    ax_heat.set_xlabel(r"Selected $\delta$")
    ax_heat.set_ylabel(r"Hindsight $\delta$")
    ticks = np.arange(0, 0.51, 0.10)
    ax_heat.set_xticks(ticks)
    ax_heat.set_yticks(ticks)
    ax_heat.set_aspect("equal")
    for spine in ax_heat.spines.values():
        spine.set_visible(False)
    cbar = fig.colorbar(mesh, ax=ax_heat, fraction=0.046, pad=0.04)
    cbar.set_label("Row percentage (%)", fontsize=6.5)
    cbar.ax.tick_params(labelsize=6.0)
    ax_heat.set_title("Offset selection correspondence", pad=4)
    panel_label(ax_heat, "b")

    q_styles = {0.50: ("o", "Median"), 0.90: ("s", "90th percentile"),
                0.99: ("^", "99th percentile")}
    for q, (marker, label) in q_styles.items():
        sub = regret[regret["quantile"] == q]
        ax_regret.plot(sub["n"], sub["excess_loss"], marker=marker, ms=4,
                       lw=1.4, label=label,
                       color={0.50: COLORS["raw_light"], 0.90: COLORS["raw"],
                              0.99: COLORS["accent"]}[q])
    ax_regret.set_yscale("log")
    ax_regret.set_xticks([7, 10, 15, 20])
    ax_regret.set_xlabel(r"Sample size, $n$")
    ax_regret.set_ylabel("Excess loss above hindsight")
    style_axis(ax_regret)
    ax_regret.legend(ncol=3, loc="upper right")
    ax_regret.set_title("Distribution of excess loss", pad=4)
    panel_label(ax_regret, "c")
    export_figure(fig, "fig4_selector_mechanism", MAIN_DIR)


def e10_mechanism_data(paths):
    """Load compact E10 mechanism evidence without re-running the experiment."""
    root = paths["e10_z_only"]
    summary = read_json(root / "summary.json")
    cells = pd.read_csv(root / "mechanism_by_cell.csv")
    learning = pd.read_csv(root / "learning_curve.csv")

    method_rows = pd.read_csv(root / "confirmation_by_method.csv")
    pooled = method_rows[method_rows["n"].astype(str) == "pooled"].copy()
    method_order = [
        "Default", "Paper-MLP", "In-domain-current-MLP",
        "Z-only-empirical-reference", "L6-complete-information",
    ]
    pooled["method"] = pd.Categorical(pooled["method"], method_order, ordered=True)
    risk = pooled[pooled["method"].notna()].sort_values("method").copy()
    risk["method"] = risk["method"].astype(str)
    if risk["method"].tolist() != method_order:
        raise AssertionError("E10 pooled risk method order is incomplete")

    cell_source = cells[[
        "beta", "gamma_over_eta", "n", "count",
        "l6_effective_delta_count", "l6_delta_entropy_nats",
        "l5_l6_delta_match_rate", "paper_l6_delta_match_rate",
        "z_reference_l6_delta_match_rate",
    ]].copy()
    risk_source = risk[["method", "R_mean_loss", "J1", "count"]].copy()
    learning_source = learning[[
        "n", "candidate", "repeats_per_cell", "training_samples",
        "confirmation_samples", "R_mean_loss", "J1",
    ]].copy()
    return summary, cell_source, risk_source, learning_source


def supplementary_decision_conditions(paths):
    summary, cells, risk, _ = e10_mechanism_data(paths)
    save_source(cells, "supp_decision_within_cell_hindsight.csv")
    save_source(risk, "supp_decision_z_only_risk_path.csv")
    ns = [7, 10, 15, 20]
    fig, (ax_diversity, ax_risk) = plt.subplots(
        1, 2, figsize=(183 * MM, 82 * MM),
        gridspec_kw={"width_ratios": [0.86, 1.48], "wspace": 0.38},
    )

    # Panel a: real per-cell distributions, with deterministic horizontal jitter.
    rng = np.random.default_rng(42)
    positions = np.arange(len(ns))
    for pos, n in zip(positions, ns):
        values = cells.loc[cells["n"] == n, "l6_effective_delta_count"].to_numpy()
        violin = ax_diversity.violinplot(
            values, positions=[pos], widths=0.72, showmeans=False,
            showmedians=False, showextrema=False,
        )
        for body in violin["bodies"]:
            body.set_facecolor(COLORS["pale_teal"])
            body.set_edgecolor(COLORS["l6"])
            body.set_alpha(0.95)
            body.set_linewidth(0.8)
        jitter = rng.uniform(-0.23, 0.23, size=len(values))
        ax_diversity.scatter(
            pos + jitter, values, s=5.5, color=COLORS["l6"], alpha=0.38,
            linewidths=0, zorder=2,
        )
        q1, med, q3 = np.quantile(values, [0.25, 0.50, 0.75])
        ax_diversity.vlines(pos, q1, q3, color=COLORS["ink"], lw=3.0, zorder=4)
        ax_diversity.scatter(pos, med, s=16, color="white",
                             edgecolor=COLORS["ink"], lw=0.8, zorder=5)
    pooled_median = float(np.median(cells["l6_effective_delta_count"]))
    match = summary["realization_mechanism"]
    ax_diversity.set_xticks(positions, [str(n) for n in ns])
    ax_diversity.set_xlabel(r"Sample size, $n$")
    ax_diversity.set_ylabel("Effective L6 offset count within a cell")
    ax_diversity.set_ylim(1.0, max(13.0, cells["l6_effective_delta_count"].max() + 0.5))
    ax_diversity.text(
        0.03, 0.96, f"pooled median = {pooled_median:.2f}",
        transform=ax_diversity.transAxes, ha="left", va="top",
        fontsize=5.8, color=COLORS["muted"],
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.88,
              "pad": 1.4},
    )
    ax_diversity.text(
        0.03, 0.83,
        "Exact match to L6 offset\n"
        f"L5 {100*match['l5_l6_delta_match_rate']:.1f}%   "
        f"Paper {100*match['paper_l6_delta_match_rate']:.1f}%   "
        f"Z ref. {100*match['z_reference_l6_delta_match_rate']:.1f}%",
        transform=ax_diversity.transAxes, ha="left", va="top",
        fontsize=5.5, linespacing=1.35, color=COLORS["muted"],
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.88,
              "pad": 1.4},
    )
    ax_diversity.set_title("Within-cell variation in hindsight choices", pad=4)
    style_axis(ax_diversity, ygrid=True)
    panel_label(ax_diversity, "a")

    # Panel b: observed confirmation risk path; no Bayes-risk interpretation.
    risk_labels = [
        "Default", "Paper MLP\nlevel holdout", "Current MLP\nin-domain",
        "Flexible Z-only\nreference", "L6 hindsight",
    ]
    values = risk["R_mean_loss"].to_numpy()
    xpos = np.arange(len(values))
    colors = [COLORS["default"], COLORS["raw"], "#4F789D", "#376C91", COLORS["l6"]]
    ax_risk.plot(xpos, values, color="#B8B8B8", lw=1.2, zorder=1)
    ax_risk.scatter(xpos, values, s=38, c=colors, zorder=3,
                    edgecolor="white", linewidth=0.7)
    for i, value in enumerate(values):
        ax_risk.text(i, value + 0.006, f"{value:.3f}", ha="center",
                     va="bottom", fontsize=5.8, color=COLORS["ink"])
    for i in range(len(values) - 1):
        diff = values[i] - values[i + 1]
        ax_risk.text(i + 0.5, (values[i] + values[i + 1]) / 2 + 0.003,
                     rf"$\Delta R={diff:.3f}$", ha="center", va="bottom",
                     fontsize=5.3, color=COLORS["muted"])
    residual = values[-2] - values[-1]
    ax_risk.annotate(
        "unresolved residual\n(not all perfect-information gap)",
        xy=(3.55, (values[-2] + values[-1]) / 2), xytext=(3.03, 0.272),
        ha="center", va="center", fontsize=5.4, color=COLORS["muted"],
        arrowprops={"arrowstyle": "-", "lw": 0.7, "color": COLORS["muted"]},
    )
    ax_risk.text(
        0.02, 0.04,
        "Paper→in-domain difference also changes coverage/protocol;\n"
        "the flexible Z-only reference is achieved, not Bayes-optimal.",
        transform=ax_risk.transAxes, ha="left", va="bottom",
        fontsize=5.3, color=COLORS["muted"], linespacing=1.25,
    )
    ax_risk.set_xticks(xpos, risk_labels)
    ax_risk.set_ylabel(r"Confirmation risk, $R=J_1^2$")
    ax_risk.set_ylim(0.225, 0.415)
    ax_risk.set_xlim(-0.35, 4.35)
    ax_risk.set_title("Observed risk differences under distinct decision conditions", pad=4)
    style_axis(ax_risk, ygrid=True)
    panel_label(ax_risk, "b")
    fig.subplots_adjust(bottom=0.24)
    export_figure(fig, "supp_fig_decision_conditions", SUPP_DIR)


def e11_profile_mechanism_data(paths):
    """Load compact E11 profile diagnostics without re-running MDM."""
    root = paths["e11_profile_mechanism"]
    summary = read_json(root / "summary.json")
    representatives = pd.read_csv(root / "representative_gradient_curves.csv")
    curves = pd.read_csv(root / "conditional_loss_curves.csv")
    cells = pd.read_csv(root / "cell_associations.csv")

    conditional = curves[curves["stratifier"] == "default_gamma_hat"].copy()
    if len(conditional) != 3 * 26:
        raise AssertionError("E11 default-gamma conditional curves are incomplete")
    if len(cells) != 20 or set(cells["n"].astype(int)) != {7, 10, 15, 20}:
        raise AssertionError("E11 cell association table is incomplete")

    save_source(representatives, "fig5_profile_gradient_curves.csv")
    save_source(conditional, "fig5_conditional_excess_loss.csv")
    save_source(cells, "fig5_cell_associations.csv")
    return summary, representatives, conditional, cells


def figure_5_decision_mechanism(paths):
    """Explain how sample realisation moves the MDM profile and low-risk offset."""
    summary, representatives, conditional, cells = e11_profile_mechanism_data(paths)
    fig = plt.figure(figsize=(183 * MM, 125 * MM))
    grid = fig.add_gridspec(
        2, 2, height_ratios=[1.06, 0.94], width_ratios=[1.34, 0.86],
        hspace=0.46, wspace=0.34,
    )
    ax_profile = fig.add_subplot(grid[0, :])
    ax_loss = fig.add_subplot(grid[1, 0])
    ax_rho = fig.add_subplot(grid[1, 1])

    group_order = ["low", "middle", "high"]
    group_colors = {
        "low": "#2B6F92",
        "middle": "#7A7A7A",
        "high": "#C76A3A",
    }
    group_labels = {
        "low": r"Low $\hat{\gamma}_{0.1}/\eta$",
        "middle": r"Middle $\hat{\gamma}_{0.1}/\eta$",
        "high": r"High $\hat{\gamma}_{0.1}/\eta$",
    }

    # Panel a: same true cell, three observed samples, three empirical profiles.
    for group in group_order:
        frame = representatives[representatives["profile_group"] == group].sort_values(
            "gamma_over_eta"
        )
        if frame.empty:
            raise AssertionError(f"missing E11 representative group: {group}")
        first = frame.iloc[0]
        color = group_colors[group]
        ax_profile.plot(
            frame["gamma_over_eta"], frame["gradient"], color=color, lw=1.45,
            label=(
                f"{group_labels[group]}  "
                rf"($\delta_{{L6}}={first['l6_delta']:.2f}$)"
            ),
        )
        ax_profile.scatter(
            [first["l6_gamma_hat_over_eta"]], [first["l6_delta"]],
            s=25, color=color, edgecolor="white", linewidth=0.65, zorder=5,
        )
        ax_profile.plot(
            [0, first["l6_gamma_hat_over_eta"]],
            [first["l6_delta"], first["l6_delta"]],
            color=color, lw=0.6, ls=(0, (2.2, 2.2)), alpha=0.72,
        )
    ax_profile.axvline(0.50, color=COLORS["muted"], lw=0.75, ls="--")
    ax_profile.set_xlim(0, 1.30)
    ax_profile.set_ylim(-0.08, 0.72)
    ax_profile.set_xlabel(r"Candidate location, $\gamma/\eta$")
    ax_profile.set_ylabel(r"Profile gradient, $g(\gamma)$")
    ax_profile.set_title(
        r"Random samples move the empirical MDM profile "
        r"($\beta=3$, $\gamma/\eta=0.5$, $n=10$)", pad=4
    )
    ax_profile.legend(loc="upper left", ncol=3, handlelength=2.1,
                      columnspacing=1.0, fontsize=6.1)
    ax_profile.text(
        0.995, 0.04, "circles: realised L6 intersections",
        transform=ax_profile.transAxes, ha="right", va="bottom",
        fontsize=5.5, color=COLORS["muted"],
    )
    style_axis(ax_profile, ygrid=True)
    panel_label(ax_profile, "a")

    # Panel b: average excess-loss curve after within-cell stratification.
    for group in group_order:
        frame = conditional[conditional["tertile"] == group].sort_values("delta")
        color = group_colors[group]
        minimum = frame.loc[frame["mean_excess_over_l6"].idxmin()]
        ax_loss.plot(
            frame["delta"], frame["mean_excess_over_l6"], color=color,
            lw=1.55,
            label=f"{group_labels[group]}  (min {minimum['delta']:.2f})",
        )
        ax_loss.scatter(
            [minimum["delta"]], [minimum["mean_excess_over_l6"]],
            s=23, color=color, edgecolor="white", linewidth=0.6, zorder=4,
        )
    ax_loss.set_xlabel(r"Offset, $\delta$")
    ax_loss.set_ylabel("Mean excess loss above L6")
    ax_loss.set_title("The low-risk region shifts with the realised profile", pad=4)
    ax_loss.set_xlim(0, 0.50)
    ax_loss.legend(loc="upper right", fontsize=5.7)
    style_axis(ax_loss, ygrid=True)
    panel_label(ax_loss, "b")

    # Panel c: the profile-to-offset association is evaluated within cells.
    rng = np.random.default_rng(42)
    ns = [7, 10, 15, 20]
    positions = np.arange(len(ns))
    for pos, n_value in zip(positions, ns):
        values = cells.loc[
            cells["n"].astype(int) == n_value,
            "rho_default_gamma_l6_delta",
        ].to_numpy(dtype=float)
        jitter = rng.uniform(-0.17, 0.17, size=len(values))
        ax_rho.scatter(
            pos + jitter, values, s=14, color=COLORS["raw"], alpha=0.65,
            edgecolor="white", linewidth=0.35,
        )
        ax_rho.hlines(np.median(values), pos - 0.24, pos + 0.24,
                      color=COLORS["ink"], lw=1.5)
    primary = summary["primary_result"]
    ax_rho.axhline(0, color=COLORS["muted"], lw=0.7, ls="--")
    ax_rho.set_xticks(positions, [str(value) for value in ns])
    ax_rho.set_xlabel(r"Sample size, $n$")
    ax_rho.set_ylabel(r"Within-cell Spearman $\rho$")
    ax_rho.set_ylim(-0.92, 0.08)
    ax_rho.set_title(r"$\hat{\gamma}_{0.1}/\eta$ versus L6 offset", pad=4)
    ax_rho.text(
        0.04, 0.96,
        f"median = {primary['median_within_cell_spearman_default_gamma_vs_l6_delta']:.3f}\n"
        f"negative in {100*primary['negative_default_gamma_association_cell_fraction']:.0f}% of cells",
        transform=ax_rho.transAxes, ha="left", va="top", fontsize=5.8,
        color=COLORS["muted"],
    )
    style_axis(ax_rho, ygrid=True)
    panel_label(ax_rho, "c")

    export_figure(fig, "fig5_decision_mechanism", MAIN_DIR)


def parameter_landscape_data(paths):
    """Retain the per-cell effect map as a supplementary diagnostic."""
    _, df_full = load_full_scan()
    raw = pd.read_csv(paths["selector_output"] / "raw_specialist_results.csv",
                      low_memory=False)
    combo = ["beta", "gamma_over_eta", "n"]
    raw_primary = raw[raw["seed"] == PRIMARY_SEED]
    raw_combo = raw_primary.groupby(combo, as_index=False)["true_loss"].mean()
    raw_combo["raw_J1"] = np.sqrt(raw_combo["true_loss"])

    default = df_full[np.isclose(df_full["delta"], 0.10)].copy()
    default_combo = default.groupby(combo, as_index=False)["loss"].mean()
    default_combo["default_J1"] = np.sqrt(default_combo["loss"])
    out = raw_combo.merge(default_combo[combo + ["default_J1"]], on=combo,
                          validate="one_to_one")
    out["improvement_pct"] = 100 * (1 - out["raw_J1"] / out["default_J1"])
    save_source(out, "supp_parameter_landscape.csv")
    return out


def supplementary_parameter_landscape(paths):
    data = parameter_landscape_data(paths)
    ns = [7, 10, 15, 20]
    betas = sorted(data["beta"].unique())
    ratios = sorted(data["gamma_over_eta"].unique())
    norm = TwoSlopeNorm(vmin=min(-5.0, float(data["improvement_pct"].min())),
                        vcenter=0.0,
                        vmax=max(25.0, float(data["improvement_pct"].max())))
    fig, axes = plt.subplots(2, 2, figsize=(178 * MM, 104 * MM),
                             sharex=True, sharey=True,
                             gridspec_kw={"hspace": 0.28, "wspace": 0.14})
    image = None
    for label, n, ax in zip("abcd", ns, axes.flat):
        pivot = (data[data["n"] == n]
                 .pivot(index="gamma_over_eta", columns="beta",
                        values="improvement_pct")
                 .reindex(index=ratios, columns=betas))
        image = ax.imshow(pivot.to_numpy(), origin="lower", aspect="auto",
                          cmap="RdBu", norm=norm)
        ax.set_title(rf"$n={n}$", pad=3)
        ax.set_xticks(np.arange(len(betas)), [f"{b:g}" for b in betas])
        ax.set_yticks(np.arange(len(ratios)), [f"{r:g}" for r in ratios])
        ax.tick_params(length=0)
        for row_i, ratio in enumerate(ratios):
            for col_i, beta in enumerate(betas):
                value = float(pivot.loc[ratio, beta])
                if value < 0:
                    ax.add_patch(Rectangle(
                        (col_i - 0.48, row_i - 0.48), 0.96, 0.96,
                        fill=False, edgecolor=COLORS["accent"], linewidth=1.1,
                    ))
                    label_value = f"{value:.2f}" if abs(value) < 0.1 else f"{value:.1f}"
                    ax.text(col_i, row_i, label_value, ha="center", va="center",
                            fontsize=5.3, color=COLORS["accent"], weight="bold")
        panel_label(ax, label)
    for ax in axes[-1, :]:
        ax.set_xlabel(r"Shape parameter, $\beta$")
    for ax in axes[:, 0]:
        ax.set_ylabel(r"Location-to-scale ratio, $\gamma/\eta$")
    cbar = fig.colorbar(image, ax=axes.ravel().tolist(), fraction=0.025, pad=0.025)
    cbar.set_label(r"Reduction in pooled $J_1$ vs default (%)")
    cbar.ax.tick_params(labelsize=6.0)
    n_negative = int((data["improvement_pct"] < 0).sum())
    fig.text(
        0.50, 0.01,
        f"Outlined cells indicate deterioration ({n_negative} of {len(data)} parameter combinations).",
        ha="center", fontsize=6.1, color=COLORS["muted"],
    )
    export_figure(fig, "supp_fig_parameter_landscape", SUPP_DIR)


def supplementary_z_only_learning_curve(paths):
    _, _, _, learning = e10_mechanism_data(paths)
    save_source(learning, "supp_z_only_learning_curve.csv")
    fig, ax = plt.subplots(figsize=(125 * MM, 78 * MM))
    n_colors = {7: "#D88B39", 10: "#6C96B8", 15: "#4A8B76", 20: "#7C6FA5"}
    for n in [7, 10, 15, 20]:
        group = learning[learning["n"] == n].sort_values("training_samples")
        ax.plot(group["training_samples"], group["R_mean_loss"],
                marker="o", ms=3.5, lw=1.25, color=n_colors[n], label=rf"$n={n}$")
    pooled = (learning.groupby("repeats_per_cell", as_index=False)
              .agg(training_samples=("training_samples", "sum"),
                   confirmation_samples=("confirmation_samples", "sum"),
                   R_mean_loss=("R_mean_loss", "mean")))
    ax.set_xlabel("Training samples across four per-n models")
    ax.set_ylabel(r"Confirmation risk, $R=J_1^2$")
    ax.set_title("Data-size diagnostic for the flexible Z-only reference", pad=4)
    ax.legend(ncol=2, loc="center right")
    fig.text(
        0.50, 0.015,
        "Fixed confirmation set; descriptive only and not used for model selection.",
        ha="center", va="bottom", fontsize=5.7, color=COLORS["muted"],
    )
    fig.subplots_adjust(bottom=0.18)
    style_axis(ax, ygrid=True)
    panel_label(ax, "a")
    export_figure(fig, "supp_fig_z_only_learning_curve", SUPP_DIR)


def figure_6_support_validation(paths, summary):
    held = pd.read_csv(paths["unseen_beta"] / "beta_holdout.csv")
    held = held[held["seed"] == PRIMARY_SEED]
    raw_held = held[held["model"] == "Mean-Normalized-MLP"][
        ["held_out_beta", "seed", "J1"]].rename(columns={"J1": "raw_J1"})
    default_held = held[held["model"] == "Default"][
        ["held_out_beta", "seed", "J1"]].rename(columns={"J1": "default_J1"})
    unseen = raw_held.merge(default_held, on=["held_out_beta", "seed"],
                            validate="one_to_one")
    unseen["improvement_pct"] = 100 * (1 - unseen["raw_J1"] / unseen["default_J1"])
    unseen_summary = unseen[["held_out_beta", "improvement_pct"]].copy()
    save_source(unseen_summary, "fig6_unseen_beta_improvement.csv")

    b2 = pd.read_csv(paths["traditional_ref"] / "summary.csv")
    comp = pd.DataFrame(summary["model_comparison"])
    ns = [7, 10, 15, 20]
    traditional_rows = []
    for method, model in (("Mean-normalized", "Mean-Normalized-MLP"),
                          ("Default", "Default")):
        sub = comp[(comp["model"] == model) & (comp["seed"] == PRIMARY_SEED)]
        for n in ns:
            traditional_rows.append({"method": method, "n": n,
                                     "J1": float(sub[f"J1_n{n}"].mean())})
    for method in ("WMLE", "LSE"):
        row = b2[b2["method"] == method].iloc[0]
        for n in ns:
            traditional_rows.append({"method": method, "n": n,
                                     "J1": float(row[f"J1_n{n}"])})
    traditional = pd.DataFrame(traditional_rows)
    save_source(traditional, "fig6_traditional_by_n.csv")

    qraw = pd.read_csv(paths["quantiles"] / "summary.csv")
    qorder = ["Mean-Normalized", "Default", "L6", "WMLE", "LSE"]
    qraw = qraw[(qraw["method"] != "Mean-Normalized") |
                (qraw["seed"] == PRIMARY_SEED)]
    quantile = qraw[["method", "quantile", "rmse"]].copy()
    save_source(quantile, "fig6_quantile_rmse.csv")

    fig, axes = plt.subplots(1, 3, figsize=(183 * MM, 70 * MM),
                             gridspec_kw={"wspace": 0.42})
    ax_a, ax_b, ax_c = axes
    ax_a.plot(unseen_summary["held_out_beta"], unseen_summary["improvement_pct"],
              color=COLORS["raw"], lw=1.5, marker="o", ms=3.5)
    ax_a.axhline(0, color=COLORS["default"], lw=0.8, linestyle="--")
    ax_a.set_xlabel(r"Held-out $\beta$")
    ax_a.set_ylabel(r"Reduction in $J_1$ vs default (%)")
    style_axis(ax_a)
    ax_a.set_title("Unseen parameter levels", pad=4)
    panel_label(ax_a, "a")

    method_style = {
        "Mean-normalized": (COLORS["raw"], "o", 1.7),
        "Default": (COLORS["default"], "s", 1.1),
        "WMLE": (COLORS["wmle"], "D", 1.1),
        "LSE": (COLORS["lse"], "v", 1.1),
    }
    for method, (color, marker, lw) in method_style.items():
        sub = traditional[traditional["method"] == method]
        ax_b.plot(sub["n"], sub["J1"], color=color, marker=marker, ms=3.5,
                  lw=lw, label=method)
    ax_b.set_xlabel(r"Sample size, $n$")
    ax_b.set_ylabel(r"Pooled $J_1$")
    ax_b.set_xticks(ns)
    style_axis(ax_b)
    ax_b.set_title("Traditional estimators", pad=4)
    ax_b.legend(loc="upper right", ncol=2, columnspacing=0.55,
                handletextpad=0.25, handlelength=1.3, fontsize=5.7,
                borderpad=0.2, labelspacing=0.2, frameon=True,
                framealpha=0.94, edgecolor="none")
    panel_label(ax_b, "b")

    qlabels = ["x0.90", "x0.95", "x0.99"]
    x = np.arange(3)
    offsets = dict(zip(qorder, np.linspace(-0.24, 0.24, len(qorder))))
    qcolors = {"Mean-Normalized": COLORS["raw"], "Default": COLORS["default"],
               "L6": COLORS["l6"], "WMLE": COLORS["wmle"], "LSE": COLORS["lse"]}
    markers = {"Mean-Normalized": "o", "Default": "s", "L6": "^",
               "WMLE": "D", "LSE": "v"}
    main_quantile_methods = ["Mean-Normalized", "Default", "WMLE"]
    for method in main_quantile_methods:
        sub = quantile[quantile["method"] == method].set_index("quantile").reindex(qlabels)
        y = sub["rmse"].to_numpy(dtype=float)
        ax_c.errorbar(x + offsets[method], y, yerr=None, fmt=markers[method],
                      ms=3.7, color=qcolors[method], lw=0.8, capsize=1.8,
                      label=method)
    ax_c.set_xticks(x, [r"$x_{0.90}$", r"$x_{0.95}$", r"$x_{0.99}$"])
    ax_c.set_xlabel("Reliability level $R$")
    ax_c.set_ylabel("Relative RMSE")
    style_axis(ax_c)
    ax_c.set_title("Reliability life", pad=4)
    ax_c.legend(loc="upper left", ncol=1, columnspacing=0.7,
                handletextpad=0.35)
    panel_label(ax_c, "c")
    export_figure(fig, "fig6_support_validation", MAIN_DIR)


def supplementary_seed_stability(summary):
    seeds = pd.DataFrame(summary["seed_table"])
    labels = ["Pooled", "n=7", "n=10", "n=15", "n=20"]
    columns = ["pooled_J1", "J1_n7", "J1_n10", "J1_n15", "J1_n20"]
    rows = []
    for label, col in zip(labels, columns):
        for _, row in seeds.iterrows():
            rows.append({"group": label, "seed": int(row["seed"]), "J1": float(row[col])})
    data = pd.DataFrame(rows)
    save_source(data, "supp_seed_stability.csv")

    fig, ax = plt.subplots(figsize=(89 * MM, 67 * MM))
    x = np.arange(len(labels))
    offsets = [-0.08, 0, 0.08]
    for offset, seed in zip(offsets, sorted(data["seed"].unique())):
        vals = [data[(data["group"] == label) & (data["seed"] == seed)]["J1"].iloc[0]
                for label in labels]
        is_primary = seed == PRIMARY_SEED
        ax.scatter(x + offset, vals, s=20 if is_primary else 15,
                   facecolor=COLORS["raw"] if is_primary else "white",
                   edgecolor=COLORS["raw"], lw=0.8,
                   label=f"seed {seed}" + (" (primary)" if is_primary else ""),
                   zorder=4 if is_primary else 3)
    mins = data.groupby("group", sort=False)["J1"].min().reindex(labels)
    maxs = data.groupby("group", sort=False)["J1"].max().reindex(labels)
    primary = (data[data["seed"] == PRIMARY_SEED].set_index("group")["J1"]
               .reindex(labels))
    ax.errorbar(x, primary, yerr=np.vstack([primary - mins, maxs - primary]),
                fmt="none", color=COLORS["raw_light"], capsize=2.5, lw=1.1,
                label="three-seed range")
    ax.set_xticks(x, labels)
    ax.set_ylabel(r"Pooled $J_1$")
    style_axis(ax)
    ax.legend(ncol=2, loc="upper right", columnspacing=0.9, handletextpad=0.4)
    export_figure(fig, "supp_fig_seed_stability", SUPP_DIR)


def supplementary_unseen_beta(paths):
    raw = pd.read_csv(paths["unseen_beta"] / "beta_holdout.csv")
    raw["method"] = raw["model"].replace(
        {"Mean-Normalized-MLP": "Mean-normalized"})
    data = (raw.groupby(["held_out_beta", "method"], as_index=False)
            .agg(seed_min=("J1", "min"), seed_max=("J1", "max"))
            .rename(columns={"held_out_beta": "beta"}))
    primary = (raw[raw["seed"] == PRIMARY_SEED]
               [["held_out_beta", "method", "J1"]]
               .rename(columns={"held_out_beta": "beta", "J1": "primary_J1"}))
    data = data.merge(primary, on=["beta", "method"], validate="one_to_one")
    betas = sorted(data["beta"].astype(float).unique())
    save_source(data, "supp_unseen_beta.csv")

    fig, ax = plt.subplots(figsize=(125 * MM, 72 * MM))
    styles = {
        "Mean-normalized": (COLORS["raw"], "o", "-"),
        "Default": (COLORS["default"], "s", "-"),
        "L6": (COLORS["l6"], "^", "--"),
    }
    for method, (color, marker, ls) in styles.items():
        sub = data[data["method"] == method]
        if method == "Mean-normalized":
            ax.fill_between(sub["beta"], sub["seed_min"], sub["seed_max"],
                            color=COLORS["raw_light"], alpha=0.35, linewidth=0)
        ax.plot(sub["beta"], sub["primary_J1"], color=color, marker=marker, ms=4,
                lw=1.5, linestyle=ls, label=method)
    ax.set_xlabel(r"Held-out shape parameter, $\beta$")
    ax.set_ylabel(r"Pooled $J_1$")
    ax.set_xticks(betas)
    style_axis(ax)
    ax.legend(loc="upper left")
    ax.text(0.98, 0.03, "Line: primary seed 42; shading: three-seed range",
            transform=ax.transAxes, ha="right", fontsize=6.1, color=COLORS["muted"])
    export_figure(fig, "supp_fig_unseen_beta", SUPP_DIR)


def supplementary_traditional(paths, summary):
    b2 = pd.read_csv(paths["traditional_ref"] / "summary.csv")
    comp = pd.DataFrame(summary["model_comparison"])
    ns = [7, 10, 15, 20]
    rows = []
    for method, model in (("Mean-normalized", "Mean-Normalized-MLP"),
                          ("Default", "Default"), ("L6", "L6-hindsight")):
        sub = comp[(comp["model"] == model) & (comp["seed"] == PRIMARY_SEED)]
        for n in ns:
            rows.append({"method": method, "n": n,
                         "J1": float(sub[f"J1_n{n}"].mean())})
    for method in ("WMLE", "LSE"):
        row = b2[b2["method"] == method].iloc[0]
        for n in ns:
            rows.append({"method": method, "n": n, "J1": float(row[f"J1_n{n}"])})
    data = pd.DataFrame(rows)
    save_source(data, "supp_traditional_by_n.csv")

    fig, ax = plt.subplots(figsize=(125 * MM, 76 * MM))
    style = {
        "Mean-normalized": (COLORS["raw"], "o", 1.8),
        "Default": (COLORS["default"], "s", 1.2),
        "L6": (COLORS["l6"], "^", 1.2),
        "WMLE": (COLORS["wmle"], "D", 1.2),
        "LSE": (COLORS["lse"], "v", 1.2),
    }
    for method, (color, marker, lw) in style.items():
        sub = data[data["method"] == method]
        ax.plot(sub["n"], sub["J1"], color=color, marker=marker, ms=3.8,
                lw=lw, label=method)
    ax.set_xlabel(r"Sample size, $n$")
    ax.set_ylabel(r"Pooled $J_1$")
    ax.set_xticks(ns)
    style_axis(ax)
    ax.legend(ncol=3, loc="upper right", columnspacing=1.0, handletextpad=0.45)
    export_figure(fig, "supp_fig_traditional_per_n", SUPP_DIR)


def supplementary_quantiles(paths):
    raw = pd.read_csv(paths["quantiles"] / "summary.csv")
    order = ["Mean-Normalized", "Default", "L6", "WMLE", "LSE"]
    ranges = (raw.groupby(["method", "quantile"], as_index=False)
              .agg(rmse_min=("rmse", "min"), rmse_max=("rmse", "max")))
    primary = raw[(raw["method"] != "Mean-Normalized") |
                  (raw["seed"] == PRIMARY_SEED)][["method", "quantile", "rmse"]]
    agg = primary.merge(ranges, on=["method", "quantile"], validate="one_to_one")
    agg["method"] = pd.Categorical(agg["method"], order, ordered=True)
    agg = agg.sort_values(["method", "quantile"])
    save_source(agg, "supp_quantile_rmse.csv")

    q_order = ["x0.90", "x0.95", "x0.99"]
    x = np.arange(len(q_order))
    offsets = dict(zip(order, np.linspace(-0.24, 0.24, len(order))))
    colors = {"Mean-Normalized": COLORS["raw"], "Default": COLORS["default"],
              "L6": COLORS["l6"], "WMLE": COLORS["wmle"], "LSE": COLORS["lse"]}
    markers = {"Mean-Normalized": "o", "Default": "s", "L6": "^",
               "WMLE": "D", "LSE": "v"}
    fig, ax = plt.subplots(figsize=(125 * MM, 76 * MM))
    for method in order:
        sub = agg[agg["method"] == method].set_index("quantile").reindex(q_order)
        y = sub["rmse"].to_numpy(dtype=float)
        xpos = x + offsets[method]
        yerr = None
        if method == "Mean-Normalized":
            yerr = np.vstack([y - sub["rmse_min"].to_numpy(dtype=float),
                              sub["rmse_max"].to_numpy(dtype=float) - y])
        ax.errorbar(xpos, y, yerr=yerr, fmt=markers[method], ms=4.2,
                    color=colors[method], mfc=colors[method], mec=colors[method],
                    lw=0.9, capsize=2, label=method)
    ax.set_xticks(x, [r"$x_{0.90}$", r"$x_{0.95}$", r"$x_{0.99}$"])
    ax.set_xlabel("Reliability level $R$")
    ax.set_ylabel("Relative RMSE")
    style_axis(ax)
    ax.legend(ncol=3, loc="upper left", columnspacing=1.0, handletextpad=0.4)
    ax.text(0.98, 0.03, "Mean-normalized point: primary seed 42; error bars: three-seed range",
            transform=ax.transAxes, ha="right", fontsize=6.0, color=COLORS["muted"])
    export_figure(fig, "supp_fig_quantile_rmse", SUPP_DIR)


def write_mean_selector_tables(paths, summary):
    """Synchronize compact manuscript tables with the E8 evidence package."""
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    comp = pd.DataFrame(summary["model_comparison"])
    labels = [
        ("Mean-normalized MLP", "Mean-Normalized-MLP"),
        (r"Default ($\delta=0.1$)", "Default"),
        ("L6 (hindsight)", "L6-hindsight"),
    ]
    main_rows = []
    for label, model in labels:
        sub = comp[(comp["model"] == model) & (comp["seed"] == PRIMARY_SEED)]
        main_rows.append({
            "方法": label,
            "$J_1$ pooled": float(sub["J1"].mean()),
            **{f"$n={n}$": float(sub[f"J1_n{n}"].mean()) for n in (7, 10, 15, 20)},
            "失败率": float(sub["failure_rate"].mean()),
        })
    main = pd.DataFrame(main_rows)
    main.to_csv(TABLES_DIR / "table2_main_results.csv", index=False,
                encoding="utf-8")
    lines = [
        "**表 3：主方法比较（同一留出协议、同一测试样本）**", "",
        "| 方法 | $J_1$ pooled | $n=7$ | $n=10$ | $n=15$ | $n=20$ | 失败率 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in main.itertuples(index=False):
        lines.append(f"| {row[0]} | {row[1]:.4f} | {row[2]:.4f} | "
                     f"{row[3]:.4f} | {row[4]:.4f} | {row[5]:.4f} | "
                     f"{100*row[6]:.2f}% |")
    (TABLES_DIR / "table2_main_results.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")

    held = pd.read_csv(paths["unseen_beta"] / "beta_holdout.csv")
    held_table = (held[held["seed"] == PRIMARY_SEED]
                  .pivot(index="held_out_beta", columns="model", values="J1")
                  .reset_index())
    held_table = held_table[["held_out_beta", "Mean-Normalized-MLP", "Default", "L6"]]
    held_table.columns = ["留出 $\\beta$", "Mean-normalized $J_1$",
                          "Default $J_1$", "L6 $J_1$"]
    held_table.to_csv(TABLES_DIR / "supp_table_unseen_beta.csv", index=False,
                      encoding="utf-8")
    held_lines = [
        "**补充表：未见 $\\beta$ 留出验证——每个留出 $\\beta$ 的 pooled $J_1$**",
        "", "| 留出 $\\beta$ | Mean-normalized $J_1$ | Default $J_1$ | L6 $J_1$ |",
        "|---:|---:|---:|---:|",
    ]
    for row in held_table.itertuples(index=False):
        held_lines.append(f"| {row[0]:g} | {row[1]:.4f} | {row[2]:.4f} | {row[3]:.4f} |")
    (TABLES_DIR / "supp_table_unseen_beta.md").write_text(
        "\n".join(held_lines) + "\n", encoding="utf-8")

    qraw = pd.read_csv(paths["quantiles"] / "summary.csv")
    qtable = qraw[(qraw["method"] != "Mean-Normalized") |
                  (qraw["seed"] == PRIMARY_SEED)].copy()
    qtable = qtable.rename(columns={"bias": "相对 Bias", "rmse": "相对 RMSE",
                                    "mae": "相对 MAE",
                                    "p95_abs_rel": "P95(|相对误差|)",
                                    "failure_rate": "失败率"})
    qtable = qtable[["method", "quantile", "相对 Bias", "相对 RMSE",
                     "相对 MAE", "P95(|相对误差|)", "失败率"]]
    qtable = qtable.rename(columns={"method": "方法", "quantile": "分位点"})
    order = ["Mean-Normalized", "Default", "L6", "WMLE", "LSE"]
    qtable["方法"] = pd.Categorical(qtable["方法"], order, ordered=True)
    qtable = qtable.sort_values(["方法", "分位点"]).reset_index(drop=True)
    qtable["方法"] = qtable["方法"].astype(str).replace(
        {"Mean-Normalized": "Mean-normalized"})
    qtable.to_csv(TABLES_DIR / "supp_table_quantiles.csv", index=False,
                  encoding="utf-8")
    qlines = [
        "**补充表：工程寿命分位点 $x_{0.90}/x_{0.95}/x_{0.99}$ 相对误差指标**",
        "", "| 方法 | 分位点 | 相对 Bias | 相对 RMSE | 相对 MAE | P95(|相对误差|) | 失败率 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in qtable.itertuples(index=False):
        qlines.append(f"| {row[0]} | {row[1]} | {row[2]:.4f} | {row[3]:.4f} | "
                      f"{row[4]:.4f} | {row[5]:.4f} | {100*row[6]:.3f}% |")
    (TABLES_DIR / "supp_table_quantiles.md").write_text(
        "\n".join(qlines) + "\n", encoding="utf-8")

    primary_main = comp[(comp["model"] == "Mean-Normalized-MLP") &
                        (comp["seed"] == PRIMARY_SEED)].iloc[0]
    stability = pd.DataFrame(summary["seed_table"])["pooled_J1"]
    primary_unseen = held[held["seed"] == PRIMARY_SEED]
    unseen_model = primary_unseen[primary_unseen["model"] == "Mean-Normalized-MLP"]
    unseen_default = primary_unseen[primary_unseen["model"] == "Default"]
    unseen_j1 = float(np.sqrt(np.mean(unseen_model["J1"].to_numpy(dtype=float) ** 2)))
    unseen_default_j1 = float(np.sqrt(np.mean(unseen_default["J1"].to_numpy(dtype=float) ** 2)))
    unseen_improvement = 100 * (1 - unseen_j1 / unseen_default_j1)
    primary_quantile = qtable[qtable["方法"] == "Mean-normalized"]
    support_rows = [
        {
            "问题": "是否依赖一次随机初始化",
            "证据": "固定 seed 42 为主结果；2026/3407 作初始化敏感性核查",
            "结论": (f"主结果 pooled $J_1$ = {primary_main['J1']:.4f}; "
                    f"三 seed 范围 {stability.min():.4f}–{stability.max():.4f}"),
        },
        {
            "问题": "未见参数值能否保持收益",
            "证据": "按 $\\beta$ 水平逐一留出（8 折）",
            "结论": (f"seed 42 pooled $J_1$ = {unseen_j1:.4f}; "
                    f"相对 Default 降低 {unseen_improvement:.1f}%"),
        },
        {
            "问题": "与传统方法相比位于什么水平",
            "证据": "WMLE/LSE 同一 48,000 样本外部参照",
            "结论": "Mean-normalized (seed 42) 0.5846；WMLE 0.7288；LSE 0.8725",
        },
        {
            "问题": "参数收益能否传递到工程寿命",
            "证据": "$x_{0.90},x_{0.95},x_{0.99}$ 重派生",
            "结论": ("传递有限：seed 42 相对 RMSE 为 0.1608、0.2136、0.3753；"
                    "对应 Default 为 0.1607、0.2142、0.3777"),
        },
    ]
    support = pd.DataFrame(support_rows)
    support.to_csv(TABLES_DIR / "table3_support_verification.csv", index=False,
                   encoding="utf-8")
    slines = ["**表 4：支撑验证摘要（细节见补充材料）**", "",
              "| 问题 | 证据 | 结论 |", "|---|---|---|"]
    slines.extend(f"| {r['问题']} | {r['证据']} | {r['结论']} |"
                  for r in support_rows)
    (TABLES_DIR / "table3_support_verification.md").write_text(
        "\n".join(slines) + "\n", encoding="utf-8")


_PG_FAMILY_LABEL = {"PG-beta": r"$\beta$", "PG-beta-n": r"$\beta,\,n$",
                    "PG-full": r"$\beta,\gamma/\eta,\,n$"}
_PG_MAPPING_LABEL = {"nearest_grid": "grid", "interpolated": "interp"}


def _pg_variant_label(family, mapping):
    """Short but figure/caption-decodable rule label (estimator is the group)."""
    return f"{_PG_FAMILY_LABEL[family]} · {_PG_MAPPING_LABEL[mapping]}"


def supplementary_parameter_guided(paths):
    """Negative supporting experiment: plug-in parameter guidance fails overall.

    Panel a: horizontal forest plot of the 12 one-step PG-minus-Default J1
    differences with paired 95% CIs, grouped by initial estimator; zero line
    with right = worse.
    Panel b: best one-step rule's (WMLE / beta / interp) J1 difference by true
    beta, showing the beta=1.5 exception.
    Panel c: nearest-beta-cell correctness (%) by true beta for MDM-0.1 and
    WMLE, labeled as a diagnostic, not causal proof.
    """
    boot = pd.read_csv(paths["pg_selector"] / "paired_bootstrap.csv")
    by_beta = pd.read_csv(paths["pg_selector"] / "summary_by_beta.csv")
    cell = pd.read_csv(paths["pg_selector"] / "beta_cell_correctness.csv")

    one_step = boot[boot["variant"] == "one_step"].copy().sort_values(
        ["estimator", "family", "mapping"]).reset_index(drop=True)
    one_step["label"] = [_pg_variant_label(r.family, r.mapping)
                         for r in one_step.itertuples()]
    save_source(one_step[["label", "estimator", "family", "mapping", "variant",
                          "observed_j1_diff", "ci_low", "ci_high"]],
                "supp_pg_bootstrap.csv")

    best = by_beta[(by_beta["estimator"] == "WMLE")
                   & (by_beta["family"] == "PG-beta")
                   & (by_beta["mapping"] == "interpolated")
                   & (by_beta["variant"] == "one_step")].copy()
    best["true_beta"] = best["true_beta"].astype(float)
    best = best.sort_values("true_beta").reset_index(drop=True)
    save_source(best[["true_beta", "PG_J1", "Default_J1", "J1_diff"]],
                "supp_pg_by_beta.csv")

    # true_beta mixes 'ALL' (str) with numeric levels, so pandas infers object
    # dtype; convert to float AFTER dropping the ALL row so the x-axis is a
    # continuous numeric coordinate (never a categorical string axis).
    cell_by = cell[cell["true_beta"] != "ALL"].copy()
    cell_by["true_beta"] = cell_by["true_beta"].astype(float)
    cell_by = cell_by.sort_values(["estimator", "true_beta"]).reset_index(drop=True)
    save_source(cell_by[["estimator", "true_beta", "n", "n_correct",
                         "correct_rate"]], "supp_pg_cell_correctness.csv")

    fig = plt.figure(figsize=(183 * MM, 82 * MM))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.12, 0.72, 0.98], wspace=0.42)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[0, 2])

    # ---- Panel a: horizontal forest plot grouped by estimator ----
    est_order = ["MDM-0.1", "WMLE"]
    y = np.arange(12)
    colors_a = np.where(one_step["estimator"] == "MDM-0.1",
                        COLORS["raw"], COLORS["wmle"])
    ax_a.errorbar(one_step["observed_j1_diff"], y, xerr=np.vstack(
        [one_step["observed_j1_diff"] - one_step["ci_low"],
         one_step["ci_high"] - one_step["observed_j1_diff"]]),
        fmt="none", ecolor=COLORS["ink"], elinewidth=0.8, capsize=2.2, zorder=3)
    ax_a.scatter(one_step["observed_j1_diff"], y, s=22, facecolor="white",
                 edgecolor=colors_a, linewidth=1.3, zorder=4)
    ax_a.axvline(0, color=COLORS["default"], lw=0.9, linestyle="--")
    ax_a.set_yticks(y, one_step["label"], fontsize=6.4)
    ax_a.tick_params(axis="y", length=0)
    # estimator group separators and labels on the right side
    for cutoff, est in ((5.5, "MDM-0.1"), (11.5, "WMLE")):
        ax_a.axhline(cutoff, color=COLORS["light"], lw=0.8)
        ax_a.text(1.02, cutoff - 2.5, est, transform=ax_a.get_yaxis_transform(),
                  ha="left", va="center", fontsize=6.6, weight="bold",
                  color=COLORS["ink"])
    ax_a.set_xlabel(r"PG $J_1$ minus Default $J_1$ (positive = worse)")
    ax_a.set_xlim(-0.03, 0.088)
    # leave headroom above the top row (y=11) so the note never covers a point/CI
    ax_a.set_ylim(-1.2, 13.2)
    style_axis(ax_a, xgrid=True)
    ax_a.text(0.02, 0.975, "All 12 one-step rules worse than Default",
              transform=ax_a.transAxes, va="top", fontsize=6.0,
              color=COLORS["muted"])
    panel_label(ax_a, "a")

    # ---- Panel b: best rule by true beta (beta=1.5 exception) ----
    ax_b.plot(best["true_beta"], best["J1_diff"], color=COLORS["raw"], lw=1.5,
              marker="o", ms=4)
    ax_b.axhline(0, color=COLORS["default"], lw=0.9, linestyle="--")
    ax_b.scatter([1.5],
                 [float(best.loc[best["true_beta"] == 1.5, "J1_diff"].iloc[0])],
                 s=30, facecolor=COLORS["accent"], edgecolor="white", lw=0.7,
                 zorder=5)
    ax_b.annotate("only improvement\nat $\\beta=1.5$",
                  xy=(1.5, -0.0104), xytext=(2.15, 0.030),
                  fontsize=5.8, color=COLORS["accent"], ha="left", va="bottom",
                  arrowprops={"arrowstyle": "-", "lw": 0.7,
                              "color": COLORS["accent"]})
    ax_b.set_xlabel(r"True shape parameter, $\beta$")
    ax_b.set_ylabel(r"$J_1$ difference")
    ax_b.set_xticks([float(v) for v in best["true_beta"]])
    ax_b.tick_params(axis="x", labelsize=5.8)
    ax_b.set_ylim(-0.042, 0.048)
    style_axis(ax_b, ygrid=True)
    panel_label(ax_b, "b")

    # ---- Panel c: nearest-beta-cell correctness (%) ----
    for est, color, marker in (("MDM-0.1", COLORS["raw"], "o"),
                               ("WMLE", COLORS["wmle"], "s")):
        sub = cell_by[cell_by["estimator"] == est].sort_values("true_beta")
        ax_c.plot(sub["true_beta"], sub["correct_rate"] * 100.0,
                  color=color, marker=marker, ms=3.8, lw=1.4, label=est)
    ax_c.set_xlabel(r"True shape parameter, $\beta$")
    ax_c.set_ylabel("Nearest-cell correctness (%)")
    ax_c.set_xticks([1.5, 2.5, 3.5, 4.5])   # every other tick avoids crowding
    ax_c.tick_params(axis="x", labelsize=5.8)
    ax_c.set_ylim(0, 72)
    style_axis(ax_c, ygrid=True)
    ax_c.legend(loc="upper right", handletextpad=0.3, borderpad=0.3,
                labelspacing=0.25)
    ax_c.text(0.02, 0.03, "diagnostic, not causal proof",
              transform=ax_c.transAxes, fontsize=5.7, color=COLORS["muted"])
    panel_label(ax_c, "c")

    export_figure(fig, "supp_fig_parameter_guided", SUPP_DIR)


def write_parameter_guided_tables(paths):
    """Supplementary tables for the PG negative supporting experiment."""
    boot = pd.read_csv(paths["pg_selector"] / "paired_bootstrap.csv")
    variant = pd.read_csv(paths["pg_selector"] / "variant_summary.csv")
    by_beta = pd.read_csv(paths["pg_selector"] / "summary_by_beta.csv")

    rows = []
    for _, r in boot.sort_values(["estimator", "family", "mapping",
                                  "variant"]).iterrows():
        j1 = float(variant[(variant["estimator"] == r["estimator"])
                           & (variant["family"] == r["family"])
                           & (variant["mapping"] == r["mapping"])
                           & (variant["variant"] == r["variant"])]["J1"].iloc[0])
        rows.append({
            "估计量": r["estimator"], "选择族": r["family"],
            "映射": r["mapping"], "阶段": r["variant"],
            "PG J1": j1,
            "PG-Default J1 差": float(r["observed_j1_diff"]),
            "95% CI 下限": float(r["ci_low"]),
            "95% CI 上限": float(r["ci_high"]),
            "更差 repeat 块比例": float(r["frac_blocks_pg_worse"]),
        })
    detail = pd.DataFrame(rows)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    detail.to_csv(TABLES_DIR / "supp_table_parameter_guided.csv", index=False,
                  encoding="utf-8")

    best = by_beta[(by_beta["estimator"] == "WMLE")
                   & (by_beta["family"] == "PG-beta")
                   & (by_beta["mapping"] == "interpolated")
                   & (by_beta["variant"] == "one_step")].sort_values("true_beta")
    best_rows = [{
        "真 beta": float(r.true_beta), "n": int(r.n),
        "PG J1": float(r.PG_J1), "Default J1": float(r.Default_J1),
        "J1 差": float(r.J1_diff),
    } for r in best.itertuples()]

    lines = [
        "**补充表：参数引导（plug-in）偏移量选择——12 个单步变体与迭代诊断**",
        "",
        "参数引导选择先用 MDM-0.1 或 WMLE 得到初步参数估计，再把估计当作真参数去查询 L3–L5 对应的条件均值损失曲线并选择偏移量。48,000 样本、repeat-id 五折 cross-fit；$J_1=\sqrt{\mathrm{mean}\,\ell_i}$（三参数损失）。J1 差与 95% 区间来自固定种子（2026）配对 repeat-block bootstrap；差值为正表示 PG 比 Default（$J_1=0.6304$）更差。",
        "",
        "| 初始估计量 | 选择族 | 映射 | 阶段 | PG J1 | PG−Default J1 差 | 95% CI 下限 | 95% CI 上限 | 更差 repeat 块比例 |",
        "|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for _, r in detail.iterrows():
        lines.append(
            f"| {r['估计量']} | {r['选择族']} | {r['映射']} | {r['阶段']} "
            f"| {r['PG J1']:.4f} | {r['PG-Default J1 差']:+.4f} "
            f"| {r['95% CI 下限']:.4f} | {r['95% CI 上限']:.4f} "
            f"| {r['更差 repeat 块比例']*100:.1f}% |")
    lines.append("")
    lines.append("**补充表（续）：最佳单步规则（WMLE / PG-beta / interpolated）按真 $\\beta$ 分层。** 仅在 $\\beta=1.5$ 优于 Default；$\\beta=2.0$–5.0 均更差。")
    lines.append("")
    lines.append("| 真 $\\beta$ | $n$ | PG J1 | Default J1 | J1 差 |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in best_rows:
        lines.append(f"| {r['真 beta']:g} | {r['n']} | {r['PG J1']:.4f} "
                     f"| {r['Default J1']:.4f} | {r['J1 差']:+.4f} |")
    lines.append("")
    lines.append("注：邻近 $\\beta$ 网格单元正确率与初估误差—损失关系只与该机制解释一致，不作为唯一因果机制的证明；连续插值同样失败，误差分层可能与真 $\\beta$ 混杂。")
    (TABLES_DIR / "supp_table_parameter_guided.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


def main():
    paths = source_paths()
    summary = load_summary(paths)
    MAIN_DIR.mkdir(parents=True, exist_ok=True)
    SUPP_DIR.mkdir(parents=True, exist_ok=True)
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)

    figure_1_method_structure()
    figure_2_delta_risk(paths)
    figure_3_main_results(paths, summary)
    figure_4_selector_mechanism(paths)
    figure_5_decision_mechanism(paths)
    figure_6_support_validation(paths, summary)
    supplementary_seed_stability(summary)
    supplementary_unseen_beta(paths)
    supplementary_traditional(paths, summary)
    supplementary_quantiles(paths)
    supplementary_parameter_landscape(paths)
    supplementary_z_only_learning_curve(paths)
    supplementary_decision_conditions(paths)
    write_mean_selector_tables(paths, summary)
    supplementary_parameter_guided(paths)
    write_parameter_guided_tables(paths)
    write_submission_provenance(paths)
    print("Generated 14 submission figures and supplementary tables "
          "in PNG/SVG/PDF/TIFF formats.")


if __name__ == "__main__":
    main()
