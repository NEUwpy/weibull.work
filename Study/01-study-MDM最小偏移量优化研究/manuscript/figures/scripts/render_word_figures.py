"""Redraw Study01 manuscript figures for a 17.49 cm Word text width.

This Word figure generator imports the sealed-data plotting functions without
changing their data, then replaces only the export contract and typography.
"""

from __future__ import annotations

import importlib.util
import hashlib
import json
import re
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.text import Text
from PIL import Image


ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'scripts/documents'))
from panel_labels import normalize_panel_labels
SOURCE_SCRIPTS = ROOT / "Study/01-study-MDM最小偏移量优化研究/manuscript/figures/scripts"
OUT = SOURCE_SCRIPTS.parent / "word"
MAIN = OUT / "main"
SUPP = OUT / "supplementary"
DERIVED = OUT / "derived"
REPORT = OUT / "figure-report.json"
ASSEMBLY_MANIFEST = OUT / "assembly-manifest.json"
TARGET_WIDTH_MM = 174.9
TARGET_FONT_PT = 10.5
MAX_HEIGHT_MM = 190.0
REPORT_ROWS: list[dict] = []
LOCALIZE = None
V111_NOTES = {
    "supp_fig_unseen_beta": "Line: primary seed 42; shading: three-seed range",
    "supp_fig_quantile_rmse": "Mean-normalized point: primary seed 42; error bars: three-seed range",
    "supp_fig_parameter_landscape": "Outlined cells indicate deterioration (35 of 160 parameter combinations).",
    "supp_fig_z_only_learning_curve": "Fixed confirmation set; descriptive only and not used for model selection.",
}

