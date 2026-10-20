"""把有限的原理演示数据嵌入HTML；不生成蒙特卡洛结果，不改动已有样本。

在项目根目录运行：
python/.venv/Scripts/python.exe "Study/04-study-小样本三参数Weibull估计方法比较与选择/方法分类/原理图解/更新图解数据.py"
"""
from pathlib import Path
import json
import re
import sys

import numpy as np
from scipy.optimize import brentq, minimize_scalar

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "python"))
from methods.lse import log_weibull_order_stat_means
from methods.wmle import get_weight_j1, get_weight_j2, get_weight_j3


def pack(v):
    if isinstance(v, np.ndarray):
        return [pack(x) for x in v.tolist()]
    if isinstance(v, (float, np.floating)):
        return round(float(v), 9) if np.isfinite(v) else None
    if isinstance(v, dict):
        return {k: pack(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [pack(x) for x in v]
    return v


def shape_score(x, b, g, j2=1.0):
    z = np.log(x - g)
    z = z - z.mean()
    w = np.exp(b * (z - z.max()))
    return j2 / b - np.dot(w / w.sum(), z)


def profile_mdm(x, g):
    p = (np.arange(1, len(x) + 1) - .3) / (len(x) + .4)
    q = -np.log1p(-p)

    def objective(b):
        return float(np.std((x - g) / q ** (1 / b), ddof=1))

    # 有界示意计算，与正式实验结果和求解器身份分开。
    grid = np.geomspace(.15, 15, 75)
    vals = np.array([objective(b) for b in grid])
    candidates = [(grid[0], vals[0]), (grid[-1], vals[-1])]
    for k in range(1, len(grid) - 1):
        if vals[k] <= vals[k - 1] and vals[k] <= vals[k + 1]:
            r = minimize_scalar(objective, bounds=(grid[k - 1], grid[k + 1]), method="bounded")
            candidates.append((r.x, r.fun))
    b, sd = min(candidates, key=lambda t: t[1])
    etas = (x - g) / q ** (1 / b)
    return b, sd, float(etas.mean()), etas


def main():
    source = ROOT / "Research/00-方法对比/交付/结果/报告1/中间数据/样本.json"
    samples = json.loads(source.read_text(encoding="utf-8-sig"))
    cases = []
    for beta in (5.0, 2.0):
        sample = next(s for s in samples if s["beta"] == beta and s["n"] == 7 and s["sample_id"] == 31)
        x = np.array(sample["observations"], dtype=float)
        zwhite = log_weibull_order_stat_means(len(x))
        j2 = get_weight_j2(len(x))
        bgrid = np.linspace(.3, 10, 240)
        conditional = {
            "beta": bgrid,
            "mle": [shape_score(x, b, 500) for b in bgrid],
            "wmle": [shape_score(x, b, 500, j2) for b in bgrid],
            "mleRoot": brentq(lambda b: shape_score(x, b, 500), .01, 50),
            "wmleRoot": brentq(lambda b: shape_score(x, b, 500, j2), .01, 50),
            "kr": [shape_score(x[1:], b, x[0]) for b in bgrid],
            "krRoot": brentq(lambda b: shape_score(x[1:], b, x[0]), .01, 50),
        }
        # 稠密近端点网格，仅供演示曲线；端点没有用虚拟梯度补齐。
        gammas = np.unique(np.r_[np.linspace(0, x[0] * .98, 180), x[0] - np.geomspace(.2, x[0] * .02, 65)])
        prof = [profile_mdm(x, g) for g in gammas]
        sd = np.array([v[1] for v in prof])
        gradients = np.gradient(sd, gammas, edge_order=2)
        assert np.isfinite(gradients).all()
        cases.append({
            "id": f"r00-b{int(beta)}-n7-31", "beta": beta, "eta": 1000, "gamma": 500,
            "n": 7, "sampleId": 31, "seed": sample["seed"], "x": x, "white": zwhite,
            "j1": get_weight_j1(7), "j2": j2, "j3AtTrueBeta": get_weight_j3(7, beta),
            "score": conditional,
            "mdm": {"g": gammas, "beta": [v[0] for v in prof], "sd": sd,
                    "eta": [v[2] for v in prof], "etas": [v[3] for v in prof], "grad": gradients},
        })
        # 固定坐标下的方向关系，以及消元性质独立核对。
        u = np.log(x - 500)
        zz = zwhite - zwhite.mean()
        uu = u - u.mean()
        beta_white = np.dot(zz, zz) / np.dot(uu, zz)
        beta_park = np.dot(uu, zz) / np.dot(uu, uu)
        r2 = np.dot(uu, zz) ** 2 / (np.dot(uu, uu) * np.dot(zz, zz))
        assert np.isclose(beta_park, r2 * beta_white)
        w = (x - x.min()) / np.ptp(x)
        transformed = 1.7 * x + 380
        assert np.allclose(w, (transformed - transformed.min()) / np.ptp(transformed))
        assert np.allclose(transformed - transformed.min(), 1.7 * (x - x.min()))
        assert np.isclose(np.sum((1 - np.arange(7) / 7) * np.diff(np.r_[0, x])), x.mean())

    payload = pack({"version": "2026-10-20-v1", "source": str(source.relative_to(ROOT)), "cases": cases,
                    "scope": "Research00存档样本上的原理演示；不替代Study04正式七法结果。MDM形状演示域0.15–15，梯度为网格差分。"})
    html = Path(__file__).with_name("上半部分原理图解与批注.html")
    text = html.read_text(encoding="utf-8")
    block = '<script id="demo-data" type="application/json">' + json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c") + '</script>'
    updated, count = re.subn(r'<script id="demo-data" type="application/json">.*?</script>', lambda _: block, text, count=1, flags=re.S)
    assert count == 1, "HTML数据占位不存在"
    html.write_text(updated, encoding="utf-8")
    print(json.dumps({"html": str(html), "cases": len(cases), "checks": "finite curves, regression identity, W/V affine identity, Cran m1=sample mean", "bytes": html.stat().st_size}, ensure_ascii=False))


if __name__ == "__main__":
    main()
