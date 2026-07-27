"""Study01 P0-P1 final REVISE v4: fail-closed integrity, separate evidence gaps."""
import json, hashlib, sys, warnings
from pathlib import Path
import pandas as pd, numpy as np

warnings.filterwarnings("ignore", category=pd.errors.DtypeWarning)

STUDY_CODE = Path(__file__).resolve().parents[1] / "Study" / "01-study-MDM最小偏移量优化研究" / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))
from gen_labels import classify_generalization

ARTIFACT = Path("Study/01-study-MDM最小偏移量优化研究/artifacts/formal")
E4 = ARTIFACT / "E4_robustness"
EXIT = 0


def integrity_fail(msg):
    global EXIT
    print(f"  INTEGRITY FAIL: {msg}")
    EXIT = 1


def evidence_gap(msg):
    print(f"  EVIDENCE GAP: {msg}")


def ok(msg):
    print(f"  OK: {msg}")


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_sums(sums_path, expected_count, resolve_dir=None):
    """Verify SHA256SUMS file. resolve_dir: dir for relative paths."""
    if not sums_path.is_file():
        integrity_fail(f"{sums_path.name} missing")
        return
    resolve_dir = resolve_dir if resolve_dir is not None else sums_path.parent
    raw = sums_path.read_text(encoding="utf-8").strip()
    entries = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            integrity_fail(f"{sums_path.name} malformed: {line[:80]}")
            continue
        entries.append((parts[0], parts[1]))
    if len(entries) != expected_count:
        integrity_fail(f"{sums_path.name}: {len(entries)} entries (expected {expected_count})")
    seen = set()
    verified = 0
    for sha, rel in entries:
        if rel in seen:
            integrity_fail(f"{sums_path.name} duplicate: {rel}")
            continue
        seen.add(rel)
        fp = resolve_dir / rel
        if not fp.is_file():
            integrity_fail(f"{sums_path.name} file missing: {fp}")
            continue
        if _sha256(fp) != sha:
            integrity_fail(f"{sums_path.name} SHA mismatch: {rel}")
        else:
            verified += 1
    if verified == expected_count:
        ok(f"{sums_path.name}: {verified}/{expected_count} verified")


# ============================================================
print("=== P0.1 Manifest SHA256 ===")
for path in sorted(ARTIFACT.rglob("manifest*.json"), key=lambda p: str(p)):
    print(f"  {path.relative_to(ARTIFACT)}: {_sha256(path)}")

# ============================================================
print("\n=== P0.2 E4d data integrity ===")
m = json.loads((E4 / "manifest_e4d.json").read_text(encoding="utf-8"))
prov = m.get("output_provenance", {})

e4d_raw = pd.read_csv(E4 / "E4d_selector_extrapolation.csv", dtype=str)
e4d_raw["beta_f"] = e4d_raw["beta"].astype(float)
e4d_raw["ge_f"] = e4d_raw["gamma_over_eta"].astype(float)
e4d_raw["n_int"] = e4d_raw["n"].astype(int)
e4d_raw["repeat_id_int"] = e4d_raw["repeat_id"].astype(int)

is_nn = e4d_raw["fold"].notna() & (e4d_raw["fold"] != "") & (e4d_raw["fold"] != "nan")
e4d_nn = e4d_raw[is_nn].copy()
e4d_nn["fold_int"] = e4d_nn["fold"].apply(lambda x: int(x.split("_")[-1]) - 1 if "_" in x else int(float(x)))
e4d_nn["seed_int"] = e4d_nn["seed"].apply(lambda x: int(float(x)))
print(f"  Total: {len(e4d_raw)}, NN: {len(e4d_nn)}, Ref: {len(e4d_raw)-len(e4d_nn)}")

# P0.2a Sample keys
print("\n--- P0.2a: Sample keys ---")
basic = e4d_nn.groupby(["beta_f", "ge_f", "n_int", "repeat_id_int"]).size()
if len(basic) == 17000 and (basic == 15).all():
    ok("17,000 basic keys, each exactly 15 models")
else:
    integrity_fail(f"basic keys: {len(basic)} (exp 17000), all15={(basic==15).all()}")
full = e4d_nn.groupby(["beta_f","ge_f","n_int","repeat_id_int","fold_int","seed_int"]).size()
if len(full) == 255000 and (full == 1).all():
    ok("255,000 full keys, all unique")
else:
    integrity_fail(f"full keys: {len(full)} (exp 255000)")