# Stable Word-image identities.  The document slot is the assembly key; the
# source SVG and generator retain the scientific provenance of each redraw.
SOURCE_IDENTITY = {
    "fig1_adaptive_selection_drawio_v111": ("Study01论文正文.docx", 1, "main/fig1_adaptive_selection_drawio_v111.svg", "preserve_framework"),
    "fig2_offset_risk_decomposition_v112": ("Study01论文正文.docx", 2, "main/fig2_offset_risk_decomposition_v112.svg", "plot_offset_revision_v112.fig2"),
    "fig3_beta_domain_restored_3d": ("Study01论文正文.docx", 3, "main/fig3_beta_domain_restored_3d.svg", "draw_beta_domain_3d"),
    "fig4_information_spaces_restored_3d": ("Study01论文正文.docx", 4, "main/fig4_information_spaces_restored_3d.svg", "draw_information_spaces"),
    "fig5_information_level_results": ("Study01论文正文.docx", 5, "main/fig5_information_level_results.svg", "plot_fig5_information_level_results.draw_figure"),
    "fig6_per_n_J1": ("Study01论文正文.docx", 6, "main/fig6_per_n_J1.svg", "make_submission_figures.figure_6_main_results"),
    "fig7_sample_columns_v112": ("Study01论文正文.docx", 7, "main/fig7_sample_columns_v112.svg", "plot_fig7_sample_columns.main"),
    "supp_fig_offset_sd_v110": ("Study01论文附录.docx", 1, "supplementary/supp_fig_offset_sd_v110.svg", "plot_offset_revision_v112.supp"),
    "fig7_selector_mechanism": ("Study01论文附录.docx", 2, "main/fig7_selector_mechanism.svg", "make_submission_figures.figure_7_selector_mechanism"),
    "supp_fig_parameter_guided": ("Study01论文附录.docx", 3, "supplementary/supp_fig_parameter_guided.svg", "make_submission_figures.supplementary_parameter_guided"),
    "supp_fig_unseen_beta_v111": ("Study01论文附录.docx", 4, "supplementary/supp_fig_unseen_beta_v111.svg", "make_submission_figures.supplementary_unseen_beta"),
    "supp_fig_traditional_per_n": ("Study01论文附录.docx", 5, "supplementary/supp_fig_traditional_per_n.svg", "make_submission_figures.supplementary_traditional"),
    "supp_fig_quantile_rmse_v111": ("Study01论文附录.docx", 6, "supplementary/supp_fig_quantile_rmse_v111.svg", "make_submission_figures.supplementary_quantiles"),
    "supp_fig_decision_conditions": ("Study01论文附录.docx", 7, "supplementary/supp_fig_decision_conditions.svg", "make_submission_figures.supplementary_decision_conditions"),
    "supp_fig_parameter_landscape_v111": ("Study01论文附录.docx", 8, "supplementary/supp_fig_parameter_landscape_v111.svg", "make_submission_figures.supplementary_parameter_landscape"),
    "supp_fig_z_only_learning_curve_v111": ("Study01论文附录.docx", 9, "supplementary/supp_fig_z_only_learning_curve_v111.svg", "make_submission_figures.supplementary_z_only_learning_curve"),
    "supp_fig_sample_groups_v110": ("Study01论文附录.docx", 10, "supplementary/supp_fig_sample_groups_v110.svg", "plot_fig7_sample_columns.supplementary"),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_plot_module():
    path = SOURCE_SCRIPTS / "make_submission_figures.py"
    spec = importlib.util.spec_from_file_location("study01_source_plots", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def configure_fonts() -> None:
    mpl.rcParams.update({
        "font.family": ["Times New Roman", "SimSun"],
        "font.serif": ["Times New Roman", "SimSun"],
        "font.sans-serif": ["Times New Roman", "SimSun"],
        "font.size": TARGET_FONT_PT,
        "axes.labelsize": TARGET_FONT_PT,
        "axes.titlesize": TARGET_FONT_PT,
        "xtick.labelsize": TARGET_FONT_PT,
        "ytick.labelsize": TARGET_FONT_PT,
        "legend.fontsize": TARGET_FONT_PT,
        "font.weight": "normal",
        "font.style": "normal",
        "mathtext.fontset": "custom",
        "mathtext.default": "regular",
        "mathtext.rm": "Times New Roman",
        "mathtext.it": "Times New Roman",
        "mathtext.bf": "Times New Roman",
        "mathtext.sf": "Times New Roman",
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "axes.unicode_minus": False,
    })


def word_export(fig, stem: str, folder: Path, *, tiff=True):
    """Export at an exact physical canvas size; never use tight cropping."""
    if stem in V111_NOTES:
        matches = [t for t in fig.findobj(match=Text)
                   if t.get_text() == V111_NOTES[stem]]
        if len(matches) == 1:
            matches[0].remove()
        if stem == "supp_fig_z_only_learning_curve":
            fig.axes[0].set_xlabel("每个样本量模型的训练样本数")
        stem += "_v111"
    if LOCALIZE is not None:
        LOCALIZE(fig)
    # Source functions set their own rcParams and many tick labels are created
    # lazily.  Re-apply the final contract here, then materialize every tick.
    configure_fonts()
    source_width = fig.get_figwidth()
    source_height = fig.get_figheight()
    target_width_in = TARGET_WIDTH_MM / 25.4
    target_height_in = source_height * target_width_in / source_width
    height_overrides_mm = {
        "supp_fig_parameter_guided": 185.0,
        "supp_fig_parameter_landscape_v111": 188.0,
    }
    if stem in height_overrides_mm:
        target_height_in = height_overrides_mm[stem] / 25.4
    if target_height_in * 25.4 > MAX_HEIGHT_MM:
        target_height_in = MAX_HEIGHT_MM / 25.4
    fig.set_size_inches(target_width_in, target_height_in, forward=True)

    # Force lazy tick-label Text objects into existence without rendering them
    # under the source script's font settings.
    for axis in fig.axes:
        axis.get_xticklabels(which="both")
        axis.get_yticklabels(which="both")
    if stem == "supp_fig_parameter_guided" and len(fig.axes) >= 3:
        fig.axes[0].set_position([.22, .56, .72, .38])
        fig.axes[1].set_position([.12, .10, .34, .32])
        fig.axes[2].set_position([.60, .10, .34, .32])
    if stem == "supp_fig_parameter_landscape_v111" and len(fig.axes) >= 5:
        for axis, y in zip(fig.axes[:4], [.80, .59, .38, .12]):
            axis.set_position([.13, y, .72, .15])
        # The source used a shared-y 2x2 layout and suppressed the right-column
        # tick labels.  In the Word-scale four-row layout every row must carry
        # the same five position-ratio ticks.
        y_ticks = fig.axes[0].get_yticks()
        y_labels = [t.get_text() for t in fig.axes[0].get_yticklabels()]
        for axis in fig.axes[:4]:
            axis.set_yticks(y_ticks, y_labels)
            axis.tick_params(axis="y", which="both", labelleft=True)
            for tick in axis.yaxis.get_major_ticks():
                tick.label1.set_visible(True)
        fig.axes[4].set_position([.88, .15, .025, .72])
    if stem == "supp_fig_decision_conditions" and len(fig.axes) >= 2:
        labels = [t.get_text() for t in fig.axes[1].get_xticklabels()]
        if labels:
            labels[0] = "固定\n规则"
            fig.axes[1].set_xticks(fig.axes[1].get_xticks(), labels)
    latin_regular = FontProperties(family="Times New Roman",
                                   style="normal", weight="normal",
                                   size=TARGET_FONT_PT)
    chinese_regular = FontProperties(family="SimSun",
                                     style="normal", weight="normal",
                                     size=TARGET_FONT_PT)
    for artist in fig.findobj(match=Text):
        if not artist.get_text().strip():
            continue
        # Keep panel letters slightly larger; all scientific and explanatory
        # text uses the requested five-size body text at final insertion width.
        # Matplotlib's raster mathtext parser cannot reliably select a CJK
        # fallback from a family list.  A CJK-containing text object therefore
        # uses SimSun as its base face; any $...$ segment is still rendered by
        # the custom Times New Roman mathtext configuration above.
        artist.set_fontproperties(
            chinese_regular if re.search(r"[\u3400-\u9fff]", artist.get_text())
            else latin_regular
        )
        artist.set_fontsize(TARGET_FONT_PT)
        if stem == "supp_fig_decision_conditions" and artist.get_text() == "固定规则":
            artist.set_text("固定\n规则")

    if stem == "fig6_per_n_J1":
        ax_left, ax_right = fig.axes[:2]
        for artist in fig.findobj(match=Text):
            if artist.get_text() == "相对固定规则的降幅":
                x, _ = artist.get_position()
                artist.set_position((x, 0.995))
            elif artist.get_text() in {"固定规则", "自适应选择", "L6 事后参照"}:
                artist.set_visible(False)
            elif artist.axes is ax_right and artist.get_position()[0] >= 19.9:
                # Keep the n=20 percentage and top annotation inside the axes.
                artist.set_ha("right")
                x, y = artist.get_position()
                artist.set_position((19.85, y))
        # Source order is Adaptive, Default, L6; present the semantic order
        # used by the manuscript without relabeling the wrong line style.
        handles = [ax_left.lines[1], ax_left.lines[0], ax_left.lines[2]]
        ax_left.legend(handles, ["固定规则", "自适应选择", "L6 事后参照"],
                       loc="upper right", bbox_to_anchor=(.98,.92), frameon=False, handlelength=1.6,
                       borderaxespad=.25, labelspacing=.35)
        for artist in ax_right.texts:
            if artist.get_text() == "正值：自适应误差较低":
                artist.set_text("正值：自适应\n误差较低")
                artist.set_transform(ax_right.transAxes)
                artist.set_position((.72, .18))
                artist.set_ha("center")

    fig.canvas.draw()
    # 3D axes may create a second set of projected tick Text objects during
    # their first draw. Apply the exact same contract once more afterward.
    for artist in fig.findobj(match=Text):
        if artist.get_text().strip():
            artist.set_fontproperties(
                chinese_regular if re.search(r"[\u3400-\u9fff]", artist.get_text())
                else latin_regular
            )
            artist.set_fontsize(TARGET_FONT_PT)
    fig.canvas.draw()
    out_folder = SUPP if stem == "fig7_selector_mechanism" else (
        MAIN if folder.name == "main" else SUPP
    )
    out_folder.mkdir(parents=True, exist_ok=True)
    svg = out_folder / f"{stem}.svg"
    png = out_folder / f"{stem}.png"
    normalize_panel_labels(fig)
    fig.savefig(svg, facecolor="white")
    fig.savefig(png, dpi=600, facecolor="white")
    # SVG uses browser-style glyph fallback.  Declare both requested faces on
    # every span while retaining per-artist raster selection above.
    svg_text = svg.read_text(encoding="utf-8")
    svg_text = re.sub(
        r"font-family: (?:'[^']+'(?:, )?)+(?:, sans-serif)?",
        "font-family: 'Times New Roman', 'SimSun'",
        svg_text,
    )
    svg.write_text(svg_text, encoding="utf-8", newline="\n")
    with Image.open(png) as image:
        pixel_size = list(image.size)
    REPORT_ROWS.append({
        "stem": stem,
        "width_mm": round(fig.get_figwidth() * 25.4, 3),
        "height_mm": round(fig.get_figheight() * 25.4, 3),
        "font_pt": TARGET_FONT_PT,
        "math_script_pt": round(TARGET_FONT_PT * 0.7, 2),
        "png_dpi": 600,
        "png_pixels": pixel_size,
        "svg": str(svg),
        "png": str(png),
        "output_svg_sha256": sha256_file(svg),
        "output_png_sha256": sha256_file(png),
    })
    plt.close(fig)


def save_report() -> None:
    ordered_rows = sorted(
        REPORT_ROWS,
        key=lambda row: SOURCE_IDENTITY[row["stem"]][:2],
    )
    for row in ordered_rows:
        document, image_index, source_rel, generator = SOURCE_IDENTITY[row["stem"]]
        source_svg = ROOT / "Study/01-study-MDM最小偏移量优化研究/manuscript/figures" / source_rel
        row["source_identity"] = {
            "document": document,
            "image_index": image_index,
            "source_svg": str(source_svg),
            "source_svg_sha256": sha256_file(source_svg),
            "generator": generator,
        }
    payload = {
        "target_width_mm": TARGET_WIDTH_MM,
        "font_contract": {
            "normal_text_pt": TARGET_FONT_PT,
            "Chinese": "SimSun",
            "Latin_and_digits": "Times New Roman",
            "weight": "normal",
            "style": "normal",
            "mathtext": "Times New Roman custom; native script scaling retained",
        },
        "figures": ordered_rows,
    }
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ASSEMBLY_MANIFEST.write_text(json.dumps({
        "schema": "study01-word-figure-assembly-v1",
        "count": len(ordered_rows),
        "assembly_key": ["source_identity.document", "source_identity.image_index"],
        "target_width_cm": TARGET_WIDTH_MM / 10,
        "font_contract": payload["font_contract"],
        "figures": ordered_rows,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def preserve_framework() -> None:
    """Keep the author-approved original Fig. 1, including its original Word size."""
    import zipfile
    import shutil
    stem = "fig1_adaptive_selection_drawio_v111"
    manuscript = SOURCE_SCRIPTS.parent.parent
    with zipfile.ZipFile(manuscript / "backup/20260906-143123/Study01论文正文.docx") as z:
        (MAIN / (stem + ".png")).write_bytes(z.read("word/media/image1.png"))
    shutil.copy2(SOURCE_SCRIPTS.parent / "main" / (stem + ".svg"), MAIN / (stem + ".svg"))
    # Change only the two section labels; all original boxes and arrows stay intact.
    from lxml import etree as ET
    from matplotlib.patches import Rectangle
    raster = plt.imread(MAIN / (stem + '.png'))
    fig = plt.figure(figsize=(6, 6 * 757 / 1267))
    ax = fig.add_axes([0, 0, 1, 1]); ax.imshow(raster, extent=(0,1267,757,0)); ax.axis('off')
    headings = [('a', 20, '离线训练：学习候选偏移量的损失'),
                ('b', 460, '实际估计：按当前样本选择偏移量')]
    svgpath = MAIN / (stem + '.svg'); tree = ET.parse(str(svgpath))
    for letter, y, title in headings:
        ax.add_patch(Rectangle((0,y-4),1267,56,color='white',zorder=5))
        ax.text(633.5,y+24,f'({letter})  {title}',ha='center',va='center',
                fontfamily=['Times New Roman','SimSun'],fontsize=10.5,zorder=6)
        group = tree.xpath(f'//*[@data-cell-id="panel_{letter}"]')[0]
        for child in list(group): group.remove(child)
        node=ET.SubElement(group,'{http://www.w3.org/2000/svg}text',
            x='633.5',y=str(y+24),attrib={'text-anchor':'middle','dominant-baseline':'central',
            'font-family':'Times New Roman, SimSun','font-size':str(10.5*1267/432),'fill':'#26343C'})
        node.text=f'({letter})  {title}'
    fig.savefig(MAIN / (stem+'.png'),dpi=600); plt.close(fig)
    tree.write(str(svgpath),encoding='utf-8',xml_declaration=True)
    with Image.open(MAIN / (stem + ".png")) as im:
        pixels = list(im.size)
    REPORT_ROWS.append({"stem": stem, "width_mm": 152.4,
        "height_mm": 152.4 * pixels[1] / pixels[0], "font_pt": None,
        "note": "Original author-approved layout and typography preserved; exempt from redraw.",
        "png_pixels": pixels, "png": str(MAIN / (stem + ".png")),
        "svg": str(MAIN / (stem + ".svg")),
        "output_png_sha256": sha256_file(MAIN / (stem + ".png")),
        "output_svg_sha256": sha256_file(MAIN / (stem + ".svg"))})


def draw_framework() -> None:
    """Redraw the complete two-stage Study01 workflow at Word scale."""
    fig, ax = plt.subplots(figsize=(TARGET_WIDTH_MM / 25.4, 155 / 25.4))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    def box(x, y, w, h, title, detail="", blue=False):
        edge = "#426F94" if blue else "#9AA8B1"
        face = "#ECF3F8" if blue else "#F7F8F9"
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=.35,rounding_size=1.2",
                                    facecolor=face, edgecolor=edge, linewidth=1.0))
        ax.text(x+w/2, y+h*.70, title, ha="center", va="center")
        if detail:
            ax.text(x+w/2, y+h*.31, detail, ha="center", va="center", linespacing=1.12)

    def arrow(x1, y1, x2, y2, blue=False, dashed=False):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                    mutation_scale=10, linewidth=1.0,
                                    linestyle="--" if dashed else "-",
                                    color="#426F94" if blue else "#596773"))

    def feedback_arrow():
        """Route the training feedback below the loss curve without crossing it."""
        color = "#426F94"
        ax.plot([87, 87, 44], [67, 55.8, 55.8], color=color, lw=1.0, ls="--")
        ax.add_patch(FancyArrowPatch((44, 55.8), (41.7, 61.2), arrowstyle="-|>",
                                    mutation_scale=10, linewidth=1.0,
                                    linestyle="--", color=color))

    def curve(x, y, w, h, title, blue=False, selected=False):
        ax.text(x, y+h+1.2, title, ha="left", va="bottom")
        ax.plot([x, x, x+w], [y+h, y, y], color="#A7B1B8", lw=.8)
        xx = np.linspace(x+1, x+w-1, 26)
        yy = y + h*(.16 + 1.05*((xx-(x+w*.47))/w)**2)
        ax.plot(xx, yy, color="#426F94" if blue else "#697A84", lw=1.2,
                marker="o", ms=1.2)
        ax.text(x, y-1, "0", ha="center", va="top")
        ax.text(x+w, y-1, "0.50", ha="center", va="top")
        ax.text(x+w/2, y-1, r"$\delta$", ha="center", va="top")
        if selected:
            i = int(np.argmin(yy)); ax.scatter(xx[i], yy[i], s=20, color="#B57729", zorder=4)
            ax.plot([xx[i], xx[i]], [y, yy[i]], color="#B57729", lw=.8, ls="--")
            ax.text(xx[i], yy[i]+2, r"$\hat\delta$", color="#A66A20", ha="center")

    ax.text(1, 98, "a  离线训练：学习候选偏移量的损失", ha="left", va="top")
    box(1, 73, 16, 12, "模拟样本", r"$X_n;\ \beta,\eta,\gamma$")
    box(22, 78, 20, 12, "逐候选运行 MDM", "26 点\n实际联合损失")
    box(22, 57.5, 20, 18, "", "", True)
    ax.text(32, 66.5,
            "损失曲线预测\n分样本量 MLP\n均值归一化\n训练折内标准化",
            ha="center", va="center", linespacing=1.2)
    curve(48, 78, 18, 9, "实际损失")
    curve(48, 60, 18, 9, "预测损失", True)
    box(75, 68, 23, 15, "曲线预测误差", "标准化损失曲线间\n的平方误差", True)
    arrow(17, 79, 22, 84); arrow(17, 77, 22, 67, True)
    arrow(42, 84, 47, 83); arrow(42, 67, 47, 65, True)
    arrow(67, 83, 75, 78); arrow(67, 65, 75, 73, True)
    feedback_arrow()
    ax.text(2, 54, "仅样本进入预测器；真参数仅用于离线构造训练损失", ha="left", va="center")
    ax.plot([1, 99], [51, 51], color="#D6DDE2", lw=.8)

    ax.text(1, 49.7, "b  实际估计：按当前样本选择偏移量", ha="left", va="top")
    box(1, 35, 16, 11, "当前样本", r"$X_n$")
    box(22, 35, 20, 11, "均值归一化", "沿用训练期\n标准化")
    box(47, 35, 18, 11, "已训练 MLP", "分样本量模型", True)
    arrow(17, 40.5, 22, 40.5); arrow(42, 40.5, 47, 40.5, True)
    curve(3, 12, 25, 11, "预测损失与选点", True, True)
    box(36, 11, 17, 13, "MDM", "参数拟合")
    box(61, 11, 18, 13, "参数估计", r"$\hat\beta,\hat\eta,\hat\gamma$")
    arrow(65, 35, 28, 24, True); arrow(28, 17.5, 36, 17.5, True); arrow(53, 17.5, 61, 17.5)
    ax.plot([9, 9, 44.5], [35, 27, 27], color="#596773", lw=1.0)
    arrow(44.5, 27, 44.5, 24)
    ax.text(25, 29, "原始样本直接进入 MDM", ha="center", va="bottom")
    word_export(fig, "fig1_adaptive_selection_drawio_v111", MAIN)


def draw_information_spaces(aux) -> None:
    aux.write_source_data()
    fig = plt.figure(figsize=(TARGET_WIDTH_MM / 25.4, 132 / 25.4))
    # Three equal panels above, two equal panels centered below.
    positions = [(.01,.55,.30,.34), (.345,.55,.30,.34), (.68,.55,.30,.34),
                 (.1775,.08,.30,.34), (.5125,.08,.30,.34)]
    for index, layer in enumerate(["L1", "L2", "L3", "L4", "L5"]):
        ax = fig.add_axes(positions[index], projection="3d")
        aux.add_information_space(ax, layer)
        ax.set_xticks([1.5, 3.0, 5.0])
        ax.set_yticks([.10, .50, 1.00])
        ax.set_zticks([7, 10, 15, 20])
        ax.tick_params(labelsize=TARGET_FONT_PT)
        ax.set_box_aspect((1.22, .96, .90), zoom=.92)
        ax.title.set_y(.94)
        ax.set_zlabel("")
        for artist in list(ax.texts):
            if artist.get_text() == r"$n$":
                artist.remove()
        ax.text2D(.91, .83, r"$n$", transform=ax.transAxes,
                  ha="center", va="center")
    word_export(fig, "fig4_information_spaces_restored_3d", MAIN)


def draw_beta_domain_3d(aux) -> None:
    data = aux.load_surface_data()
    curves, summary, centers, deltas, j1, center_mesh, delta_mesh, j1_fine = data
    levels = np.array([.50,.51,.52,.53,.54,.55,.56,.57,.58,.59,.60,.615,
                       .63,.645,.66,.68,.70,.73,.76,.80,.85,.90,.95,1.00])
    cmap = mpl.colormaps["YlGnBu"]
    norm = mpl.colors.BoundaryNorm(levels, cmap.N, clip=True)
    fig = plt.figure(figsize=(TARGET_WIDTH_MM / 25.4, 188 / 25.4))
    gs = fig.add_gridspec(2, 2, left=.03, right=.97, bottom=.08, top=.96,
                          height_ratios=[1.05, .95], hspace=.20, wspace=.10)
    a = fig.add_subplot(gs[0,0], projection="3d")
    b = fig.add_subplot(gs[0,1], projection="3d", computed_zorder=False)
    c = fig.add_subplot(gs[1,:])
    aux.panel_a(a)
    # Replace the source's projected 3D slab labels with two stable 2D labels;
    # the exact intervals are unchanged and no longer collide after scaling.
    for artist in list(a.texts):
        if "B_1=" in artist.get_text() or "B_2=" in artist.get_text():
            artist.remove()
    a.text2D(.43, .89, r"$B_1=[2.50,3.50]$", transform=a.transAxes,
             color="#1F6483", ha="left", va="center")
    a.text2D(.56, .81, r"$B_2=[2.75,3.75]$", transform=a.transAxes,
             color="#A85B29", ha="left", va="center")
    aux.panel_c(b, curves, summary, centers, deltas, j1, center_mesh,
                delta_mesh, j1_fine, cmap, norm)
    # Reserve the rightmost canvas band for the projected interval labels and
    # retain only the endpoints required to communicate the domain sweep.
    keep = np.array([0, len(centers)-1])
    b.set_yticks(centers[keep])
    b.set_yticklabels([
        f"[{summary.iloc[i].beta_lower:.2f}, {summary.iloc[i].beta_upper:.2f}]"
        for i in keep
    ])
    b.set_ylabel("")
    b.text2D(.96, .92, "形状参数域 B(c)", transform=b.transAxes,
             rotation=0, ha="right", va="center")
    a.set_xticks([1.5, 3.0, 5.0])
    a.set_yticks([.10, .50, 1.00])
    a.set_zticks([7, 15, 20])
    a.set_box_aspect((1.22, .96, .90), zoom=.92)
    b.set_xticks([0, .25, .50])
    b.set_zticks([.50, .75, 1.00])
    b.tick_params(axis="y", pad=8)
    b.set_box_aspect((1.20, 1.00, .88), zoom=.84)
    aux.panel_b(c, summary, centers, center_mesh, delta_mesh, j1_fine,
                cmap, norm, levels)
    c.set_box_aspect(None)
    c.set_title(r"c   $J_1$ 风险俯视图", loc="left", y=1.02)
    scalar = mpl.cm.ScalarMappable(norm=norm, cmap=cmap); scalar.set_array([])
    cb = fig.colorbar(scalar, ax=c, orientation="vertical", fraction=.025, pad=.02)
    cb.ax.set_title(r"$J_1$")
    # Explicit positions avoid tight-layout style projection spill: panel b
    # gets a wide right band; panel c gets enough left margin for interval text.
    a.set_position([.02, .55, .42, .38])
    b.set_position([.43, .55, .39, .38])
    c.set_position([.17, .08, .69, .39])
    cb.ax.set_position([.89, .08, .018, .39])
    word_export(fig, "fig3_beta_domain_restored_3d", MAIN)


def load_aux_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def generate_all_module_figures() -> None:
    global LOCALIZE
    configure_fonts()
    plot = load_plot_module()
    LOCALIZE = plot.localize_figure
    sys.modules["make_submission_figures"] = plot
    plot.MAIN_DIR = MAIN
    plot.SUPP_DIR = SUPP
    plot.DERIVED_DIR = DERIVED
    plot.TABLES_DIR = DERIVED / 'tables'
    plot.export_figure = word_export
    paths = plot.source_paths()
    summary = plot.load_summary(paths)
    preserve_framework()
    plot.figure_7_selector_mechanism(paths)
    plot.supplementary_parameter_guided(paths)
    plot.supplementary_unseen_beta(paths)
    plot.figure_6_main_results(paths, summary)
    plot.supplementary_traditional(paths, summary)
    plot.supplementary_quantiles(paths)
    plot.supplementary_decision_conditions(paths)
    plot.supplementary_parameter_landscape(paths)
    plot.supplementary_z_only_learning_curve(paths)

    fig5 = load_aux_module(
        "study01_fig5_word",
        SOURCE_SCRIPTS / "plot_fig5_information_level_results.py",
    )
    fig5.SOURCE_PATH = DERIVED / "fig5_information_level_results.csv"
    results = fig5.read_formal_results()
    fig5.write_source_data(results)
    fig5.export_figure(fig5.draw_figure(results))

    fig3 = load_aux_module(
        "study01_fig3_word",
        SOURCE_SCRIPTS / "plot_fig3_beta_domain_sensitivity.py",
    )
    draw_beta_domain_3d(fig3)

    fig4 = load_aux_module(
        "study01_fig4_word",
        SOURCE_SCRIPTS / "plot_fig4_information_spaces.py",
    )
    fig4.SOURCE_PATH = DERIVED / "fig4_information_space_cells.csv"
    draw_information_spaces(fig4)

    offset = load_aux_module(
        "plot_offset_revision_v112",
        SOURCE_SCRIPTS / "plot_offset_revision_v112.py",
    )
    sys.modules["plot_offset_revision_v112"] = offset
    offset.save = lambda fig, name, folder="main": word_export(
        fig, name, MAIN if folder == "main" else SUPP
    )
    offset.fig2()
    offset.supp()

    sample = load_aux_module(
        "study01_sample_columns_word",
        SOURCE_SCRIPTS / "plot_fig7_sample_columns.py",
    )
    sample.save = offset.save
    sample.main()
    save_report()


if __name__ == "__main__":
    generate_all_module_figures()
