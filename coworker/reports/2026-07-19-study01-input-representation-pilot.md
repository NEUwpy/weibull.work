# Study01 input representation pilot report

Date: 2026-07-19

## Scope

Executed the narrow contract in `coworker/plans/2026-07-19-study01-input-representation-pilot.md`: compare the current 13-feature Vector-MLP with a sorted raw-sample representation on one existing E3b combo-holdout fold and one seed. No formal E3/E4 artifact was modified and no Monte Carlo scan was rerun.

## Implementation

- Added `Study/01-study-MDM最小偏移量优化研究/code/run_input_representation_pilot.py`.
- Reused sealed E3b `sample_features.csv` and `risk_curves.csv` (45,000 aligned samples).
- Used `combo_fold_1`, seed 42, 36,000 train samples, 9,000 test samples, the same 26-point per-sample loss-curve target, `(256,128,64)` MLP, train-only scaling, and true selected-J1 evaluation.
- Feature input: the current 13 observable summary features.
- Raw input: sorted raw observations, train-only scalar z-score, right padding to `n=20`, explicit 20-position mask, and `n` (41 dimensions). Sorting removes dependence on the original observation order; the mask separates padding from observations.

## Results

| Input | pooled J1 ↓ | n=7 | n=10 | n=20 | Runtime | Iterations |
|-------|------------:|----:|-----:|-----:|--------:|-----------:|
| 13 summary features | 0.530403 | 0.615673 | 0.563518 | 0.383896 | 52.3 s | 59 |
| sorted raw + mask | 0.532171 | 0.620301 | 0.558615 | 0.390888 | 130.2 s | 113 |

Raw minus feature pooled J1 = +0.001768 (+0.33%; lower is better). The feature representation is slightly better for `n=7` and `n=20`; the raw representation is slightly better for `n=10`. The pilot does not show a material raw-input advantage.

## Interpretation

The result supports keeping the 13-feature representation for the current paper because it is fixed-width, interpretable, auditable, and did not lose visible selection quality in this matched pilot. The raw model took about 2.5 times as long in this run, but this is descriptive only because input dimension and optimization paths differ.

This does not prove that engineered features are universally superior. The result is one fold and one seed, uses one sorted/padded raw representation rather than every possible set architecture, and remains pilot-only. It must not be promoted to formal multi-fold/multi-seed evidence or a continuous-space generalization claim.

## Changed files

- `Study/01-study-MDM最小偏移量优化研究/code/run_input_representation_pilot.py`
- `python/tests/test_study01_input_representation_pilot.py`
- `Study/01-study-MDM最小偏移量优化研究/artifacts/pilot/input_representation/{summary.json,comparison.csv,selected_predictions.csv}`
- `Study/01-study-MDM最小偏移量优化研究/260720汇报/02-组会汇报目标与准备方案.md`
- this report and its plan

## Checks

- `python -m pytest python/tests/test_study01_input_representation_pilot.py -q` -> `4 passed in 7.67s`.
- Pilot command completed successfully in 186.6 seconds.
- `python -m pytest python/tests/test_study01_e3b_contract.py python/tests/test_study01_input_representation_pilot.py -q` -> `15 passed in 3.25s`.
- `git diff --check` -> passed (line-ending notices only; no whitespace errors).
- Git status confirms outputs are under `artifacts/pilot/input_representation/`; no tracked formal E3/E4 artifact was modified by the pilot.

## Deviations

None from the narrow contract. No multi-fold or multi-seed expansion was attempted.

## Reviewer verdict

**APPROVE**

The implementation matches the narrow plan, the comparison is aligned on fold/seed/target/evaluation, formal evidence is preserved, and the report keeps the result at pilot-only evidence strength. No blocking issue remains for using this result in the group meeting with the stated limitations.

## 2026-07-19 scope extension: sample-size question

- Added a matched 12-feature model that removes only explicit `n`.
- Re-ran the three-model pilot on the same fold, seed, targets, and evaluation.
- Full features: pooled J1 0.530403; per-n 0.615673 / 0.563518 / 0.383896.
- Features without `n`: pooled J1 0.524485; per-n 0.611602 / 0.553986 / 0.379865.
- Sorted raw input: pooled J1 0.532171; per-n 0.620301 / 0.558615 / 0.390888.
- Added standalone evidence/interpretation document `样本特征选取与样本量关系/01-原始样本与统计特征输入验证.md` with explicit pilot-only boundaries and 11/11 fallacy scan.
- Contract tests: `python -m pytest python/tests/test_study01_input_representation_pilot.py -q` -> 5 passed.

Reviewer verdict for extension: **APPROVE**, subject to retaining the one-fold/one-seed limitation and not removing `n` from the formal model on this evidence alone.

## 2026-07-19 scope extension: joint vs sample-size-specific training

- Added three 12-feature specialists trained separately for `n=7/10/20` and routed test rows by known `n`.
- Clean comparison against the unified 12-feature model keeps feature fields, fold, seed, architecture, target, total sample count, and selected-J1 evaluation aligned.
- Unified 12-feature model: pooled 0.524485; per-n 0.611602 / 0.553986 / 0.379865.
- Routed specialists: pooled 0.531443; per-n 0.624057 / 0.559222 / 0.380943.
- No negative transfer was observed in this pilot; the unified model was lower-J1 for every sample-size group.
- Added `样本特征选取与样本量关系/02-联合样本量与分样本量训练验证.md` with the capacity, one-fold/one-seed, and generalization limitations.
- Contract tests before execution: `6 passed`.

Reviewer verdict for extension: **APPROVE** for group-meeting use at pilot-only strength; do not claim universal superiority without 5-fold × multi-seed confirmation.
