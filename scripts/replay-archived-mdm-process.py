"""Export calculation points missing from a registered Research00 MDM archive."""

import argparse
import hashlib
import importlib
import inspect
import json
import sys
from pathlib import Path

import numpy as np


def read_verified(root, manifest, relative):
    raw = (root / relative).read_bytes()
    record = manifest["files"][relative]
    if len(raw) != record["bytes"] or hashlib.sha256(raw).hexdigest() != record["sha256"]:
        raise ValueError(f"Archive file changed: {relative}")
    return raw


def replay_run(mdm, sample, row, steps):
    native_minimize = mdm.minimize_scalar
    shape_trials = {}
    trial_gammas = set(mdm._build_geometric_gamma_grid(min(sample), steps))
    trial_gammas.add(row["gamma_hat"])
    calculation = {}

    def observe_minimize(objective, *args, **kwargs):
        gamma = inspect.getclosurevars(objective).nonlocals["gamma"]
        if gamma not in trial_gammas:
            return native_minimize(objective, *args, **kwargs)
        points = shape_trials[gamma] = []

        def observe_point(beta):
            sigma = objective(beta)
            points.append([float(beta), float(sigma)])
            return sigma

        return native_minimize(observe_point, *args, **kwargs)

    def observe_return(frame, event, _):
        if event == "return" and frame.f_code is mdm.MDM.run.__code__:
            calculation.update(frame.f_locals)

    model = mdm.MDM(sample)
    mdm.minimize_scalar = observe_minimize
    previous_profiler = sys.getprofile()
    sys.setprofile(observe_return)
    try:
        estimate = model.run(trace=True, offset=row["delta"], gamma_steps=steps)
    finally:
        sys.setprofile(previous_profiler)
        mdm.minimize_scalar = native_minimize

    archived = tuple(row[key] for key in ("beta_hat", "eta_hat", "gamma_hat", "r_squared", "converged"))
    replayed_gradient = {point["gamma"]: point["gradient"] for point in model.trace_data["grad_gamma_curve"]}
    if estimate != archived or any(
        replayed_gradient.get(point["gamma"]) != point["gradient"] for point in row["criterion_curve"]
    ):
        raise ValueError(f"Replay differs from archive at repetition {row['id']}")
    for key in ("root_solver", "root_bracket", "root_solver_iterations"):
        if model.last_solution_info[key] != row["extra"]["solution_info"][key]:
            raise ValueError(f"Replay differs in {key} at repetition {row['id']}")
    if not any(beta == row["beta_hat"] for beta, _ in shape_trials[row["gamma_hat"]]):
        raise ValueError(f"No adopted shape evaluation at repetition {row['id']}")
    return {
        "id": row["id"],
        "profile": np.column_stack([
            calculation["gammas"], calculation["sigma_mins"], calculation["best_betas"],
        ])[::-1].tolist(),
        "shape": sorted(shape_trials[row["gamma_hat"]]),
        "trialShapes": [sorted(shape_trials[gamma]) for gamma in calculation["gammas"][::-1]],
        "pseudoScales": np.column_stack([calculation["denom"], calculation["etas"]]).tolist(),
        "scaleSum": float(np.sum(calculation["etas"])),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_root", type=Path)
    parser.add_argument("batch_id")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    catalog_path = Path(__file__).resolve().parents[1] / "src/content/monte-carlo/research00.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    entry = next(entry for entry in catalog["entries"] if entry["id"] == args.batch_id)
    process = entry["mdmProcess"]
    root = args.data_root / entry["directory"]
    if args.output.resolve().is_relative_to(root.resolve()):
        raise ValueError("Store the replay outside the frozen batch directory")
    manifest_raw = (root / "manifest.json").read_bytes()
    if hashlib.sha256(manifest_raw).hexdigest() != entry["manifestSha256"]:
        raise ValueError("Archive manifest changed")
    manifest = json.loads(manifest_raw)
    for relative in (process["source"], process["base"]):
        read_verified(root, manifest, relative)
    workbook = json.loads(read_verified(root, manifest, "workbook.json"))
    records = read_verified(root, manifest, process["records"]).splitlines()
    samples = {sample[0]: sample[1:] for sample in workbook["groups"][str(process["n"])]["samples"]}
    matching = [
        row for line in records if (row := json.loads(line))["method_id"] == "mdm"
        and row["n"] == process["n"] and row["delta"] == process["delta"]
    ]
    if sorted(row["id"] for row in matching) != sorted(samples):
        raise ValueError("Estimation records do not match the workbook sample IDs")

    sys.path.insert(0, str((root / process["base"]).parent))
    mdm = importlib.import_module("methods.mdm")
    steps = manifest["configuration"]["figure_contract"]["gamma_steps"]
    runs = [replay_run(mdm, samples[row["id"]], row, steps) for row in matching]
    output = json.dumps({
        "manifestSha256": entry["manifestSha256"],
        "n": process["n"],
        "delta": process["delta"],
        "runs": runs,
    }, allow_nan=False, separators=(",", ":")).encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as file:
        file.write(output)
    print(f"{len(runs)} exact replays, SHA-256 {hashlib.sha256(output).hexdigest()}")


if __name__ == "__main__":
    main()
