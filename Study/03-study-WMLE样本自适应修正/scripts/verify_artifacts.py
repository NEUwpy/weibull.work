"""Validate data lineage, row accounting, diagnostics and local document links."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import platform
import re
import subprocess
import sys
import numpy as np
import pandas as pd

STUDY = Path(__file__).resolve().parents[1]
ROOT = STUDY.parents[1]
OUT = STUDY / "results/analysis_v1"


def main():
    d = pd.read_csv(OUT / "all_case_rows.csv")
    s = pd.read_csv(OUT / "cell_summary_all.csv")
    eq = pd.read_csv(OUT / "equation_diagnostics.csv")
    old = pd.read_csv(OUT / "historical_display_comparison.csv")
    sources = json.loads((STUDY / "evidence/source_manifest.json").read_text(encoding="utf-8"))
    for r in sources:
        assert hashlib.sha256((ROOT/r["source"]).read_bytes()).hexdigest() == r["sha256"]
        assert hashlib.sha256((STUDY/r["destination"]).read_bytes()).hexdigest() == r["sha256"]
    assert len(d) == 4500 and len(s) == 57 and len(eq) == len(d)
    assert int(d.valid.sum()) == 4356
    assert not d.duplicated(["cohort","beta","eta","gamma","sample_size","repeat_id"]).any()
    assert d.seed_namespace.notna().all()
    assert d.loc[~d.valid, ["e_beta","e_eta","e_gamma","E"]].isna().all().all()
    assert s.total.sum() == len(d) and s.valid.sum() == d.valid.sum()
    assert eq.loc[eq.valid, "fit_objective_recomputed"].max() <= 1e-8
    assert old.converged_display.eq(old.converged_replay).all()
    assert int(old.converged_display.sum()) == 818
    deltas = old[["beta_hat_delta","eta_hat_delta","gamma_hat_delta"]].abs().max()
    assert deltas.max() < 1e-8
    inventory = pd.read_csv(STUDY / "results/existing_cases_v1/source_inventory.csv")
    assert len(inventory) == 8 and inventory.groups.sum() == 850
    assert inventory.max_regeneration_delta.max() < 1e-8
    link_count = 0
    for p in [STUDY/"README.md", STUDY/"00-当前研究现状.md",
              STUDY/"01-原WMLE统计与机制分析.md", OUT/"统计报告.md"]:
        for target in re.findall(r"\]\(([^)]+)\)", p.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            assert (p.parent/target.split("#")[0]).exists(), (p, target)
            link_count += 1
    scripts = sorted((STUDY/"scripts").glob("*.py"))
    for p in scripts:
        compile(p.read_text(encoding="utf-8"),str(p),"exec")
    result = dict(status="passed", python=platform.python_version(),
                  packages={n:importlib.metadata.version(n) for n in
                            ["numpy","scipy","pandas","openpyxl","matplotlib"]},
                  rows=len(d), cells=len(s), valid=int(d.valid.sum()),
                  failed=int((~d.valid).sum()), verified_source_files=len(sources),
                  historical_display_matches=818,
                  historical_parameter_max_abs_delta=deltas.to_dict(),
                  max_sample_regeneration_delta=inventory.max_regeneration_delta.max(),
                  local_links_checked=link_count, compiled_scripts=len(scripts),
                  code_version=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
                  scripts=[dict(path=str(p.relative_to(STUDY)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in scripts],
                  limitations=["Formal J3 scan and neural training not executed.",
                               "Package snapshot requires the repository runtime.",
                               "Extra ignored dependency copies are outside the source manifest."])
    (OUT/"verification.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ["scripts","packages"]},ensure_ascii=False))


if __name__ == "__main__":
    # Create the linked artifact before validating its documentation link.
    OUT.mkdir(parents=True,exist_ok=True)
    p = OUT/"verification.json"
    if not p.exists():
        p.write_text('{"status":"pending"}',encoding="utf-8")
    main()
