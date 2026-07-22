"""
Study/01 Formal E4 — Validation Analysis Script

Handles all 4 tracks:
  E4a: Feature ablation (5-fold × 3 seeds × 4 groups, E3b MLP config)
  E4b: Boundary reference robustness (Default/L1/L2/L3/L4/L5/L6 on boundary combos)
  E4c: Off-grid reference robustness (same references on off-grid combos)
  E4d: Selector extrapolation diagnostic (train on main grid, evaluate on boundary/offgrid)

Reads:
  - Existing formal MC chunks: artifacts/formal/shared_data/chunks/chunk_####_mdm.csv
    (authoritative main-grid source for E4a + E4d training)
  - New boundary MC data: artifacts/formal/E4_robustness/boundary_risk_curves.csv (E4b)
  - New offgrid MC data: artifacts/formal/E4_robustness/offgrid_risk_curves.csv (E4c)

Writes:
  - artifacts/formal/E4_robustness/E4a_feature_ablation.csv
  - artifacts/formal/E4_robustness/E4b_boundary_reference.csv
  - artifacts/formal/E4_robustness/E4c_offgrid_reference.csv
  - artifacts/formal/E4_robustness/E4d_selector_extrapolation.csv (or E4d_skip_reason.md)
  - artifacts/formal/E4_robustness/endpoint_diagnostics.csv
  - artifacts/formal/E4_robustness/near_optimal_diagnostics.csv
  - artifacts/formal/E4_robustness/cost_report.csv
  - artifacts/formal/E4_robustness/split_report.csv
  - artifacts/formal/E4_robustness/manifest.json
  - artifacts/formal/E4_robustness/summary.json
  - artifacts/formal/E4_robustness/run_log.txt
  - artifacts/formal/E4_robustness/E4_acceptance_report.md
"""

import sys
import os
import json
import hashlib
import io
import re
import copy
import tempfile
import importlib.util
import time
import math
import gc
import subprocess
import warnings
from datetime import datetime, timezone
from itertools import product

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

# ============================================================
# Path setup
# ============================================================

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")

