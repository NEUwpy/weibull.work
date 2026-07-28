"""P2 MC data generation with checkpoint/resume at combo level.

Generates 39 combos x 26 deltas x 1000 repeats = 1,014,000 MDM estimates.
Output: artifacts/formal/extended_validation/p2_generalization/

Usage:
    python run_p2_generate.py          # full run (checkpoint/resume)
    python run_p2_generate.py --status # show progress
"""

import os, sys, csv, json, time, argparse, hashlib
from pathlib import Path
from datetime import datetime, timezone
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r"D:\weibull\python")

from p2_config import (
    build_p2_combos, P2_TOTAL_COMBOS, P2_NI_COMBOS, P2_PI_COMBOS,
    DELTA_GRID, REPEATS, SEED_NAMESPACE, ETA, OUTPUT_DIR_NAME,
    DEFAULT_DELTA, L1_DELTA,
)
from config import STUDY_ROOT

from methods.mdm import MDM
from studies.common.sample import generate_sample

# Output directory
P2_DIR = Path(STUDY_ROOT) / "artifacts" / "formal" / OUTPUT_DIR_NAME
CHUNKS_DIR = P2_DIR / "chunks"
PROGRESS_PATH = P2_DIR / "progress.json"
MANIFEST_PATH = P2_DIR / "manifest.json"

MDM_FIELDS = [
    "track", "beta", "eta", "gamma", "gamma_over_eta", "n", "repeat_id", "delta",
    "beta_hat", "eta_hat", "gamma_hat", "r_squared", "converged",
    "time_ms", "status",
]


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run_one_sample(beta, ge, n, repeat_id, eta=ETA):
    """Run MDM on one sample across all 26 deltas. Returns list of dict rows."""
    gamma = ge * eta
    seed_int = _derive_seed(beta, ge, n, repeat_id)
    sample = generate_sample(beta=beta, eta=eta, gamma=gamma, n=n,
                              repeat_id=repeat_id, seed=seed_int)

    rows = []
    for delta in DELTA_GRID:
        t0 = time.perf_counter()
        try:
            estimator = MDM(sample.tolist())
            result = estimator.run(trace=False, offset=delta)
            bh, eh, gh, r2 = float(result[0]), float(result[1]), float(result[2]), float(result[3])
            conv = bool(result[4]) if len(result) > 4 else True
            elapsed = (time.perf_counter() - t0) * 1000
            ok_val = (np.isfinite(bh) and np.isfinite(eh) and np.isfinite(gh)
                      and bh > 0 and eh > 0 and gh < np.min(sample) and conv)
            rows.append({
                "beta": beta, "eta": eta, "gamma": gamma, "gamma_over_eta": ge,
                "n": n, "repeat_id": repeat_id, "delta": delta,
                "beta_hat": bh, "eta_hat": eh, "gamma_hat": gh,
                "r_squared": r2, "converged": conv,
                "time_ms": round(elapsed, 3), "status": "ok" if ok_val else "fail",
            })
        except Exception:
            elapsed = (time.perf_counter() - t0) * 1000
            rows.append({
                "beta": beta, "eta": eta, "gamma": gamma, "gamma_over_eta": ge,
                "n": n, "repeat_id": repeat_id, "delta": delta,
                "beta_hat": np.nan, "eta_hat": np.nan, "gamma_hat": np.nan,
                "r_squared": np.nan, "converged": False,
                "time_ms": round(elapsed, 3), "status": "error",
            })
    return rows


def _combo_id(track, beta, ge, n):
    return f"{track}_{beta:.2f}_{ge:.2f}_{n}"


def _chunk_path(track, beta, ge, n):
    fn = f"{_combo_id(track, beta, ge, n)}.csv"
    return CHUNKS_DIR / fn


import hashlib as _hashlib

