"""用Research00存档样本解释判据选点；不重算或覆盖正式实验结果。

运行：python/.venv/Scripts/python.exe <本文件>
输出：Study04/reviewbyhtml/方法分类/assets/机制图中的draw.io原生矢量图和小型复核记录。
PNG、SVG、PDF由draw.io导出；XML保留曲线、坐标与公式。
"""

from pathlib import Path
import base64
import json
import math
import sys
import urllib.parse
import xml.etree.ElementTree as ET
import zlib

import numpy as np
from scipy.optimize import minimize_scalar

HERE = Path(__file__).resolve().parent
REPO = next(p for p in HERE.parents if (p / "python" / "base.py").exists())
sys.path.insert(0, str(REPO / "python"))
from methods.mdm import MDM
from methods.lse import LSE, log_weibull_order_stat_means
from methods.lre import LRE
from methods.mle import MLE
from methods.wmle import WMLE
from methods import wmle as wmle_weights
from methods.conditional_profiles import mle_profile, wmle_residuals

OUT = HERE.parent.parent / "reviewbyhtml" / "方法分类" / "assets" / "机制图"
SOURCE = REPO / "Research/00-方法对比/交付/结果/报告1/中间数据/样本.json"
SAMPLES = json.loads(SOURCE.read_text(encoding="utf-8"))
INK, BLUE, RED, GREEN, GRAY = "#263238", "#52788F", "#B44948", "#63835B", "#7D8790"
FONT = "Microsoft YaHei"