def _load_local_module(unique_name, path):
    """Load one repository-local module without basename/sys.path pollution."""
    spec = importlib.util.spec_from_file_location(unique_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load local module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_CONFIG = _load_local_module(
    '_study01_e4_config', os.path.join(STUDY_CODE_DIR, 'config.py')
)
_UTILS = _load_local_module(
    '_study01_e4_utils', os.path.join(STUDY_CODE_DIR, 'utils.py')
)
_SAMPLE = _load_local_module(
    '_study01_e4_sample',
    os.path.join(PYTHON_DIR, 'studies', 'common', 'sample.py'),
)

BETA_GRID = _CONFIG.BETA_GRID
ETA_GRID = _CONFIG.ETA_GRID
GAMMA_OVER_ETA_GRID = _CONFIG.GAMMA_OVER_ETA_GRID
N_GRID = _CONFIG.N_GRID
DELTA_GRID = _CONFIG.DELTA_GRID
DEFAULT_DELTA = _CONFIG.DEFAULT_DELTA
R_MAIN = _CONFIG.R_MAIN
R_ROBUSTNESS = _CONFIG.R_ROBUSTNESS
SEED_NAMESPACE = _CONFIG.SEED_NAMESPACE
ARTIFACTS_DIR = _CONFIG.ARTIFACTS_DIR
SHARED_DATA_DIR = _CONFIG.SHARED_DATA_DIR
now_iso = _UTILS.now_iso
generate_sample = _SAMPLE.generate_sample

# ============================================================
# Output directory
# ============================================================

E4_OUTPUT_DIR = os.path.join(ARTIFACTS_DIR, "E4_robustness")
os.makedirs(E4_OUTPUT_DIR, exist_ok=True)

MAIN_CHUNKS_DIR = os.path.join(SHARED_DATA_DIR, "chunks")
MC_AGGREGATE_PATH = os.path.join(SHARED_DATA_DIR, "mc_scan_raw.csv")
MC_MANIFEST_PATH = os.path.join(SHARED_DATA_DIR, "manifest.json")
BOUNDARY_PATH = os.path.join(E4_OUTPUT_DIR, "boundary_risk_curves.csv")
OFFGRID_PATH = os.path.join(E4_OUTPUT_DIR, "offgrid_risk_curves.csv")

# ============================================================
# Feature columns (same as E3b)
# ============================================================

FEATURE_COLS_ZSCORE = [
    'x_min', 'x_max', 'range', 'Q1', 'Med', 'Q3', 'IQR', 'x_bar', 's'
]
FEATURE_COLS_RAW = ['n', 'CV', 'g1', 'g2']
SAMPLE_FEATURE_COLS = FEATURE_COLS_ZSCORE + FEATURE_COLS_RAW

BANNED_FIELDS = {'beta', 'eta', 'gamma', 'gamma_over_eta', 'seed', 'repeat_id', 'combo_id'}

ABLATION_GROUPS = {
    'full': SAMPLE_FEATURE_COLS,
    'n_only': ['n'],
    'scale_quantile': ['n', 'x_min', 'x_max', 'range', 'Q1', 'Med', 'Q3', 'IQR', 'x_bar', 's'],
    'shape': ['n', 'CV', 'g1', 'g2'],
}

N_DELTAS = len(DELTA_GRID)
NEAR_OPTIMAL_EPS = [0.01, 0.02, 0.05]
STABILITY_SEEDS = [42, 2026, 3407]

# E3b-equivalent MLP config
MLP_HIDDEN_LAYERS = (256, 128, 64)
MLP_MAX_ITER = 300
MLP_BATCH_SIZE = 256
MLP_ALPHA = 1e-4
MLP_LR = 1e-3
MLP_VALIDATION_FRACTION = 0.15
MLP_N_ITER_NO_CHANGE = 20

SAMPLE_KEYS = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']

# Frozen combo lists
E4B_BOUNDARY_COMBOS = [
    ("B01", 1.2, 0.0, 5), ("B02", 1.2, 0.0, 20), ("B03", 1.2, 0.5, 5),
    ("B04", 1.2, 0.5, 20), ("B05", 1.2, 1.0, 50), ("B06", 1.2, 0.1, 10),
    ("B07", 6.0, 0.0, 5), ("B08", 6.0, 0.0, 20), ("B09", 6.0, 0.5, 7),
    ("B10", 6.0, 0.5, 50), ("B11", 6.0, 1.0, 20), ("B12", 6.0, 0.1, 10),
    ("B13", 2.5, 0.0, 5), ("B14", 2.5, 0.0, 50), ("B15", 2.5, 0.5, 50),
    ("B16", 2.5, 1.0, 5), ("B17", 1.5, 0.0, 10), ("B18", 4.0, 0.0, 20),
    ("B19", 2.0, 0.1, 50), ("B20", 4.0, 1.0, 5),
]
E4C_OFFGRID_COMBOS = [
    ("O01", 1.8, 0.3, 12), ("O02", 3.3, 0.7, 15), ("O03", 5.5, 0.2, 30),
    ("O04", 1.3, 0.9, 8), ("O05", 4.7, 0.4, 25), ("O06", 2.2, 0.0, 6),
    ("O07", 5.8, 0.8, 45), ("O08", 1.6, 0.05, 50), ("O09", 3.8, 0.95, 5),
    ("O10", 2.8, 0.6, 18), ("O11", 4.4, 0.15, 35), ("O12", 1.25, 0.25, 7),
    ("O13", 5.9, 0.75, 20), ("O14", 3.6, 0.35, 10),
]

log_lines = []
def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    log_lines.append(line)


class PreflightError(Exception):
    """Raised when preflight input validation fails (fail-closed)."""
    pass


def get_project_git_info_strict():
    """Return PROJECT_ROOT short commit plus dirty suffix, or fail closed."""
    try:
        commit_result = subprocess.run(
            ['git', '-C', PROJECT_ROOT, 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, timeout=10,
        )
        if commit_result.returncode != 0:
            raise PreflightError(
                "E4d git provenance failed: rev-parse returned nonzero"
            )
        commit = commit_result.stdout.strip().lower()
        if re.fullmatch(r'[0-9a-f]{4,40}', commit) is None:
            raise PreflightError(
                f"E4d git provenance returned invalid commit: {commit!r}"
            )
        dirty_result = subprocess.run(
            ['git', '-C', PROJECT_ROOT, 'status', '--porcelain'],
            capture_output=True, text=True, timeout=10,
        )
        if dirty_result.returncode != 0:
            raise PreflightError(
                "E4d git provenance failed: status returned nonzero"
            )
    except PreflightError:
        raise
    except (OSError, subprocess.SubprocessError) as exc:
        raise PreflightError(f"E4d git provenance unavailable: {exc}") from exc
    return commit + ('-dirty' if dirty_result.stdout.strip() else '')


E4D_CONTRACT_VERSION = "study01-e4d-preflight-v1"
_E4D_GATE_SENTINEL = object()
_BOUND_INPUT_SENTINEL = object()


class _BoundInputCapability:
    """Opaque binding between one parsed object identity and byte provenance."""
    __slots__ = ('_identity', '_value', '_record', '_kind')

    def __init__(self, identity, value, record, kind):
        if identity is not _BOUND_INPUT_SENTINEL:
            raise TypeError("_BoundInputCapability cannot be constructed directly")
        self._identity = identity
        self._value = value
        self._record = copy.deepcopy(record)
        self._kind = str(kind)

    def _require_binding(self, value, kind):
        if (
            self._identity is not _BOUND_INPUT_SENTINEL
            or self._kind != kind
            or self._value is not value
        ):
            raise PreflightError(
                f"E4d bound input capability/object mismatch [{kind}]"
            )

    def _export_record(self):
        return copy.deepcopy(self._record)


class _ValidatedE4dGate:
    """Opaque capability created only after the complete E4d gate passes."""
    __slots__ = ('_identity', '_provenance', '_generation_git_commit')

    def __init__(self, identity, provenance, generation_git_commit):
        if identity is not _E4D_GATE_SENTINEL:
            raise TypeError("_ValidatedE4dGate cannot be constructed directly")
        self._identity = identity
        self._provenance = copy.deepcopy(provenance)
        self._generation_git_commit = str(generation_git_commit)

    @property
    def generation_git_commit(self):
        return self._generation_git_commit

    def export_provenance(self):
        """Return a manifest-safe deep copy; never expose mutable gate state."""
        exported = copy.deepcopy(self._provenance)
        # Fail here if a future field stops being JSON serializable.
        return json.loads(json.dumps(exported))


def _require_validated_e4d_gate(gate):
    if not isinstance(gate, _ValidatedE4dGate) or (
        gate._identity is not _E4D_GATE_SENTINEL
    ):
        raise PreflightError(
            "E4d formal output requires a genuine validated preflight gate"
        )
    return gate


def attach_e4d_gate_to_manifest(manifest, gate):
    """Return a deep-copied manifest with exported gate provenance attached."""
    _require_validated_e4d_gate(gate)
    if not isinstance(manifest, dict):
        raise TypeError("E4 manifest must be a dict")
    attached = copy.deepcopy(manifest)
    existing_commit = attached.get('git_commit')
    if existing_commit not in (None, gate.generation_git_commit):
        raise PreflightError(
            "E4 manifest git_commit does not match the validated gate"
        )
    attached['git_commit'] = gate.generation_git_commit
    attached['e4d_preflight_provenance'] = gate.export_provenance()
    return json.loads(json.dumps(attached))


def sha256_file(path, chunk_size=1024 * 1024):
    """Return a streaming SHA256 digest for one provenance file."""
    digest = hashlib.sha256()
    with open(path, 'rb') as file_obj:
        while True:
            chunk = file_obj.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _stable_provenance_path(absolute_path, project_root):
    """Return a stable, auditable path for provenance records.

    - Paths inside *project_root*: project-relative with forward slashes.
    - Paths outside *project_root*, or on a different Windows drive:
      absolute path with ``abs://`` prefix (explicit, auditable fallback).
    """
    abs_path = os.path.abspath(absolute_path)
    try:
        rel = os.path.relpath(abs_path, project_root)
        # Guard against path traversal (e.g. '../../outside')
        if not rel.startswith('..'):
            return rel.replace(os.sep, '/')
    except ValueError:
        # Different drive on Windows — relpath raises ValueError
        pass
    # Fallback: explicit absolute path marker for audit trail
    return 'abs://' + abs_path.replace(os.sep, '/')


def _record_for_bytes(path, raw_bytes):
    """Describe the exact bytes parsed by an input loader."""
    absolute_path = os.path.abspath(path)
    return {
        'path': _stable_provenance_path(absolute_path, PROJECT_ROOT),
        'sha256': hashlib.sha256(raw_bytes).hexdigest(),
        'size_bytes': len(raw_bytes),
    }


def _read_input_bytes(path, label):
    absolute_path = os.path.abspath(path)
    if not os.path.isfile(absolute_path):
        raise PreflightError(f"E4d input missing [{label}]: {absolute_path}")
    try:
        with open(absolute_path, 'rb') as file_obj:
            return file_obj.read()
    except OSError as exc:
        raise PreflightError(
            f"E4d input unreadable [{label}]: {absolute_path}: {exc}"
        ) from exc


def read_csv_with_provenance(path, label):
    """Parse a CSV and hash the same immutable byte batch (no path re-read)."""
    raw_bytes = _read_input_bytes(path, label)
    try:
        frame = pd.read_csv(io.BytesIO(raw_bytes))
    except Exception as exc:
        raise PreflightError(f"E4d CSV parse failed [{label}]: {exc}") from exc
    record = _record_for_bytes(path, raw_bytes)
    record['row_count'] = int(len(frame))
    capability = _BoundInputCapability(
        _BOUND_INPUT_SENTINEL, frame, record, 'csv'
    )
    return frame, capability


def read_json_with_provenance(path, label):
    """Parse JSON and hash the same immutable byte batch (no path re-read)."""
    raw_bytes = _read_input_bytes(path, label)
    try:
        value = json.loads(raw_bytes.decode('utf-8-sig'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreflightError(f"E4d JSON parse failed [{label}]: {exc}") from exc
    record = _record_for_bytes(path, raw_bytes)
    capability = _BoundInputCapability(
        _BOUND_INPUT_SENTINEL, value, record, 'json'
    )
    return value, capability


def _expected_main_chunk_units():
    """Return the 45 frozen work units in generate_mc_data.py order."""
    units = []
    for eta in ETA_GRID:
        for goe in GAMMA_OVER_ETA_GRID:
            gamma = goe * eta
            for beta in BETA_GRID:
                for n in N_GRID:
                    units.append({
                        'beta': float(beta),
                        'eta': float(eta),
                        'gamma': float(gamma),
                        'gamma_over_eta': float(goe),
                        'n': int(n),
                    })
    return units


def load_authoritative_main_chunks(
        chunks_dir=MAIN_CHUNKS_DIR, chunk_paths=None,
        expected_repeats=R_MAIN):
    """Load and bind the 45 authoritative main-grid MDM chunks.

    Chunk identity comes from the frozen four-digit filename and must be a
    one-to-one mapping to the frozen generation work-unit order. Each file is
    parsed from the exact bytes used for its SHA256 record.
    """
    expected_units = _expected_main_chunk_units()
    expected_ids = set(range(len(expected_units)))
    if chunk_paths is None:
        chunks_path = os.path.abspath(chunks_dir)
        if not os.path.isdir(chunks_path):
            raise PreflightError(
                f"E4d authoritative main chunk directory missing: {chunks_path}"
            )
        chunk_paths = list(
            os.path.join(chunks_path, name)
            for name in os.listdir(chunks_path)
            if name.startswith('chunk_') and name.endswith('_mdm.csv')
        )

    by_identity = {}
    invalid_names = []
    duplicate_ids = []
    pattern = re.compile(r'^chunk_(\d{4})_mdm\.csv$')
    for path in chunk_paths:
        filename = os.path.basename(os.fspath(path))
        match = pattern.fullmatch(filename)
        if match is None:
            invalid_names.append(filename)
            continue
        chunk_id = int(match.group(1))
        if chunk_id in by_identity:
            duplicate_ids.append(chunk_id)
        else:
            by_identity[chunk_id] = os.fspath(path)
    if invalid_names:
        raise PreflightError(
            f"E4d authoritative chunk filenames are invalid: {sorted(invalid_names)}"
        )
    if duplicate_ids:
        raise PreflightError(
            "E4d authoritative main chunks contain duplicate identities: "
            f"{sorted(set(duplicate_ids))}"
        )

    actual_ids = set(by_identity)
    missing_ids = sorted(expected_ids - actual_ids)
    unexpected_ids = sorted(actual_ids - expected_ids)
    if missing_ids or unexpected_ids:
        raise PreflightError(
            "E4d authoritative main chunk identity set is incomplete: "
            f"missing={missing_ids}, unexpected={unexpected_ids}"
        )

    expected_rows = int(expected_repeats) * len(DELTA_GRID)
    frames = []
    records = []
    metadata_columns = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n']
    for chunk_id, expected_unit in enumerate(expected_units):
        frame, chunk_capability = read_csv_with_provenance(
            by_identity[chunk_id], f'main_grid_chunk_{chunk_id:04d}'
        )
        record = chunk_capability._export_record()
        missing_columns = [
            column for column in metadata_columns if column not in frame.columns
        ]
        if missing_columns:
            raise PreflightError(
                f"E4d chunk {chunk_id:04d} missing metadata columns: "
                f"{missing_columns}"
            )
        if len(frame) != expected_rows:
            raise PreflightError(
                f"E4d chunk {chunk_id:04d} row_count={len(frame)}, "
                f"expected={expected_rows}"
            )
        actual_units = frame[metadata_columns].drop_duplicates()
        if len(actual_units) != 1:
            raise PreflightError(
                f"E4d chunk {chunk_id:04d} mixes multiple combo identities"
            )
        actual_unit = actual_units.iloc[0].to_dict()
        mismatches = [
            column for column in metadata_columns
            if not np.isclose(
                float(actual_unit[column]), float(expected_unit[column]),
                rtol=0.0, atol=1e-12,
            )
        ]
        if mismatches:
            raise PreflightError(
                f"E4d chunk {chunk_id:04d} does not match frozen work-unit "
                f"order; mismatched columns={mismatches}"
            )
        record['chunk_id'] = chunk_id
        record['unit'] = expected_unit
        frames.append(frame)
        records.append(record)

    merged = pd.concat(frames, ignore_index=True, sort=False)
    capability = _BoundInputCapability(
        _BOUND_INPUT_SENTINEL, merged, records, 'main_grid_chunks'
    )
    return merged, capability


def _provenance_file_records(path_map):
    """Build manifest-safe path/hash records, failing closed on missing files."""
    records = {}
    for name, path in sorted(path_map.items()):
        absolute_path = os.path.abspath(path)
        if not os.path.isfile(absolute_path):
            raise PreflightError(
                f"E4d provenance file missing [{name}]: {absolute_path}"
            )
        records[name] = {
            'path': _stable_provenance_path(absolute_path, PROJECT_ROOT),
            'sha256': sha256_file(absolute_path),
        }
    return records


def _validated_bound_input_capabilities(
        input_capabilities, df_mc, mc_manifest, df_boundary, df_offgrid):
    """Validate opaque same-byte capabilities and export their records."""
    required = {
        'main_grid_chunks', 'main_grid_mc_manifest',
        'boundary_risk_curves', 'offgrid_risk_curves',
    }
    if not isinstance(input_capabilities, dict) or set(
        input_capabilities
    ) != required:
        raise PreflightError(
            "E4d bound input capabilities must contain exactly: "
            f"{sorted(required)}"
        )
    bindings = {
        'main_grid_chunks': (df_mc, 'main_grid_chunks'),
        'main_grid_mc_manifest': (mc_manifest, 'json'),
        'boundary_risk_curves': (df_boundary, 'csv'),
        'offgrid_risk_curves': (df_offgrid, 'csv'),
    }
    input_records = {}
    for name, (value, kind) in bindings.items():
        capability = input_capabilities[name]
        if not isinstance(capability, _BoundInputCapability):
            raise PreflightError(
                f"E4d input is not an opaque bound capability [{name}]"
            )
        capability._require_binding(value, kind)
        input_records[name] = capability._export_record()

    chunks = input_records['main_grid_chunks']
    if not isinstance(chunks, list) or len(chunks) != len(
        _expected_main_chunk_units()
    ):
        raise PreflightError(
            "E4d bound input provenance must contain 45 main-grid chunk records"
        )

    def validate_record(record, label):
        if not isinstance(record, dict):
            raise PreflightError(f"E4d provenance record is invalid [{label}]")
        digest = record.get('sha256')
        if not isinstance(digest, str) or re.fullmatch(r'[0-9a-f]{64}', digest) is None:
            raise PreflightError(
                f"E4d provenance SHA256 is invalid [{label}]"
            )
        if not record.get('path') or int(record.get('size_bytes', 0)) <= 0:
            raise PreflightError(
                f"E4d provenance path/size is invalid [{label}]"
            )

    chunk_ids = []
    for index, record in enumerate(chunks):
        validate_record(record, f'main_grid_chunk_{index:04d}')
        chunk_ids.append(record.get('chunk_id'))
    if chunk_ids != list(range(len(chunks))):
        raise PreflightError(
            "E4d main-grid chunk provenance is not in frozen identity order"
        )
    for name in sorted(required - {'main_grid_chunks'}):
        validate_record(input_records[name], name)

    # Defensive copy: downstream manifest construction cannot mutate the
    # loader-owned records used for this validation decision.
    return json.loads(json.dumps(input_records))


def _validate_risk_key_contract(df, label, sample_keys, expected_repeats):
    """Validate unique, complete ``sample key + delta`` risk-curve cells."""
    if not isinstance(df, pd.DataFrame):
        raise PreflightError(f"E4d {label} risk table is not a DataFrame")
    try:
        expected_repeats = int(expected_repeats)
    except (TypeError, ValueError) as exc:
        raise PreflightError(
            f"E4d {label} expected repeat count must be an integer"
        ) from exc
    if expected_repeats <= 0:
        raise PreflightError(
            f"E4d {label} expected repeat count must be positive"
        )
    required = list(sample_keys) + ['delta']
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise PreflightError(
            f"E4d {label} risk table missing contract columns: {missing}"
        )
    if df.empty:
        raise PreflightError(f"E4d {label} risk table is empty")
    if df[required].isna().any().any():
        null_columns = df[required].columns[df[required].isna().any()].tolist()
        raise PreflightError(
            f"E4d {label} risk keys contain nulls in: {null_columns}"
        )

    normalized = df[required].copy()
    numeric_columns = [
        column for column in required if column not in {'combo_id'}
    ]
    for column in numeric_columns:
        try:
            normalized[column] = pd.to_numeric(
                normalized[column], errors='raise'
            )
        except (TypeError, ValueError) as exc:
            raise PreflightError(
                f"E4d {label} risk-key column {column!r} must be numeric"
            ) from exc
        if not np.isfinite(normalized[column].to_numpy(dtype=float)).all():
            raise PreflightError(
                f"E4d {label} risk-key column {column!r} is non-finite"
            )

    if 'combo_id' in normalized.columns:
        normalized['combo_id'] = normalized['combo_id'].astype(str)
        if normalized['combo_id'].str.strip().eq('').any():
            raise PreflightError(f"E4d {label} contains blank combo_id values")

    for column in ['n', 'repeat_id']:
        values = normalized[column].to_numpy(dtype=float)
        if not np.equal(values, np.floor(values)).all():
            raise PreflightError(
                f"E4d {label} risk-key column {column!r} must be integer"
            )
        normalized[column] = normalized[column].astype(int)
    if (normalized['n'] <= 0).any() or (normalized['repeat_id'] < 0).any():
        raise PreflightError(
            f"E4d {label} requires n > 0 and repeat_id >= 0"
        )

    eta_values = normalized['eta'].to_numpy(dtype=float)
    gamma_values = normalized['gamma'].to_numpy(dtype=float)
    goe_values = normalized['gamma_over_eta'].to_numpy(dtype=float)
    if (normalized['beta'] <= 0).any() or (eta_values <= 0).any():
        raise PreflightError(f"E4d {label} requires beta > 0 and eta > 0")
    if not np.isclose(
        gamma_values / eta_values, goe_values, rtol=0.0, atol=1e-12
    ).all():
        raise PreflightError(
            f"E4d {label} has inconsistent gamma and gamma_over_eta metadata"
        )

    delta_values = normalized['delta'].to_numpy(dtype=float)
    delta_index = np.full(len(normalized), -1, dtype=np.int16)
    for index, expected_delta in enumerate(DELTA_GRID):
        matches = np.isclose(
            delta_values, float(expected_delta), rtol=0.0, atol=1e-12
        )
        delta_index[matches] = index
    if (delta_index < 0).any():
        examples = sorted(set(delta_values[delta_index < 0].tolist()))[:5]
        raise PreflightError(
            f"E4d {label} contains delta outside frozen DELTA_GRID: {examples}"
        )
    normalized['_delta_index'] = delta_index

    full_key = list(sample_keys) + ['_delta_index']
    duplicate_keys = normalized.duplicated(subset=full_key, keep=False)
    if duplicate_keys.any():
        examples = normalized.loc[duplicate_keys, full_key].head(5).to_dict('records')
        raise PreflightError(
            f"E4d {label} contains duplicate sample+delta risk keys: {examples}"
        )

    delta_counts = normalized.groupby(list(sample_keys), dropna=False)[
        '_delta_index'
    ].nunique()
    incomplete = delta_counts[delta_counts != len(DELTA_GRID)]
    if not incomplete.empty:
        examples = [tuple(key) if isinstance(key, tuple) else key
                    for key in incomplete.index[:5]]
        raise PreflightError(
            f"E4d {label} samples must contain the exact frozen "
            f"{len(DELTA_GRID)}-point DELTA_GRID; incomplete keys: {examples}"
        )

    combo_keys = [key for key in sample_keys if key != 'repeat_id']
    repeat_sets = normalized[combo_keys + ['repeat_id']].drop_duplicates().groupby(
        combo_keys, dropna=False
    )['repeat_id'].agg(lambda values: frozenset(int(v) for v in values))
    frozen_repeat_ids = frozenset(range(int(expected_repeats)))
    bad_repeats = repeat_sets[repeat_sets != frozen_repeat_ids]
    if not bad_repeats.empty:
        raise PreflightError(
            f"E4d {label} must contain repeat_id 0..{expected_repeats - 1} "
            f"for every combo; bad combo count={len(bad_repeats)}"
        )


def _main_combo_set(df_mc):
    """Validate and return the frozen main-grid combo tuples."""
    combo_columns = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n']
    actual = {
        (float(row.beta), float(row.eta), float(row.gamma),
         float(row.gamma_over_eta), int(row.n))
        for row in df_mc[combo_columns].drop_duplicates().itertuples(index=False)
    }
    expected = {
        (float(beta), float(eta), float(goe * eta), float(goe), int(n))
        for beta, eta, goe, n in product(
            BETA_GRID, ETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID
        )
    }
    if actual != expected:
        raise PreflightError(
            "E4d main-grid combo set does not match frozen config: "
            f"missing={sorted(expected - actual)[:5]}, "
            f"unexpected={sorted(actual - expected)[:5]}"
        )
    return actual


def _eval_combo_set(combo_list):
    return {
        (float(beta), 1.0, float(goe), float(goe), int(n))
        for _, beta, goe, n in combo_list
    }


def _validate_mc_manifest_contract(mc_manifest, main_repeats):
    """Bind main-grid data validation to its frozen generation manifest."""
    if not isinstance(mc_manifest, dict):
        raise PreflightError("E4d MC manifest must be a JSON object")
    expected_grid = {
        'beta': [float(value) for value in BETA_GRID],
        'eta': [float(value) for value in ETA_GRID],
        'gamma_over_eta': [float(value) for value in GAMMA_OVER_ETA_GRID],
        'n': [int(value) for value in N_GRID],
    }
    manifest_grid = mc_manifest.get('parameter_grid')
    if manifest_grid != expected_grid:
        raise PreflightError(
            "E4d MC manifest parameter_grid does not match frozen config"
        )
    if mc_manifest.get('delta_grid') != list(DELTA_GRID):
        raise PreflightError(
            "E4d MC manifest delta_grid does not match frozen DELTA_GRID"
        )
    try:
        manifest_repeats = int(mc_manifest.get('repeats', -1))
        expected_repeats = int(main_repeats)
    except (TypeError, ValueError) as exc:
        raise PreflightError(
            "E4d MC manifest repeats must be an integer"
        ) from exc
    if manifest_repeats != expected_repeats:
        raise PreflightError(
            "E4d MC manifest repeats does not match the main-grid contract"
        )
    if mc_manifest.get('seed_namespace') != SEED_NAMESPACE:
        raise PreflightError(
            "E4d MC manifest seed_namespace does not match frozen config"
        )


def validate_e4d_preflight_contract(
        df_mc, df_boundary, df_offgrid, mc_manifest,
        input_capabilities, code_paths, main_repeats=R_MAIN,
        eval_repeats=R_ROBUSTNESS):
    """Fail closed before E4d and return reusable features plus provenance.

    Training labels are validated exclusively from ``df_mc``. Boundary and
    off-grid truth are evaluation-only inputs and are never merged into the
    training frame.
    """
    bound_input_records = _validated_bound_input_capabilities(
        input_capabilities, df_mc, mc_manifest, df_boundary, df_offgrid
    )
    generation_git_commit = get_project_git_info_strict()
    _validate_mc_manifest_contract(mc_manifest, main_repeats)
    _validate_risk_key_contract(
        df_mc, 'main_grid', SAMPLE_KEYS, main_repeats
    )
    _validate_risk_key_contract(
        df_boundary, 'boundary', ['combo_id'] + SAMPLE_KEYS, eval_repeats
    )
    _validate_risk_key_contract(
        df_offgrid, 'offgrid', ['combo_id'] + SAMPLE_KEYS, eval_repeats
    )

    # Reuse the P1b metadata/sample reconstruction contract. These features
    # are derived from frozen metadata and deterministic sample generation;
    # estimator truth columns are not used.
    try:
        boundary_features = build_feature_table_for_combos(
            E4B_BOUNDARY_COMBOS, df_boundary
        )
        offgrid_features = build_feature_table_for_combos(
            E4C_OFFGRID_COMBOS, df_offgrid
        )
    except ValueError as exc:
        raise PreflightError(
            f"E4d boundary/offgrid P1b metadata contract failed: {exc}"
        ) from exc

    main_combos = _main_combo_set(df_mc)
    boundary_combos = _eval_combo_set(E4B_BOUNDARY_COMBOS)
    offgrid_combos = _eval_combo_set(E4C_OFFGRID_COMBOS)
    overlaps = {
        'main_boundary': main_combos & boundary_combos,
        'main_offgrid': main_combos & offgrid_combos,
        'boundary_offgrid': boundary_combos & offgrid_combos,
    }
    nonempty_overlaps = {
        name: sorted(values)[:5] for name, values in overlaps.items() if values
    }
    if nonempty_overlaps:
        raise PreflightError(
            "E4d training/evaluation combo sets overlap or are mixed: "
            f"{nonempty_overlaps}"
        )

    provenance = {
        'contract_version': E4D_CONTRACT_VERSION,
        'status': 'validated',
        'validated_at': now_iso(),
        'generation_time': {
            'git_commit': generation_git_commit,
            'input_files': bound_input_records,
            'code_files': _provenance_file_records(code_paths),
            'data_roles': {
                'training_labels': ['main_grid'],
                'evaluation_truth_only': ['boundary', 'offgrid'],
            },
            'sample_counts': {
                'main_grid': int(len(df_mc) // len(DELTA_GRID)),
                'boundary': int(len(df_boundary) // len(DELTA_GRID)),
                'offgrid': int(len(df_offgrid) // len(DELTA_GRID)),
            },
        },
        'sealed_release': {
            'status': 'pending_artifact_commit',
            'git_commit': None,
            'rule': (
                'The commit sealing generated artifacts is recorded after '
                'generation in the independent execution/review report.'
            ),
        },
    }
    gate = _ValidatedE4dGate(
        _E4D_GATE_SENTINEL, provenance, generation_git_commit
    )
    return gate, boundary_features, offgrid_features


def write_e4d_formal_output(df_results, output_path, gate):
    """Atomically write E4d output only after the validated contract gate."""
    _require_validated_e4d_gate(gate)
    output_path = os.path.abspath(output_path)
    output_dir = os.path.dirname(output_path)
    output_name = os.path.basename(output_path)
    tmp_path = None
    try:
        file_descriptor, tmp_path = tempfile.mkstemp(
            prefix=f'.{output_name}.', suffix='.tmp', dir=output_dir
        )
        os.close(file_descriptor)
        df_results.to_csv(tmp_path, index=False)
        os.replace(tmp_path, output_path)
        tmp_path = None
    finally:
        try:
            if tmp_path is not None and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            # Never mask the original write/replace exception.
            pass


def preflight_check_inputs(requested_tracks, input_path_map):
    """Validate that all required input files exist for the requested tracks.

    Args:
        requested_tracks: set of track strings (e.g. {'e4b', 'e4c'})
        input_path_map: dict mapping track -> list of required file paths

    Raises:
        PreflightError: with a descriptive message if any input is missing.
    """
    missing_inputs = []
    for track in sorted(requested_tracks):
        for path in input_path_map.get(track, []):
            if not os.path.exists(path):
                missing_inputs.append((track, path))
    if missing_inputs:
        lines = ["Required input files missing for requested tracks:"]
        for track, path in missing_inputs:
            lines.append(f"  [{track}] {path}")
        raise PreflightError("\n".join(lines))


def write_merged_cost_report(cost_path, new_rows, requested_tracks):
    """Replace requested-track costs while preserving all other tracks.

    A subset run owns only the tracks named in ``requested_tracks``. Existing
    rows for those tracks are removed before the current rows are appended;
    rows for every other track remain untouched. Repeating the same subset run
    therefore replaces, rather than duplicates, its prior cost rows.
    """
    requested = {str(track).strip().lower() for track in requested_tracks}
    new_cost = pd.DataFrame(new_rows)

    # Validate ownership before reading or touching the shared report.
    if not new_cost.empty:
        if 'track' not in new_cost.columns:
            raise ValueError("New cost rows must include a non-empty 'track'")
        new_track_raw = new_cost['track']
        empty_track = (
            new_track_raw.isna()
            | new_track_raw.astype(str).str.strip().eq('')
        )
        if empty_track.any():
            raise ValueError("New cost rows must include a non-empty 'track'")
        new_track = new_track_raw.astype(str).str.strip().str.lower()
        unexpected_tracks = set(new_track) - requested
        if unexpected_tracks:
            raise ValueError(
                "New cost rows contain tracks that were not requested: "
                f"{sorted(unexpected_tracks)}"
            )

    if os.path.exists(cost_path):
        try:
            existing_cost = pd.read_csv(cost_path)
        except pd.errors.EmptyDataError:
            existing_cost = pd.DataFrame(columns=['track'])
        if 'track' not in existing_cost.columns:
            raise ValueError(
                f"Existing cost report has no 'track' column: {cost_path}"
            )
        existing_track = existing_cost['track'].astype(str).str.strip().str.lower()
        preserved_cost = existing_cost.loc[~existing_track.isin(requested)].copy()
    else:
        preserved_cost = pd.DataFrame()

    frames = [df for df in (preserved_cost, new_cost) if not df.empty]
    if frames:
        merged_cost = pd.concat(frames, ignore_index=True, sort=False)
    elif len(preserved_cost.columns) > 0:
        merged_cost = preserved_cost.reset_index(drop=True)
    elif len(new_cost.columns) > 0:
        merged_cost = new_cost.reset_index(drop=True)
    else:
        merged_cost = pd.DataFrame(columns=['track'])
    merged_cost.to_csv(cost_path, index=False)
    return merged_cost


# ============================================================
# Feature computation (same as E3b)
# ============================================================

def compute_sample_features(sample):
    n = len(sample)
    s_sorted = np.sort(sample)
    x_min = float(s_sorted[0])
    x_max = float(s_sorted[-1])
    rng = x_max - x_min
    Q1 = float(np.percentile(s_sorted, 25))
    Med = float(np.median(s_sorted))
    Q3 = float(np.percentile(s_sorted, 75))
    IQR = Q3 - Q1
    x_bar = float(np.mean(s_sorted))
    s = float(np.std(s_sorted, ddof=1)) if n > 1 else 0.0
    CV = s / x_bar if x_bar > 0 else 0.0
    if n > 2 and s > 0:
        z = (s_sorted - x_bar) / s
        g1 = float(np.sum(z**3) / n)
        g2 = float(np.sum(z**4) / n - 3.0)
    else:
        g1 = 0.0
        g2 = 0.0
    return {
        'n': n,
        'x_min': x_min, 'x_max': x_max, 'range': rng,
        'Q1': Q1, 'Med': Med, 'Q3': Q3, 'IQR': IQR,
        'x_bar': x_bar, 's': s, 'CV': CV, 'g1': g1, 'g2': g2
    }


def compute_loss(df):
    r_beta = (df['beta_hat'] - df['beta']) / df['beta']
    r_eta = (df['eta_hat'] - df['eta']) / df['eta']
    r_gamma = (df['gamma_hat'] - df['gamma']) / df['eta']
    df = df.copy()
    df['loss'] = r_beta**2 + r_eta**2 + r_gamma**2
    df['loss'] = df['loss'].replace([np.inf, -np.inf], np.nan)
    return df


def build_feature_table_for_combos(combo_list, risk_data,
                                   seed_ns=SEED_NAMESPACE):
    """Build one feature row for every sample present in ``risk_data``.

    ``combo_list`` freezes the expected combo metadata; it does not define the
    repeat range. The actual unique ``(combo_id, repeat_id)`` keys in the
    supplied risk/loss table are authoritative, so 500-repeat, 1000-repeat,
    and non-contiguous repeat sets are handled without synthesizing samples.
    """
    required_columns = [
        'combo_id', 'beta', 'eta', 'gamma', 'gamma_over_eta', 'n',
        'repeat_id',
    ]
    missing_columns = [
        column for column in required_columns if column not in risk_data.columns
    ]
    if missing_columns:
        raise ValueError(
            "Risk data missing required sample-key columns: "
            f"{missing_columns}"
        )
    if risk_data.empty:
        raise ValueError("Risk data contains no sample keys")

    expected_rows = []
    for combo in combo_list:
        if len(combo) != 4:
            raise ValueError(
                "Each combo must be (combo_id, beta, gamma_over_eta, n)"
            )
        combo_id, beta, gamma_over_eta, n = combo
        expected_rows.append({
            'combo_id': combo_id,
            'beta': float(beta),
            'eta': 1.0,
            'gamma': float(gamma_over_eta),
            'gamma_over_eta': float(gamma_over_eta),
            'n': int(n),
        })
    expected = pd.DataFrame(expected_rows)
    if expected.empty:
        raise ValueError("Combo list is empty")
    expected_id_null = expected['combo_id'].isna().any()
    expected['combo_id'] = expected['combo_id'].astype(str)
    invalid_expected_ids = (
        expected_id_null
        or expected['combo_id'].str.strip().eq('').any()
        or expected['combo_id'].duplicated().any()
    )
    if invalid_expected_ids:
        raise ValueError("Combo list must contain unique, non-blank combo_id values")

    data = risk_data.copy()
    if data[required_columns].isna().any().any():
        null_columns = data[required_columns].columns[
            data[required_columns].isna().any()
        ].tolist()
        raise ValueError(
            "Risk data contains null sample-key values in columns: "
            f"{null_columns}"
        )

    data['combo_id'] = data['combo_id'].astype(str)
    if data['combo_id'].str.strip().eq('').any():
        raise ValueError("Risk data contains blank combo_id values")

    numeric_columns = [
        'beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id',
    ]
    for column in numeric_columns:
        try:
            data[column] = pd.to_numeric(data[column], errors='raise')
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Risk data column {column!r} must be numeric"
            ) from exc
        if not np.isfinite(data[column].to_numpy(dtype=float)).all():
            raise ValueError(
                f"Risk data column {column!r} contains non-finite values"
            )

    for column in ['n', 'repeat_id']:
        values = data[column].to_numpy(dtype=float)
        if not np.equal(values, np.floor(values)).all():
            raise ValueError(
                f"Risk data column {column!r} must contain integers"
            )
        data[column] = data[column].astype(int)
    if (data['n'] <= 0).any() or (data['repeat_id'] < 0).any():
        raise ValueError("Risk data requires n > 0 and repeat_id >= 0")

    # Rows repeat across delta by design. A repeated full risk key is corrupt;
    # a table without delta must contain one row per sample key.
    risk_key_columns = ['combo_id', 'repeat_id']
    if 'delta' in data.columns:
        if data['delta'].isna().any():
            raise ValueError("Risk data contains null delta values")
        try:
            data['delta'] = pd.to_numeric(data['delta'], errors='raise')
        except (TypeError, ValueError) as exc:
            raise ValueError("Risk data column 'delta' must be numeric") from exc
        if not np.isfinite(data['delta'].to_numpy(dtype=float)).all():
            raise ValueError("Risk data column 'delta' contains non-finite values")
        risk_key_columns.append('delta')
    duplicate_risk_keys = data.duplicated(
        subset=risk_key_columns, keep=False
    )
    if duplicate_risk_keys.any():
        examples = (
            data.loc[duplicate_risk_keys, risk_key_columns]
            .head(5)
            .to_dict('records')
        )
        raise ValueError(
            f"Risk data contains duplicate keys {risk_key_columns}: {examples}"
        )

    sample_metadata = data[required_columns].drop_duplicates()
    conflicting_sample_keys = sample_metadata.duplicated(
        subset=['combo_id', 'repeat_id'], keep=False
    )
    if conflicting_sample_keys.any():
        examples = (
            sample_metadata.loc[
                conflicting_sample_keys, ['combo_id', 'repeat_id']
            ]
            .drop_duplicates()
            .head(5)
            .to_dict('records')
        )
        raise ValueError(
            "Risk data has inconsistent metadata for sample keys: "
            f"{examples}"
        )

    expected_ids = set(expected['combo_id'])
    actual_ids = set(sample_metadata['combo_id'])
    missing_ids = sorted(expected_ids - actual_ids)
    unexpected_ids = sorted(actual_ids - expected_ids)
    if missing_ids or unexpected_ids:
        raise ValueError(
            "Risk data combo_id set does not match frozen combo list: "
            f"missing={missing_ids}, unexpected={unexpected_ids}"
        )

    actual_combo_metadata = sample_metadata[
        ['combo_id', 'beta', 'eta', 'gamma', 'gamma_over_eta', 'n']
    ].drop_duplicates()
    if actual_combo_metadata['combo_id'].duplicated(keep=False).any():
        inconsistent_ids = sorted(actual_combo_metadata.loc[
            actual_combo_metadata['combo_id'].duplicated(keep=False),
            'combo_id',
        ].unique())
        raise ValueError(
            "Risk data has inconsistent metadata across repeats for combos: "
            f"{inconsistent_ids}"
        )

    metadata_check = actual_combo_metadata.merge(
        expected, on='combo_id', how='outer', suffixes=('_actual', '_expected'),
        validate='one_to_one', indicator=True,
    )
    mismatch_columns = []
    for column in ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n']:
        actual_values = metadata_check[f'{column}_actual'].to_numpy(dtype=float)
        expected_values = metadata_check[
            f'{column}_expected'
        ].to_numpy(dtype=float)
        matches = np.isclose(
            actual_values, expected_values, rtol=0.0, atol=1e-12
        )
        if not matches.all():
            mismatch_columns.append(column)
    if not metadata_check['_merge'].eq('both').all() or mismatch_columns:
        raise ValueError(
            "Risk data combo metadata does not match frozen combo list; "
            f"mismatched columns: {mismatch_columns}"
        )

    combo_order = {
        str(combo_id): index
        for index, (combo_id, _, _, _) in enumerate(combo_list)
    }
    sample_metadata = sample_metadata.assign(
        _combo_order=sample_metadata['combo_id'].map(combo_order)
    ).sort_values(['_combo_order', 'repeat_id']).drop(columns='_combo_order')

    records = []
    for row in sample_metadata.itertuples(index=False):
        sample = generate_sample(
            float(row.beta), float(row.eta), float(row.gamma), int(row.n),
            int(row.repeat_id), seed=seed_ns,
        )
        feats = compute_sample_features(sample)
        feats.update({
            'combo_id': row.combo_id,
            'beta': float(row.beta),
            'eta': float(row.eta),
            'gamma': float(row.gamma),
            'gamma_over_eta': float(row.gamma_over_eta),
            'n': int(row.n),
            'repeat_id': int(row.repeat_id),
        })
        records.append(feats)
    return pd.DataFrame(records)


def build_feature_table_from_mc(df_mc, seed_ns=SEED_NAMESPACE):
    """Build features from MC scan data (for E4a — existing main grid)."""
    sample_keys_df = (
        df_mc[['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']]
        .drop_duplicates()
        .sort_values(['beta', 'gamma_over_eta', 'n', 'repeat_id'])
        .reset_index(drop=True)
    )
    log(f"  Computing features for {len(sample_keys_df)} unique samples...")
    feat_records = []
    t0 = time.time()
    for _, row in sample_keys_df.iterrows():
        beta = float(row['beta'])
        eta = float(row['eta'])
        gamma = float(row['gamma'])
        n = int(row['n'])
        rid = int(row['repeat_id'])
        sample = generate_sample(beta, eta, gamma, n, rid, seed=seed_ns)
        feats = compute_sample_features(sample)
        for k, v in row.to_dict().items():
            feats[k] = v
        feat_records.append(feats)
    df_feat = pd.DataFrame(feat_records)
    log(f"  Features done in {time.time()-t0:.1f}s")
    return df_feat


# ============================================================
# Split definitions (same 5-fold as E3b)
# ============================================================

def get_combo_split():
    combos = list(product(BETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID))
    folds = []
    for fold_idx in range(5):
        test_combos = [c for i, c in enumerate(combos) if i % 5 == fold_idx]
        train_combos = [c for i, c in enumerate(combos) if i % 5 != fold_idx]
        folds.append({
            'fold_name': f'combo_fold_{fold_idx+1}',
            'train_combos': train_combos,
            'test_combos': test_combos,
        })
    return folds


# ============================================================
# E4a: Feature ablation
# ============================================================

def run_e4a(df_mc):
    """Run formal feature ablation: 4 groups × 5 folds × 3 seeds."""
    log("=== E4a: Feature Ablation ===")

    # Build feature table
    df_feat = build_feature_table_from_mc(df_mc)
    merge_keys = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
    df_merged = df_mc.merge(df_feat, on=merge_keys, how='left', suffixes=('', '_feat'))
    for col in list(df_merged.columns):
        if col.endswith('_feat'):
            df_merged.drop(columns=col, inplace=True)
    df_merged = compute_loss(df_merged)

    # Verify no banned fields in features
    assert not (set(SAMPLE_FEATURE_COLS) & BANNED_FIELDS), "Banned field in features!"

    results = []
    cost_rows = []
    folds = get_combo_split()

    for fold in folds:
        fold_name = fold['fold_name']
        train_combos = set(fold['train_combos'])
        test_combos = set(fold['test_combos'])

        def is_in_combos(row, combo_set):
            return (row['beta'], row['gamma_over_eta'], row['n']) in combo_set

        df_train = df_merged[df_merged.apply(
            lambda r: is_in_combos(r, train_combos), axis=1
        )].copy()
        df_test = df_merged[df_merged.apply(
            lambda r: is_in_combos(r, test_combos), axis=1
        )].copy()

        log(f"  Fold {fold_name}: train={len(df_train)}, test={len(df_test)}")

        # Z-score from train
        zscore_means = {}
        zscore_stds = {}
        for col in FEATURE_COLS_ZSCORE:
            vals = df_train[col].astype(float)
            zscore_means[col] = float(vals.mean())
            zscore_stds[col] = float(vals.std(ddof=0))
            if zscore_stds[col] < 1e-12:
                zscore_stds[col] = 1.0

        # Failure penalty from train
        train_valid_loss = df_train['loss'].dropna()
        failure_penalty = float(np.nanpercentile(train_valid_loss, 99))

        df_train['loss_filled'] = df_train['loss'].fillna(failure_penalty)
        df_test['loss_filled'] = df_test['loss'].fillna(failure_penalty)

        for group_name, group_features in ABLATION_GROUPS.items():
            for seed in STABILITY_SEEDS:
                log(f"    {fold_name} / {group_name} / seed={seed}")
                t0 = time.time()

                res = _train_eval_ablation(
                    df_train, df_test, group_features,
                    zscore_means, zscore_stds, failure_penalty,
                    fold_name, seed
                )

                elapsed = time.time() - t0
                res['elapsed_s'] = elapsed
                results.append(res)

                cost_rows.append({
                    'track': 'E4a',
                    'fold': fold_name,
                    'feature_group': group_name,
                    'seed': seed,
                    'n_features': len(group_features),
                    'elapsed_s': elapsed,
                    'n_train': len(df_train),
                    'n_test': len(df_test),
                })
                log(f"      J1={res['pooled_J1']:.6f}, elapsed={elapsed:.1f}s")

                gc.collect()

    df_results = pd.DataFrame(results)
    df_cost = pd.DataFrame(cost_rows)
    return df_results, df_cost


def _train_eval_ablation(df_train, df_test, group_features,
                          zscore_means, zscore_stds, failure_penalty,
                          fold_name, seed):
    """Train one ablation model and evaluate."""
    # Pivot to vector
    def pivot_vector(df, label_col):
        feat_cols = [c for c in SAMPLE_FEATURE_COLS if c not in SAMPLE_KEYS]
        sample_df = df[SAMPLE_KEYS + feat_cols].drop_duplicates(
            subset=SAMPLE_KEYS).reset_index(drop=True)
        pivot = df.pivot_table(
            index=SAMPLE_KEYS, columns='delta',
            values=label_col, aggfunc='first'
        ).reset_index()
        result = pivot[SAMPLE_KEYS].merge(sample_df, on=SAMPLE_KEYS, how='left')
        Y = np.full((len(pivot), N_DELTAS), np.nan)
        for j, d in enumerate(DELTA_GRID):
            if d in pivot.columns:
                Y[:, j] = pivot[d].values
        Y = np.where(np.isnan(Y), failure_penalty, Y)
        assert len(result) == Y.shape[0]
        return result, Y

    train_samples, Y_train = pivot_vector(df_train, 'loss_filled')
    test_samples, Y_test = pivot_vector(df_test, 'loss_filled')

    # Build feature matrix for this group
    zscore_subset = [c for c in FEATURE_COLS_ZSCORE if c in group_features]
    raw_subset = [c for c in FEATURE_COLS_RAW if c in group_features]

    def build_X(df_samples):
        cols = []
        for col in zscore_subset:
            vals = df_samples[col].astype(float).values
            std = zscore_stds.get(col, 1.0)
            mean = zscore_means.get(col, 0.0)
            if std < 1e-12:
                std = 1.0
            cols.append((vals - mean) / std)
        for col in raw_subset:
            cols.append(df_samples[col].astype(float).values)
        return np.column_stack(cols).astype(np.float32) if cols else \
            np.zeros((len(df_samples), 0), dtype=np.float32)

    X_train = build_X(train_samples)
    X_test = build_X(test_samples)

    if X_train.shape[1] == 0:
        return {
            'fold': fold_name, 'feature_group': group_features[0] if group_features else 'empty',
            'seed': seed, 'pooled_J1': float('nan'), 'n_samples': 0,
            'error': 'no features'
        }

    # Train
    target_scaler = StandardScaler()
    Y_train_scaled = target_scaler.fit_transform(Y_train)

    with warnings.catch_warnings():
        warnings.simplefilter('ignore', category=ConvergenceWarning)
        model = MLPRegressor(
            hidden_layer_sizes=MLP_HIDDEN_LAYERS,
            activation='relu', solver='adam',
            alpha=MLP_ALPHA, learning_rate_init=MLP_LR,
            max_iter=MLP_MAX_ITER, early_stopping=True,
            validation_fraction=MLP_VALIDATION_FRACTION,
            n_iter_no_change=MLP_N_ITER_NO_CHANGE,
            random_state=seed, batch_size=MLP_BATCH_SIZE,
        )
        model.fit(X_train, Y_train_scaled)

    Y_pred = target_scaler.inverse_transform(model.predict(X_test))
    Y_pred = np.clip(Y_pred, 0, None)

    # Evaluate
    best_idx = np.argmin(Y_pred, axis=1)
    true_losses = Y_test[np.arange(len(Y_test)), best_idx]
    j1 = math.sqrt(np.mean(true_losses))

    # Per-n
    per_n = {}
    test_n_values = test_samples['n'].values
    for n_val in sorted(np.unique(test_n_values)):
        mask = test_n_values == n_val
        if mask.sum() > 0:
            per_n[int(n_val)] = math.sqrt(np.mean(true_losses[mask]))

    # Endpoint rate
    sel_deltas = np.array([DELTA_GRID[i] for i in best_idx])
    p_extreme = float(np.isin(sel_deltas, [0.00, 0.02, 0.48, 0.50]).mean())

    # Near-optimal
    oracle_min = np.min(Y_test, axis=1)
    regret = true_losses - oracle_min
    rel_regret = np.where(oracle_min > 1e-12, regret / oracle_min, regret)
    near_rates = {f'near_{eps}': float(np.mean(rel_regret <= eps)) for eps in NEAR_OPTIMAL_EPS}

    group_label = group_features[0] if len(group_features) <= 1 else group_name_label(group_features)
    return {
        'fold': fold_name,
        'feature_group': group_label,
        'n_features': len(group_features),
        'seed': seed,
        'pooled_J1': j1,
        'n_samples': len(test_samples),
        'n_iter': model.n_iter_,
        'endpoint_rate': p_extreme,
        'near_1pct': near_rates['near_0.01'],
        'near_2pct': near_rates['near_0.02'],
        'near_5pct': near_rates['near_0.05'],
        'mean_regret': float(np.mean(regret)),
        **{f'J1_n{n_val}': per_n.get(n_val, float('nan')) for n_val in N_GRID},
    }


def group_name_label(features):
    """Convert feature list to group name."""
    for name, group in ABLATION_GROUPS.items():
        if group == features:
            return name
    return 'unknown'


# ============================================================
# E4b/E4c: Reference evaluation
# ============================================================

def evaluate_references(df_mc_new, label):
    """Evaluate Default/L1/L2/L3/L4/L5/L6 on new MC data.

    L1: global best constant delta on THIS data.
    L2: per-n best delta on THIS data.
    L3: per-beta best delta.
    L4: per-(beta,n) best delta.
    L5: per-(beta,gamma_over_eta,n) best delta.
    L6: per-sample hindsight best delta.
    """
    log(f"=== {label}: Reference Evaluation ===")

    df = compute_loss(df_mc_new)
    df_valid = df.dropna(subset=['loss']).copy()

    if len(df_valid) == 0:
        log(f"  WARNING: No valid rows for {label}!")
        return pd.DataFrame(), {}

    # Compute reference delta tables from THIS data
    # Default
    default_delta = DEFAULT_DELTA

    # L1: global best
    global_loss = df_valid.groupby('delta')['loss'].apply(
        lambda x: np.sqrt(np.nanmean(x)))
    l1_delta = float(global_loss.idxmin())

    # L2: per-n best
    l2_table = {}
    for n_val in df_valid['n'].unique():
        df_n = df_valid[df_valid['n'] == n_val]
        loss_by_d = df_n.groupby('delta')['loss'].apply(lambda x: np.sqrt(np.nanmean(x)))
        l2_table[int(n_val)] = float(loss_by_d.idxmin())

    # L3: per-beta best
    l3_table = {}
    for b_val in df_valid['beta'].unique():
        df_b = df_valid[df_valid['beta'] == b_val]
        loss_by_d = df_b.groupby('delta')['loss'].apply(lambda x: np.sqrt(np.nanmean(x)))
        l3_table[float(b_val)] = float(loss_by_d.idxmin())

    # L4: per-(beta,n) best
    l4_table = {}
    for b_val in df_valid['beta'].unique():
        for n_val in df_valid[df_valid['beta'] == b_val]['n'].unique():
            df_bn = df_valid[(df_valid['beta'] == b_val) & (df_valid['n'] == n_val)]
            loss_by_d = df_bn.groupby('delta')['loss'].apply(lambda x: np.sqrt(np.nanmean(x)))
            l4_table[(float(b_val), int(n_val))] = float(loss_by_d.idxmin())

    # L5: per-(beta,gamma_over_eta,n) best
    l5_table = {}
    for (b_val, goe_val, n_val), grp in df_valid.groupby(['beta', 'gamma_over_eta', 'n']):
        loss_by_d = grp.groupby('delta')['loss'].apply(lambda x: np.sqrt(np.nanmean(x)))
        l5_table[(float(b_val), float(goe_val), int(n_val))] = float(loss_by_d.idxmin())

    # Build per-sample evaluation
    sample_keys = (
        df_valid[['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']]
        .drop_duplicates()
        .sort_values(['beta', 'gamma_over_eta', 'n', 'repeat_id'])
        .reset_index(drop=True)
    )

    results = []
    endpoint_rows = []
    near_opt_rows = []

    for _, srow in sample_keys.iterrows():
        beta = float(srow['beta'])
        eta = float(srow['eta'])
        gamma = float(srow['gamma'])
        goe = float(srow['gamma_over_eta'])
        n_val = int(srow['n'])
        rid = int(srow['repeat_id'])

        # Get this sample's loss curve
        sample_df = df_valid[
            (df_valid['beta'] == beta) &
            (df_valid['gamma_over_eta'] == goe) &
            (df_valid['n'] == n_val) &
            (df_valid['repeat_id'] == rid)
        ].sort_values('delta')

        if len(sample_df) != N_DELTAS:
            continue

        losses = sample_df['loss'].values
        delta_values = sample_df['delta'].values

        # L6 hindsight
        l6_idx = int(np.argmin(losses))

        # Evaluate each reference
        refs = {
            'Default': (delta_values == default_delta),
            'L1': (delta_values == l1_delta),
            'L2': (delta_values == l2_table.get(n_val, l1_delta)),
            'L3': (delta_values == l3_table.get(beta, l1_delta)),
            'L4': (delta_values == l4_table.get((beta, n_val), l1_delta)),
            'L5': (delta_values == l5_table.get((beta, goe, n_val), l1_delta)),
            'L6-hindsight': np.arange(N_DELTAS) == l6_idx,
        }

        oracle_min = float(losses[l6_idx])

        for ref_name, ref_mask in refs.items():
            idx = np.where(ref_mask)[0]
            if len(idx) == 0:
                continue
            sel_idx = idx[0]
            sel_loss = float(losses[sel_idx])
            sel_delta = float(delta_values[sel_idx])

            regret = sel_loss - oracle_min
            rel_regret = regret / oracle_min if oracle_min > 1e-12 else regret

            results.append({
                'track': label,
                'model': ref_name,
                'beta': beta,
                'gamma_over_eta': goe,
                'n': n_val,
                'repeat_id': rid,
                'selected_delta': sel_delta,
                'true_loss': sel_loss,
                'oracle_min': oracle_min,
                'regret': regret,
                'rel_regret': rel_regret,
            })

            # Endpoint
            p_extreme = sel_delta in [0.00, 0.02, 0.48, 0.50]
            endpoint_rows.append({
                'track': label,
                'model': ref_name,
                'beta': beta,
                'gamma_over_eta': goe,
                'n': n_val,
                'is_extreme': p_extreme,
            })

            # Near-optimal
            near_opt_rows.append({
                'track': label,
                'model': ref_name,
                'beta': beta,
                'gamma_over_eta': goe,
                'n': n_val,
                'near_1pct': int(rel_regret <= 0.01),
                'near_2pct': int(rel_regret <= 0.02),
                'near_5pct': int(rel_regret <= 0.05),
            })

    df_results = pd.DataFrame(results)

    # Aggregate
    summary = {}
    if len(df_results) > 0:
        for model in df_results['model'].unique():
            sub = df_results[df_results['model'] == model]
            j1 = math.sqrt(sub['true_loss'].mean())
            per_n = {}
            for n_val in sorted(sub['n'].unique()):
                sub_n = sub[sub['n'] == n_val]
                per_n[int(n_val)] = math.sqrt(sub_n['true_loss'].mean())

            summary[model] = {
                'pooled_J1': j1,
                'n_samples': len(sub),
                'mean_regret': float(sub['regret'].mean()),
                'per_n_J1': per_n,
            }

    log(f"  {len(df_results)} evaluation rows, {len(summary)} models")
    for model, s in summary.items():
        log(f"    {model}: J1={s['pooled_J1']:.6f}")

    return df_results, summary


# ============================================================
# E4d: Selector extrapolation diagnostic
# ============================================================

def run_e4d(df_mc, df_boundary_feat, df_offgrid_feat,
            df_boundary_loss, df_offgrid_loss):
    """Train Vector-MLP-L6 on main grid, evaluate on boundary/offgrid.

    This is a diagnostic — not deployment proof.
    """
    log("=== E4d: Selector Extrapolation Diagnostic ===")

    # Build features for main grid
    df_feat = build_feature_table_from_mc(df_mc)
    merge_keys = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
    df_merged = df_mc.merge(df_feat, on=merge_keys, how='left', suffixes=('', '_feat'))
    for col in list(df_merged.columns):
        if col.endswith('_feat'):
            df_merged.drop(columns=col, inplace=True)
    df_merged = compute_loss(df_merged)

    # Use fold 1 as representative (same as E3b feature ablation baseline)
    folds = get_combo_split()
    fold = folds[0]
    train_combos = set(fold['train_combos'])

    def is_train(row):
        return (row['beta'], row['gamma_over_eta'], row['n']) in train_combos

    df_train = df_merged[df_merged.apply(is_train, axis=1)].copy()

    # Z-score from train
    zscore_means = {}
    zscore_stds = {}
    for col in FEATURE_COLS_ZSCORE:
        vals = df_train[col].astype(float)
        zscore_means[col] = float(vals.mean())
        zscore_stds[col] = float(vals.std(ddof=0))
        if zscore_stds[col] < 1e-12:
            zscore_stds[col] = 1.0

    train_valid = df_train['loss'].dropna()
    failure_penalty = float(np.nanpercentile(train_valid, 99))
    df_train['loss_filled'] = df_train['loss'].fillna(failure_penalty)

    # Pivot train to vector
    def pivot_vector(df, label_col):
        feat_cols_local = [c for c in SAMPLE_FEATURE_COLS if c not in SAMPLE_KEYS]
        sample_df = df[SAMPLE_KEYS + feat_cols_local].drop_duplicates(
            subset=SAMPLE_KEYS).reset_index(drop=True)
        pivot = df.pivot_table(
            index=SAMPLE_KEYS, columns='delta',
            values=label_col, aggfunc='first'
        ).reset_index()
        result = pivot[SAMPLE_KEYS].merge(sample_df, on=SAMPLE_KEYS, how='left')
        Y = np.full((len(pivot), N_DELTAS), np.nan)
        for j, d in enumerate(DELTA_GRID):
            if d in pivot.columns:
                Y[:, j] = pivot[d].values
        Y = np.where(np.isnan(Y), failure_penalty, Y)
        return result, Y

    train_samples, Y_train = pivot_vector(df_train, 'loss_filled')
    log(f"  Train samples: {len(train_samples)}")

    # Build X_train with full features
    cols = []
    for col in FEATURE_COLS_ZSCORE:
        vals = train_samples[col].astype(float).values
        cols.append((vals - zscore_means[col]) / max(zscore_stds[col], 1e-12))
    for col in FEATURE_COLS_RAW:
        cols.append(train_samples[col].astype(float).values)
    X_train = np.column_stack(cols).astype(np.float32)

    # Train with seed 42
    log("  Training Vector-MLP-L6 (seed=42)...")
    t0 = time.time()
    target_scaler = StandardScaler()
    Y_train_scaled = target_scaler.fit_transform(Y_train)

    with warnings.catch_warnings():
        warnings.simplefilter('ignore', category=ConvergenceWarning)
        model = MLPRegressor(
            hidden_layer_sizes=MLP_HIDDEN_LAYERS,
            activation='relu', solver='adam',
            alpha=MLP_ALPHA, learning_rate_init=MLP_LR,
            max_iter=MLP_MAX_ITER, early_stopping=True,
            validation_fraction=MLP_VALIDATION_FRACTION,
            n_iter_no_change=MLP_N_ITER_NO_CHANGE,
            random_state=42, batch_size=MLP_BATCH_SIZE,
        )
        model.fit(X_train, Y_train_scaled)

    train_elapsed = time.time() - t0
    log(f"  Training done in {train_elapsed:.1f}s, n_iter={model.n_iter_}")

    # Evaluate on boundary and offgrid
    results = []

    for eval_label, df_eval_feat, df_eval_loss in [
        ("E4b_boundary", df_boundary_feat, df_boundary_loss),
        ("E4c_offgrid", df_offgrid_feat, df_offgrid_loss),
    ]:
        if df_eval_feat is None or len(df_eval_feat) == 0:
            continue

        # Build X_eval with same z-score params
        cols = []
        for col in FEATURE_COLS_ZSCORE:
            vals = df_eval_feat[col].astype(float).values
            cols.append((vals - zscore_means[col]) / max(zscore_stds[col], 1e-12))
        for col in FEATURE_COLS_RAW:
            cols.append(df_eval_feat[col].astype(float).values)
        X_eval = np.column_stack(cols).astype(np.float32)

        # Predict
        Y_pred = target_scaler.inverse_transform(model.predict(X_eval))
        Y_pred = np.clip(Y_pred, 0, None)

        # For each sample, select delta and look up true loss
        for i in range(len(df_eval_feat)):
            row = df_eval_feat.iloc[i]
            beta = float(row['beta'])
            goe = float(row['gamma_over_eta'])
            n_val = int(row['n'])
            rid = int(row['repeat_id'])

            best_delta_idx = int(np.argmin(Y_pred[i]))
            sel_delta = DELTA_GRID[best_delta_idx]

            # Look up true loss at selected delta
            match = df_eval_loss[
                (df_eval_loss['beta'] == beta) &
                (df_eval_loss['gamma_over_eta'] == goe) &
                (df_eval_loss['n'] == n_val) &
                (df_eval_loss['repeat_id'] == rid) &
                (df_eval_loss['delta'] == sel_delta)
            ]
            if len(match) > 0:
                true_loss = float(match.iloc[0]['loss'])
                if np.isnan(true_loss):
                    true_loss = failure_penalty
            else:
                true_loss = failure_penalty

            results.append({
                'track': eval_label,
                'model': 'Vector-MLP-L6-extrapolation',
                'beta': beta,
                'gamma_over_eta': goe,
                'n': n_val,
                'repeat_id': rid,
                'selected_delta': sel_delta,
                'true_loss': true_loss,
            })

    df_results = pd.DataFrame(results)
    if len(df_results) > 0:
        for track in df_results['track'].unique():
            sub = df_results[df_results['track'] == track]
            j1 = math.sqrt(sub['true_loss'].mean())
            log(f"  {track} Vector-MLP-L6 extrapolation J1={j1:.6f}")

    return df_results, train_elapsed


# ============================================================
# Main
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Study/01 Formal E4 Validation Analysis")
    parser.add_argument(
        '--tracks', type=str, default='e4a,e4b,e4c,e4d',
        help='Comma-separated tracks to run (e.g. "e4b,e4c"). '
             'Default: all tracks.')
    args = parser.parse_args()

    requested_tracks = set(t.strip().lower() for t in args.tracks.split(','))
    valid_tracks = {'e4a', 'e4b', 'e4c', 'e4d'}
    invalid = requested_tracks - valid_tracks
    if invalid:
        print(f"ERROR: Unknown tracks: {invalid}. Valid: {valid_tracks}")
        sys.exit(1)

    # ============================================================
    # Pre-validate required inputs for requested tracks (fail-closed)
    # ============================================================
    required_inputs = {
        'e4a': [MAIN_CHUNKS_DIR, MC_MANIFEST_PATH],
        'e4b': [MC_MANIFEST_PATH, BOUNDARY_PATH],
        'e4c': [MC_MANIFEST_PATH, OFFGRID_PATH],
        'e4d': [
            MAIN_CHUNKS_DIR, MC_MANIFEST_PATH, BOUNDARY_PATH, OFFGRID_PATH
        ],
    }
    try:
        preflight_check_inputs(requested_tracks, required_inputs)
    except PreflightError as e:
        print(f"ERROR: {e}")
        print("Aborting before any output is produced.")
        sys.exit(1)

    log("=" * 70)
    log("Study/01 Formal E4 — Validation Analysis")
    log(f"Started: {now_iso()}")
    log(f"Output: {E4_OUTPUT_DIR}")
    log(f"Tracks requested: {sorted(requested_tracks)}")
    log("=" * 70)

    overall_t0 = time.time()
    all_cost = []
    cost_e4a = pd.DataFrame()  # default empty for cost report logic

    # Track status tracking for accurate summary semantics
    track_status = {}
    for t in valid_tracks:
        if t in requested_tracks:
            track_status[t] = {'requested': True, 'status': 'pending'}
        else:
            track_status[t] = {'requested': False, 'status': 'not_requested'}

    # --- Load inputs from the same bytes used for their SHA256 records ---
    try:
        mc_manifest, mc_manifest_capability = read_json_with_provenance(
            MC_MANIFEST_PATH, 'main_grid_mc_manifest'
        )
        needs_main_grid = bool({'e4a', 'e4d'} & requested_tracks)
        if needs_main_grid:
            log("Loading 45 authoritative main-grid MC chunks...")
            df_mc, main_chunks_capability = load_authoritative_main_chunks()
            log(
                f"  Loaded: {len(df_mc)} rows from "
                f"{len(_expected_main_chunk_units())} chunks"
            )
        else:
            df_mc = pd.DataFrame()
            main_chunks_capability = None
    except PreflightError as exc:
        print(f"ERROR: {exc}")
        print("Aborting before any formal E4 output is produced.")
        sys.exit(1)

    # --- Check boundary/offgrid data availability ---
    # (Required inputs already validated above for requested tracks.)
    has_boundary = os.path.exists(BOUNDARY_PATH)
    has_offgrid = os.path.exists(OFFGRID_PATH)

    df_boundary = None
    df_offgrid = None
    boundary_capability = None
    offgrid_capability = None

    try:
        if has_boundary:
            df_boundary, boundary_capability = read_csv_with_provenance(
                BOUNDARY_PATH, 'boundary_risk_curves'
            )
            log(f"  Boundary data: {len(df_boundary)} rows")

        if has_offgrid:
            df_offgrid, offgrid_capability = read_csv_with_provenance(
                OFFGRID_PATH, 'offgrid_risk_curves'
            )
            log(f"  Off-grid data: {len(df_offgrid)} rows")
    except PreflightError as exc:
        print(f"ERROR: {exc}")
        print("Aborting before any formal E4 output is produced.")
        sys.exit(1)

    # E4d is fail-closed: validate all risk keys, frozen grids, disjoint data
    # roles, and generation provenance before any track writes formal output.
    e4d_gate = None
    df_boundary_feat = None
    df_offgrid_feat = None
    if 'e4d' in requested_tracks:
        e4d_input_capabilities = {
            'main_grid_chunks': main_chunks_capability,
            'main_grid_mc_manifest': mc_manifest_capability,
            'boundary_risk_curves': boundary_capability,
            'offgrid_risk_curves': offgrid_capability,
        }
        e4d_code_paths = {
            'e4_formal_validation': os.path.abspath(__file__),
            'e4_mc_generation': os.path.join(
                STUDY_CODE_DIR, 'run_E4_mc_generation.py'
            ),
            'main_mc_generation': os.path.join(
                STUDY_CODE_DIR, 'generate_mc_data.py'
            ),
            'study01_config': os.path.join(STUDY_CODE_DIR, 'config.py'),
            'sample_generation': os.path.join(
                PYTHON_DIR, 'studies', 'common', 'sample.py'
            ),
            'mdm_method': os.path.join(PYTHON_DIR, 'methods', 'mdm.py'),
            'study01_utils': os.path.join(STUDY_CODE_DIR, 'utils.py'),
        }
        try:
            e4d_gate, df_boundary_feat, df_offgrid_feat = (
                validate_e4d_preflight_contract(
                    df_mc, df_boundary, df_offgrid, mc_manifest,
                    e4d_input_capabilities, e4d_code_paths,
                )
            )
        except PreflightError as exc:
            print(f"ERROR: {exc}")
            print("Aborting before any formal E4 output is produced.")
            sys.exit(1)
        log("  E4d fail-closed/provenance contract: VALIDATED")

    # --- E4a: Feature ablation ---
    df_e4a = pd.DataFrame()
    if 'e4a' in requested_tracks:
        e4a_t0 = time.time()
        df_e4a, cost_e4a = run_e4a(df_mc)
        e4a_elapsed = time.time() - e4a_t0
        log(f"E4a total: {e4a_elapsed:.1f}s")
        all_cost.append({'track': 'E4a', 'elapsed_s': e4a_elapsed, 'note': 'feature ablation'})
        track_status['e4a']['status'] = 'completed'

        # Save E4a
        e4a_path = os.path.join(E4_OUTPUT_DIR, "E4a_feature_ablation.csv")
        df_e4a.to_csv(e4a_path, index=False)
        log(f"  Saved: {e4a_path}")
    else:
        log("E4a SKIPPED (not in --tracks)")

    # --- E4b: Boundary reference evaluation ---
    df_e4b = pd.DataFrame()
    e4b_summary = {}
    if 'e4b' in requested_tracks and df_boundary is not None:
        e4b_t0 = time.time()
        df_e4b, e4b_summary = evaluate_references(df_boundary, "E4b")
        e4b_elapsed = time.time() - e4b_t0
        e4b_path = os.path.join(E4_OUTPUT_DIR, "E4b_boundary_reference.csv")
        df_e4b.to_csv(e4b_path, index=False)
        log(f"  Saved: {e4b_path}")
        all_cost.append({'track': 'E4b', 'elapsed_s': e4b_elapsed, 'note': 'boundary reference evaluation'})
        track_status['e4b']['status'] = 'completed'
    elif 'e4b' not in requested_tracks:
        log("E4b SKIPPED (not in --tracks)")

    # --- E4c: Off-grid reference evaluation ---
    df_e4c = pd.DataFrame()
    e4c_summary = {}
    if 'e4c' in requested_tracks and df_offgrid is not None:
        e4c_t0 = time.time()
        df_e4c, e4c_summary = evaluate_references(df_offgrid, "E4c")
        e4c_elapsed = time.time() - e4c_t0
        e4c_path = os.path.join(E4_OUTPUT_DIR, "E4c_offgrid_reference.csv")
        df_e4c.to_csv(e4c_path, index=False)
        log(f"  Saved: {e4c_path}")
        all_cost.append({'track': 'E4c', 'elapsed_s': e4c_elapsed, 'note': 'offgrid reference evaluation'})
        track_status['e4c']['status'] = 'completed'
    elif 'e4c' not in requested_tracks:
        log("E4c SKIPPED (not in --tracks)")

    # --- E4d: Selector extrapolation diagnostic ---
    df_e4d = pd.DataFrame()
    e4d_train_time = 0
    e4d_skip = False

    if 'e4d' not in requested_tracks:
        log("E4d SKIPPED (not in --tracks)")
        # track_status['e4d'] already set to not_requested
    elif df_boundary is not None and df_offgrid is not None:
        try:
            # Compute loss for boundary/offgrid
            df_boundary_loss = compute_loss(df_boundary)
            df_offgrid_loss = compute_loss(df_offgrid)

            df_e4d, e4d_train_time = run_e4d(
                df_mc, df_boundary_feat, df_offgrid_feat,
                df_boundary_loss, df_offgrid_loss
            )
            e4d_path = os.path.join(E4_OUTPUT_DIR, "E4d_selector_extrapolation.csv")
            write_e4d_formal_output(df_e4d, e4d_path, e4d_gate)
            log(f"  Saved: {e4d_path}")
            all_cost.append({'track': 'E4d', 'elapsed_s': e4d_train_time,
                           'note': 'selector extrapolation diagnostic'})
            track_status['e4d']['status'] = 'completed'
        except PreflightError:
            # A contract failure is never downgraded to skipped_error.
            raise
        except Exception as e:
            log(f"  E4d FAILED: {type(e).__name__}: {e}")
            e4d_skip = True
            track_status['e4d']['status'] = 'skipped_error'
    else:
        log("  E4d SKIPPED: boundary/offgrid data not available")
        e4d_skip = True
        track_status['e4d']['status'] = 'skipped_no_input'

    # Write E4d skip reason ONLY if e4d was requested but could not run
    if e4d_skip and 'e4d' in requested_tracks:
        skip_path = os.path.join(E4_OUTPUT_DIR, "E4d_skip_reason.md")
        with open(skip_path, 'w') as f:
            f.write("# E4d Skip Reason\n\n")
            f.write("E4d selector extrapolation was skipped because ")
            if not has_boundary or not has_offgrid:
                f.write("boundary/offgrid MC data was not available.\n")
            else:
                f.write("of an execution error (see run log).\n")

    # --- Endpoint diagnostics ---
    endpoint_path = os.path.join(E4_OUTPUT_DIR, "endpoint_diagnostics.csv")
    endpoint_dfs = []
    for df_ref, label in [(df_e4b, 'E4b'), (df_e4c, 'E4c')]:
        if len(df_ref) > 0:
            for model in df_ref['model'].unique():
                sub = df_ref[df_ref['model'] == model]
                p_extreme = float(sub['selected_delta'].isin([0.00, 0.02, 0.48, 0.50]).mean())
                endpoint_dfs.append({
                    'track': label,
                    'model': model,
                    'pooled_P_extreme': p_extreme,
                    'n_samples': len(sub),
                })
    if endpoint_dfs:
        pd.DataFrame(endpoint_dfs).to_csv(endpoint_path, index=False)

    # --- Near-optimal diagnostics ---
    near_path = os.path.join(E4_OUTPUT_DIR, "near_optimal_diagnostics.csv")
    near_dfs = []
    for df_ref, label in [(df_e4b, 'E4b'), (df_e4c, 'E4c')]:
        if len(df_ref) > 0:
            for model in df_ref['model'].unique():
                sub = df_ref[df_ref['model'] == model]
                near_dfs.append({
                    'track': label,
                    'model': model,
                    'mean_regret': float(sub['regret'].mean()),
                    'mean_rel_regret': float(sub['rel_regret'].mean()),
                    'near_1pct_rate': float((sub['rel_regret'] <= 0.01).mean()),
                    'near_2pct_rate': float((sub['rel_regret'] <= 0.02).mean()),
                    'near_5pct_rate': float((sub['rel_regret'] <= 0.05).mean()),
                })
    if near_dfs:
        pd.DataFrame(near_dfs).to_csv(near_path, index=False)

    # --- Cost report ---
    cost_path = os.path.join(E4_OUTPUT_DIR, "cost_report.csv")
    # Add per-fold costs from E4a
    all_cost_rows = []
    all_cost_rows.extend([c for c in all_cost])
    # Add detailed E4a cost
    for _, row in cost_e4a.iterrows():
        all_cost_rows.append(dict(row))
    write_merged_cost_report(cost_path, all_cost_rows, requested_tracks)

    # --- Split report (E4a-specific, only if E4a was requested) ---
    if 'e4a' in requested_tracks:
        split_path = os.path.join(E4_OUTPUT_DIR, "split_report.csv")
        split_rows = []
        for fold in get_combo_split():
            for combo in fold['test_combos']:
                split_rows.append({
                    'fold': fold['fold_name'],
                    'test_beta': combo[0],
                    'test_gamma_over_eta': combo[1],
                    'test_n': combo[2],
                })
        pd.DataFrame(split_rows).to_csv(split_path, index=False)

    # --- Manifest ---
    git_commit = (
        e4d_gate.generation_git_commit
        if e4d_gate is not None else get_project_git_info_strict()
    )
    total_elapsed = time.time() - overall_t0

    # Build output_files list dynamically: only files that were actually produced this run
    output_files_actual = []
    output_files_actual.append("cost_report.csv")
    if 'e4a' in requested_tracks and len(df_e4a) > 0:
        output_files_actual.append("E4a_feature_ablation.csv")
        output_files_actual.append("split_report.csv")
    if len(df_e4b) > 0:
        output_files_actual.append("E4b_boundary_reference.csv")
    if len(df_e4c) > 0:
        output_files_actual.append("E4c_offgrid_reference.csv")
    if endpoint_dfs:
        output_files_actual.append("endpoint_diagnostics.csv")
    if near_dfs:
        output_files_actual.append("near_optimal_diagnostics.csv")
    if not e4d_skip and len(df_e4d) > 0:
        output_files_actual.append("E4d_selector_extrapolation.csv")
    elif e4d_skip and 'e4d' in requested_tracks:
        output_files_actual.append("E4d_skip_reason.md")

    # Use track-specific manifest/summary/run_log filenames when not all tracks are requested
    is_full_run = requested_tracks == valid_tracks
    if is_full_run:
        manifest_name = "manifest.json"
        summary_name = "summary.json"
        run_log_name = "run_log.txt"
    else:
        track_tag = "_".join(sorted(requested_tracks))
        manifest_name = f"manifest_{track_tag}.json"
        summary_name = f"summary_{track_tag}.json"
        run_log_name = f"run_log_{track_tag}.txt"

    output_files_actual.append(manifest_name)
    output_files_actual.append(summary_name)
    output_files_actual.append(run_log_name)

    manifest = {
        "run_id": "E4_formal_validation_v1",
        "created_at": now_iso(),
        "status": "FORMAL",
        "tracks_requested": sorted(requested_tracks),
        "is_full_run": is_full_run,
        "track_status": track_status,
        "code_entry": "code/run_E4_formal_validation.py",
        "mc_generation_entry": "code/run_E4_mc_generation.py",
        "git_commit": git_commit,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "input_data": {
            "main_grid_source": "artifacts/formal/shared_data/chunks/chunk_####_mdm.csv",
            "main_grid_chunk_count": (
                len(_expected_main_chunk_units())
                if main_chunks_capability is not None else 0
            ),
            "main_grid_aggregate_compat_path": MC_AGGREGATE_PATH,
            "main_grid_aggregate_used": False,
            "mc_manifest": mc_manifest.get("run_id", "unknown"),
            "mc_git_commit": mc_manifest.get("git_commit", "unknown"),
            "boundary_path": BOUNDARY_PATH,
            "offgrid_path": OFFGRID_PATH,
            "mc_seed_namespace": mc_manifest.get("seed_namespace", SEED_NAMESPACE),
        },
        "method_versions": {
            "mdm": {
                "source": "python/methods/mdm.py",
                "class": "MDM",
                "run_signature": "run(offset: float, gamma_steps=60, rank_method='bernard')",
            },
            "sample": {
                "source": "python/studies/common/sample.py",
                "function": "generate_sample(beta, eta, gamma, n, repeat_id, seed)",
            },
            "mlp": {
                "class": "sklearn.neural_network.MLPRegressor",
                "hidden_layer_sizes": list(MLP_HIDDEN_LAYERS),
                "max_iter": MLP_MAX_ITER,
                "early_stopping": True,
            },
        },
        "parameter_grids": {
            "e4a_main_grid": {
                "beta": BETA_GRID,
                "eta": ETA_GRID,
                "gamma_over_eta": GAMMA_OVER_ETA_GRID,
                "n": N_GRID,
            },
            "e4b_boundary_combos": [
                {"id": cid, "beta": b, "gamma_over_eta": g, "n": n}
                for cid, b, g, n in E4B_BOUNDARY_COMBOS
            ],
            "e4c_offgrid_combos": [
                {"id": cid, "beta": b, "gamma_over_eta": g, "n": n}
                for cid, b, g, n in E4C_OFFGRID_COMBOS
            ],
        },
        "delta_grid": DELTA_GRID,
        "repeats": {
            "e4a": R_MAIN,
            "e4b": "R=500 (from mc_generation)",
            "e4c": "R=500 (from mc_generation)",
        },
        "seeds": STABILITY_SEEDS,
        "metrics_contract": {
            "J1": "sqrt(mean_i[((beta_hat-beta)/beta)^2 + ((eta_hat-eta)/eta)^2 + ((gamma_hat-gamma)/eta)^2])",
        },
        "feature_contract": {
            "vector_input": SAMPLE_FEATURE_COLS,
            "banned_fields": list(BANNED_FIELDS),
            "zscore_applied": FEATURE_COLS_ZSCORE,
            "zscore_source": "training_set_only",
            "raw_passthrough": FEATURE_COLS_RAW,
        },
        "total_elapsed_s": total_elapsed,
        "output_files": output_files_actual,
        "notes": [
            "E4a/E4d use the 45 authoritative main-grid MDM chunks (read-only, frozen identity order).",
            "E4b/E4c use new MDM risk curves generated by run_E4_mc_generation.py.",
            "E4d is a diagnostic, not a deployment-ready continuous-space proof.",
            "E4b uses Option C: reference-only evaluation at boundary (no NN deployment).",
            "E4c is evaluation-only. Continuous-space training is E3c.",
        ],
    }

    if e4d_gate is not None:
        manifest = attach_e4d_gate_to_manifest(
            manifest, e4d_gate
        )

    # output_files_actual already includes E4d outputs if applicable

    with open(os.path.join(E4_OUTPUT_DIR, manifest_name), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, default=str)

    # --- Summary ---
    summary = {
        "run_id": manifest["run_id"],
        "created_at": manifest["created_at"],
        "status": "FORMAL",
        "total_elapsed_s": total_elapsed,
        "e4a_summary": {},
        "e4b_summary": e4b_summary,
        "e4c_summary": e4c_summary,
        "track_status": track_status,
    }

    # E4a aggregate: mean/std across seeds per group
    if len(df_e4a) > 0:
        for group in df_e4a['feature_group'].unique():
            sub = df_e4a[df_e4a['feature_group'] == group]
            j1_values = sub['pooled_J1'].dropna().values
            if len(j1_values) > 0:
                summary["e4a_summary"][group] = {
                    "mean_J1": float(np.mean(j1_values)),
                    "std_J1": float(np.std(j1_values)),
                    "n_runs": len(j1_values),
                    "mean_endpoint_rate": float(sub['endpoint_rate'].mean()),
                    "mean_near_5pct": float(sub['near_5pct'].mean()),
                }

    with open(os.path.join(E4_OUTPUT_DIR, summary_name), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    # --- Run log ---
    with open(os.path.join(E4_OUTPUT_DIR, run_log_name), 'w', encoding='utf-8') as f:
        f.write(f"Study/01 Formal E4 Validation Analysis\n")
        f.write(f"Tracks: {sorted(requested_tracks)}\n")
        f.write(f"Started: {manifest['created_at']}\n")
        f.write(f"Git commit: {git_commit}\n")
        f.write(f"Total elapsed: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)\n\n")
        for line in log_lines:
            f.write(line + "\n")

    log(f"\n{'='*70}")
    log(f"FORMAL E4 ANALYSIS COMPLETE")
    log(f"  Total elapsed: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
    log(f"  Output: {E4_OUTPUT_DIR}")
    log(f"{'='*70}")


if __name__ == "__main__":
    main()
