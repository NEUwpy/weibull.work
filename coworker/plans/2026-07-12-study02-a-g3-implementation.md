# Study/02 A G3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify the reproducible Study/02 A pipeline, pass the G3 pilot gate, then execute the sealed A-E1/A-E3/A-E2 formal sequence needed to answer the P0 questions.

**Architecture:** A focused `study02a` package lives under the canonical Study/02 `code/` directory and reuses `python/studies/common/sample.py` for every Weibull sample. Pure modules handle frozen config, parameter design, representations, models, training, evaluation and artifacts; a CLI composes them without embedding research decisions. Formal tests remain sealed until the pilot report, experiment matrix, resource estimate and independent review all pass.

**Tech Stack:** Python 3.12, NumPy 2.1, SciPy 1.14 (`scipy.stats.qmc.Sobol`), pandas 2.2, PyTorch 2.11 CPU, pytest, matplotlib through the frozen Nature Python workflow.

## Global Constraints

- Authority order: repository `README.md`, Study/02 `02-A-实验协议.md`, `configs/A-g2-protocol-v1.json`, then `configs/A-g2-search-v1.json`.
- Do not duplicate sample generation; call `studies.common.sample.generate_sample` with the frozen sample namespace.
- Screening seeds are `420001..420003`; formal seeds are `420101..420110`; their intersection must remain empty.
- training, validation, calibration and each module test use disjoint parameter-design and sample namespaces.
- A module test may be unsealed once only after its manifest records frozen commit and config hashes.
- Pilot data cannot support scientific conclusions; pilot output paths must include `artifacts/pilot/`.
- Formal row outputs use deterministic `csv.gz` shards no larger than 20 MiB; ledgers are append-only.
- Preserve the existing user-owned unstaged `08-更新日志.md` v1.66 corrections in every commit.
- Formal figures require a Nature claim/evidence/archetype/risk/export contract before plotting and Python-only visual QA.

## Execution Progress

- [x] Task 1 — frozen config/hash contract (`6daffdf`).
- [x] Task 2 — parameter design and role isolation (`2ed1b48`).
- [x] Task 3 — equivariant targets and feature routes (`8ddbc2f`).
- [x] Task 4 — constrained models and losses (`ee67fc7`).
- [ ] Task 5 — deterministic training and validation-only search.
- [ ] Task 6 — evaluation and method admission.
- [ ] Task 7 — matrix, artifacts and CLI.
- [ ] Task 8 — pilot gate.
- [ ] Task 9 — sequential G3 formal execution.
- [ ] Task 10 — evidence, Nature figures and G3 report.

Baseline note: the repository-wide suite on `C:/Web/Weibull` produced 109 passes and 9 pre-existing Study/01 E3b failures because that test file hard-codes `D:/weibull`; Study/02 changes do not modify or waive those tests.

---

## File Structure

- `Study/02-study-NN参数估计与分位点目标研究/code/study02a/config.py`: load configs, verify hashes and expose typed protocol values.
- `Study/02-study-NN参数估计与分位点目标研究/code/study02a/design.py`: Sobol parameter points, role isolation, legacy-grid allocation and calls to the shared sample generator.
- `Study/02-study-NN参数估计与分位点目标研究/code/study02a/representations.py`: equivariant anchors, target transforms and all frozen feature routes.
- `Study/02-study-NN参数估计与分位点目标研究/code/study02a/models.py`: MLP, DeepSets and constrained three-parameter decode.
- `Study/02-study-NN参数估计与分位点目标研究/code/study02a/training.py`: deterministic datasets, losses, early stopping and two-stage validation-only search.
- `Study/02-study-NN参数估计与分位点目标研究/code/study02a/evaluation.py`: legality, `L_param`, failure-inclusive metrics, bootstrap and global-better rule.
- `Study/02-study-NN参数估计与分位点目标研究/code/study02a/admission.py`: traditional-method declared domains and contract audit.
- `Study/02-study-NN参数估计与分位点目标研究/code/study02a/matrix.py`: deterministic expansion of all nine frozen module matrix rules.
- `Study/02-study-NN参数估计与分位点目标研究/code/study02a/artifacts.py`: manifests, hashes, gzip shards and append-only run ledger.
- `Study/02-study-NN参数估计与分位点目标研究/code/run_study02a.py`: `validate-config`, `expand-matrix`, `pilot`, `formal-select` and `formal-test` commands.
- `python/tests/test_study02a_*.py`: contract tests; no formal test data are read by the test suite.