class Canvas:
    def __init__(self, stem, title, height):
        self.stem, self.height, self.count = stem, height, 0
        self.doc = ET.Element("mxfile", host="app.diagrams.net")
        page = ET.SubElement(self.doc, "diagram", name=title, id=stem)
        model = ET.SubElement(page, "mxGraphModel", page="1", pageWidth="1800",
                              pageHeight=str(height), math="1", background="#FFFFFF")
        self.root = ET.SubElement(model, "root")
        ET.SubElement(self.root, "mxCell", id="0")
        ET.SubElement(self.root, "mxCell", id="1", parent="0")
        self.text(32, 18, 1736, 60, title, 35, bold=True)

    def cell(self, x, y, w, h, value="", style=""):
        self.count += 1
        c = ET.SubElement(self.root, "mxCell", id=f"c{self.count}", value=value,
                          vertex="1", parent="1", style=style)
        ET.SubElement(c, "mxGeometry", x=str(x), y=str(y), width=str(w),
                      height=str(h), attrib={"as": "geometry"})

    def text(self, x, y, w, h, value, size=24, color=INK, bold=False):
        self.cell(x, y, w, h, value,
                  f"text;html=1;whiteSpace=wrap;fillColor=none;strokeColor=none;"
                  f"fontFamily={FONT};fontSize={size};fontColor={color};"
                  f"fontStyle={int(bold)};align=left;verticalAlign=middle;spacing=0;")

    def formula(self, x, y, w, h, value, size=25, color=INK):
        self.text(x, y, w, h, "$$" + value + "$$", size, color)

    def box(self, x, y, w, h, value, accent=False, size=24):
        color = RED if accent else BLUE
        self.cell(x, y, w, h, value,
                  f"rounded=1;arcSize=4;html=1;whiteSpace=wrap;"
                  f"fillColor={'#F1D7D4' if accent else '#EAF0F6'};strokeColor={color};"
                  f"fontFamily={FONT};fontColor={INK};fontSize={size};align=center;verticalAlign=middle;")

    def arrow(self, points, color=BLUE):
        self.count += 1
        c = ET.SubElement(self.root, "mxCell", id=f"c{self.count}", edge="1", parent="1",
                          style=f"strokeColor={color};strokeWidth=2.2;endArrow=block;endFill=1;")
        g = ET.SubElement(c, "mxGeometry", relative="1", attrib={"as": "geometry"})
        for key, p in [("sourcePoint", points[0]), ("targetPoint", points[-1])]:
            ET.SubElement(g, "mxPoint", x=str(p[0]), y=str(p[1]), attrib={"as": key})
        if len(points) > 2:
            a = ET.SubElement(g, "Array", attrib={"as": "points"})
            for p in points[1:-1]:
                ET.SubElement(a, "mxPoint", x=str(p[0]), y=str(p[1]))

    def marks(self, x, y, w, h, dots=(), rectangles=()):
        """将一组有真实间距的点或相邻区间作为原生矢量图层。"""
        shape = ET.Element("shape", name="data-layer", w=str(w), h=str(h), aspect="variable")
        ET.SubElement(shape, "connections")
        ET.SubElement(shape, "background")
        fg = ET.SubElement(shape, "foreground")
        for a, b, radius, color in dots:
            ET.SubElement(fg, "fillcolor", color=color)
            ET.SubElement(fg, "strokecolor", color=color)
            ET.SubElement(fg, "ellipse", x=str(a - radius), y=str(b - radius),
                          w=str(radius * 2), h=str(radius * 2))
            ET.SubElement(fg, "fillstroke")
        for a, b, width, height, color in rectangles:
            ET.SubElement(fg, "fillcolor", color=color)
            ET.SubElement(fg, "strokecolor", color="#FFFFFF")
            ET.SubElement(fg, "strokewidth", width="1.2")
            ET.SubElement(fg, "rect", x=str(a), y=str(b), w=str(width), h=str(height))
            ET.SubElement(fg, "fillstroke")
        source = urllib.parse.quote(ET.tostring(shape, encoding="unicode"), safe="~()*!.'-")
        compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
        encoded = base64.b64encode(compressor.compress(source.encode()) + compressor.flush()).decode()
        self.cell(x, y, w, h, style=f"shape=stencil({encoded});fillColor=none;strokeColor={GRAY};")

    def panel(self, x, y, w, h, title):
        self.cell(x, y, w, h, "", "rounded=1;arcSize=3;fillColor=none;"
                  "strokeColor=#CED6DB;strokeWidth=1.3;dashed=1;dashPattern=3 5;container=1;collapsible=0;")
        self.text(x + 20, y + 12, w - 40, 46, title, 27, bold=True)

    def plot(self, x, y, w, h, curves=(), dots=(), vlines=(), hlines=(),
             xlim=None, ylim=None, xlabel="", ylabel="", xticks=None, yticks=None):
        """原生draw.io stencil；坐标、数值与点位使用同一线性变换。"""
        all_x = [float(v) for xx, _, _ in curves for v in xx]
        all_y = [float(v) for _, yy, _ in curves for v in yy]
        if xlim is None:
            xlim = (min(all_x), max(all_x))
        if ylim is None:
            lo, hi = min(all_y), max(all_y)
            margin = max((hi - lo) * .08, 1e-6)
            ylim = (lo - margin, hi + margin)
        left, right, top, bottom = 76, w - 22, 18, h - 62

        def pos(a, b):
            return (left + (a - xlim[0]) / (xlim[1] - xlim[0]) * (right - left),
                    bottom - (b - ylim[0]) / (ylim[1] - ylim[0]) * (bottom - top))

        shape = ET.Element("shape", name=f"plot{self.count}", w=str(w), h=str(h),
                           aspect="variable", strokewidth="inherit")
        ET.SubElement(shape, "connections")
        ET.SubElement(shape, "background")
        fg = ET.SubElement(shape, "foreground")

        def line(points, color, width=2, dash=False):
            ET.SubElement(fg, "strokecolor", color=color)
            ET.SubElement(fg, "strokewidth", width=str(width))
            ET.SubElement(fg, "dashed", dashed=str(int(dash)))
            p = ET.SubElement(fg, "path")
            ET.SubElement(p, "move", x=str(points[0][0]), y=str(points[0][1]))
            for a, b in points[1:]:
                ET.SubElement(p, "line", x=str(a), y=str(b))
            ET.SubElement(fg, "stroke")

        def label(a, b, s, color=GRAY, size=20, align="center"):
            ET.SubElement(fg, "fontfamily", family=FONT)
            ET.SubElement(fg, "fontcolor", color=color)
            ET.SubElement(fg, "fontsize", size=str(size))
            ET.SubElement(fg, "text", x=str(a), y=str(b), str=s,
                          align=align, valign="middle")

        def number(value):
            return f"{value:.0f}" if abs(value) >= 100 else f"{value:.3g}"

        def clipped_segment(a, b):
            # 真正裁剪线段，避免候选回归线的端点在框外时整条线消失。
            dx, dy = b[0] - a[0], b[1] - a[1]
            low, high = 0., 1.
            for p, q in [(-dx, a[0] - xlim[0]), (dx, xlim[1] - a[0]),
                         (-dy, a[1] - ylim[0]), (dy, ylim[1] - a[1])]:
                if abs(p) < 1e-14:
                    if q < 0:
                        return None
                elif p < 0:
                    low = max(low, q / p)
                else:
                    high = min(high, q / p)
                if low > high:
                    return None
            return [pos(a[0] + u * dx, a[1] + u * dy) for u in (low, high)]

        line([(left, top), (left, bottom), (right, bottom)], GRAY, 1.5)
        for a in xticks if xticks is not None else np.linspace(*xlim, 4):
            px, _ = pos(a, ylim[0])
            line([(px, bottom), (px, bottom + 5)], GRAY, 1)
            label(px, bottom + 21, number(a))
        for b in yticks if yticks is not None else np.linspace(*ylim, 4):
            _, py = pos(xlim[0], b)
            line([(left - 5, py), (left, py)], GRAY, 1)
            label(left - 10, py, number(b), align="right")
        for a, color in vlines:
            line([pos(a, ylim[0]), pos(a, ylim[1])], color, 1.4, True)
        for b, color in hlines:
            if ylim[0] <= b <= ylim[1]:
                line([pos(xlim[0], b), pos(xlim[1], b)], color, 1.4, True)
        for xx, yy, color in curves:
            coordinates = list(zip(xx, yy))
            for a, b in zip(coordinates[:-1], coordinates[1:]):
                if np.isfinite(a).all() and np.isfinite(b).all():
                    segment = clipped_segment(a, b)
                    if segment is not None:
                        line(segment, color, 2.5)
        ET.SubElement(fg, "dashed", dashed="0")
        for a, b, color, radius in dots:
            px, py = pos(a, b)
            ET.SubElement(fg, "fillcolor", color=color)
            ET.SubElement(fg, "strokecolor", color=color)
            ET.SubElement(fg, "ellipse", x=str(px - radius), y=str(py - radius),
                          w=str(2 * radius), h=str(2 * radius))
            ET.SubElement(fg, "fillstroke")
        label((left + right) / 2, h - 11, xlabel, INK, 23)
        label(left + 8, top - 6, ylabel, INK, 23, "left")
        encoded = urllib.parse.quote(ET.tostring(shape, encoding="unicode"), safe="~()*!.'-")
        compress = zlib.compressobj(9, zlib.DEFLATED, -15)
        data = compress.compress(encoded.encode()) + compress.flush()
        stencil = base64.b64encode(data).decode()
        self.cell(x, y, w, h, style=f"shape=stencil({stencil});fillColor=none;strokeColor={GRAY};")

    def save(self, source):
        self.text(32, self.height - 43, 1736, 30, source, 19, GRAY)
        ET.indent(self.doc)
        (OUT / (self.stem + ".drawio")).write_text(
            ET.tostring(self.doc, encoding="unicode"), encoding="utf-8")


