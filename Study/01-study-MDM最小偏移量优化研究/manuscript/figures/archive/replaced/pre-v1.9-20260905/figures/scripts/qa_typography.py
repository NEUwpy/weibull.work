"""Check native SVG size, actual text size, and unchanged numerical source data."""
from pathlib import Path
import json, re, xml.etree.ElementTree as ET, unicodedata
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
NS = "{http://www.w3.org/2000/svg}"
records=[]
issues=[]
for p in sorted([*(ROOT / "main").glob("*.svg"), *(ROOT / "supplementary").glob("*.svg")]):
    root=ET.parse(p).getroot()
    width=float(root.attrib["width"].replace("pt", ""))*25.4/72
    height=float(root.attrib["height"].replace("pt", ""))*25.4/72
    ordinary=[]; math=[]; decorations=[]
    for e in root.iter():
        if e.tag not in (NS+"text", NS+"tspan"): continue
        content=(e.text or "").strip()
        if not content: continue
        match=re.search(r"font-size:\s*([0-9.]+)px", e.attrib.get("style", ""))
        if not match: continue
        size=float(match[1])
        if all(unicodedata.category(c).startswith("M") for c in content):
            decorations.append(size);continue
        (math if e.tag==NS+"tspan" else ordinary).append(size)
        minimum=6.0 if e.tag==NS+"tspan" else 8.6
        if size+1e-4<minimum: issues.append(f"{p.stem}: {content!r} at {size} pt")
    if width>190.1: issues.append(f"{p.stem}: width {width:.2f} mm")
    records.append(dict(figure=p.stem,width_mm=round(width,2),height_mm=round(height,2),
        normal_min_pt=min(ordinary) if ordinary else None,
        math_glyph_min_pt=min(math) if math else None,accent_font_sizes=sorted(set(decorations))))
old=ROOT/"archive/replaced/pre-font-standardization-20260905/figures/data/derived"
verified=[]
for p in sorted((ROOT/"data/derived").glob("*.csv")):
    if (old/p.name).exists():
        try: pd.testing.assert_frame_equal(pd.read_csv(p),pd.read_csv(old/p.name),check_exact=True)
        except AssertionError as e: issues.append(f"numerical data changed: {p.name}: {e}")
        else: verified.append(p.name)
report=dict(status="PASS" if not issues else "FAIL", native_size=True,figures=records,
    source_csvs_identical_to_snapshot=verified,issues=issues)
(ROOT/"provenance/typography_qa.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps(dict(status=report["status"],figures=len(records),unchanged_csvs=len(verified),issues=issues),ensure_ascii=False))
if issues: raise SystemExit(1)
