# Ch5 β–profile Lightweight Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This shared worktree must not be committed or staged.

**Goal:** Produce a reproducible 300-sample audit of whether MDM profile-curve geometry varies systematically with true $\beta$, then update Ch5 with wording bounded by the observed evidence.

**Architecture:** A standalone Study/01 analysis module regenerates the sealed E1/E2 samples from their seed contract, obtains one real `MDM.run(trace=True, offset=0.1)` trace per sample, extracts interpolation and local-slope diagnostics, and writes fail-closed CSV/JSON artifacts. Pure helper functions are tested independently before the formal run; an artifact-contract test checks the completed output.

**Tech Stack:** Python 3, NumPy, pandas, SciPy, pytest, existing `python/methods/mdm.py`, existing `python/studies/common/sample.py`.

**Execution status:** Completed in the current shared `main` worktree without staging or committing. Formal run produced 300 rows and the final joint verification reported 27 passed.

---

## File map

- Create `Study/01-study-MDM最小偏移量优化研究/code/analyze_beta_profile_audit.py`: design enumeration, trace extraction, aggregation, validation, artifact writing and CLI.
- Create `python/tests/test_study01_beta_profile_audit.py`: RED/GREEN helper, real-trace smoke and formal artifact contracts.
- Create `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E2_beta_profile_audit/*`: formal CSV/JSON outputs generated only after validation.
- Modify `Study/01-study-MDM最小偏移量优化研究/draft-Ch5-初稿.md`: replace the unsupported mechanism hypothesis with the audit-supported bounded statement, or delete it if direction is inconsistent.
- Modify `Study/01-study-MDM最小偏移量优化研究/01-证据索引.md`, `03-论文骨架.md`, `04-待复核清单.md`, and `06-grill-me-论文完善续接记录.md`: register evidence, decision and verification state.

### Task 1: Pure diagnostic helpers

**Files:**
- Create: `python/tests/test_study01_beta_profile_audit.py`
- Create: `Study/01-study-MDM最小偏移量优化研究/code/analyze_beta_profile_audit.py`

- [ ] **Step 1: Write failing tests for the fixed design and curve geometry helpers**

```python
def test_build_design_has_exact_300_unique_samples():
    design = audit.build_design()
    assert len(design) == 300
    assert design["repeat_id"].min() == 0
    assert design["repeat_id"].max() == 19
    assert not design.duplicated(["beta", "n", "repeat_id"]).any()

def test_interpolate_gradient_brackets_true_gamma():
    points = [{"gamma": 0.8, "gradient": 0.4}, {"gamma": 0.2, "gradient": 0.1}]
    assert audit.interpolate_gradient(points, 0.5) == pytest.approx(0.25)

def test_local_gradient_slope_uses_nearest_seven_nonvirtual_points():
    points = [
        {"gamma": float(g), "gradient": 2.0 * g + 1.0, "virtual": g == 9}
        for g in range(10)
    ]
    assert audit.local_gradient_slope(points, target_gamma=4.0, k=7) == pytest.approx(2.0)

def test_direction_consistency_requires_three_same_nonzero_signs():
    assert audit.direction_consistent([0.4, 0.2, 0.1])
    assert not audit.direction_consistent([0.4, -0.2, 0.1])
    assert not audit.direction_consistent([0.4, 0.0, 0.1])
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```text
python -m pytest python/tests/test_study01_beta_profile_audit.py -q
```

Expected: collection/import failure because `analyze_beta_profile_audit.py` does not exist.

- [ ] **Step 3: Implement the minimal pure helpers**

```python
BETA_GRID = [1.5, 2.0, 2.5, 4.0, 5.0]
N_GRID = [7, 10, 20]
REPEAT_IDS = range(20)

def build_design():
    return pd.DataFrame(
        {"beta": beta, "eta": 1.0, "gamma": 0.5,
         "gamma_over_eta": 0.5, "n": n, "repeat_id": repeat_id}
        for beta in BETA_GRID for n in N_GRID for repeat_id in REPEAT_IDS
    )