def sample(sid):
    return next(s for s in SAMPLES if s["beta"] == 5 and s["n"] == 7 and s["sample_id"] == sid)


def mdm():
    s = sample(48)
    t = np.asarray(s["observations"])
    n = len(t)
    q = -np.log1p(-(np.arange(1, n + 1) - .3) / (n + .4))
    model = MDM(t)
    bh, eh, gh, _, valid = model.run(trace=True, offset=.1)
    assert valid and model.last_solution_info["root_solver"] == "brent"
    cache = {}

    def pseudo(b, g):
        return (t - g) / q ** (1 / b)

    def conditional(g):
        if g not in cache:
            r = minimize_scalar(lambda b: np.std(pseudo(b, g), ddof=1),
                                bounds=(.1, 15), method="bounded")
            cache[g] = (r.x, r.fun, float(np.mean(pseudo(r.x, g))))
        return cache[g]

    h = max(abs(t[0]), 1) * 1e-5

    def gradient(g):
        if g <= h:
            return (conditional(g + h)[1] - conditional(g)[1]) / h
        return (conditional(g + h)[1] - conditional(g - h)[1]) / (2 * h)

    assert abs(gradient(gh) - .1) < 2e-6
    assert np.allclose(conditional(gh)[0], bh)  # 同一条件形状搜索
    assert abs(conditional(gh)[2] - eh) < 1e-7
    grid = np.unique(np.r_[np.linspace(0, 1130, 190), 500, 750, gh])
    profile = np.array([conditional(float(g)) for g in grid])
    gradients = np.array([gradient(float(g)) for g in grid])
    colors = [BLUE, GREEN, RED]
    gs = [500, 750, gh]
    return {"method": "MDM-0.1", "sample_id": 48, "sample": s, "estimate": [bh, eh, gh],
            "gradient_at_selected_gamma": float(gradient(gh)), "conditional_curve_columns": ["beta", "std", "eta_mean"],
            "gamma_grid": grid.tolist(), "conditional_curve": profile.tolist(), "gradient_curve": gradients.tolist()}


