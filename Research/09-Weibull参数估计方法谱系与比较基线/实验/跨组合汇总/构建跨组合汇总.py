"""从 8 批 数据/三方法汇总.csv 重建 跨组合汇总.csv / .md（120 行 = 8 组合 × 5 n × 3 方法）。

口径：MLE 与 WMLE 为注册表经典实现（methods/mle.py、methods/wmle.py），MMLE 为原版 K-R 固定点；
所有数值直接取自各批现算的汇总表，不重算、不修补。
"""
import json
from pathlib import Path

import pandas as pd

R = Path(r"D:\weibull\Research\09-Weibull参数估计方法谱系与比较基线\实验")
OUT = R / "跨组合汇总"
ORDER = ["W(1.5,1000,500)", "W(2,1000,500)", "W(3,1000,500)", "W(5,1000,500)",
         "W(2,1000,1000)", "W(2,1000,3000)", "W(2,100,500)", "W(1.5,100,500)"]
METHODS = ["MLE", "MMLE", "WMLE"]
PARAMS = ["beta", "eta", "gamma"]
LABEL = {"beta": "β", "eta": "η", "gamma": "γ"}

rows = []
for name in ORDER:
    b = R / name
    cfg = json.loads((b / "程序/config.json").read_text(encoding="utf-8"))
    d = pd.read_csv(b / "数据/三方法汇总.csv")
    d["display"] = d.method.replace({"K-R MMLE": "MMLE"})
    for m in METHODS:
        for _, r in d[d.display == m].sort_values("n").iterrows():
            rec = {"组合": name, "β真值": cfg["truth"][0], "η真值": cfg["truth"][1], "γ真值": cfg["truth"][2],
                   "方法": m, "n": int(r["n"]), "总组数": int(r["total"]), "成功数": int(r["success"]),
                   "有解率": float(r["success"]) / float(r["total"])}
            for p in PARAMS:
                for met, tag in (("bias", "Bias"), ("sd", "SD"), ("rmse", "RMSE")):
                    rec["%s %s" % (LABEL[p], tag)] = float(r["%s_%s" % (p, met)])
            rows.append(rec)

df = pd.DataFrame(rows)
cols = ["组合", "β真值", "η真值", "γ真值", "方法", "n", "总组数", "成功数", "有解率",
        "β Bias", "β SD", "β RMSE", "η Bias", "η SD", "η RMSE", "γ Bias", "γ SD", "γ RMSE"]
df = df[cols]
assert len(df) == 120 and not df.duplicated(["组合", "方法", "n"]).any()
assert (df["总组数"] == 1200).all()
import numpy as np  # noqa: E402
np.testing.assert_allclose(df["有解率"], df["成功数"] / df["总组数"], rtol=1e-14)
np.testing.assert_allclose(df["β RMSE"] ** 2, df["β Bias"] ** 2 + df["β SD"] ** 2, rtol=1e-10, atol=1e-8)

df.to_csv(OUT / "跨组合汇总.csv", index=False, encoding="utf-8-sig")

lines = ["# 跨组合汇总（8 参数组合 × 5 样本量 × 3 方法，共 120 行）", "",
         "口径：MLE 与 WMLE 为注册表经典实现（`methods/mle.py`、`methods/wmle.py`，与 Research00 生产程序逐字节相同）；",
         "MMLE 为原版 Kundu–Raqab 固定点迭代。精度统计只用成功估计（失败不计入），有解率分母 1200，不做绘图裁剪。", "",
         "Bias=mean(估计−真值)，SD=std(估计−真值,ddof=0)，RMSE=sqrt(mean((估计−真值)²))。", ""]
for name in ORDER:
    sub = df[df["组合"] == name]
    lines.append("## %s" % name)
    lines.append("")
    lines.append("| 方法 | n | 成功数/总组数 | 有解率 | β Bias | β SD | β RMSE | η Bias | η SD | η RMSE | γ Bias | γ SD | γ RMSE |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for m in METHODS:
        for _, r in sub[sub["方法"] == m].sort_values("n").iterrows():
            lines.append("| %s | %d | %d/%d | %.2f%% | %.3f | %.3f | %.3f | %.2f | %.2f | %.2f | %.2f | %.2f | %.2f |" % (
                m, r["n"], r["成功数"], r["总组数"], 100 * r["有解率"],
                r["β Bias"], r["β SD"], r["β RMSE"], r["η Bias"], r["η SD"], r["η RMSE"],
                r["γ Bias"], r["γ SD"], r["γ RMSE"]))
    lines.append("")
lines.append("> 生成脚本：`实验/跨组合汇总/构建跨组合汇总.py`；数值直接取自各批 `数据/三方法汇总.csv`。")
(OUT / "跨组合汇总.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

print("跨组合汇总.csv / .md 已重建：%d 行" % len(df))
print(df.groupby(["方法"]).agg(最小有解率=("有解率", "min"), 最大有解率=("有解率", "max")).to_string())
