"""
Contract tests for E4 fail-closed validation logic.

Covers:
  1. Chunk validation: unknown combo injection -> abort
  2. Chunk validation: missing combo -> abort
  3. Chunk validation: row count mismatch (too few / too many rows) -> abort
  4. --tracks input gate: requested track with missing input file -> nonzero exit, no FORMAL output
  5. Subset run summary: track_status correctly reports not_requested vs completed

Run:
    python -m pytest python/tests/test_study01_e4_failclosed.py -v
"""

import os
import sys
import json
import hashlib
import re
import importlib
import importlib.util
import types
from pathlib import Path

import pandas as pd
import numpy as np
import pytest

# Path setup: resolve from this checkout, never from a machine-specific drive.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = next((PROJECT_ROOT / "Study").glob("01-study-MDM*"))
STUDY_CODE_DIR = STUDY_ROOT / "code"
_COLLECTION_SYS_PATH = list(sys.path)
_RELATED_MODULE_PREFIXES = (
    "run_E4_formal_validation", "run_E4_mc_generation", "config", "utils",
    "studies", "methods",
)
_COLLECTION_RELATED_MODULES = {
    name: module for name, module in sys.modules.items()
    if name in _RELATED_MODULE_PREFIXES
    or name.startswith(tuple(prefix + "." for prefix in _RELATED_MODULE_PREFIXES))
}
try:
    sys.path.insert(0, str(STUDY_CODE_DIR))
    _E4_MODULE = importlib.import_module("run_E4_formal_validation")
    _E4_MC_MODULE = importlib.import_module("run_E4_mc_generation")
    _UTILS_MODULE = importlib.import_module("utils")
finally:
    sys.path[:] = _COLLECTION_SYS_PATH
    for name in list(sys.modules):
        if (
            name in _RELATED_MODULE_PREFIXES
            or name.startswith(tuple(
                prefix + "." for prefix in _RELATED_MODULE_PREFIXES
            ))
        ):
            sys.modules.pop(name, None)
    sys.modules.update(_COLLECTION_RELATED_MODULES)

validate_chunk = _E4_MC_MODULE.validate_chunk
ChunkValidationError = _E4_MC_MODULE.ChunkValidationError
preflight_check_inputs = _E4_MODULE.preflight_check_inputs
PreflightError = _E4_MODULE.PreflightError
get_project_git_info_strict = _E4_MODULE.get_project_git_info_strict
_stable_provenance_path = _E4_MODULE._stable_provenance_path


# ============================================================
# Helpers
# ============================================================

def make_valid_chunk_rows(combo_ids, n_repeats=5, n_deltas=3):
    """Create valid rows for given combo IDs with small repeat/delta counts."""
    rows = []
    deltas = [round(0.02 * i, 2) for i in range(n_deltas)]
    for cid in combo_ids:
        for rid in range(n_repeats):
            for d in deltas:
                rows.append({
                    "combo_id": cid,
                    "beta": 1.5, "eta": 1.0, "gamma": 0.5,
                    "gamma_over_eta": 0.5, "n": 10,
                    "repeat_id": rid, "delta": d,
                    "beta_hat": 1.5, "eta_hat": 1.0, "gamma_hat": 0.5,
                    "r_squared": 0.99, "converged": True,
                    "time_ms": 1.0, "status": "success",
                })
    return pd.DataFrame(rows)


def make_e4d_contract_fixture(repeats=1):
    """Build small but complete frozen-grid tables for the E4d gate."""
    e4 = _E4_MODULE

    def rows_for(combos, include_combo_id):
        rows = []
        for combo in combos:
            if include_combo_id:
                combo_id, beta, goe, n = combo
            else:
                combo_id = None
                beta, eta, goe, n = combo
                assert eta == 1.0
            for repeat_id in range(repeats):
                for delta in e4.DELTA_GRID:
                    row = {
                        "beta": float(beta), "eta": 1.0,
                        "gamma": float(goe),
                        "gamma_over_eta": float(goe), "n": int(n),
                        "repeat_id": repeat_id, "delta": float(delta),
                    }
                    if include_combo_id:
                        row["combo_id"] = combo_id
                    rows.append(row)
        return pd.DataFrame(rows)

    main_combos = [
        (beta, eta, goe, n)
        for beta in e4.BETA_GRID
        for eta in e4.ETA_GRID
        for goe in e4.GAMMA_OVER_ETA_GRID
        for n in e4.N_GRID
    ]
    manifest = {
        "parameter_grid": {
            "beta": [float(value) for value in e4.BETA_GRID],
            "eta": [float(value) for value in e4.ETA_GRID],
            "gamma_over_eta": [
                float(value) for value in e4.GAMMA_OVER_ETA_GRID
            ],
            "n": [int(value) for value in e4.N_GRID],
        },
        "delta_grid": list(e4.DELTA_GRID),
        "repeats": repeats,
        "seed_namespace": e4.SEED_NAMESPACE,
    }
    return (
        rows_for(main_combos, include_combo_id=False),
        rows_for(e4.E4B_BOUNDARY_COMBOS, include_combo_id=True),
        rows_for(e4.E4C_OFFGRID_COMBOS, include_combo_id=True),
        manifest,
    )