def regression(cls):
    s = sample(17)
    t = np.asarray(s["observations"])
    n = len(t)
    name = cls.__name__
    bh, eh, gh, _, valid = cls(t).run()
    assert valid
    scores = (log_weibull_order_stat_means(n) if cls is LSE else
              np.log(-np.log1p(-(np.arange(1, n + 1) - 3 / 8) / (n + 1 / 4))))

    def fit(g):
        u = np.log(t - g)
        rho = float(np.corrcoef(u, scores)[0, 1])
        if cls is LSE:
            slope, intercept = np.polyfit(scores, u, 1)
            b, eta, criterion = 1 / slope, np.exp(intercept), 1 - rho ** 2
        else:
            slope, intercept = np.polyfit(u, scores, 1)
            b, eta, criterion = slope, np.exp(-intercept / slope), rho
        return b, eta, criterion, slope, intercept

    assert np.allclose(fit(gh)[:2], [bh, eh], rtol=1e-8)
    grid = np.unique(np.r_[np.linspace(0, t[0] * .995, 240), gh, 500])
    values = np.array([fit(g) for g in grid])
    min_gamma = float(grid[np.argmin(values[:, 2]) if cls is LSE else np.argmax(values[:, 2])])
    assert abs(min_gamma - gh) < 1e-6
    return {"method": name, "sample_id": 17, "sample": s, "scores": scores.tolist(),
            "estimate": [bh, eh, gh], "criterion_at_selected_gamma": float(fit(gh)[2]),
            "gamma_grid": grid.tolist(), "curve_columns": ["beta", "eta", "criterion", "slope", "intercept"],
            "curves": values.tolist()}



def draw_mdm_structure(r):
    t = np.asarray(r["sample"]["observations"])
    n = len(t)
    q = -np.log1p(-(np.arange(1, n + 1) - .3) / (n + .4))
    grid = np.asarray(r["gamma_grid"])
    profile = np.asarray(r["conditional_curve"])
    bh, eh, gh = r["estimate"]
    gradients = np.asarray(r["gradient_curve"])
    f = Canvas("MDM-伪尺度与条件定位", "MDM：先按差异定形状，再按梯度定位置", 960)
    f.box(32, 105, 420, 110, "排序寿命 t₍ᵢ₎<br>绘图概率 pᵢ", size=27)
    f.arrow([(467, 160), (528, 160)])
    f.box(545, 105, 660, 110,
          r"$$\eta_i(\beta,\gamma)=\frac{t_{(i)}-\gamma}{[-\ln(1-p_i)]^{1/\beta}}$$", size=28)
    f.arrow([(1220, 160), (1274, 160)])
    f.box(1290, 105, 478, 110,
          r"$$s_\eta=\mathrm{std}(\eta_1,\ldots,\eta_n)$$", size=28)
    xs = [32, 640, 1248]
    for x, title in zip(xs, ["① 固定γ，找条件最低点", "② 改变γ，连成差异曲线", "③ 求梯度，按阈值定位置"]):
        f.panel(x, 273, 520, 407, title)
    bs = np.linspace(1, 13, 170)
    curves, dots = [], []
    for g, color in [(500, BLUE), (750, GREEN)]:
        values = np.array([np.std((t - g) / q ** (1 / b), ddof=1) for b in bs])
        res = minimize_scalar(lambda b: np.std((t - g) / q ** (1 / b), ddof=1),
                              bounds=(.1, 15), method="bounded")
        curves.append((bs, values, color))
        dots.append((res.x, res.fun, color, 5))
    f.plot(47, 342, 490, 237, curves=curves, dots=dots, xlim=(1, 13), ylim=(0, 260),
           xlabel="候选 β", ylabel="标准差 sη", xticks=[1, 5, 9, 13], yticks=[0, 100, 200])
    f.text(58, 586, 470, 34, "蓝：γ=500　绿：γ=750；圆点为最低点", 20)
    f.formula(58, 610, 470, 62, r"(\beta^*(\gamma),\,s^*(\gamma))", 27, BLUE)
    f.arrow([(565, 468), (625, 468)])
    f.text(559, 417, 72, 42, "逐个γ", 19)
    f.plot(655, 342, 490, 237, curves=[(grid, profile[:, 1], BLUE)],
           xlabel="候选 γ", ylabel="条件最小标准差 s*", xticks=[0, 500, 1000])
    f.formula(664, 590, 470, 58, r"s^*(\gamma)=\min_\beta s_\eta(\beta,\gamma)", 27)
    f.arrow([(1173, 468), (1233, 468)])
    f.text(1170, 417, 70, 42, "求梯度", 19)
    f.plot(1263, 342, 490, 237, curves=[(grid, gradients, BLUE)],
           dots=[(gh, .1, RED, 6)], vlines=[(gh, RED)], hlines=[(.1, RED)],
           xlim=(0, 1130), ylim=(-.02, .3), xlabel="候选 γ", ylabel="梯度 g(γ)",
           xticks=[0, 500, 1000], yticks=[0, .1, .2, .3])
    f.formula(1272, 589, 470, 57, r"g(\widehat\gamma)=\frac{ds^*}{d\gamma}=\delta=0.1", 27, RED)
    f.arrow([(1508, 692), (1508, 749)], RED)
    f.text(32, 716, 300, 38, "参数恢复", 26, RED, True)
    f.box(32, 760, 1736, 100,
          r"$$\widehat\gamma\ \longrightarrow\ \widehat\beta=\beta^*(\widehat\gamma)\ \longrightarrow\ \widehat\eta=\frac1n\sum_i\eta_i(\widehat\beta,\widehat\gamma)$$", True, 28)
    f.text(32, 879, 1736, 35, "关键区别：位置由梯度阈值确定，不是再取标准差曲线的最低点。曲线采用同一实际算例，δ为设定值。", 23)
    f.save("依据：182-030／046与当前MDM-0.1；Research00报告1第48组存档寿命。图解内部交点，边界另记。")


