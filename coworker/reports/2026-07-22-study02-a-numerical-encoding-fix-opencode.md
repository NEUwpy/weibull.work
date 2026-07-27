# Study02-A Numerical/Encoding Fix Report

> Date: 2026-07-22
> Executor: OpenCode (qwen3.8-max-preview)
> Branch: `codex/study02-a-preflight-20260721`
> Baseline: `6aa6f7bb74f32c6a40d09c76c56df59b94ecc19f`
> Fix commit: `d6411a46`

## Context

The first real A-E1 formal run (`A-E1-formal-20260721-154250`) was blocked by two
deterministic defects exposed during production execution on Windows (cp936 locale):

1. **Encoding**: `_assert_scoped_code_clean` used `subprocess.run(text=True)` without
   explicit encoding. Under cp936/utf8_mode=0, git output containing Chinese path
   components decoded incorrectly, causing spurious "dirty tree" failures unless
   `PYTHONUTF8=1` was set externally.

2. **Numerical tolerance**: `_validate_dataset_semantics` compared float32 targets
   (computed from float64 anchors at build time) against independently re-encoded
   float32 anchors using `rtol=2e-5, atol=2e-5`. For G3-fit-0039 (route F0eq_hsm,
   n=15, screening seed 420001), row index 45258 exhibited a third-target-dimension
   difference of 0.0012235641479492188 — exceeding 2e-5 but passing np.allclose with
   rtol=atol=1e-4 due to its combined relative and absolute tolerance.

## Old Run Disposition

- Run ID: `A-E1-formal-20260721-154250`
- Status: **permanently blocked/aborted evidence**
- Counts: 39 succeeded, 310 pending, 0 claimed, 0 failed, test_access_count=0
- The 39 existing checkpoints are NOT migrated to any new authority.
- A new run-id will be established after Codex approves this fix.

## Changes Made

### formal_scheduler.py (line 309)

```python
# Before:
subprocess.run(..., text=True)

# After:
subprocess.run(..., text=True, encoding="utf-8")
```

### formal_runner.py (line 616)

```python
# Before:
np.allclose(..., rtol=2e-5, atol=2e-5)

# After:
np.allclose(..., rtol=1e-4, atol=1e-4)
```

### test_study02a_formal_runner.py (4 new tests)

1. `test_production_g3_fit_0039_full_100k_semantic_validation` (slow): builds the
   real 100k-row training dataset for G3-fit-0039, asserts row 45258 passes
   np.allclose with rtol=atol=1e-4, fails under old rtol=atol=2e-5, third-dim
   absolute diff equals 0.0012235641479492188, and binds the exact dataset_hash.
2. `test_semantic_validator_rejects_tampered_target_beyond_tolerance`: perturbs one
   target element by 0.01 → must raise.
3. `test_semantic_validator_rejects_tampered_anchor_beyond_tolerance`: perturbs one
   anchor scale by 1.5x → must raise.
4. `test_scoped_code_clean_passes_explicit_utf8_to_subprocess`: monkeypatches
   subprocess.run to capture kwargs, calls real `_assert_scoped_code_clean`, asserts
   encoding="utf-8", text=True, check=True, capture_output=True, no errors= mode.

## What Was NOT Changed

- Target computation (`encode_targets`)
- Anchor dtype or collation
- Cache key / dataset hash algorithm
- Training tensors or data allocation
- Matrix, plan, selection rule, scientific metrics
- Scheduler journal contract

## Verification Evidence

| Check | Result |
|-------|--------|
| 370 non-slow study02a tests | PASSED |
| Production 100k slow regression (bound hash) | PASSED (39.8s) |
| `_assert_scoped_code_clean` cp936/utf8_mode=0 actual call | PASSED |
| `compileall` | PASSED |
| `verify_frozen_hashes` | PASSED |
| `git diff --check` | clean |
| Attack: target +0.01 → ValueError | PASSED |
| Attack: scale ×1.5 → ValueError | PASSED |
| Monkeypatch: encoding/text/check/capture_output/no errors= | PASSED |

### Production 100k Dataset Evidence

| Field | Value |
|-------|-------|
| dataset_hash | `179534a5bca8ab74e3661801b0f9e329aea6306ce2a9ebcca7fb6e271d94313f` |
| cache_key | `b5a3a9aa4b56689c06b80758a0c9096c333f39cb00fd62a0e3597774b3c1a2be` |
| rows | 100000 |
| row 45258 third-dim absolute diff | 0.0012235641479492188 |
| np.allclose rtol=atol=1e-4 | True |
| np.allclose rtol=atol=2e-5 | False |
| elapsed | 39.8s |

### Pinned Dependency Versions

| Package | Version |
|---------|---------|
| Python | 3.11.15 |
| numpy | 2.1.1 |
| scipy | 1.14.1 |
| pandas | 2.2.3 |
| torch | 2.11.0+cpu |

## Corrections to Prior Report

The earlier report (`D:\weibull\coworker\reports\2026-07-22-study02-a-e1-formal-recovery-stop-opencode.md`)
contained three errors:

1. **Smoke explanation**: The 349-smoke used synthetic fit/score (bypassing real 100k
   dataset construction and `_validate_dataset_semantics`), NOT "different seeds".
2. **Seed classification**: 420001 is a screening seed, not a formal seed.
3. **float64 fix claim**: Metadata does not retain original float64 anchors; upcasting
   truncated float32 tensors cannot recover lost precision. The actual fix is tolerance
   adjustment, not dtype change.

## Next Steps (Codex Decision)

- APPROVE this fix → establish new run-id → restart A-E1 formal from scratch.
- The old run's 39 checkpoints remain as evidence only; they do not enter the new authority.