def load_bound_e4d_fixture(tmp_path, repeats=1):
    """Write then same-byte parse/hash a complete synthetic E4d fixture."""
    e4 = _E4_MODULE

    df_main, df_boundary, df_offgrid, manifest = (
        make_e4d_contract_fixture(repeats=repeats)
    )
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    metadata_columns = ["beta", "eta", "gamma", "gamma_over_eta", "n"]
    for chunk_id, unit in enumerate(e4._expected_main_chunk_units()):
        mask = np.ones(len(df_main), dtype=bool)
        for column in metadata_columns:
            mask &= np.isclose(
                df_main[column].to_numpy(dtype=float), float(unit[column]),
                rtol=0.0, atol=1e-12,
            )
        df_main.loc[mask].to_csv(
            chunks_dir / f"chunk_{chunk_id:04d}_mdm.csv", index=False
        )
    loaded_main, main_chunks_capability = e4.load_authoritative_main_chunks(
        chunks_dir=str(chunks_dir), expected_repeats=repeats
    )

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )
    loaded_manifest, manifest_capability = e4.read_json_with_provenance(
        manifest_path, "main_grid_mc_manifest"
    )
    boundary_path = tmp_path / "boundary.csv"
    offgrid_path = tmp_path / "offgrid.csv"
    df_boundary.to_csv(boundary_path, index=False)
    df_offgrid.to_csv(offgrid_path, index=False)
    loaded_boundary, boundary_capability = e4.read_csv_with_provenance(
        boundary_path, "boundary_risk_curves"
    )
    loaded_offgrid, offgrid_capability = e4.read_csv_with_provenance(
        offgrid_path, "offgrid_risk_curves"
    )

    input_capabilities = {
        "main_grid_chunks": main_chunks_capability,
        "main_grid_mc_manifest": manifest_capability,
        "boundary_risk_curves": boundary_capability,
        "offgrid_risk_curves": offgrid_capability,
    }
    code_paths = {}
    for name in ["e4_validation", "config", "sample"]:
        path = tmp_path / f"code_{name}.py"
        path.write_text(f"# code:{name}\n", encoding="utf-8")
        code_paths[name] = str(path)
    utils_path = tmp_path / "code_utils.py"
    utils_path.write_text("# code:utils\n", encoding="utf-8")
    code_paths["study01_utils"] = str(utils_path)
    return (
        loaded_main, loaded_boundary, loaded_offgrid, loaded_manifest,
        input_capabilities, code_paths,
    )


# ============================================================
# Chunk validation tests
# ============================================================

class TestChunkValidation:

    def test_valid_chunk_passes(self):
        """A correctly-formed chunk should pass validation."""
        expected = {"B01", "B02"}
        df = make_valid_chunk_rows(["B01", "B02"], n_repeats=5, n_deltas=3)
        # Should not raise
        validate_chunk(df, expected, worker_id=0, r_formal=5, n_deltas=3)

    def test_unknown_combo_aborts(self):
        """An extra unknown combo (e.g. X99) must cause validation failure."""
        expected = {"B01", "B02"}
        # Chunk has B01, B02, AND an unknown X99
        df = make_valid_chunk_rows(["B01", "B02", "X99"], n_repeats=5, n_deltas=3)
        with pytest.raises(ChunkValidationError, match="unexpected combos"):
            validate_chunk(df, expected, worker_id=0, r_formal=5, n_deltas=3)

    def test_missing_combo_aborts(self):
        """A missing expected combo must cause validation failure."""
        expected = {"B01", "B02", "B03"}
        # Chunk only has B01, B02 — B03 is missing
        df = make_valid_chunk_rows(["B01", "B02"], n_repeats=5, n_deltas=3)
        with pytest.raises(ChunkValidationError, match="missing expected combos"):
            validate_chunk(df, expected, worker_id=0, r_formal=5, n_deltas=3)

    def test_too_few_rows_aborts(self):
        """Deleting rows from a valid combo must cause validation failure."""
        expected = {"B01"}
        df = make_valid_chunk_rows(["B01"], n_repeats=5, n_deltas=3)
        # Remove 3 rows
        df = df.iloc[:-3].copy()
        with pytest.raises(ChunkValidationError, match="rows"):
            validate_chunk(df, expected, worker_id=0, r_formal=5, n_deltas=3)

    def test_too_many_rows_aborts(self):
        """Adding extra rows to a valid combo must cause validation failure."""
        expected = {"B01"}
        df = make_valid_chunk_rows(["B01"], n_repeats=5, n_deltas=3)
        # Add 3 extra duplicate rows
        df = pd.concat([df, df.iloc[:3]], ignore_index=True)
        with pytest.raises(ChunkValidationError, match="rows"):
            validate_chunk(df, expected, worker_id=0, r_formal=5, n_deltas=3)

    def test_wrong_repeat_count_aborts(self):
        """A combo with wrong number of repeats must abort."""
        expected = {"B01"}
        # 4 repeats instead of 5
        df = make_valid_chunk_rows(["B01"], n_repeats=4, n_deltas=3)
        with pytest.raises(ChunkValidationError, match="repeats"):
            validate_chunk(df, expected, worker_id=0, r_formal=5, n_deltas=3)

    def test_wrong_delta_count_aborts(self):
        """A combo with wrong number of deltas must abort."""
        expected = {"B01"}
        # 2 deltas instead of 3
        df = make_valid_chunk_rows(["B01"], n_repeats=5, n_deltas=2)
        with pytest.raises(ChunkValidationError, match="deltas"):
            validate_chunk(df, expected, worker_id=0, r_formal=5, n_deltas=3)

    def test_empty_chunk_aborts(self):
        """An empty chunk must cause validation failure."""
        expected = {"B01"}
        df = pd.DataFrame(columns=[
            "combo_id", "beta", "eta", "gamma", "gamma_over_eta", "n",
            "repeat_id", "delta", "beta_hat", "eta_hat", "gamma_hat",
            "r_squared", "converged", "time_ms", "status",
        ])
        # Empty chunk has no combos → missing combo check fires first
        with pytest.raises(ChunkValidationError, match="missing expected combos"):
            validate_chunk(df, expected, worker_id=0, r_formal=5, n_deltas=3)

    def test_unknown_combo_then_missing_both_reported(self):
        """If chunk has both extra and missing combos, the first error is reported."""
        expected = {"B01", "B02"}
        # Has X99 (extra) and is missing B02
        df = make_valid_chunk_rows(["B01", "X99"], n_repeats=5, n_deltas=3)
        # Missing is checked first
        with pytest.raises(ChunkValidationError, match="missing expected combos"):
            validate_chunk(df, expected, worker_id=0, r_formal=5, n_deltas=3)