def draw_regression_structure(records):
    f = Canvas("概率图-原型与改动", "概率图方法：分数、定位与回归方向的组合不同", 1140)
    f.box(32, 105, 1736, 86,
          r"$$u_i(\gamma)=\ln(t_{(i)}-\gamma),\qquad z_i\approx\beta u_i-\beta\ln\eta$$", size=28)
    f.text(52, 124, 300, 44, "共同分布关系", 27, BLUE, True)
    for row, r in enumerate(records):
        name = r["method"]
        lse = name == "LSE"
        y = 258 + row * 411
        color = BLUE if lse else RED
        t = np.asarray(r["sample"]["observations"])
        scores = np.asarray(r["scores"])
        grid = np.asarray(r["gamma_grid"])
        values = np.asarray(r["curves"])
        bh, eh, gh = r["estimate"]
        u = np.log(t - gh)
        xvals, yvals = (scores, u) if lse else (u, scores)
        slope, intercept = np.polyfit(xvals, yvals, 1)
        f.text(32, y - 58, 1736, 42,
               "White → Soman：期望分数＋F评分＋u对z回归" if lse else
               "Park Proposed+Plot：绘图分数＋相关评分＋z对u回归", 29, color, True)
        f.box(32, y + 88, 270, 136,
              r"White分数<br>$$z_i=E[Z_{(i:n)}]$$" if lse else
              r"绘图概率<br>$$z_i=\ln[-\ln(1-p_i)]$$", not lse, 25)
        f.arrow([(314, y + 156), (341, y + 156)], color)
        f.panel(350, y, 430, 326, "回归关系")
        f.plot(362, y + 63, 406, 197,
               curves=[(xvals, slope * xvals + intercept, color)],
               dots=[(a, b, color, 4.5) for a, b in zip(xvals, yvals)],
               xlabel="z" if lse else "u", ylabel="u" if lse else "z")
        f.formula(370, y + 270, 385, 45, r"u=a+bz" if lse else r"z=a+bu", 26, color)
        f.arrow([(792, y + 156), (829, y + 156)], color)
        f.panel(840, y, 500, 326, "改变γ，比较线性程度")
        idx = int(np.argmin(abs(grid - gh)))
        f.plot(854, y + 63, 472, 197, curves=[(grid, values[:, 2], color)],
               dots=[(gh, values[idx, 2], color, 5.5)], vlines=[(gh, color)],
               xlabel="候选 γ", ylabel="1−R²" if lse else "ρ", xticks=[0, 500, 1000])
        f.formula(860, y + 267, 460, 49,
                  r"\widehat\gamma=\arg\min(1-R^2)\ \Leftrightarrow\ \max F" if lse else
                  r"\widehat\gamma=\arg\max\rho(\gamma)", 25, color)
        f.arrow([(1352, y + 156), (1380, y + 156)], color)
        f.box(1390, y + 77, 378, 161,
              r"由选定位置的回归系数恢复<br>$$\widehat\beta=1/b,\quad\widehat\eta=e^a$$" if lse else
              r"由选定位置的回归系数恢复<br>$$\widehat\beta=b,\quad\widehat\eta=e^{-a/b}$$", not lse, 25)
    f.text(32, 1034, 1736, 47, "结构对照不表示Soman到Park的历史沿袭；两种方法同时改变分数与回归方向，不能把整体差异只归因于一项。", 23)
    f.save("依据：182-134／104、182-115／106；同一份Research00第17组存档寿命，采用当前Soman与Park实现重算。")