### Task 1: Frozen config and hash contract

**Files:**
- Create: `Study/02-study-NN参数估计与分位点目标研究/code/study02a/__init__.py`
- Create: `Study/02-study-NN参数估计与分位点目标研究/code/study02a/config.py`
- Test: `python/tests/test_study02a_config.py`

**Interfaces:**
- Produces: `load_frozen_config(study_root: Path) -> FrozenConfig` and `verify_frozen_hashes(study_root: Path) -> dict[str, str]`.
- `FrozenConfig` exposes `protocol`, `search`, `protocol_sha256`, and `search_sha256`.

- [ ] **Step 1: Write failing hash and seed-isolation tests**

```python
def test_load_frozen_config_verifies_hashes(study02_modules):
    config = study02_modules.config.load_frozen_config(STUDY_ROOT)
    assert config.protocol["status"] == "frozen_oracle_approved"
    assert config.protocol_sha256 == "f82e078051d760d7c9c11ece54b8fae7360c6db1aef3229a97b4fcd92ae01a11"

def test_screening_and_formal_seeds_are_disjoint(study02_modules):
    config = study02_modules.config.load_frozen_config(STUDY_ROOT)
    screening = set(config.protocol["seeds"]["nn_screening"])
    formal = set(config.protocol["seeds"]["nn_formal"])
    assert screening.isdisjoint(formal)
    assert len(formal) == 10
```

- [ ] **Step 2: Run `pytest python/tests/test_study02a_config.py -q` and confirm collection fails because `study02a.config` does not exist.**

- [ ] **Step 3: Implement immutable config loading and SHA verification**

```python
@dataclass(frozen=True)
class FrozenConfig:
    protocol: dict
    search: dict
    protocol_sha256: str
    search_sha256: str

def load_frozen_config(study_root: Path) -> FrozenConfig:
    hashes = verify_frozen_hashes(study_root)
    config_dir = study_root / "configs"
    protocol = json.loads((config_dir / "A-g2-protocol-v1.json").read_text(encoding="utf-8"))
    search = json.loads((config_dir / "A-g2-search-v1.json").read_text(encoding="utf-8"))
    if protocol["status"] != "frozen_oracle_approved":
        raise ValueError("Study02 protocol is not frozen")
    return FrozenConfig(protocol, search, hashes["A-g2-protocol-v1.json"], hashes["A-g2-search-v1.json"])
```

- [ ] **Step 4: Run the test and expect `2 passed`.**

- [ ] **Step 5: Commit `test/research: enforce Study02 frozen config hashes`.**

### Task 2: Parameter design, allocation and role isolation

**Files:**
- Create: `Study/02-study-NN参数估计与分位点目标研究/code/study02a/design.py`
- Test: `python/tests/test_study02a_design.py`

**Interfaces:**
- Consumes: `FrozenConfig` and `studies.common.sample.generate_sample`.
- Produces: `generate_parameter_points(role, layer, count, config) -> DataFrame`, `allocate_training_rows(distribution, n_mode, count, config) -> DataFrame`, and `generate_lifetime_sample(point, n, repeat_id, namespace) -> ndarray`.

- [ ] **Step 1: Test deterministic Sobol output, role disjointness and exact 7000-row legacy allocation**