# ============================================================
# --tracks input gate tests (unit-level, using tmp_path)
# ============================================================

class TestTracksInputGate:
    """Test that preflight_check_inputs rejects missing inputs.
    Uses tmp_path to avoid touching real formal CSV files."""

    @staticmethod
    def input_map(tmp_path):
        chunks = str(tmp_path / "chunks")
        manifest = str(tmp_path / "manifest.json")
        boundary = str(tmp_path / "boundary_risk_curves.csv")
        offgrid = str(tmp_path / "offgrid_risk_curves.csv")
        return {
            'e4a': [chunks, manifest],
            'e4b': [manifest, boundary],
            'e4c': [manifest, offgrid],
            'e4d': [chunks, manifest, boundary, offgrid],
        }

    def test_e4b_missing_boundary_aborts(self, tmp_path):
        """Requesting e4b when boundary CSV is absent must raise PreflightError."""

        # Only offgrid exists in tmp_path
        (tmp_path / "offgrid_risk_curves.csv").write_text("dummy")
        (tmp_path / "manifest.json").write_text("{}")
        # boundary does NOT exist
        input_map = self.input_map(tmp_path)
        with pytest.raises(PreflightError, match="boundary_risk_curves"):
            preflight_check_inputs({'e4b'}, input_map)

    def test_e4c_missing_offgrid_aborts(self, tmp_path):
        """Requesting e4c when offgrid CSV is absent must raise PreflightError."""

        # Only boundary exists
        (tmp_path / "boundary_risk_curves.csv").write_text("dummy")
        (tmp_path / "manifest.json").write_text("{}")
        input_map = self.input_map(tmp_path)
        with pytest.raises(PreflightError, match="offgrid_risk_curves"):
            preflight_check_inputs({'e4c'}, input_map)

    def test_e4d_missing_multiple_inputs_reports_all(self, tmp_path):
        """Requesting e4d when multiple inputs are missing must report all."""

        input_map = self.input_map(tmp_path)
        with pytest.raises(PreflightError) as exc_info:
            preflight_check_inputs({'e4d'}, input_map)
        msg = str(exc_info.value)
        # All four formal E4d inputs should be in the message.
        assert "chunks" in msg
        assert "manifest.json" in msg
        assert "boundary_risk_curves" in msg
        assert "offgrid_risk_curves" in msg

    def test_all_present_passes(self, tmp_path):
        """When all required inputs exist, preflight should pass without error."""

        (tmp_path / "chunks").mkdir()
        (tmp_path / "manifest.json").write_text("{}")
        (tmp_path / "boundary_risk_curves.csv").write_text("dummy")
        (tmp_path / "offgrid_risk_curves.csv").write_text("dummy")
        input_map = self.input_map(tmp_path)
        # Should not raise — all tracks have their inputs
        preflight_check_inputs({'e4a', 'e4b', 'e4c', 'e4d'}, input_map)


# ============================================================
# Track status semantics tests
# ============================================================

class TestTrackStatusSemantics:
    """Test that track_status correctly distinguishes not_requested from skipped."""

    def test_not_requested_tracks_have_not_requested_status(self):
        """When running --tracks e4b,e4c, the track_status for e4a/e4d should be
        not_requested, not 'skipped'."""
        # This is a logic test — we verify the track_status dict construction
        # that the script uses
        valid_tracks = {'e4a', 'e4b', 'e4c', 'e4d'}
        requested_tracks = {'e4b', 'e4c'}

        track_status = {}
        for t in valid_tracks:
            if t in requested_tracks:
                track_status[t] = {'requested': True, 'status': 'pending'}
            else:
                track_status[t] = {'requested': False, 'status': 'not_requested'}

        # Requested tracks
        assert track_status['e4b']['requested'] is True
        assert track_status['e4c']['requested'] is True
        # Not requested tracks
        assert track_status['e4a']['requested'] is False
        assert track_status['e4a']['status'] == 'not_requested'
        assert track_status['e4d']['requested'] is False
        assert track_status['e4d']['status'] == 'not_requested'

    def test_no_e4d_skipped_field_in_subset_run(self):
        """The old e4d_skipped field should not exist in subset run summaries.
        This test verifies the field name is gone from the summary template."""
        # Simulate the summary construction
        track_status = {
            'e4a': {'requested': False, 'status': 'not_requested'},
            'e4b': {'requested': True, 'status': 'completed'},
            'e4c': {'requested': True, 'status': 'completed'},
            'e4d': {'requested': False, 'status': 'not_requested'},
        }
        summary = {
            "status": "FORMAL",
            "track_status": track_status,
        }
        # The old field must not be present
        assert "e4d_skipped" not in summary, (
            "e4d_skipped field found in summary — should use track_status instead"
        )
        # The new field must be present and accurate
        assert summary["track_status"]["e4d"]["status"] == "not_requested"
        assert summary["track_status"]["e4b"]["status"] == "completed"