def correct_tl_example():
    """原文182-138式(4)、(5)：二阶L矩与对称t=1的TL矩对照。"""
    path = OUT / "矩方法-加权汇总与变体.drawio"
    doc = ET.parse(path)
    root = doc.find(".//root")
    for c in list(root):
        if c.get("id", "").startswith("tl-"):
            root.remove(c)

    def cell(suffix, x, y, w, h, value="", style=""):
        c = ET.SubElement(root, "mxCell", id="tl-revised-" + suffix, parent="1",
                          vertex="1", value=value, style=style)
        ET.SubElement(c, "mxGeometry", x=str(x), y=str(y), width=str(w),
                      height=str(h), attrib={"as": "geometry"})

    textstyle = (f"text;html=1;whiteSpace=wrap;fillColor=none;strokeColor=none;"
                 f"fontFamily={FONT};fontSize=24;fontColor={INK};align=left;verticalAlign=middle;")
    cell("label-l", 1240, 500, 500, 45, "L₂：2个概念次序量", textstyle)
    for j, x in enumerate([1330, 1600]):
        cell("l-dot-" + str(j), x, 570, 12, 12,
             style=f"ellipse;fillColor={BLUE};strokeColor={BLUE};")
    cell("l-formula", 1240, 602, 500, 65,
         r"$$\lambda_2=\tfrac12 E(Y_{2:2}-Y_{1:2})$$", textstyle)
    cell("label-tl", 1240, 687, 500, 45, "TL₂（两端各1）：4个概念次序量", textstyle)
    for j, x in enumerate([1290, 1415, 1540, 1665]):
        color = RED if j in (1, 2) else GRAY
        cell("tl-dot-" + str(j), x, 755, 12, 12,
             style=f"ellipse;fillColor={color};strokeColor={color};")
    cell("tl-formula", 1240, 788, 500, 65,
         r"$$\lambda_2^{(1)}=\tfrac12 E(Y_{3:4}-Y_{2:4})$$", textstyle)
    cell("note", 1240, 874, 500, 110,
         "把概念样本从2扩大到4，<br>使用中间两项的期望差。<br>实际样本另按权重估计。", textstyle)
    ET.indent(doc)
    path.write_text(ET.tostring(doc.getroot(), encoding="unicode"), encoding="utf-8")


def splice(canvas, path, remove):
    """局部修订原结构图，保留未受影响面板和稳定ID。"""
    doc = ET.parse(path)
    root = doc.find(".//root")
    for cell in list(root):
        if remove(cell.get("id", "")):
            root.remove(cell)
    for cell in list(canvas.root):
        if cell.get("id") in ("0", "1", "c1"):
            continue
        cell.set("id", "mechanism-v6-" + cell.get("id"))
        root.append(cell)
    ET.indent(doc)
    path.write_text(ET.tostring(doc.getroot(), encoding="unicode"), encoding="utf-8")


def patch_likelihood():
    """保留原型与三个改动面板，只在判据环节嵌入必要曲线。"""
    s = sample(18)
    t = np.asarray(s["observations"])
    estimate = MLE(t).run()
    assert estimate[4]
    bh, eh, gh = estimate[:3]
    grid = np.unique(np.r_[np.linspace(0, t[0] * .995, 150), gh])
    profiles = [mle_profile(t, g) for g in grid]
    ref = mle_profile(t, 500)["ll"]
    ll = np.array([p["ll"] - ref for p in profiles])
    assert abs(mle_profile(t, gh)["beta"] - bh) < 1e-6
    f = Canvas("unused", "unused", 1200)
    f.text(952, 196, 358, 38, "③ 比较有限似然候选", 26, bold=True)
    f.plot(940, 246, 372, 155, curves=[(grid, ll, BLUE)],
           dots=[(gh, mle_profile(t, gh)["ll"] - ref, RED, 5)],
           xlabel="候选 γ", ylabel="相对对数似然", xticks=[0, 1000])
    f.text(952, 398, 358, 30, "此曲线条件：β≥1，尺度已消去", 18, GRAY)

    s2 = sample(41)
    t2 = np.asarray(s2["observations"])
    estimate2 = WMLE(t2).run()
    assert estimate2[4]
    b2, e2, g2 = estimate2[:3]
    residual = wmle_residuals(t2, b2, g2, wmle_weights)
    assert np.max(np.abs(residual)) < 2e-7
    # 两条零值关系的局部图，保留每条关系的所有分支，不模拟求解器轨迹。
    from matplotlib.figure import Figure
    contour_figure = Figure()
    ax = contour_figure.subplots()
    gx, bx = np.meshgrid(np.linspace(800, 1120, 140), np.linspace(1.8, 5.5, 140))
    a, b = wmle_residuals(t2, bx, gx, wmle_weights)
    curves = []
    for surface, color in [(a, BLUE), (b, RED)]:
        contour = ax.contour(gx, bx, surface, levels=[0])
        curves.extend((p[:, 0], p[:, 1], color) for p in contour.allsegs[0] if len(p) > 1)
    f.text(1236, 525, 512, 34, "改权重项 → 移动联立方程的交点", 23, RED, True)
    f.formula(1244, 562, 500, 50, r"\tfrac1\beta\ \longrightarrow\ \tfrac{J_2(n)}\beta", 25, RED)
    f.formula(1244, 619, 500, 50, r"\tfrac{\beta}{\beta-1}\ \longrightarrow\ J_3(n,\beta)", 25, RED)
    f.plot(1238, 693, 510, 189, curves=curves, dots=[(g2, b2, RED, 5.5)],
           xlim=(800, 1120), ylim=(1.8, 5.5), xlabel="候选 γ", ylabel="候选 β",
           xticks=[800, 1000], yticks=[2, 4])
    f.text(1244, 877, 500, 30, "蓝T₁=0　红T₂=0；dᵢ=tᵢ−γ", 20)
    f.formula(1244, 908, 500, 66,
              r"\widehat\eta=[\overline{d^{\widehat\beta}}/J_1(n)]^{1/\widehat\beta}", 24)
    path = OUT / "似然方法-原型与改动.drawio"
    remove_ids = {"score-title", "score-β", "score-η", "score-γ"}
    splice(f, path, lambda cid: cid.startswith("mechanism-v6-") or cid in remove_ids
           or cid.startswith("wmle-") or cid.startswith("weight-"))
    doc = ET.parse(path)
    doc.find(".//mxCell[@id='prototype']").set("value", "(a) MLE原型：同一份数据 → 密度乘积 → 比较候选 → 参数估计")
    likelihood_formula = doc.find(".//mxCell[@id='likelihood-formula']")
    likelihood_formula.set("value", r"$$\textstyle\ell(\theta)=\sum_i\ln f(t_i;\theta)$$")
    likelihood_formula.find("mxGeometry").set("y", "360")
    likelihood_formula.find("mxGeometry").set("height", "62")
    ET.indent(doc)
    path.write_text(ET.tostring(doc.getroot(), encoding="unicode"), encoding="utf-8")
    return {"method": "MLE / WMLE local mechanism", "mle_sample_id": 18,
            "wmle_sample_id": 41, "mle_estimate": estimate[:3],
            "wmle_estimate": estimate2[:3], "wmle_joint_residual": list(residual)}


