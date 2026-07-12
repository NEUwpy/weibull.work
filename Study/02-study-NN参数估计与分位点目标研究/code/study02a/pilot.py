"""Pilot-only checks for the frozen Study/02 G3 protocol."""

from __future__ import annotations

from datetime import datetime, timezone
from concurrent.futures import ProcessPoolExecutor
import gzip
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import shutil
import time
from typing import Any, Sequence

import numpy as np
import pandas as pd
import torch

from .admission import DECLARED_DOMAINS, audit_method_contracts
from .artifacts import append_ledger, write_manifest
from .config import FrozenConfig
from .design import allocate_training_rows, generate_lifetime_sample, generate_parameter_points
from .models import build_mlp
from .representations import SetFeatures, anchor_sample, build_features, encode_targets
from .training import fit_candidate


ROUTES = ["H0_hsm", "H0_kde_scott1024", "H1", "F0eq_hsm", "F0eq_kde_scott1024", "F1eq", "F2", "V", "S"]


def _optimizer_batch_size(optimizer_id: str, unknown_batch_size: int) -> int:
    if optimizer_id == "adam_historical":
        return 32
    if optimizer_id == "o1":
        return 128
    if optimizer_id in {"stage1", "o2", "o3"}:
        return 512
    return int(unknown_batch_size)


def project_formal_runtime(
    matrix: pd.DataFrame,
    seconds_per_batch: dict[int, float],
    settings: dict[str, Any],
    *,
    effective_worker_factor: float | None = None,
) -> dict[str, Any]:
    """Conservatively extrapolate measured batch times over the sealed fit matrix."""

    unknown_size = int(settings["unknown_training_size"])
    max_epochs = int(settings["formal_max_epochs"])
    unknown_batch = int(settings["unknown_optimizer_batch_size"])
    total_seconds = 0.0
    total_updates = 0
    by_batch: dict[str, dict[str, float | int]] = {}
    for row in matrix.to_dict("records"):
        training_size = int(row["training_size"])
        if training_size < 0:
            training_size = unknown_size
        batch_size = _optimizer_batch_size(str(row["optimizer"]), unknown_batch)
        updates = math.ceil(training_size / batch_size) * max_epochs
        total_updates += updates
        elapsed = updates * float(seconds_per_batch[batch_size])
        total_seconds += elapsed
        bucket = by_batch.setdefault(str(batch_size), {"fits": 0, "updates": 0, "seconds": 0.0})
        bucket["fits"] = int(bucket["fits"]) + 1
        bucket["updates"] = int(bucket["updates"]) + updates
        bucket["seconds"] = float(bucket["seconds"]) + elapsed
    headroom = float(settings["runtime_headroom_factor"])
    projected_serial = total_seconds * headroom
    nominal_workers = int(settings.get("concurrency_workers", settings.get("parallel_workers", 1)))
    effective_workers = float(effective_worker_factor if effective_worker_factor is not None else nominal_workers)
    projected_wall = projected_serial / effective_workers
    limit_seconds = float(settings["wall_time_limit_hours"]) * 3600.0
    return {
        "measured_seconds_per_batch": {str(key): value for key, value in sorted(seconds_per_batch.items())},
        "projected_optimizer_updates": total_updates,
        "projection_by_batch_size": by_batch,
        "runtime_headroom_factor": headroom,
        "parallel_workers": nominal_workers,
        "effective_worker_factor": effective_workers,
        "projected_serial_seconds": projected_serial,
        "projected_wall_seconds": projected_wall,
        "wall_time_limit_seconds": limit_seconds,
        "runtime_gate_pass": projected_wall <= limit_seconds,
    }