def _derive_seed(beta, ge, n, repeat_id):
    """Deterministic seed from combo key + repeat_id using SHA-256."""
    key = f"{SEED_NAMESPACE}:{beta:.6f}:{ge:.6f}:{n}:{repeat_id}"
    digest = _hashlib.sha256(key.encode()).digest()
    return int.from_bytes(digest[:4], "big")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_generation():
    """Main generation loop with checkpoint/resume."""
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    combos = build_p2_combos()

    # Load progress
    completed = set()
    if PROGRESS_PATH.is_file():
        progress = json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
        completed = set(progress.get("completed_combo_ids", []))

    total = P2_TOTAL_COMBOS
    done_count = len(completed)
    print(f"P2 Generation: {done_count}/{total} combos completed, "
          f"{total - done_count} remaining")

    t_start = time.time()
    new_completed = 0

    for track, beta, ge, n in combos:
        cid = _combo_id(track, beta, ge, n)
        if cid in completed:
            continue

        chunk_path = _chunk_path(track, beta, ge, n)
        if chunk_path.is_file():
            completed.add(cid)
            continue

        print(f"  [{new_completed + 1}/{total - done_count}] {cid}")
        gamma = ge * ETA
        all_rows = []
        for repeat_id in range(REPEATS):
            rows = _run_one_sample(beta, ge, n, repeat_id)
            for r in rows:
                r["track"] = track
            all_rows.extend(rows)

        chunk_path.parent.mkdir(parents=True, exist_ok=True)
        with open(chunk_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=MDM_FIELDS)
            writer.writeheader()
            writer.writerows(all_rows)

        completed.add(cid)
        new_completed += 1

        # Save progress after each combo
        progress = {
            "completed_combo_ids": sorted(completed),
            "total_combos": total,
            "updated_at": _now_iso(),
        }
        PROGRESS_PATH.write_text(json.dumps(progress, ensure_ascii=False, indent=2),
                                  encoding="utf-8")

    elapsed = time.time() - t_start
    print(f"P2 Generation complete: {len(completed)}/{total} combos, "
          f"{new_completed} new in {elapsed:.0f}s")


def _git_sha():
    import subprocess
    result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                            text=True, cwd=STUDY_ROOT)
    return result.stdout.strip()


def write_manifest():
    """Write manifest after generation is complete."""
    combos = build_p2_combos()
    # Verify all chunks exist
    missing = []
    for track, beta, ge, n in combos:
        cp = _chunk_path(track, beta, ge, n)
        if not cp.is_file():
            missing.append(_combo_id(track, beta, ge, n))
    if missing:
        print(f"WARNING: {len(missing)} chunks missing, manifest incomplete")
        for m in missing:
            print(f"  {m}")
        return

    manifest = {
        "manifest_version": "study01-p2-generation-v1",
        "run_id": "P2_mc_generation_v1",
        "code_commit": _git_sha(),
        "created_at": _now_iso(),
        "combo_counts": {"P2-NI": P2_NI_COMBOS, "P2-PI": P2_PI_COMBOS,
                         "total": P2_TOTAL_COMBOS},
        "repeats_per_combo": REPEATS,
        "delta_grid": DELTA_GRID,
        "eta": ETA,
        "seed_namespace": SEED_NAMESPACE,
        "mdm_python_file": "python/methods/mdm.py",
        "output_dir": str(P2_DIR),
        "combo_ids": sorted(_combo_id(t, b, g, n) for t, b, g, n in combos),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"Manifest written: {MANIFEST_PATH}")


def write_sha256sums():
    """Write SHA256SUMS for all chunk files."""
    if not MANIFEST_PATH.is_file():
        print("Manifest not found, skipping SHA256SUMS")
        return
    sums_path = P2_DIR / "SHA256SUMS"
    lines = []
    for track, beta, ge, n in build_p2_combos():
        cp = _chunk_path(track, beta, ge, n)
        if cp.is_file():
            sha = _sha256_file(cp)
            lines.append(f"{sha}  {cp.relative_to(P2_DIR.parent).as_posix()}")
    # Also hash manifest and progress
    for extra in [MANIFEST_PATH, PROGRESS_PATH]:
        if extra.is_file():
            sha = _sha256_file(extra)
            lines.append(f"{sha}  {extra.relative_to(P2_DIR.parent).as_posix()}")
    lines.sort()
    sums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"SHA256SUMS written: {sums_path}")


def status():
    """Show generation progress."""
    combos = build_p2_combos()
    done = sum(1 for t, b, g, n in combos if _chunk_path(t, b, g, n).is_file())
    for track in ["P2-NI", "P2-PI"]:
        td = sum(1 for t, b, g, n in combos if t == track
                 and _chunk_path(t, b, g, n).is_file())
        tc = sum(1 for t, b, g, n in combos if t == track)
        print(f"  {track}: {td}/{tc}")
    print(f"  Total: {done}/{P2_TOTAL_COMBOS}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--manifest", action="store_true")
    parser.add_argument("--sha256sums", action="store_true")
    args = parser.parse_args()

    if args.status:
        status()
    elif args.manifest:
        write_manifest()
    elif args.sha256sums:
        write_sha256sums()
    else:
        run_generation()
        write_manifest()
        write_sha256sums()