```python
def test_role_parameter_points_are_deterministic_and_disjoint(cfg):
    train_a = generate_parameter_points("training", "core", 64, cfg)
    train_b = generate_parameter_points("training", "core", 64, cfg)
    valid = generate_parameter_points("validation", "core", 64, cfg)
    pd.testing.assert_frame_equal(train_a, train_b)
    keys = ["beta", "eta", "rho"]
    assert train_a.merge(valid, on=keys).empty

def test_historical_shared_allocation_is_exact(cfg):
    rows = allocate_historical_rows("training", 7000, cfg)
    assert len(rows) == 7000
    assert rows["cell_id"].nunique() == 400
    assert set(rows["n"]) == {5, 7, 10, 15, 20}
```

- [ ] **Step 2: Run the file and confirm missing-function failures.**

- [ ] **Step 3: Implement scrambled Sobol transformation**

```python
def generate_parameter_points(role, layer, count, cfg):
    seed = role_design_seed(role, layer, cfg)
    raw = qmc.Sobol(d=3, scramble=True, seed=seed).random(count)
    beta = np.exp(np.log(beta_min) + raw[:, 0] * np.log(beta_max / beta_min))
    eta = np.exp(np.log(eta_min) + raw[:, 1] * np.log(eta_max / eta_min))
    rho = rho_min + raw[:, 2] * (rho_max - rho_min)
    return pd.DataFrame({"point_id": np.arange(count), "beta": beta, "eta": eta, "rho": rho, "gamma": rho * eta})
```

- [ ] **Step 4: Implement quotient-remainder allocation and delegate every sample to `generate_sample`.**

- [ ] **Step 5: Run `pytest python/tests/test_study02a_design.py python/tests/test_sample.py -q`; expect all pass.**

- [ ] **Step 6: Commit `feat/research: add Study02 isolated parameter design`.**

### Task 3: Equivariant targets and feature routes

**Files:**
- Create: `Study/02-study-NN参数估计与分位点目标研究/code/study02a/representations.py`
- Test: `python/tests/test_study02a_representations.py`

**Interfaces:**
- Produces: `anchor_sample(x) -> Anchor`, `encode_targets(beta, eta, gamma, anchor) -> ndarray`, `decode_targets(y, anchor) -> tuple`, and `build_features(route_id, x, n) -> ndarray`.

- [ ] **Step 1: Write scale/translation round-trip tests at `1e-6` tolerance**

```python
@pytest.mark.parametrize("scale,shift", [(1e-3, -500.0), (1e3, 5e6)])
def test_main_representation_is_scale_translation_equivariant(scale, shift):
    x = np.array([120., 135., 180., 220., 410.])
    params = (2.2, 140.0, 80.0)
    base = decode_targets(encode_targets(*params, anchor_sample(x)), anchor_sample(x))
    xt = scale * x + shift
    pt = (params[0], scale * params[1], scale * params[2] + shift)
    transformed = decode_targets(encode_targets(*pt, anchor_sample(xt)), anchor_sample(xt))
    assert transformed[0] == pytest.approx(base[0], rel=1e-6)
    assert transformed[1] == pytest.approx(scale * base[1], rel=1e-6)
    assert transformed[2] == pytest.approx(scale * base[2] + shift, rel=1e-6)
```

- [ ] **Step 2: Add tests for IQR→range fallback, constant-sample failure, exact route widths and distinct HSM/KDE IDs.**

- [ ] **Step 3: Implement anchor and target transformations without absolute epsilon.**

```python
def anchor_sample(x):
    a = float(np.min(x))
    s = float(np.quantile(x, .75, method="linear") - np.quantile(x, .25, method="linear"))
    if s == 0.0:
        s = float(np.max(x) - np.min(x))
    if s == 0.0:
        raise DegenerateSampleError("constant sample")
    return Anchor(location=a, scale=s, z=(np.asarray(x) - a) / s)
```

- [ ] **Step 4: Implement all feature formulas exactly from `feature_contract`, including lower-interval tie breaks.**

- [ ] **Step 5: Run the representation tests and expect all pass.**

- [ ] **Step 6: Commit `feat/research: add equivariant Study02 representations`.**

### Task 4: Constrained models and loss functions

**Files:**
- Create: `Study/02-study-NN参数估计与分位点目标研究/code/study02a/models.py`
- Create: `Study/02-study-NN参数估计与分位点目标研究/code/study02a/training.py`
- Test: `python/tests/test_study02a_models.py`