def _timed_mlp_fit(payload: tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, Any], int, int]) -> float:
    train_x, train_y, validation_x, validation_y, settings, batch_size, epochs = payload
    torch.set_num_threads(int(settings.get("threads_per_worker", 1)))
    started = time.perf_counter()
    fit_candidate(
        lambda: build_mlp(train_x.shape[1], settings["widths"], str(settings["activation"]), 0.0),
        (torch.tensor(train_x), torch.tensor(train_y)),
        (torch.tensor(validation_x), torch.tensor(validation_y)),
        seed=int(settings["seed"]),
        max_epochs=int(epochs),
        min_epochs=int(epochs),
        patience=int(epochs),
        batch_size=int(batch_size),
    )
    return time.perf_counter() - started


def _benchmark_formal_batches(
    config: FrozenConfig,
    settings: dict[str, Any],
) -> tuple[dict[int, float], dict[str, Any], float]:
    rows = allocate_training_rows(
        "core_continuous",
        "fixed_n",
        int(settings["training_rows"]),
        config,
        fixed_n=int(settings["fixed_n"]),
    )
    namespace = int(config.protocol["seeds"]["sample"]["pilot"])
    x_rows: list[np.ndarray] = []
    y_rows: list[np.ndarray] = []
    for row in rows.to_dict("records"):
        sample = generate_lifetime_sample(row, namespace)
        anchor = anchor_sample(sample)
        x_rows.append(np.asarray(build_features("F2", sample, int(row["n"])), dtype=np.float32))
        y_rows.append(np.asarray(encode_targets(row["beta"], row["eta"], row["gamma"], anchor), dtype=np.float32))
    x = np.asarray(x_rows, dtype=np.float32)
    y = np.asarray(y_rows, dtype=np.float32)
    split = int(len(x) * (1.0 - float(settings["validation_fraction"])))
    train_x, validation_x = x[:split], x[split:]
    train_y, validation_y = y[:split], y[split:]
    mean, sd = train_x.mean(axis=0), train_x.std(axis=0)
    sd[sd == 0] = 1.0
    train_x = np.asarray((train_x - mean) / sd, dtype=np.float32)
    validation_x = np.asarray((validation_x - mean) / sd, dtype=np.float32)
    train_y = np.asarray(train_y, dtype=np.float32)
    validation_y = np.asarray(validation_y, dtype=np.float32)
    base_payload = (train_x, train_y, validation_x, validation_y, settings)
    epochs = int(settings["epochs"])
    batch_sizes = [int(value) for value in settings["batch_sizes"]]
    for batch_size in batch_sizes:
        _timed_mlp_fit((*base_payload, batch_size, int(settings["warmup_epochs"])))

    measurements: dict[int, list[float]] = {batch_size: [] for batch_size in batch_sizes}
    orders = settings["measurement_orders"]
    if len(orders) != int(settings["measured_repetitions"]):
        raise ValueError("measurement_orders must match measured_repetitions")
    for order in orders:
        if sorted(map(int, order)) != sorted(batch_sizes):
            raise ValueError("each measurement order must contain every frozen batch size exactly once")
        for batch_size in map(int, order):
            elapsed = _timed_mlp_fit((*base_payload, batch_size, epochs))
            measurements[batch_size].append(elapsed / (epochs * math.ceil(len(train_x) / batch_size)))
    measured = {batch_size: float(np.median(values)) for batch_size, values in measurements.items()}

    workers = int(settings["concurrency_workers"])
    concurrency_batch = int(settings["concurrency_batch_size"])
    concurrency_epochs = int(settings["concurrency_epochs"])
    concurrency_payload = (*base_payload, concurrency_batch, concurrency_epochs)
    single_reference = measured[concurrency_batch] * concurrency_epochs * math.ceil(len(train_x) / concurrency_batch)
    speedups: list[float] = []
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as executor:
        warmups = [executor.submit(_timed_mlp_fit, concurrency_payload) for _ in range(int(settings["concurrency_warmup_tasks"]))]
        for future in warmups:
            future.result()
        for _ in range(int(settings["concurrency_repetitions"])):
            started = time.perf_counter()
            futures = [executor.submit(_timed_mlp_fit, concurrency_payload) for _ in range(workers)]
            for future in futures:
                future.result()
            wall = time.perf_counter() - started
            speedups.append(min(float(workers), workers * single_reference / wall))
    effective_workers = float(np.quantile(speedups, 0.25, method="linear"))
    details = {
        "warmup_epochs": int(settings["warmup_epochs"]),
        "measured_repetitions": int(settings["measured_repetitions"]),
        "measurement_orders": orders,
        "seconds_per_batch_repetitions": {str(key): value for key, value in measurements.items()},
        "batch_time_aggregate": "median",
        "concurrency_workers": workers,
        "concurrency_speedup_repetitions": speedups,
        "effective_worker_aggregate": "q25",
        "effective_worker_factor": effective_workers,
    }
    return measured, details, effective_workers


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
    pilot_amendment: dict[str, Any] | None = None,
    matrix_path: Path | None = None,
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
                        if isinstance(features, SetFeatures):
                            if not np.isfinite(features.values).all() or features.mask.shape != (n,) or features.n != n:
                                raise ValueError("invalid set feature contract")
                        elif not np.isfinite(features).all():
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
        admission_settings = (pilot_amendment or {}).get("admission", {})
        for method_id, domain in DECLARED_DOMAINS.items():
            result = audit_method_contracts(
                method_id,
                domain,
                sample.tolist(),
                runner=run_method,
                deterministic_rtol=float(admission_settings.get("deterministic_rtol", 1e-12)),
                equivariance_rtol=float(admission_settings.get("equivariance_rtol", 1e-3)),
                scale_factor=float(admission_settings.get("scale_factor", 1000.0)),
            )
            for contract_id, status in result.case_status.items():
                admission_rows.append({
                    "method_id": method_id,
                    "admitted_core": result.admitted_core,
                    "contract_id": contract_id,
                    "case_status": status,
                    "residual": result.residuals.get(contract_id),
                    "message": result.messages[contract_id],
                })
    pd.DataFrame(admission_rows, columns=["method_id", "admitted_core", "contract_id", "case_status", "residual", "message"]).to_csv(
        output_dir / "admission_report.csv", index=False, encoding="utf-8", lineterminator="\n"
    )

    smoke_seconds = None
    smoke_checkpoint = None
    runtime_projection = None
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

        if pilot_amendment is not None and matrix_path is not None:
            runtime_settings = dict(pilot_amendment["runtime_benchmark"])
            measured, benchmark_details, effective_workers = _benchmark_formal_batches(config, runtime_settings)
            runtime_projection = project_formal_runtime(
                pd.read_csv(matrix_path), measured, runtime_settings,
                effective_worker_factor=effective_workers,
            )
            runtime_projection["benchmark_details"] = benchmark_details

    disk = shutil.disk_usage(output_dir)
    formal_result_rows = 3 * 256 * 200 * len(config.protocol["sample_sizes"]["core"])
    storage_settings = (pilot_amendment or {}).get("storage_gate", {})
    assumed_compressed_bytes_per_result_row = int(storage_settings.get("assumed_compressed_bytes_per_result_row", 512))
    assumed_checkpoint_bytes_per_fit = int(storage_settings.get("assumed_checkpoint_bytes_per_fit", 2 * 1024 * 1024))
    storage_headroom = float(storage_settings.get("headroom_factor", 2.0))
    estimated_formal_artifact_bytes = storage_headroom * (
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
        "formal_storage_headroom_factor": storage_headroom,
        "estimated_formal_artifact_bytes": int(estimated_formal_artifact_bytes),
        "storage_gate_pass": estimated_formal_artifact_bytes < int(disk.free * float(storage_settings.get("max_fraction_of_current_free_disk", 0.8))),
        "runtime_projection": runtime_projection,
        "runtime_gate_pass": runtime_projection["runtime_gate_pass"] if runtime_projection else None,
        "resource_gate_pass": bool(
            estimated_formal_artifact_bytes < int(disk.free * float(storage_settings.get("max_fraction_of_current_free_disk", 0.8)))
            and (runtime_projection is None or runtime_projection["runtime_gate_pass"])
        ),
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
