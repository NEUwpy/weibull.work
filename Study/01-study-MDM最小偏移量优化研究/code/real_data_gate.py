"""
Study/01 — Real Data Admission Gate (R3 preflight)

Per frozen contract 07-剩余实验目标与规划.md §4.3:

  1. Verify data source identity, version/URL, license, and download SHA256.
  2. Minimum 60 complete, uncensored, single-failure-mode lifetimes; stop if < 60.
  3. Freeze Weibull-fit check method and pass/fail threshold before viewing
     method comparison results.
  4. On gate failure: register ``dataset-ineligible`` and stop; do NOT run
     Default / L2 / NN comparison and do NOT interpret as selector failure.

This module is the *admission* gate only. The formal run script
(``run_real_data_validation.py``) calls it before any method comparison.

Expected data directory layout:
    artifacts/formal/real_data/
        <dataset_id>/
            source.json          # provenance manifest (see RealDataSource)
            lifetimes.csv        # single column: failure_time (float)
"""

import os
import json
import hashlib
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd

# ── Weibull fit helpers ──

def _weibull_cdf(x, beta, eta, gamma=0.0):
    """Three-parameter Weibull CDF."""
    z = np.maximum((x - gamma) / eta, 0.0)
    return 1.0 - np.exp(-z ** beta)


def _estimate_weibull_ols(lifetimes):
    """Quick OLS-based Weibull parameter estimates (not MDM — deliberately
    simple and independent). Returns (beta, eta, gamma=0) or (NaN, NaN, NaN)
    on failure.
    """
    n = len(lifetimes)
    if n < 10:
        return float('nan'), float('nan'), float('nan')
    t_sorted = np.sort(lifetimes.astype(float))
    ranks = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
    y = np.log(-np.log(1.0 - ranks))
    valid = np.isfinite(y) & (t_sorted > 0)
    if valid.sum() < 5:
        return float('nan'), float('nan'), float('nan')
    x = np.log(t_sorted[valid])
    y = y[valid]
    # y = beta * x - beta * log(eta)  =>  y = a + b*x
    b = np.polyfit(x, y, 1)[0]
    if b <= 0:
        return float('nan'), float('nan'), float('nan')
    beta = b
    a = np.mean(y - b * x)
    eta = math.exp(-a / beta)
    return float(beta), float(eta), 0.0


# ── Data source provenance ──

class RealDataSource:
    """Immutable description of a real dataset's provenance.

    Once constructed, all fields are read-only. The instance can be
    serialised to JSON for the manifest.
    """
    __slots__ = (
        'dataset_id', 'name', 'source_url', 'version',
        'license_name', 'license_url',
        'download_sha256', 'original_filename',
        'failure_mode', 'censoring_semantics',
        'n_total', 'n_uncensored',
        'inclusion_rule', 'exclusion_rule',
    )

    def __init__(self, **kwargs):
        for key in self.__slots__:
            setattr(self, key, kwargs.get(key))

    def to_dict(self):
        return {key: getattr(self, key) for key in self.__slots__}

    def validate(self):
        """Raise ValueError if any required field is missing or invalid."""
        required = [
            'dataset_id', 'source_url', 'license_name', 'download_sha256',
            'n_total', 'n_uncensored',
        ]
        for field in required:
            value = getattr(self, field, None)
            if value is None:
                raise ValueError(f"RealDataSource.{field} is required")
        if self.n_total < 0:
            raise ValueError("n_total must be >= 0")
        if self.n_uncensored < 0:
            raise ValueError("n_uncensored must be >= 0")
        if self.n_uncensored > self.n_total:
            raise ValueError("n_uncensored cannot exceed n_total")
        sha = self.download_sha256
        if not isinstance(sha, str) or len(sha) != 64:
            raise ValueError(
                "download_sha256 must be a 64-character hex string"
            )

    @classmethod
    def from_json(cls, path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**data)


# ── Gate logic ──

class RealDataGateResult:
    """Outcome of the real-data admission gate.

    ``passed`` is True only when all checks succeed.
    ``reason`` explains the failure (empty string on pass).
    ``diagnostics`` holds computed metrics for later reporting.
    """
    __slots__ = ('passed', 'reason', 'diagnostics', 'source')

    def __init__(self, passed, reason='', diagnostics=None, source=None):
        self.passed = bool(passed)
        self.reason = str(reason)
        self.diagnostics = diagnostics or {}
        self.source = source


# Pre-declared Weibull-fit thresholds (frozen BEFORE viewing any method
# comparison results).
WEIBULL_FIT_MIN_R2 = 0.70     # minimum R-squared for OLS Weibull fit
WEIBULL_FIT_MIN_N = 10        # minimum sample size for fit estimation
MIN_UNCENSORED_LIFETIMES = 60  # minimum complete, uncensored lifetimes


