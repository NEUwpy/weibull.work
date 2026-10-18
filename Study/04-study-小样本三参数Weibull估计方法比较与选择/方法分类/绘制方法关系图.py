"""从已核对的分类工作稿生成报告上篇的四张PNG；不读取或改写实验数据。"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


HERE = Path(__file__).resolve().parent
OUT = HERE / "图片"
INK = "#263747"
BLUE = "#30678C"
GREEN = "#36765F"
GREY = "#687784"
TEXTS = []


def canvas(height=8.0):
    fig, ax = plt.subplots(figsize=(16, height))
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    ax.set(xlim=(0, 16), ylim=(0, height))
    ax.axis("off")
    return fig, ax


def node(ax, x, y, w, h, label, fill="#EFF4F8", color=BLUE, size=16):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.025,rounding_size=0.08",
        facecolor=fill, edgecolor=color, linewidth=1.15, zorder=2,
    ))
    artist = ax.text(x+w/2, y+h/2, label, ha="center", va="center",
                     fontsize=size, color=INK, linespacing=1.5, zorder=3)
    TEXTS.append((artist, (x, y, w, h)))


def edge(ax, start, end, label=None, label_at=None, mathematical=False, both=False):
    # Solid arrows represent explicit inheritance / use / combination;
    # dashed links represent mathematical or shared-construction relations.
    style = "<->" if both else ("-" if mathematical else "-|>")
    color = GREY if mathematical else BLUE
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle=style,
        mutation_scale=17, linewidth=1.4, color=color,
        linestyle=(0, (5, 3)) if mathematical else "-", zorder=1))
    if label:
        point = label_at or ((start[0]+end[0])/2, (start[1]+end[1])/2+.35)
        ax.text(*point, label, ha="center", va="center", fontsize=13,
                color=color, linespacing=1.3,
                bbox=dict(facecolor="white", edgecolor="none", pad=2), zorder=4)


def save(fig, name):
    # Verify that node labels fit, rather than silently clipping long names.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for artist, (x, y, w, h) in TEXTS:
        if artist.figure is not fig:
            continue
        a = artist.axes.transData.transform((x+.10, y+.08))
        b = artist.axes.transData.transform((x+w-.10, y+h-.08))
        for _ in range(8):
            bb = artist.get_window_extent(renderer)
            if bb.width <= b[0]-a[0] and bb.height <= b[1]-a[1]:
                break
            artist.set_fontsize(artist.get_fontsize()-.5)
            fig.canvas.draw()
        bb = artist.get_window_extent(renderer)
        assert bb.width <= b[0]-a[0] and bb.height <= b[1]-a[1], artist.get_text()
        assert artist.get_fontsize() >= 12, artist.get_text()
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT/name, dpi=220, facecolor="white")
    plt.close(fig)
    print(name)


def overview():
    fig, ax = canvas(10)
    rows = [
        ("似然与修正估计方程", "MLE · Cohen–Whitten MMLE · Smith／K–R\nCMLE · WMLE · DMMLE · LSPF／LPF"),
        ("概率区间准则", "MPS\n分位数分组似然 QML／QMP"),
        ("分布关系与拟合", "概率图回归 · CDF-LSE／WLSE · EIV\nMDM · 密度拟合 · 灰色／SVR组合"),
        ("矩与统计关系\n匹配／反演", "常规矩 · Weibull矩 · PWM · L矩／截尾L矩\n标准化统计量匹配 · 枢轴反演"),
        ("线性最小方差估计", "条件位置MVLUE\nMVLE-H及扩展／迭代"),
        ("后验推断", "先验＋似然 → 后验点估计\nGibbs／Laplace用于计算后验量"),
        ("直接学习参数映射", "样本／特征 → 参数\nANN · BPNN"),
    ]
    node(ax, .25, 4.4, 2.0, 1.2, "三参数Weibull\n参数估计", size=16)
    ax.plot([2.25, 2.65], [5, 5], color=GREY, lw=1.1)
    centers = [8.95-i*1.3 for i in range(7)]
    ax.plot([2.65, 2.65], [centers[-1], centers[0]], color=GREY, lw=1.1)
    for cy, (family, examples) in zip(centers, rows):
        ax.plot([2.65, 3.05], [cy, cy], color=GREY, lw=1.1)
        node(ax, 3.05, cy-.48, 3.5, .96, family, size=17)
        ax.plot([6.55, 7], [cy, cy], color=GREY, lw=1.1)
        node(ax, 7, cy-.48, 8.65, .96, examples,
             fill="#FAFBFC", color="#BBC6CE", size=15)
    save(fig, "01_方法原理分类总览.png")


def likelihood():
    fig, ax = canvas(8)
    xs, w, h = [.65, 6.15, 11.65], 3.7, 1.2
    labels = [
        "Jacquelin（1993）\n二参数推导",
        "Cousineau（2009）\n三参数WMLE",
        "杨小玉等（2024）\n形状偏差修正",
        "Smith（1985）\n最小值定位、删点",
        "Kundu–Raqab（2009）\n两样本场景适配",
        "da Silva等（2025）\nDMMLE",
    ]
    for row, y in enumerate([6.1, 3.2]):
        for i, x in enumerate(xs):
            node(ax, x, y, w, h, labels[row*3+i], size=16)
        for i, label in enumerate(
            ["三参数扩展", "形状偏差修正"] if row == 0
            else ["采用并适配", "修改似然基础"]
        ):
            edge(ax, (xs[i]+w, y+h/2), (xs[i+1], y+h/2), label)
    node(ax, xs[1], .5, w, h, "Firth（1993）\n得分偏差修正", fill="#EAF3EE", color=GREEN)
    edge(ax, (xs[1]+w, 1.1), (xs[2]+w/2, 3.2), "组合", (11.4, 1.65))
    save(fig, "02_似然路线的文献沿袭.png")


def probability_plot():
    fig, ax = canvas(8)
    rows = [
        ("White（1969）\n两参数分数与回归", "Soman–Misra（1992）\n三参数主分支", "增加位置搜索"),
        ("Park（2017）\n相关性定位与参数恢复", "Park（2018）\n同一构造的存在性论证", "理论补充"),
        ("Nagatsuka等（2013）\nLSPF位置修正关系", "Yang等（2023）\n回归＋位置修正交替迭代", "局部借用"),
    ]
    for y, (left, right, label) in zip([6.1, 3.55, 1.0], rows):
        node(ax, .75, y, 5.2, 1.3, left, size=18)
        node(ax, 10.05, y, 5.2, 1.3, right, size=18)
        edge(ax, (5.95, y+.65), (10.05, y+.65), label, (8, y+1.05))
    save(fig, "03_概率图路线的文献关系.png")


def moments_and_statistics():
    fig, ax = canvas(10)
    xs, w, h = [.65, 6.15, 11.65], 3.7, 1.25
    for x, label in zip(xs, ["Greenwood等（1979）\n概率加权矩 PWM",
                            "Hosking（1990）\nL矩",
                            "Elamir–Seheult（2003）\n截尾L矩"]):
        node(ax, x, 8.0, w, h, label, size=16)
    edge(ax, (xs[0]+w, 8.625), (xs[1], 8.625), "线性转换", (5.25, 9.35), mathematical=True, both=True)
    edge(ax, (xs[1]+w, 8.625), (xs[2], 8.625), "截尾推广", (10.75, 9.35))
    node(ax, xs[0], 5.5, w, h, "Cran\nWeibull矩", fill="#F4F5F6", color=GREY)
    edge(ax, (2.5, 6.75), (2.5, 8.0), "总体泛函联系", (4.6, 7.35), mathematical=True)
    ax.plot([.65, 15.35], [4.55, 4.55], color="#D8DEE4", lw=.8)
    for x, label in zip(xs, ["Nagatsuka等（2003）\nW统计量均值匹配",
                            "Nagatsuka等（2013）\nW统计量似然 LSPF",
                            "Nagatsuka–Balakrishnan\n（2015）V统计量似然 LPF"]):
        node(ax, x, 1.4, w, h, label, size=15)
    edge(ax, (xs[0]+w, 2.025), (xs[1], 2.025), "共享W构造\n估计准则不同", (5.25, 3.2), mathematical=True)
    edge(ax, (xs[1]+w, 2.025), (xs[2], 2.025), "改换统计量\n保留尺度信息", (10.75, 3.2))
    save(fig, "04_矩与统计量的文献关系.png")


if __name__ == "__main__":
    plt.rcParams.update({"font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "Arial", "DejaVu Sans"],
        "axes.unicode_minus": False})
    overview()
    likelihood()
    probability_plot()
    moments_and_statistics()
