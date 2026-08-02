"""Unified checkpoint index for P / D / Dctrl across existing + incremental n.

Existing P checkpoints come from the approved A-E1 run (read-only); existing
D/Dctrl checkpoints from the approved B3 run (read-only). New checkpoints are
written by study02b_inc.train_inc into the current run directory and registered
here by run-id. Loading uses the canonical study02a checkpoint codec so hashes
are stable.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch

_STUDY_CODE = Path(__file__).resolve().parent.parent
if str(_STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(_STUDY_CODE))

from study02a.models import build_mlp
from study02a.training import load_checkpoint
from study02b.training import build_d_mlp

from study02b_inc import a_data as A
from study02b_inc import config as C


def _git_tip() -> str:
    import subprocess
    r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                       cwd=str(C.REPO_ROOT), timeout=5)
    return r.stdout.strip() or "unknown"


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def build_p_index(run_dir: Path | None = None) -> dict[int, list[dict]]:
    """n -> [{seed, path, sha256}] for P checkpoints (existing + incremental)."""
    index: dict[int, list[dict]] = {}

    # Existing A-E1 winner-retrain checkpoints (read-only)
    plan = {}
    if C.P_PLAN_PATH.exists():
        with open(C.P_PLAN_PATH, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    if row.get("fit_id"):
                        plan[row["fit_id"]] = row
    for fit_num in range(299, 349):
        fid = f"G3-fit-{fit_num:04d}"
        row = plan.get(fid)
        if row is None:
            continue
        n = row.get("fixed_n")
        seed = row.get("seed")
        if n is None or seed is None:
            continue
        ckpt = C.P_OUTPUTS / fid / "checkpoint.pt"
        if not ckpt.exists():
            continue
        index.setdefault(int(n), []).append({
            "seed": int(seed), "path": str(ckpt),
            "sha256": _sha256_bytes(ckpt.read_bytes()), "source": "A-E1",
        })

    # Incremental P checkpoints in the run dir
    if run_dir is not None:
        train_manifest = Path(run_dir) / "training" / "manifest.json"
        if train_manifest.exists():
            tm = json.loads(train_manifest.read_text(encoding="utf-8"))
            for e in tm.get("checkpoints", []):
                if e.get("route") != "P":
                    continue
                index.setdefault(int(e["n"]), []).append({
                    "seed": int(e["seed"]), "path": e["checkpoint_path"],
                    "sha256": e["checkpoint_sha256"], "source": "inc",
                })
    return index


def build_d_index(run_dir: Path, extra_run_dirs: list[Path] | None = None) -> dict[int, dict[str, list[dict]]]:
    """n -> {selected/controlled: [checkpoint records]} for D checkpoints.

    Reads B3 (5 existing n) + the current run's training manifest + any
    superseded run dirs whose D/Dctrl are reused (their P is invalid, but the
    D/Dctrl checkpoints are unchanged and reused read-only).
    """
    index: dict[int, dict[str, list[dict]]] = {}

    # Existing B3 checkpoints
    if C.B3_MANIFEST_PATH.exists():
        b3 = json.loads(C.B3_MANIFEST_PATH.read_text(encoding="utf-8"))
        for e in b3["d_checkpoints"]:
            n = int(e["n"])
            group = "selected" if e["group"] == "selected" else "controlled"
            index.setdefault(n, {}).setdefault(group, []).append({
                "seed": int(e["seed"]), "path": e["path"],
                "sha256": e["sha256"], "widths": e["widths"], "source": "B3",
            })

    def _merge_manifest(run: Path, source: str):
        train_manifest = run / "training" / "manifest.json"
        if not train_manifest.exists():
            return
        tm = json.loads(train_manifest.read_text(encoding="utf-8"))
        for e in tm.get("checkpoints", []):
            if e.get("route") not in ("D", "Dctrl"):
                continue
            n = int(e["n"])
            group = e["group"]
            index.setdefault(n, {}).setdefault(group, []).append({
                "seed": int(e["seed"]), "path": e.get("checkpoint_path", e.get("path")),
                "sha256": e.get("checkpoint_sha256", e.get("sha256")),
                "widths": e["widths"], "source": source,
            })

    _merge_manifest(run_dir, "inc")
    for extra in (extra_run_dirs or []):
        _merge_manifest(extra, "superseded-reuse")
    return index


def d_target_stats(run_dir: Path, extra_run_dirs: list[Path] | None = None) -> dict[int, dict]:
    """n -> {mean, sd} D target stats (B3, current run, superseded runs)."""
    stats: dict[int, dict] = {}
    if C.B3_MANIFEST_PATH.exists():
        b3 = json.loads(C.B3_MANIFEST_PATH.read_text(encoding="utf-8"))
        for n_str, s in b3.get("target_stats", {}).items():
            stats[int(n_str)] = {"mean": s["mean"], "sd": s["sd"], "source": "B3"}
    for run in [run_dir] + list(extra_run_dirs or []):
        train_manifest = run / "training" / "manifest.json"
        if not train_manifest.exists():
            continue
        tm = json.loads(train_manifest.read_text(encoding="utf-8"))
        src = "inc" if run == run_dir else "superseded-reuse"
        for n_str, s in tm.get("target_stats", {}).items():
            stats[int(n_str)] = {"mean": s["mean"], "sd": s["sd"], "source": src}
    return stats


def p_scalers(run_dir: Path) -> dict[int, dict]:
    """n -> {mean, sd} P input scaler (A-E1 cache for existing, inc manifest for new).

    Existing n reconstruct the A-E1 training scaler from the frozen cache;
    missing n read the scaler stored by the incremental training manifest.
    """
    scalers: dict[int, dict] = {}
    for n in C.N_EXISTING:
        try:
            scalers[n] = A.a_p_scaler_from_cache(n)
        except KeyError:
            continue
    train_manifest = run_dir / "training" / "manifest.json"
    if train_manifest.exists():
        tm = json.loads(train_manifest.read_text(encoding="utf-8"))
        for n_str, s in tm.get("p_scalers", {}).items():
            scalers[int(n_str)] = s
    return scalers


def load_model(route: str, n: int, seed: int, record: dict) -> torch.nn.Module:
    if route == "P":
        m = build_mlp(int(n), C.P_WIDTHS, C.ACTIVATION, C.DROPOUT)
    else:
        widths = record.get("widths") or (
            C.DCTRL_WIDTHS if route == "Dctrl" else C.D_SELECTED_WIDTHS
        )
        m = build_d_mlp(int(n), widths, C.ACTIVATION, C.DROPOUT)
    state = load_checkpoint(Path(record["path"]).read_bytes())
    m.load_state_dict(state)
    m.eval()
    return m


def verify_p_index_sha256(entries: list[dict]) -> str:
    """Aggregate fingerprint of a P checkpoint list."""
    payload = "\n".join(sorted(f"{e['seed']}:{e['sha256']}" for e in entries))
    return hashlib.sha256(payload.encode()).hexdigest()