def run_real_data_gate(data_dir, source_json_path=None):
    """Run the real-data admission gate for a dataset directory.

    Args:
        data_dir: path to the dataset directory (contains lifetimes.csv
                  and optionally source.json).
        source_json_path: optional override for the source manifest.

    Returns:
        RealDataGateResult with passed=True/False.
    """
    source_path = source_json_path or os.path.join(data_dir, 'source.json')
    if not os.path.exists(source_path):
        return RealDataGateResult(
            False, f"Source manifest not found: {source_path}"
        )

    try:
        source = RealDataSource.from_json(source_path)
        source.validate()
    except (ValueError, json.JSONDecodeError) as exc:
        return RealDataGateResult(
            False, f"Source manifest invalid: {exc}"
        )

    lifetimes_path = os.path.join(data_dir, 'lifetimes.csv')
    if not os.path.exists(lifetimes_path):
        return RealDataGateResult(
            False, f"Lifetimes file not found: {lifetimes_path}"
        )

    try:
        df = pd.read_csv(lifetimes_path)
    except Exception as exc:
        return RealDataGateResult(
            False, f"Cannot read lifetimes CSV: {exc}"
        )

    # ── Check 1: Minimum uncensored lifetimes ──
    if source.n_uncensored < MIN_UNCENSORED_LIFETIMES:
        return RealDataGateResult(
            False,
            f"n_uncensored={source.n_uncensored} < "
            f"minimum {MIN_UNCENSORED_LIFETIMES}",
            source=source,
        )

    # ── Check 2: Data columns ──
    if 'failure_time' not in df.columns:
        if len(df.columns) == 1:
            df.rename(columns={df.columns[0]: 'failure_time'}, inplace=True)
        else:
            return RealDataGateResult(
                False,
                "lifetimes.csv must have a 'failure_time' column",
                source=source,
            )

    lifetimes = df['failure_time'].dropna().astype(float).values
    if len(lifetimes) < MIN_UNCENSORED_LIFETIMES:
        return RealDataGateResult(
            False,
            f"Actual non-NA lifetimes ({len(lifetimes)}) < "
            f"minimum {MIN_UNCENSORED_LIFETIMES}",
            source=source,
        )

    # ── Check 3: Weibull fit pre-check ──
    if len(lifetimes) < WEIBULL_FIT_MIN_N:
        return RealDataGateResult(
            False,
            f"Too few lifetimes for Weibull fit check "
            f"({len(lifetimes)} < {WEIBULL_FIT_MIN_N})",
            source=source,
        )
    if np.any(lifetimes <= 0):
        return RealDataGateResult(
            False,
            "Lifetimes contain non-positive values",
            source=source,
        )

    beta_hat, eta_hat, gamma_hat = _estimate_weibull_ols(lifetimes)
    if not all(np.isfinite([beta_hat, eta_hat])):
        return RealDataGateResult(
            False,
            "Weibull OLS fit failed — non-finite parameter estimates",
            source=source,
        )

    # Compute R-squared for fit quality
    n = len(lifetimes)
    t_sorted = np.sort(lifetimes)
    ranks = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
    f_hat = _weibull_cdf(t_sorted, beta_hat, eta_hat, gamma_hat)
    ss_res = np.sum((ranks - f_hat) ** 2)
    ss_tot = np.sum((ranks - np.mean(ranks)) ** 2)
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 0.0

    if r_squared < WEIBULL_FIT_MIN_R2:
        return RealDataGateResult(
            False,
            f"Weibull fit R²={r_squared:.4f} < "
            f"threshold {WEIBULL_FIT_MIN_R2}",
            diagnostics={
                'beta_hat': beta_hat,
                'eta_hat': eta_hat,
                'gamma_hat': gamma_hat,
                'r_squared': r_squared,
                'fit_method': 'OLS',
            },
            source=source,
        )

    # ── Gate passed ──
    diagnostics = {
        'n_total': int(source.n_total),
        'n_uncensored': int(source.n_uncensored),
        'n_loaded': int(len(lifetimes)),
        'lifetime_min': float(np.min(lifetimes)),
        'lifetime_max': float(np.max(lifetimes)),
        'lifetime_median': float(np.median(lifetimes)),
        'lifetime_mean': float(np.mean(lifetimes)),
        'beta_hat': float(beta_hat),
        'eta_hat': float(eta_hat),
        'gamma_hat': float(gamma_hat),
        'r_squared': float(r_squared),
        'fit_method': 'OLS',
        'weibull_fit_min_r2': WEIBULL_FIT_MIN_R2,
        'min_uncensored': MIN_UNCENSORED_LIFETIMES,
    }

    return RealDataGateResult(
        True,
        diagnostics=diagnostics,
        source=source,
    )