def patch_cran():
    """补全统计量到参数的短链，不增加逐参数结果图。"""
    t = np.asarray(sample(17)["observations"])
    n = len(t)
    f = Canvas("unused", "unused", 1180)
    f.text(54, 496, 510, 38, "阶梯面积 → 矩差消元 → 形状", 25, RED, True)
    curves = []
    for k, color in [(1, BLUE), (2, RED), (4, GREEN)]:
        xx, yy = [0], [1.]
        for i, value in enumerate(t):
            xx.extend([value, value])
            yy.extend([(1 - i / n) ** k, (1 - (i + 1) / n) ** k])
        curves.append((xx, yy, color))
    f.plot(48, 550, 510, 151, curves=curves, xlim=(0, 1900), ylim=(0, 1),
           xlabel="寿命 t", ylabel="S、S²、S⁴", xticks=[0, 1000], yticks=[0, 1])
    f.formula(52, 710, 508, 60,
              r"\overline m_k=\int_0^\infty\widehat S(t)^kdt,\ k=1,2,4", 23)
    f.formula(52, 779, 508, 55,
              r"\mu_k=\gamma+\eta\Gamma(1+1/\beta)k^{-1/\beta}", 23)
    f.formula(52, 837, 508, 65,
              r"\frac{\mu_1-\mu_2}{\mu_2-\mu_4}=2^{1/\beta}", 26, RED)
    f.text(54, 910, 502, 34, "样本矩差之比记为R，反解β", 22, RED, True)
    f.formula(52, 950, 508, 51,
              r"\widehat\beta=\ln2/\ln R", 26, RED)
    splice(f, OUT / "矩方法-加权汇总与变体.drawio",
           lambda cid: cid.startswith("cran-") or cid.startswith("mechanism-v6-"))


def patch_invariance():
    t = np.asarray(sample(17)["observations"])
    vs = t - t[0]
    ws = vs / vs[-1]
    for transformed in (t + 100, 2 * t):
        assert np.allclose((transformed - transformed[0]) / (transformed[-1] - transformed[0]), ws)
    f = Canvas("unused", "unused", 1080)
    # 同一统计量内的三行共享一把尺；不再各自拉伸成同一宽度。
    for start_x, width, normalized in [(56, 770, True), (920, 820, False)]:
        x0 = start_x + 153
        scale = width - 185
        for row, (label, factor) in enumerate([("原样本", 1), ("平移+100", 1), ("放大×2", 2)]):
            y = 600 + row * 44
            f.text(start_x, y - 14, 145, 30, label, 20, GRAY)
            values = ws if normalized else factor * vs / (2 * vs[-1])
            color = BLUE if normalized else (RED if row == 2 else BLUE)
            f.marks(x0 - 5, y - 6, scale + 10, 12,
                    dots=[(5 + float(v) * scale, 6, 4, color) for v in values])
        f.text(x0 - 6, 714, 40, 30, "0", 19, GRAY)
        f.text(x0 + scale - 55, 714, 95, 30,
               "1" if normalized else f"{2 * vs[-1]:.0f}", 19, GRAY)
    splice(f, OUT / "不变统计量-W与V.drawio",
           lambda cid: cid.startswith("mechanism-v6-") or cid in ("w-w-ranks", "v-v-ranks"))