def _finite_nonvirtual_points(points):
    return [p for p in points if not p.get("virtual", False)
            and np.isfinite(p["gamma"]) and np.isfinite(p["gradient"])]

def interpolate_gradient(points, target_gamma):
    ordered = sorted(_finite_nonvirtual_points(points), key=lambda p: p["gamma"])
    xs = np.asarray([p["gamma"] for p in ordered], dtype=float)
    ys = np.asarray([p["gradient"] for p in ordered], dtype=float)
    if target_gamma < xs[0] or target_gamma > xs[-1]:
        raise ValueError("true gamma is outside the finite trace interval")
    return float(np.interp(target_gamma, xs, ys))

def local_gradient_slope(points, target_gamma, k=7):
    candidates = sorted(
        _finite_nonvirtual_points(points),
        key=lambda p: (abs(p["gamma"] - target_gamma), p["gamma"]),
    )[:k]
    if len(candidates) != k:
        raise ValueError(f"need exactly {k} finite nonvirtual points")
    return float(np.polyfit(
        [p["gamma"] for p in candidates],
        [p["gradient"] for p in candidates], 1,
    )[0])

def direction_consistent(values):
    signs = [int(np.sign(value)) for value in values]
    return len(signs) == 3 and 0 not in signs and len(set(signs)) == 1
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run the same pytest command. Expected: four helper tests pass.

### Task 2: Real MDM trace extraction and fail-closed aggregation

**Files:**
- Modify: `python/tests/test_study01_beta_profile_audit.py`
- Modify: `Study/01-study-MDM最小偏移量优化研究/code/analyze_beta_profile_audit.py`

- [ ] **Step 1: Add failing tests for one real trace and trend aggregation**

```python
def test_extract_one_real_trace_has_finite_contract_fields():
    row = audit.build_design().iloc[0].to_dict()
    result = audit.extract_sample_metrics(row)
    for name in audit.METRIC_COLS:
        assert np.isfinite(result[name])
    assert result["solution_strategy"] in {"truncated_at_zero", "brent_root"}

def test_compute_trends_reports_each_n_and_pooled():
    frame = pd.DataFrame(
        {"beta": [1.5, 2.0, 2.5, 4.0, 5.0] * 3,
         "n": np.repeat([7, 10, 20], 5),
         "gradient_at_zero": [1, 2, 3, 4, 5] * 3}
    )
    trends = audit.compute_trends(frame, ["gradient_at_zero"])
    assert set(trends["scope"]) == {"n=7", "n=10", "n=20", "pooled"}
    assert trends.query("scope != 'pooled'")["spearman_rho"].tolist() == pytest.approx([1, 1, 1])
```

- [ ] **Step 2: Run these tests and verify RED**

Expected: missing `extract_sample_metrics`, `compute_trends`, or `METRIC_COLS`.

- [ ] **Step 3: Implement extraction, aggregation and validation**

Use `generate_sample(beta, eta, gamma, n, repeat_id, seed="study01_v1")`, instantiate `MDM(sample)`, and call `run(trace=True, offset=0.1)`. Read `mdm.trace_data["grad_gamma_curve"]` and `mdm.last_solution_info`; compute the five continuous diagnostics from the confirmed contract. Implement `summarize_by_beta_n` with median/Q1/Q3 and strategy counts, and `compute_trends` with `scipy.stats.spearmanr` separately for each $n$ plus pooled. Reject non-finite metrics, duplicate keys, wrong row counts, wrong cell counts, or missing scopes before artifact writes.

- [ ] **Step 4: Run the focused tests and verify GREEN**

Expected: helper and real-trace tests pass without writing formal artifacts.

### Task 3: Formal artifact writer and 300-sample run

**Files:**
- Modify: `python/tests/test_study01_beta_profile_audit.py`
- Modify: `Study/01-study-MDM最小偏移量优化研究/code/analyze_beta_profile_audit.py`
- Create: `Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E2_beta_profile_audit/`

