"""Pilot-only checks for the frozen Study/02 G3 protocol."""

from __future__ import annotations

from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import time
from typing import Any, Sequence

import numpy as np
import pandas as pd
import torch

from .admission import DECLARED_DOMAINS, audit_method
from .artifacts import append_ledger, write_manifest
from .config import FrozenConfig
from .design import generate_lifetime_sample, generate_parameter_points
from .models import build_mlp
from .representations import anchor_sample, build_features, encode_targets
from .training import fit_candidate


ROUTES = ["H0_hsm", "H0_kde_scott1024", "H1", "F0eq_hsm", "F0eq_kde_scott1024", "F1eq", "F2", "V", "S"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_gzip_csv(frame: pd.DataFrame, path: Path) -> None:
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            frame.to_csv(compressed, index=False, encoding="utf-8", lineterminator="\n")


def run_pilot(
    config: FrozenConfig,
    output_dir: Path,
    *,
    run_id: str,
    code_version: str,
    points: int,
    repeats: int,
    n_values: Sequence[int],
    run_methods: bool = True,
    train_smoke: bool = True,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Pilot output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    namespace = int(config.protocol["seeds"]["sample"]["pilot"])
    parameter_points = generate_parameter_points("pilot", "core", int(points), config)
    sample_rows: list[dict[str, Any]] = []
    feature_failures: list[dict[str, str]] = []
    samples: list[tuple[dict[str, Any], np.ndarray]] = []

    for point in parameter_points.to_dict("records"):
        for n in [int(value) for value in n_values]:
            for repeat_id in range(int(repeats)):
                spec = {**point, "n": n, "repeat_id": repeat_id}
                sample = generate_lifetime_sample(spec, namespace)
                samples.append((spec, sample))
                row = {
                    "point_id": point["point_id"], "beta": point["beta"], "eta": point["eta"],
                    "gamma": point["gamma"], "rho": point["rho"], "n": n, "repeat_id": repeat_id,
                    "sample_min": float(sample.min()), "sample_max": float(sample.max()),
                }
                for index, value in enumerate(sample, start=1):
                    row[f"x{index}"] = float(value)
                sample_rows.append(row)
                for route in ROUTES:
                    try:
                        features = build_features(route, sample, n)
                        if not np.isfinite(features).all():
                            raise ValueError("non-finite feature")
                    except Exception as error:
                        feature_failures.append({
                            "point_id": str(point["point_id"]), "n": str(n), "repeat_id": str(repeat_id),
                            "route": route, "error": f"{type(error).__name__}: {error}",
                        })

    sample_frame = pd.DataFrame(sample_rows)
    sample_path = output_dir / "pilot_samples.csv.gz"
    _write_gzip_csv(sample_frame, sample_path)
    pd.DataFrame(feature_failures, columns=["point_id", "n", "repeat_id", "route", "error"]).to_csv(
        output_dir / "feature_failures.csv", index=False, encoding="utf-8", lineterminator="\n"
    )

    admission_rows = []
    if run_methods:
        from studies.common.runner import run_method
        sample = samples[-1][1]
        cases = [{"case_id": "pilot-core", "sample": sample.tolist(), "in_declared_domain": True}]
        for method_id, domain in DECLARED_DOMAINS.items():
            result = audit_method(method_id, domain, cases, runner=run_method)
            admission_rows.append({
                "method_id": method_id,
                "admitted_core": result.admitted_core,
                "case_status": result.case_status["pilot-core"],
                "message": result.messages["pilot-core"],
            })
    pd.DataFrame(admission_rows, columns=["method_id", "admitted_core", "case_status", "message"]).to_csv(
        output_dir / "admission_report.csv", index=False, encoding="utf-8", lineterminator="\n"
    )

    smoke_seconds = None
    smoke_checkpoint = None
    if train_smoke:
        x_rows, y_rows, point_ids = [], [], []
        for spec, sample in samples:
            anchor = anchor_sample(sample)
            x_rows.append(build_features("F2", sample, int(spec["n"])))
            y_rows.append(encode_targets(spec["beta"], spec["eta"], spec["gamma"], anchor))
            point_ids.append(spec["point_id"])
        x = np.asarray(x_rows, dtype=np.float32)
        y = np.asarray(y_rows, dtype=np.float32)
        train_points = set(parameter_points["point_id"].iloc[: max(1, points // 2)])
        train_mask = np.array([point_id in train_points for point_id in point_ids])
        mean, sd = x[train_mask].mean(axis=0), x[train_mask].std(axis=0)
        sd[sd == 0] = 1.0
        x = (x - mean) / sd
        training_data = (torch.tensor(x[train_mask]), torch.tensor(y[train_mask]))
        validation_data = (torch.tensor(x[~train_mask]), torch.tensor(y[~train_mask]))
        start_fit = time.perf_counter()
        fit = fit_candidate(
            lambda: build_mlp(x.shape[1], (16, 8), "relu", 0.0),
            training_data, validation_data, seed=420001,
            max_epochs=12, min_epochs=4, patience=4, batch_size=64,
        )
        smoke_seconds = time.perf_counter() - start_fit
        smoke_checkpoint = fit.checkpoint_sha256

    disk = shutil.disk_usage(output_dir)
    formal_result_rows = 3 * 256 * 200 * len(config.protocol["sample_sizes"]["core"])
    assumed_compressed_bytes_per_result_row = 512
    assumed_checkpoint_bytes_per_fit = 2 * 1024 * 1024
    estimated_formal_artifact_bytes = 2 * (
        formal_result_rows * assumed_compressed_bytes_per_result_row
        + 820 * assumed_checkpoint_bytes_per_fit
    )
    estimate = {
        "matrix_fits": 820,
        "pilot_smoke_fit_seconds": smoke_seconds,
        "serial_fit_hours_from_smoke": (820 * smoke_seconds / 3600.0) if smoke_seconds else None,
        "disk_free_bytes": disk.free,
        "disk_80_percent_bytes": int(disk.free * 0.8),
        "pilot_output_bytes": sum(path.stat().st_size for path in output_dir.glob("*")),
        "estimated_formal_result_rows": formal_result_rows,
        "assumed_compressed_bytes_per_result_row": assumed_compressed_bytes_per_result_row,
        "assumed_checkpoint_bytes_per_fit": assumed_checkpoint_bytes_per_fit,
        "formal_storage_headroom_factor": 2,
        "estimated_formal_artifact_bytes": estimated_formal_artifact_bytes,
        "resource_gate_pass": estimated_formal_artifact_bytes < int(disk.free * 0.8),
        "formal_test_remains_sealed": True,
    }
    write_manifest(estimate, output_dir / "resource_estimate.json")
    completed = datetime.now(timezone.utc)
    log_lines = [
        f"run_id={run_id}", f"started_at={started.isoformat()}", f"completed_at={completed.isoformat()}",
        f"total_samples={len(sample_rows)}", f"feature_failures={len(feature_failures)}",
        f"method_rows={len(admission_rows)}", f"smoke_checkpoint={smoke_checkpoint}", "test_state=sealed",
    ]
    (output_dir / "run_log.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    output_files = sorted(path.name for path in output_dir.iterdir()) + ["manifest.json"]
    manifest = {
        "run_id": run_id, "artifact_type": "g3_pilot", "code_version": code_version,
        "protocol_sha256": config.protocol_sha256, "search_sha256": config.search_sha256,
        "seed_namespace": namespace, "points": int(points), "repeats": int(repeats),
        "n_values": [int(value) for value in n_values], "total_samples": len(sample_rows),
        "feature_failures": len(feature_failures), "test_state": "sealed", "output_files": output_files,
    }
    write_manifest(manifest, output_dir / "manifest.json")
    checksums = {path.name: _sha256(path) for path in output_dir.iterdir() if path.is_file()}
    if ledger_path is not None:
        append_ledger({
            "run_id": run_id, "command": "pilot", "started_at": started.isoformat(),
            "completed_at": completed.isoformat(), "exit_code": 0, "code_version": code_version,
            "protocol_sha256": config.protocol_sha256, "search_sha256": config.search_sha256,
            "seed_namespace": namespace, "output_path": str(output_dir), "checksums": checksums,
            "test_state": "sealed",
        }, ledger_path)
    return {**manifest, "resource_estimate": estimate, "checksums": checksums}