# P0.2b Models
print("\n--- P0.2b: Models ---")
if len(e4d_nn.groupby(["fold_int","seed_int"]).size()) == 15:
    ok("15 models (5 folds x 3 seeds)")
else:
    integrity_fail("not 15 models")
ref_set = set(zip(
    e4d_nn[(e4d_nn["fold_int"]==0)&(e4d_nn["seed_int"]==42)]["beta_f"],
    e4d_nn[(e4d_nn["fold_int"]==0)&(e4d_nn["seed_int"]==42)]["ge_f"],
    e4d_nn[(e4d_nn["fold_int"]==0)&(e4d_nn["seed_int"]==42)]["n_int"],
    e4d_nn[(e4d_nn["fold_int"]==0)&(e4d_nn["seed_int"]==42)]["repeat_id_int"],
))
ok_flag = True
for (f,s), gd in e4d_nn.groupby(["fold_int","seed_int"]):
    if set(zip(gd["beta_f"],gd["ge_f"],gd["n_int"],gd["repeat_id_int"])) != ref_set:
        integrity_fail(f"fold={f} seed={s}: key set differs")
        ok_flag = False
if ok_flag:
    ok("all 15 models share identical key set")

# P0.2c provenance
print("\n--- P0.2c: output_provenance ---")
n = 0
for rel_path, entry in prov.items():
    exp = entry["sha256"] if isinstance(entry, dict) else str(entry)
    fp = Path(rel_path)
    if not fp.is_file():
        integrity_fail(f"provenance missing: {rel_path}")
        continue
    if _sha256(fp) != exp:
        integrity_fail(f"provenance SHA mismatch: {rel_path}")
    else:
        n += 1
if n == len(prov):
    ok(f"output_provenance: {n} files all match")

# P0.2d SHA256SUMS
print("\n--- P0.2d: SHA256SUMS_e4d ---")
_verify_sums(E4 / "SHA256SUMS_e4d", 7, resolve_dir=Path("."))

# P0.2e Split
print("\n--- P0.2e: Split existence ---")
sp = E4 / "split_report.csv"
if not sp.is_file():
    integrity_fail("split_report.csv missing")
else:
    split = pd.read_csv(sp)
    if len(split["fold"].unique()) == 5:
        ok("split_report exists with 5 folds")
    else:
        integrity_fail(f"split has {len(split['fold'].unique())} folds")

# ============================================================
print("\n=== P0.3 E3b gate recursive ===")
gate = json.loads((E4 / "E4d_e3b_gate_results.json").read_text(encoding="utf-8"))
gate_ok = True