- [ ] **Step 1: Add a failing artifact-contract test**

The test requires `profile_metrics.csv`, `by_beta_n.csv`, `trend_summary.csv`, `summary.json`, and `manifest.json`; exactly 300 metric rows, 15 aggregate rows, four scopes per metric, and explicit `causal_claim_allowed=false`.

- [ ] **Step 2: Run only the artifact-contract test and verify RED**

Expected: output directory or required files absent.

- [ ] **Step 3: Implement atomic artifact writing and CLI**

Write all outputs to a temporary sibling directory, validate them, then replace individual destination files. Include the fixed grid, repeat IDs, seed namespace, exact MDM call, code version, workspace dirty flag, row counts, metric definitions, direction-consistency booleans, and the bounded wording in JSON. The CLI takes no experiment-design overrides so the formal contract cannot drift silently.

- [ ] **Step 4: Run the formal audit**

Run:

```text
python Study/01-study-MDM最小偏移量优化研究/code/analyze_beta_profile_audit.py
```

Expected: progress reaches 300/300, then prints output paths and elapsed time with exit code 0.

- [ ] **Step 5: Run the full audit test and verify GREEN**

Run:

```text
python -m pytest python/tests/test_study01_beta_profile_audit.py -q
```

Expected: all helper, real-trace and artifact-contract tests pass.

### Task 4: Evidence interpretation and manuscript synchronization

**Files:**
- Modify: `Study/01-study-MDM最小偏移量优化研究/draft-Ch5-初稿.md`
- Modify: `Study/01-study-MDM最小偏移量优化研究/01-证据索引.md`
- Modify: `Study/01-study-MDM最小偏移量优化研究/03-论文骨架.md`
- Modify: `Study/01-study-MDM最小偏移量优化研究/04-待复核清单.md`
- Modify: `Study/01-study-MDM最小偏移量优化研究/06-grill-me-论文完善续接记录.md`

- [ ] **Step 1: Read `trend_summary.csv` and `by_beta_n.csv` without rounding away sign changes**

Record the exact within-$n$ Spearman coefficients and the extreme-$\beta$ medians/IQRs for each profile metric.

- [ ] **Step 2: Apply the stop rule**

If the selected profile-geometry metric has inconsistent directions across $n$, delete the mechanism explanation. If consistent, replace it with the bounded sentence “profile 曲线几何随 $\beta$ 系统变化，与该机制解释一致”, followed by exact effect descriptors and the explicit statement that the audit does not identify a causal tail-shape mechanism.

- [ ] **Step 3: Synchronize the evidence index and grill continuation files**

Register this as a lightweight mechanism audit, not a new formal E-number and not E4. Mark Question 50 as confirmed and implemented; set Question 51 as not yet asked.

### Task 5: Fresh verification

- [ ] **Step 1: Run the joint Study/01 test suite**

```text
python -m pytest python/tests/test_study01_beta_profile_audit.py python/tests/test_study01_e1_e2_crossfit.py python/tests/test_mdm_s49.py python/tests/test_study01_framework_figure_contract.py python/tests/test_study01_figure1_contract.py python/tests/test_study01_ch6_workflow_figure_contract.py python/tests/test_study01_fig3_ladder_contract.py -q
```

Expected: zero failures.

- [ ] **Step 2: Verify artifact values and prohibited claims**

Check exact row/cell/scope counts from CSV/JSON and search Ch5 for unsupported “证明/导致/机制已确认” wording around the audit paragraph.

- [ ] **Step 3: Run whitespace verification**

```text
git diff --check
```

Expected: exit code 0; existing line-ending warnings are acceptable.

- [ ] **Step 4: Inspect the scoped diff and report without staging or committing**

Confirm no Hermes/E4 paths changed during this audit and report the numerical evidence boundary, test count, and next grill question.