**Interfaces:**
- Produces: `build_model(route_id, architecture, input_dim) -> nn.Module`, `decode_model_output(raw, anchor)`, and `compute_loss(loss_id, prediction, target, training_stats)`.

- [ ] **Step 1: Test MLP/DeepSets shapes, permutation invariance and legal decode.**

```python
def test_deepsets_is_permutation_invariant():
    model = build_deepsets(encoder=(32, 32), pool="mean", head=(64, 32), activation="relu")
    x = torch.tensor([[[0.0], [0.5], [2.0], [4.0]]])
    assert torch.allclose(model(x), model(x[:, [2, 0, 3, 1], :]), atol=1e-6)

def test_decode_is_always_legal():
    beta, eta, gamma = decode_model_output(torch.tensor([[0.0, 0.0, 0.0]]), location=100., scale=20.)[0]
    assert beta > 0 and eta > 0 and gamma < 100.
```

- [ ] **Step 2: Confirm failures before implementation.**

- [ ] **Step 3: Implement MLP, mask-aware DeepSets, exponential decode and the four frozen losses.**

- [ ] **Step 4: Test joint/independent parameter-count matching never exceeds 1.05 and reports exact counts.**

- [ ] **Step 5: Run tests; expect all pass and no CUDA requirement.**

- [ ] **Step 6: Commit `feat/research: add Study02 constrained neural estimators`.**

### Task 5: Deterministic training and validation-only search

**Files:**
- Modify: `Study/02-study-NN参数估计与分位点目标研究/code/study02a/training.py`
- Test: `python/tests/test_study02a_training.py`

**Interfaces:**
- Produces: `fit_candidate(spec, datasets, seed) -> FitResult`, `run_two_stage_search(route, datasets, cfg) -> SearchResult`, and `select_validation_winner(rows, rule) -> str`.

- [ ] **Step 1: Test that stage 1 has 12 architectures, stage 2 expands exactly top4×3, tie-break is lexical, and no test dataset argument exists.**

```python
def test_two_stage_search_expansion_is_frozen(cfg):
    specs = expand_search_specs("F2", cfg.search)
    assert len(specs.stage1) == 12
    stage2 = specs.expand_stage2(["m04", "m01", "m08", "m05"])
    assert len(stage2) == 12
    assert {s.optimizer_id for s in stage2} == {"o1", "o2", "o3"}
```

- [ ] **Step 2: Implement CPU determinism (`random`, NumPy and torch seeds; deterministic algorithms) and training-only scalers.**

- [ ] **Step 3: Implement min-50/max-500 epoch early stopping with patience 40 and best-validation checkpoint.**

- [ ] **Step 4: Run a 128-row synthetic smoke fit twice with the same seed and assert identical predictions/checkpoint hash.**

- [ ] **Step 5: Run model, representation and training tests together.**

- [ ] **Step 6: Commit `feat/research: add deterministic Study02 model search`.**

### Task 6: Evaluation and traditional-method admission

**Files:**
- Create: `Study/02-study-NN参数估计与分位点目标研究/code/study02a/evaluation.py`
- Create: `Study/02-study-NN参数估计与分位点目标研究/code/study02a/admission.py`
- Test: `python/tests/test_study02a_evaluation.py`
- Test: `python/tests/test_study02a_admission.py`

**Interfaces:**
- Produces: `evaluate_rows(rows, failure_penalty) -> dict`, `global_better(a, b, bootstrap) -> Decision`, and `audit_method(method_id, declared_domain, samples) -> AdmissionResult`.

- [ ] **Step 1: Test `L_param`, conditional/unconditional failure handling and global-better safeguards.**

```python
def test_single_parameter_gain_cannot_be_called_global_better():
    decision = global_better_from_intervals(
        failure_diff_upper=.005,
        l_param_improvement_lower=.02,
        component_worsening_upper={"beta": .01, "eta": .08, "gamma": .02},
    )
    assert decision.label == "tradeoff"
```