def check_gate(obj, prefix="gate"):
    global gate_ok
    if isinstance(obj, dict):
        for k in ("pass", "overall_pass"):
            if k in obj:
                if obj[k] is not True:
                    integrity_fail(f"{prefix}.{k}: {obj[k]}")
                    gate_ok = False
                else:
                    print(f"  {prefix}.{k}: True")
        for k, v in obj.items():
            if k in ("pass", "overall_pass"):
                continue
            check_gate(v, f"{prefix}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            check_gate(v, f"{prefix}[{i}]")


check_gate(gate)
if gate_ok:
    ok("E3b gate: all sub-checks PASS")

# ============================================================
print("\n=== P0.4 E3b mandatory files ===")
for fn in ["manifest.json", "summary.json", "vector_mlp_results.csv"]:
    if (ARTIFACT / "E3b_vector_mlp" / fn).is_file():
        ok(f"{fn}: found")
    else:
        integrity_fail(f"{fn}: MISSING")

# ============================================================
print("\n=== P0.5 P8 NIST ===")
p8d = ARTIFACT / "real_data" / "nist-6061-t6-fatigue"
p8m = json.loads((p8d / "real_data_manifest.json").read_text(encoding="utf-8"))
for fn in ["real_data_manifest.json", "real_holdout_results.csv", "real_holdout_summary.json"]:
    if (p8d / fn).is_file():
        ok(f"{fn}: found")
    else:
        integrity_fail(f"{fn}: MISSING")

_verify_sums(p8d / "SHA256SUMS_p8a", 5, resolve_dir=p8d)

hr = pd.read_csv(p8d / "real_holdout_results.csv", dtype=str)
if len(hr) == p8m.get("expected_rows", 25500):
    ok(f"holdout rows: {len(hr)}")
else:
    integrity_fail(f"rows: {len(hr)} exp {p8m.get('expected_rows',25500)}")

gp = p8m.get("gate_passed", p8m.get("gate", {}).get("passed"))
if gp is True:
    ok("P8 gate_passed: True")
else:
    integrity_fail(f"gate_passed: {gp}")

# ============================================================
print("\n=== P1. Classification ===")
labels = []
for _, row in e4d_nn.iterrows():
    ps, ns = classify_generalization(row["beta_f"], row["ge_f"], int(row["n_int"]))
    labels.append(f"p_{ps}_n_{ns}")
e4d_nn["compound"] = labels
for lb, cnt in e4d_nn.groupby("compound").size().sort_values(ascending=False).items():
    print(f"  {lb}: {cnt:>8,} ({cnt/len(e4d_nn)*100:.1f}%)")

pure = {"pure_p_interp":"p_interp_n_on_grid","pure_n_interp":"p_on_grid_n_interp",
        "pure_p_extrap":"p_extrap_n_on_grid","pure_n_extrap":"p_on_grid_n_extrap"}
print("\n  Pure axis coverage:")
for desc, label in pure.items():
    ld = e4d_nn[e4d_nn["compound"] == label]
    nc = len(ld.groupby(["beta_f","ge_f","n_int"])) if len(ld)>0 else 0
    print(f"    {desc}: {len(ld):,} rows, {nc} combos")
    if len(ld) == 0:
        evidence_gap(f"{desc}: ZERO coverage (P2 required)")

n15 = e4d_nn[e4d_nn["n_int"] == 15]
if len(n15[n15["compound"] == "p_on_grid_n_interp"]) == 0:
    ok("confirmed: n=15 has ZERO pure n_interp")

# P1 per-model J1
print("\n=== P1. 15-model per-axis J1 ===")
for lb in sorted(e4d_nn["compound"].unique()):
    ld = e4d_nn[e4d_nn["compound"] == lb]
    if len(ld) == 0:
        continue
    j1s = [float(np.sqrt(np.mean(gd["true_loss"].astype(float)))) for (_,_), gd in ld.groupby(["fold_int","seed_int"])]
    a = np.array(j1s)
    print(f"  {lb} ({len(ld):,}): med={np.median(a):.4f} Q1={np.percentile(a,25):.4f} Q3={np.percentile(a,75):.4f}")

# P1 Default/L1 paired
print("\n=== P1. Default/L1 paired (tol=0.001 descriptive) ===")
ref = pd.concat([pd.read_csv(E4 / "E4b_boundary_reference.csv"),
                 pd.read_csv(E4 / "E4c_offgrid_reference.csv")], ignore_index=True)
ref["tl_f"] = ref["true_loss"].astype(float)
ref["beta_f"] = ref["beta"].astype(float)
ref["ge_f"] = ref["gamma_over_eta"].astype(float)
ref["n_int"] = ref["n"].astype(int)
ref["repeat_id_int"] = ref["repeat_id"].astype(int)
TOL = 0.001

for lb in sorted(e4d_nn["compound"].unique()):
    ld = e4d_nn[e4d_nn["compound"] == lb]
    for rm in ["Default", "L1"]:
        rd = ref[ref["model"] == rm]
        mrg = pd.merge(
            ld[["beta_f","ge_f","n_int","repeat_id_int","true_loss","fold_int","seed_int"]],
            rd[["beta_f","ge_f","n_int","repeat_id_int","tl_f"]],
            on=["beta_f","ge_f","n_int","repeat_id_int"])
        if len(mrg) == 0:
            continue
        w = l = t = 0
        for (f,s), md in mrg.groupby(["fold_int","seed_int"]):
            d = float(np.sqrt(np.mean(md["true_loss"].astype(float)))) - float(np.sqrt(np.mean(md["tl_f"].astype(float))))
            if d < -TOL: w += 1
            elif d > TOL: l += 1
            else: t += 1
        print(f"  {lb} vs {rm}: {w}W/{l}L/{t}T")

# ============================================================
print(f"\n{'='*40}")
if EXIT == 0:
    print("P0_INTEGRITY: PASS")
    print("P1_EVIDENCE: GAP_REQUIRES_P2 (pure_n_interp = 0)")
    print("Exiting 0")
else:
    print(f"P0_INTEGRITY: {EXIT} FAILURE(S)")
print(f"{'='*40}")
raise SystemExit(EXIT)