def patch_spacing():
    t = np.asarray(sample(17)["observations"])
    f = Canvas("unused", "unused", 1080)
    scores = []
    for row, (beta, eta, gamma) in enumerate([(5, 1000, 500), (2, 500, 1000)]):
        cdf = 1 - np.exp(-((t - gamma) / eta) ** beta)
        boundaries = np.r_[0, cdf, 1]
        spacings = np.diff(boundaries)
        assert len(spacings) == len(t) + 1 and np.all(spacings > 0) and np.isclose(spacings.sum(), 1)
        score = float(np.log(spacings).sum())
        scores.append(score)
        y = 556 + row * 100
        f.text(56, y - 38, 490, 34, f"候选{'A' if row == 0 else 'B'}：Σln Dᵢ={score:.2f}", 22,
               BLUE if row == 0 else RED, True)
        f.marks(64, y, 472, 34, rectangles=[
            (boundaries[i] * 472, 0, spacing * 472, 34,
             '#EAF0F6' if i % 2 == 0 else '#F1D7D4') for i, spacing in enumerate(spacings)])
        f.text(60, y + 37, 50, 25, "0", 18, GRAY)
        f.text(526, y + 37, 30, 25, "1", 18, GRAY)
    selected = "A" if scores[0] > scores[1] else "B"
    f.text(56, 725, 492, 37, f"同一批寿命，准则在A、B中偏好{selected}", 22, RED, True)
    f.formula(56, 782, 492, 52, r"\textstyle\max\sum_{i=1}^{n+1}\ln D_i", 27, RED)
    f.text(56, 846, 492, 48, "参数改变CDF，也改变每段概率。<br>A、B为候选对照，未声称全局最优。", 20, GRAY)
    splice(f, OUT / "概率区间-MPS与分组.drawio",
           lambda cid: cid.startswith("mechanism-v6-") or cid in ("mps-spacings", "mps-d", "mps-obj"))
    return {"method": "MPS candidate comparison", "sample_id": 17,
            "candidate_parameters_beta_eta_gamma": [[5, 1000, 500], [2, 500, 1000]],
            "log_spacing_scores": scores}


def patch_linear_weights():
    """182-140原文给出的条件权重，不自行模拟或声称新的性能。"""
    weights = np.array([.1558, .1407, .1730, .2170, .3135])
    assert abs(weights.sum() - 1) < 1e-12
    ranks = np.arange(1, 6)
    f = Canvas("unused", "unused", 1080)
    f.plot(54, 524, 508, 221,
           curves=[([i, i], [0, w], BLUE) for i, w in zip(ranks, weights)],
           dots=[(i, w, RED, 5) for i, w in zip(ranks, weights)],
           xlim=(.5, 5.5), ylim=(0, .35), xlabel="次序 i", ylabel="组合权重 aᵢ",
           xticks=[1, 2, 3, 4, 5], yticks=[0, .15, .3])
    f.text(56, 754, 500, 50, "原文算例：n=5，已知β=5、η=1。<br>不同次序量的权重由协方差决定。", 21, GRAY)
    f.formula(56, 813, 500, 65, r"a=\frac{\Sigma^{-1}1}{1^T\Sigma^{-1}1}", 28, RED)
    splice(f, OUT / "线性估计-条件权重与迭代.drawio",
           lambda cid: cid.startswith("mechanism-v6-") or cid in
           ("variance-var", "variance-weights", "variance-not-average"))


if __name__ == "__main__":
    records = [mdm(), regression(LSE), regression(LRE)]
    draw_mdm_structure(records[0])
    draw_regression_structure(records[1:])
    correct_tl_example()
    records.append(patch_likelihood())
    patch_cran()
    patch_invariance()
    records.append(patch_spacing())
    patch_linear_weights()
    (OUT / "判据机制图-复核数据.json").write_text(
        json.dumps({"source": str(SOURCE.relative_to(REPO)), "records": records}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    for r in records:
        print(r["method"], r.get("sample_id", ""), r.get("estimate", ""))