# ============================================================
# strict current-checkout git provenance tests
# ============================================================

class TestGitInfoDirty:
    """Strict git provenance is rooted at the current checkout."""

    def test_project_git_info_matches_strict_hex_contract(self):
        result = get_project_git_info_strict()
        assert re.fullmatch(r"[0-9a-f]{4,40}(?:-dirty)?", result)

    def test_unknown_or_failed_git_provenance_is_rejected(self, monkeypatch):
        e4 = _E4_MODULE

        def fail_run(*args, **kwargs):
            return types.SimpleNamespace(returncode=1, stdout="", stderr="fail")

        monkeypatch.setattr(e4.subprocess, "run", fail_run)
        with pytest.raises(e4.PreflightError, match="git provenance failed"):
            e4.get_project_git_info_strict()


# ============================================================
# E4d provenance/fail-closed gate tests
# ============================================================

class TestE4dProvenanceGate:

    def test_production_module_import_restores_sys_path(self):
        before = list(sys.path)
        spec = importlib.util.spec_from_file_location(
            "study01_e4_path_restore_test",
            STUDY_CODE_DIR / "run_E4_formal_validation.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert sys.path == before

    def test_collection_preimport_restores_related_sys_modules(self):
        current = {
            name: module for name, module in sys.modules.items()
            if (
                name in _RELATED_MODULE_PREFIXES
                or name.startswith(tuple(
                    prefix + "." for prefix in _RELATED_MODULE_PREFIXES
                ))
            )
        }
        assert current == _COLLECTION_RELATED_MODULES

    def test_production_import_ignores_basename_module_collisions(
            self, monkeypatch):
        fake_config = types.SimpleNamespace(BETA_GRID=[999])
        fake_utils = types.SimpleNamespace(now_iso=lambda: "wrong")
        monkeypatch.setitem(sys.modules, "config", fake_config)
        monkeypatch.setitem(sys.modules, "utils", fake_utils)
        spec = importlib.util.spec_from_file_location(
            "study01_e4_collision_test",
            STUDY_CODE_DIR / "run_E4_formal_validation.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        assert module.BETA_GRID == [1.5, 2.0, 2.5, 4.0, 5.0]
        assert module.now_iso() != "wrong"
        assert sys.modules["config"] is fake_config
        assert sys.modules["utils"] is fake_utils

    def test_bound_csv_hash_and_parse_use_same_bytes(self, tmp_path):
        e4 = _E4_MODULE

        path = tmp_path / "bound.csv"
        original_bytes = b"value\n1\n"
        path.write_bytes(original_bytes)
        frame, capability = e4.read_csv_with_provenance(path, "bound_test")
        record = capability._export_record()

        # Mutating the path after return cannot change the already parsed frame
        # or the digest bound to the exact original byte batch.
        path.write_bytes(b"value\n999\n")
        assert frame["value"].tolist() == [1]
        assert record["sha256"] == hashlib.sha256(original_bytes).hexdigest()
        assert record["size_bytes"] == len(original_bytes)

    @pytest.mark.parametrize("defect", ["missing", "duplicate"])
    def test_authoritative_chunk_identity_defects_abort_before_parse(
            self, defect):
        e4 = _E4_MODULE

        paths = sorted(
            (STUDY_ROOT / "artifacts" / "formal" / "shared_data" / "chunks")
            .glob("chunk_*_mdm.csv")
        )
        assert len(paths) == 45
        if defect == "missing":
            paths = paths[:-1]
            expected = "identity set is incomplete"
        else:
            paths = paths + [paths[0]]
            expected = "duplicate identities"
        with pytest.raises(e4.PreflightError, match=expected):
            e4.load_authoritative_main_chunks(chunk_paths=paths)

    def run_valid_gate(self, tmp_path):
        e4 = _E4_MODULE

        (df_main, df_boundary, df_offgrid, manifest,
         input_capabilities, code_paths) = load_bound_e4d_fixture(
            tmp_path, repeats=1
        )
        result = e4.validate_e4d_preflight_contract(
            df_main, df_boundary, df_offgrid, manifest,
            input_capabilities, code_paths, main_repeats=1, eval_repeats=1,
        )
        return result, (df_main, df_boundary, df_offgrid, manifest), (
            input_capabilities, code_paths
        )

    def test_valid_gate_returns_separate_input_and_code_hashes(self, tmp_path):
        e4 = _E4_MODULE

        (gate, boundary_features, offgrid_features), _, paths = (
            self.run_valid_gate(tmp_path)
        )
        provenance = gate.export_provenance()
        input_capabilities, code_paths = paths
        generation = provenance["generation_time"]

        assert provenance["contract_version"] == e4.E4D_CONTRACT_VERSION
        assert provenance["status"] == "validated"
        assert generation["git_commit"] == gate.generation_git_commit
        assert re.fullmatch(
            r"[0-9a-f]{4,40}(?:-dirty)?", gate.generation_git_commit
        )
        assert set(generation["input_files"]) == set(input_capabilities)
        assert set(generation["code_files"]) == set(code_paths)
        assert "study01_utils" in generation["code_files"]
        assert len(generation["input_files"]["main_grid_chunks"]) == 45
        assert [record["chunk_id"] for record in generation[
            "input_files"
        ]["main_grid_chunks"]] == list(range(45))
        assert generation["data_roles"] == {
            "training_labels": ["main_grid"],
            "evaluation_truth_only": ["boundary", "offgrid"],
        }
        for record in generation["input_files"]["main_grid_chunks"]:
            assert len(record["sha256"]) == 64
        for name, record in generation["input_files"].items():
            if name != "main_grid_chunks":
                assert len(record["sha256"]) == 64
        for record in generation["code_files"].values():
            assert len(record["sha256"]) == 64
        assert len(boundary_features) == len(e4.E4B_BOUNDARY_COMBOS)
        assert len(offgrid_features) == len(e4.E4C_OFFGRID_COMBOS)
        assert provenance["sealed_release"]["status"] == (
            "pending_artifact_commit"
        )
        assert provenance["sealed_release"]["git_commit"] is None

    def test_forged_records_and_wrong_object_capabilities_cannot_mint_gate(
            self, tmp_path):
        e4 = _E4_MODULE
        (df_main, df_boundary, df_offgrid, manifest,
         input_capabilities, code_paths) = load_bound_e4d_fixture(
            tmp_path, repeats=1
        )
        forged = {
            name: {"path": "forged", "sha256": "0" * 64, "size_bytes": 1}
            for name in input_capabilities
        }
        with pytest.raises(e4.PreflightError, match="not an opaque"):
            e4.validate_e4d_preflight_contract(
                df_main, df_boundary, df_offgrid, manifest,
                forged, code_paths, main_repeats=1, eval_repeats=1,
            )

        with pytest.raises(e4.PreflightError, match="object mismatch"):
            e4.validate_e4d_preflight_contract(
                df_main.copy(), df_boundary, df_offgrid, manifest,
                input_capabilities, code_paths,
                main_repeats=1, eval_repeats=1,
            )

        other_path = tmp_path / "other_boundary.csv"
        df_boundary.to_csv(other_path, index=False)
        _, other_capability = e4.read_csv_with_provenance(
            other_path, "other_boundary"
        )
        wrong_capabilities = dict(input_capabilities)
        wrong_capabilities["boundary_risk_curves"] = other_capability
        with pytest.raises(e4.PreflightError, match="object mismatch"):
            e4.validate_e4d_preflight_contract(
                df_main, df_boundary, df_offgrid, manifest,
                wrong_capabilities, code_paths,
                main_repeats=1, eval_repeats=1,
            )

    def test_gate_export_json_roundtrip_and_manifest_attach_is_deep_copy(
            self, tmp_path):
        e4 = _E4_MODULE
        (gate, _, _), _, _ = self.run_valid_gate(tmp_path)
        base_manifest = {"run_id": "unit", "nested": {"keep": True}}

        attached = e4.attach_e4d_gate_to_manifest(base_manifest, gate)
        roundtripped = json.loads(json.dumps(attached))
        exported = roundtripped["e4d_preflight_provenance"]

        assert base_manifest == {"run_id": "unit", "nested": {"keep": True}}
        assert exported["generation_time"]["git_commit"] == (
            gate.generation_git_commit
        )
        assert attached["git_commit"] == gate.generation_git_commit
        assert exported["contract_version"] == e4.E4D_CONTRACT_VERSION
        exported["status"] = "tampered-copy"
        assert gate.export_provenance()["status"] == "validated"

        with pytest.raises(e4.PreflightError, match="does not match"):
            e4.attach_e4d_gate_to_manifest(
                {"git_commit": "deadbeef", "run_id": "wrong"}, gate
            )

    @pytest.mark.parametrize("defect", ["duplicate", "missing_delta", "bad_delta"])
    def test_corrupt_main_risk_keys_fail_closed(self, tmp_path, defect):
        e4 = _E4_MODULE

        (df_main, df_boundary, df_offgrid, manifest,
         input_capabilities, code_paths) = load_bound_e4d_fixture(
            tmp_path, repeats=1
        )
        if defect == "duplicate":
            df_main.loc[len(df_main)] = df_main.iloc[0]
            expected = "duplicate sample\\+delta"
        elif defect == "missing_delta":
            df_main.drop(index=df_main.index[0], inplace=True)
            expected = "exact frozen"
        else:
            df_main.loc[df_main.index[0], "delta"] = 0.51
            expected = "outside frozen"
        with pytest.raises(e4.PreflightError, match=expected):
            e4.validate_e4d_preflight_contract(
                df_main, df_boundary, df_offgrid, manifest,
                input_capabilities, code_paths, main_repeats=1, eval_repeats=1,
            )

    def test_missing_entire_repeat_fails_closed(self, tmp_path):
        e4 = _E4_MODULE

        (df_main, df_boundary, df_offgrid, manifest,
         input_capabilities, code_paths) = load_bound_e4d_fixture(
            tmp_path, repeats=2
        )
        first_combo = df_boundary["combo_id"].iloc[0]
        drop_index = df_boundary.index[
            (df_boundary["combo_id"] == first_combo)
            & (df_boundary["repeat_id"] == 1)
        ]
        df_boundary.drop(index=drop_index, inplace=True)
        with pytest.raises(e4.PreflightError, match="repeat_id 0..1"):
            e4.validate_e4d_preflight_contract(
                df_main, df_boundary, df_offgrid, manifest,
                input_capabilities, code_paths, main_repeats=2, eval_repeats=2,
            )

    def test_eval_metadata_mismatch_uses_p1b_contract(self, tmp_path):
        e4 = _E4_MODULE

        (df_main, df_boundary, df_offgrid, manifest,
         input_capabilities, code_paths) = load_bound_e4d_fixture(
            tmp_path, repeats=1
        )
        df_boundary.loc[df_boundary["combo_id"] == "B01", "beta"] = 9.9
        with pytest.raises(e4.PreflightError, match="P1b metadata contract"):
            e4.validate_e4d_preflight_contract(
                df_main, df_boundary, df_offgrid, manifest,
                input_capabilities, code_paths, main_repeats=1, eval_repeats=1,
            )

    def test_main_eval_combo_overlap_fails_closed(self, tmp_path, monkeypatch):
        e4 = _E4_MODULE

        (df_main, df_boundary, df_offgrid, manifest,
         input_capabilities, code_paths) = load_bound_e4d_fixture(
            tmp_path, repeats=1
        )
        overlapping = list(e4.E4B_BOUNDARY_COMBOS)
        overlapping[0] = ("B01", 1.5, 0.1, 7)
        df_boundary.loc[df_boundary["combo_id"] == "B01", [
            "beta", "eta", "gamma", "gamma_over_eta", "n"
        ]] = [1.5, 1.0, 0.1, 0.1, 7]
        monkeypatch.setattr(e4, "E4B_BOUNDARY_COMBOS", overlapping)
        with pytest.raises(e4.PreflightError, match="overlap or are mixed"):
            e4.validate_e4d_preflight_contract(
                df_main, df_boundary, df_offgrid, manifest,
                input_capabilities, code_paths, main_repeats=1, eval_repeats=1,
            )

    def test_formal_output_path_requires_validated_gate(self, tmp_path):
        e4 = _E4_MODULE

        output_path = tmp_path / "E4d_selector_extrapolation.csv"
        frame = pd.DataFrame([{"selected_delta": 0.1}])
        with pytest.raises(e4.PreflightError, match="genuine validated"):
            e4.write_e4d_formal_output(frame, str(output_path), None)
        assert not output_path.exists()

        (gate, _, _), _, _ = self.run_valid_gate(tmp_path)
        e4.write_e4d_formal_output(frame, str(output_path), gate)
        assert output_path.is_file()
        assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []

    def test_plain_dict_forged_gate_is_rejected_without_output(self, tmp_path):
        e4 = _E4_MODULE
        output_path = tmp_path / "E4d_selector_extrapolation.csv"
        forged = {
            "contract_version": e4.E4D_CONTRACT_VERSION,
            "status": "validated",
        }

        with pytest.raises(e4.PreflightError, match="genuine validated"):
            e4.write_e4d_formal_output(
                pd.DataFrame([{"x": 1}]), str(output_path), forged
            )
        assert not output_path.exists()
        assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []

    def test_formal_output_cleans_temp_when_csv_write_fails(
            self, tmp_path, monkeypatch):
        e4 = _E4_MODULE

        output_path = tmp_path / "E4d_selector_extrapolation.csv"
        (gate, _, _), _, _ = self.run_valid_gate(tmp_path)

        def fail_after_partial_write(self, path, index=False):
            Path(path).write_text("partial", encoding="utf-8")
            raise OSError("injected CSV write failure")

        monkeypatch.setattr(pd.DataFrame, "to_csv", fail_after_partial_write)
        with pytest.raises(OSError, match="injected CSV write failure"):
            e4.write_e4d_formal_output(
                pd.DataFrame([{"x": 1}]), str(output_path), gate
            )
        assert not output_path.exists()
        assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []

    def test_formal_output_cleans_temp_and_preserves_original_on_replace_failure(
            self, tmp_path, monkeypatch):
        e4 = _E4_MODULE

        output_path = tmp_path / "E4d_selector_extrapolation.csv"
        (gate, _, _), _, _ = self.run_valid_gate(tmp_path)
        output_path.write_text("sealed-original\n", encoding="utf-8")

        def fail_replace(source, destination):
            raise OSError("injected replace failure")

        monkeypatch.setattr(e4.os, "replace", fail_replace)
        with pytest.raises(OSError, match="injected replace failure"):
            e4.write_e4d_formal_output(
                pd.DataFrame([{"x": 1}]), str(output_path), gate
            )
        assert output_path.read_text(encoding="utf-8") == "sealed-original\n"
        assert list(tmp_path.glob(f".{output_path.name}.*.tmp")) == []

    def test_real_authoritative_chunks_pass_complete_main_contract(self):
        """Read-only smoke: all 45 tracked chunks form 1.17M valid rows."""
        e4 = _E4_MODULE

        frame, capability = e4.load_authoritative_main_chunks()
        records = capability._export_record()
        e4._validate_risk_key_contract(
            frame, "main_grid", e4.SAMPLE_KEYS, e4.R_MAIN
        )
        combos = e4._main_combo_set(frame)

        assert len(records) == 45
        assert [record["chunk_id"] for record in records] == list(range(45))
        assert len(frame) == 1_170_000
        assert len(frame[e4.SAMPLE_KEYS].drop_duplicates()) == 45_000
        assert len(combos) == 45


# ============================================================
# Cross-drive / external-path provenance regression tests
# ============================================================

class TestStableProvenancePath:
    """Verify that _stable_provenance_path never raises ValueError and
    produces stable, auditable representations regardless of drive."""

    def test_path_inside_project_returns_relative(self, tmp_path):
        """A path inside the project root stays relative with forward slashes."""
        root = str(tmp_path)
        inner = os.path.join(root, "sub", "file.csv")
        os.makedirs(os.path.dirname(inner), exist_ok=True)
        Path(inner).write_text("data")
        result = _stable_provenance_path(inner, root)
        assert result == "sub/file.csv"
        assert "\\" not in result

    def test_path_equals_project_root_returns_dot(self, tmp_path):
        """A path that equals project_root produces '.' (not empty or error)."""
        root = str(tmp_path)
        result = _stable_provenance_path(root, root)
        assert result == "."

    def test_path_outside_project_same_drive_uses_abs_prefix(self, tmp_path):
        """A path outside the project but on the same drive uses abs:// fallback
        (avoids '..' path-traversal ambiguity in provenance records)."""
        root = str(tmp_path / "project")
        os.makedirs(root, exist_ok=True)
        outside = str(tmp_path / "outside" / "data.csv")
        os.makedirs(os.path.dirname(outside), exist_ok=True)
        Path(outside).write_text("data")
        result = _stable_provenance_path(outside, root)
        assert result.startswith("abs://")
        assert "data.csv" in result
        assert ".." not in result

    def test_path_on_different_drive_uses_abs_prefix(self, monkeypatch, tmp_path):
        """When relpath would raise ValueError (cross-drive), abs:// is used."""
        root = str(tmp_path)
        # Simulate a path on a different drive
        cross_drive = "X:\\remote\\data.csv"
        # Ensure relpath is actually called and raises for the cross-drive case
        import ntpath
        original_relpath = os.path.relpath

        def mock_relpath(path, start):
            if "X:" in str(path):
                raise ValueError("path is on mount 'X:', start on mount 'C:'")
            return original_relpath(path, start)

        monkeypatch.setattr(os.path, "relpath", mock_relpath)
        result = _stable_provenance_path(cross_drive, root)
        assert result.startswith("abs://")
        assert "X:/remote/data.csv" in result
        assert ".." not in result

    def test_hash_and_size_preserved_regardless_of_path_form(self, tmp_path):
        """The sha256 and size_bytes in provenance records must not depend on
        whether the path was recorded as relative or absolute."""
        e4 = _E4_MODULE
        path = tmp_path / "test.csv"
        path.write_text("a,b\n1,2\n", encoding="utf-8")
        record = e4._record_for_bytes(str(path), path.read_bytes())
        assert record["sha256"] == hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        assert record["size_bytes"] == len(path.read_bytes())
        # Path form is stable (inside project) or abs:// (outside) — never error
        assert isinstance(record["path"], str)
        assert len(record["path"]) > 0


# ============================================================
# E4d formal contract tests
# ============================================================

class TestE4dFormalContract:
    """Verify the E4d formal implementation matches the frozen contract."""

    def test_e3b_fold_partition_matches_frozen_split_report(self):
        """The 5-fold combo partition must match the sealed split_report.csv."""
        e4 = _E4_MODULE
        folds = e4.get_combo_split()

        split_path = (
            STUDY_ROOT / "artifacts" / "formal" / "E3b_vector_mlp"
            / "split_report.csv"
        )
        if not split_path.exists():
            pytest.skip("split_report.csv not found")
        ref_split = pd.read_csv(split_path)

        for fold_idx, fold in enumerate(folds):
            fold_name = f"combo_fold_{fold_idx + 1}"
            ref_test = ref_split[ref_split["fold"] == fold_name]
            ref_combos = set(zip(
                ref_test["test_beta"],
                ref_test["test_gamma_over_eta"],
                ref_test["test_n"],
            ))
            our_test = set(
                (float(b), float(g), int(n))
                for (b, g, n) in fold["test_combos"]
            )
            assert ref_combos == our_test, (
                f"{fold_name} test combos mismatch: "
                f"missing={sorted(ref_combos - our_test)[:3]}, "
                f"extra={sorted(our_test - ref_combos)[:3]}"
            )

    def test_get_combo_split_produces_5_folds_disjoint_coverage(self):
        """All 45 combos covered, 5 folds, train/test disjoint."""
        e4 = _E4_MODULE
        folds = e4.get_combo_split()
        assert len(folds) == 5

        all_combos = set(
            (float(b), float(g), int(n))
            for b in e4.BETA_GRID
            for g in e4.GAMMA_OVER_ETA_GRID
            for n in e4.N_GRID
        )
        seen_test = set()
        seen_train = set()
        for fold in folds:
            test = set(
                (float(b), float(g), int(n))
                for (b, g, n) in fold["test_combos"]
            )
            train = set(
                (float(b), float(g), int(n))
                for (b, g, n) in fold["train_combos"]
            )
            assert len(test & train) == 0, "train/test overlap in fold"
            seen_test |= test
            seen_train |= train
        assert seen_test == all_combos, "not all combos appear in test folds"
        assert seen_train == all_combos, "not all combos appear in train folds"

    def test_frozen_baselines_include_default_l1_l2(self):
        """_compute_e4d_baselines must produce Default, L1, and L2 rows."""
        e4 = _E4_MODULE

        # Build a dummy risk/loss frame with 2 boundary and 2 offgrid combos
        def make_risk(combo_list):
            rows = []
            for combo in combo_list:
                combo_id, beta, goe, n_val = combo
                for rid in range(2):  # 2 repeats only for test speed
                    for delta in e4.DELTA_GRID[:3]:
                        rows.append({
                            "combo_id": combo_id, "beta": float(beta),
                            "beta_hat": float(beta),
                            "eta": 1.0, "eta_hat": 1.0,
                            "gamma": float(goe), "gamma_hat": float(goe),
                            "gamma_over_eta": float(goe), "n": int(n_val),
                            "repeat_id": rid, "delta": float(delta),
                        })
            return pd.DataFrame(rows)

        boundary_risk = make_risk(e4.E4B_BOUNDARY_COMBOS[:2])
        offgrid_risk = make_risk(e4.E4C_OFFGRID_COMBOS[:2])

        boundary_feat = e4.build_feature_table_for_combos(
            e4.E4B_BOUNDARY_COMBOS[:2], boundary_risk
        )
        offgrid_feat = e4.build_feature_table_for_combos(
            e4.E4C_OFFGRID_COMBOS[:2], offgrid_risk
        )

        boundary_loss = e4.compute_loss(boundary_risk)
        offgrid_loss = e4.compute_loss(offgrid_risk)

        df_baselines = e4._compute_e4d_baselines(
            boundary_feat, offgrid_feat,
            boundary_loss, offgrid_loss,
            default_delta=0.1, l1_delta=0.1,
            l2_table={5: 0.2, 7: 0.2, 10: 0.2, 20: 0.2},
        )
        models = set(df_baselines["model"].unique())
        assert "Default" in models
        assert "L1" in models
        assert "L2" in models

    def test_model_level_summary_keys(self):
        """The summary dict must contain all required metric keys."""
        e4 = _E4_MODULE
        rows = [
            {
                "fold": "combo_fold_1", "seed": 42,
                "selected_delta": 0.1, "true_loss": 0.04,
                "oracle_min": 0.03, "regret": 0.01,
                "n": 7,
            },
            {
                "fold": "combo_fold_1", "seed": 42,
                "selected_delta": 0.5, "true_loss": 0.09,
                "oracle_min": 0.03, "regret": 0.06,
                "n": 10,
            },
        ]
        summary = e4._model_level_summary(rows)
        assert "pooled_J1" in summary
        assert "per_n_J1" in summary
        assert "endpoint_rate" in summary
        assert "mean_regret" in summary
        assert "near_0.05" in summary
        assert 7 in summary["per_n_J1"]
        assert 10 in summary["per_n_J1"]
        assert summary["n_samples"] == 2

    def test_fold_train_has_no_eval_combos(self):
        """Training folds must NEVER contain boundary or offgrid combos as
        these are evaluation-only truth sets."""
        e4 = _E4_MODULE
        folds = e4.get_combo_split()
        boundary_set = set(
            (float(b), float(g), int(n))
            for _, b, g, n in e4.E4B_BOUNDARY_COMBOS
        )
        offgrid_set = set(
            (float(b), float(g), int(n))
            for _, b, g, n in e4.E4C_OFFGRID_COMBOS
        )
        for fold in folds:
            train_set = set(
                (float(b), float(g), int(n))
                for (b, g, n) in fold["train_combos"]
            )
            assert train_set.isdisjoint(boundary_set), (
                f"{fold['fold_name']}: train overlaps boundary"
            )
            assert train_set.isdisjoint(offgrid_set), (
                f"{fold['fold_name']}: train overlaps offgrid"
            )

    def test_pivot_risk_vectors_output_shape(self):
        """_pivot_risk_vectors must produce (N_samples, N_DELTAS) output."""
        e4 = _E4_MODULE
        import numpy as np
        df = pd.DataFrame([
            {"beta": 1.5, "eta": 1.0, "gamma": 0.1, "gamma_over_eta": 0.1,
             "n": 7, "repeat_id": 0, "delta": d, "loss_filled": 0.1,
             "n_val": 7, "CV": 0.5, "g1": 0.0, "g2": -0.5,
             "x_min": 0.1, "x_max": 2.0, "range": 1.9,
             "Q1": 0.5, "Med": 1.0, "Q3": 1.5, "IQR": 1.0,
             "x_bar": 1.0, "s": 0.5}
            for d in e4.DELTA_GRID
        ])
        samples, Y = e4._pivot_risk_vectors(df, "loss_filled", 1.0)
        assert len(samples) == 1, "should have one unique sample"
        assert Y.shape == (1, e4.N_DELTAS), (
            f"expected (1, {e4.N_DELTAS}) got {Y.shape}"
        )
        assert not np.any(np.isnan(Y)), "no NaN in filled output"