- [ ] **Step 2: Test that an out-of-domain transformed case is recorded without removing a method from core admission.**

- [ ] **Step 3: Implement paired cluster bootstrap with seed `520001`, 2000 replicates and parameter-point clusters.**

- [ ] **Step 4: Implement method manifests for MLE, MPS, WMLE, MDM-0.1, LRE, MMLE, LSE, MM and PWM; unknown domains fail closed.**

- [ ] **Step 5: Run existing common runner/metrics tests plus new evaluation/admission tests.**

- [ ] **Step 6: Commit `feat/research: add Study02 evaluation and method admission`.**

### Task 7: Matrix, manifests, shards and append-only ledger

**Files:**
- Create: `Study/02-study-NN参数估计与分位点目标研究/code/study02a/matrix.py`
- Create: `Study/02-study-NN参数估计与分位点目标研究/code/study02a/artifacts.py`
- Create: `Study/02-study-NN参数估计与分位点目标研究/code/run_study02a.py`
- Test: `python/tests/test_study02a_artifacts.py`
- Test: `python/tests/test_study02a_matrix.py`

**Interfaces:**
- Produces: `expand_module_matrix(cfg) -> DataFrame`, `append_ledger(entry, path)`, `write_manifest(run, path)`, `write_csv_gz_shards(rows, max_mib=20)`, and CLI commands.

- [ ] **Step 1: Test all nine matrix rules expand, H0/H1 have 30 formal fits, G3 is ≤900 fits and formal test rows start sealed.**

- [ ] **Step 2: Test ledger append preserves failed runs and shard decompression reproduces deterministic row order.**

- [ ] **Step 3: Implement config-driven matrix expansion with no hard-coded alternative choices.**

- [ ] **Step 4: Implement atomic manifest writes and append-only JSONL using one canonical JSON object per line.**

- [ ] **Step 5: Add CLI validation**

```powershell
python "Study/02-study-NN参数估计与分位点目标研究/code/run_study02a.py" validate-config
python "Study/02-study-NN参数估计与分位点目标研究/code/run_study02a.py" expand-matrix --output "Study/02-study-NN参数估计与分位点目标研究/artifacts/pilot/G3-matrix"
```

Expected: hash verification passes; matrix reports nine rules, no seed overlap and `test_state=sealed`.

- [ ] **Step 6: Commit `feat/research: add Study02 auditable experiment orchestration`.**

### Task 8: G3 pilot gate

**Files:**
- Create: `Study/02-study-NN参数估计与分位点目标研究/artifacts/pilot/G3-pilot-20260712-01/manifest.json`
- Create: `Study/02-study-NN参数估计与分位点目标研究/artifacts/pilot/G3-pilot-20260712-01/run_log.txt`
- Create: `Study/02-study-NN参数估计与分位点目标研究/artifacts/pilot/G3-pilot-20260712-01/resource_estimate.json`
- Create: `coworker/reports/2026-07-12-study02-a-g3-pilot-codex.md`
- Create after review: `coworker/reviews/2026-07-12-study02-a-g3-pilot-oracle.md`

**Interfaces:**
- Consumes the CLI and sealed configs; produces no scientific conclusion.

- [ ] **Step 1: Run the full Study02 contract suite and save pytest output in the pilot run directory.**
- [ ] **Step 2: Execute `pilot --modules A-E1,A-E2,A-E3 --points 32 --repeats 4 --n 5,20`; keep every warning and method failure.**
- [ ] **Step 3: Generate `experiment_matrix.csv`, `resource_estimate.json`, `admission_report.csv`, manifest, log and ledger entry.**
- [ ] **Step 4: Verify role-point intersections are zero, test remains sealed, predicted disk stays below 80% of 55.4 GiB free-at-G2 snapshot, and actual fit count is ≤900.**
- [ ] **Step 5: Request independent oracle review; revise code/protocol version until APPROVE.**
- [ ] **Step 6: Commit and push the approved pilot as its own phase checkpoint.**

### Task 9: Sequential G3 formal execution

**Files:**
- Create: `Study/02-study-NN参数估计与分位点目标研究/artifacts/formal/A-E1/G3-AE1-formal-v1/manifest.json`
- Create: `Study/02-study-NN参数估计与分位点目标研究/artifacts/formal/A-E3/G3-AE3-formal-v1/manifest.json`
- Create: `Study/02-study-NN参数估计与分位点目标研究/artifacts/formal/A-E2/G3-AE2-formal-v1/manifest.json`

- [ ] **Step 1: Freeze code commit/config hashes and run A-E1 training/validation only; select F2/V baseline without opening A-E1 test.**
- [ ] **Step 2: Fit A-E3 loss/architecture/joint/shared candidates from the frozen A-E1 selection; select on validation only.**
- [ ] **Step 3: Fit A-E2 size/distribution variants from the frozen A-E3 baseline; select on validation only.**
- [ ] **Step 4: Write the complete selection trace, checkpoint hashes and selected IDs; run leakage audit.**
- [ ] **Step 5: Atomically change only A-E1/A-E3/A-E2 test manifests from `sealed` to `unsealed_once`, evaluate shared paired test samples once, then mark `consumed`.**
- [ ] **Step 6: Aggregate A1/A4/A5/A6/A7/A8/A9/A10/A17/A18 evidence with conditional and failure-inclusive metrics.**
- [ ] **Step 7: Independent oracle review to APPROVE, then phase commit and push.**

### Task 10: G3 evidence, Nature figures and report

**Files:**
- Create: `Study/02-study-NN参数估计与分位点目标研究/05-A-证据索引.md`
- Create: `Study/02-study-NN参数估计与分位点目标研究/figures/G3-input/figure-contract.md`
- Create: `Study/02-study-NN参数估计与分位点目标研究/figures/G3-input/plot_input_comparison.py`
- Create: `Study/02-study-NN参数估计与分位点目标研究/figures/G3-input/input-source-data.csv`
- Create: `Study/02-study-NN参数估计与分位点目标研究/figures/G3-input/qa.md`
- Create: `Study/02-study-NN参数估计与分位点目标研究/figures/G3-learning/figure-contract.md`
- Create: `Study/02-study-NN参数估计与分位点目标研究/figures/G3-learning/plot_learning_curves.py`
- Create: `Study/02-study-NN参数估计与分位点目标研究/figures/G3-learning/learning-source-data.csv`
- Create: `Study/02-study-NN参数估计与分位点目标研究/figures/G3-learning/qa.md`
- Create: `coworker/reports/2026-07-12-study02-a-g3-formal-codex.md`

- [ ] **Step 1: Define one claim per figure before plotting; map panels to exact formal summary/source rows.**
- [ ] **Step 2: Plot learning curves, input comparison, loss/architecture comparison and seed stability using the Nature Python contract; export SVG/PDF/PNG.**
- [ ] **Step 3: Visually inspect every PNG at final size and record clipping, font, colorblind and uncertainty checks.**
- [ ] **Step 4: Update the evidence index with question → run ID → table/figure → bounded answer → limitation.**
- [ ] **Step 5: Run full verification, independent oracle review, update `08-更新日志.md`, commit and push G3.**

## Plan Self-Review

- Spec coverage: all G3 P0 questions map to Tasks 3–10; four-role isolation and test sealing map to Tasks 1, 2, 7–9; artifacts and Nature requirements map to Tasks 7–10.
- Placeholder scan: no unspecified implementation markers remain; A11/A12 are intentionally outside G3 and already frozen as G5 pre-formal work.
- Type consistency: config → design/representations → models/training → evaluation → artifacts/CLI interfaces are named once and consumed downstream with matching names.
- Scope: this plan implements G3 only. G4 and G5 remain separate phase plans after G3 evidence is approved.

## Execution Choice

Inline execution is selected because the user requested continuous execution in the current task and did not authorize subagent-driven implementation. Use `executing-plans` with review checkpoints and preserve the single-writer lease.
