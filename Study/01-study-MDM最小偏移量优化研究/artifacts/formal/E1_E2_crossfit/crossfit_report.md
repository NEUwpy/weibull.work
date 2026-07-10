# E1/E2 L1-L5 Cross-Fit Sensitivity Validation

Selection uses four repeat-id folds; every reported loss is scored on the untouched fifth fold.
L6 is excluded because it is an intentionally in-sample per-sample hindsight benchmark.

## Pooled held-out J1

| layer | J1 |
|---|---:|
| Default | 0.633219 |
| L1 | 0.632913 |
| L2 | 0.632732 |
| L3 | 0.585068 |
| L4 | 0.582585 |
| L5 | 0.571924 |

## Comparison with same-sample selection/evaluation

| layer | same-sample J1 | cross-fit J1 | difference | relative change |
|---|---:|---:|---:|---:|
| Default | 0.633219 | 0.633219 | +0.000000 | +0.000% |
| L1 | 0.632913 | 0.632913 | +0.000000 | +0.000% |
| L2 | 0.632541 | 0.632732 | +0.000191 | +0.030% |
| L3 | 0.585068 | 0.585068 | +0.000000 | +0.000% |
| L4 | 0.582090 | 0.582585 | +0.000495 | +0.085% |
| L5 | 0.571170 | 0.571924 | +0.000753 | +0.132% |

## Selection stability

| layer | groups | groups stable in all folds | maximum unique deltas |
|---|---:|---:|---:|
| L1 | 1 | 1 | 1 |
| L2 | 3 | 2 | 2 |
| L3 | 5 | 5 | 1 |
| L4 | 15 | 10 | 2 |
| L5 | 45 | 28 | 3 |

## Fold-level J1

| fold | layer | J1 |
|---:|---|---:|
| 0 | Default | 0.625563 |
| 0 | L1 | 0.625373 |
| 0 | L2 | 0.624924 |
| 0 | L3 | 0.578153 |
| 0 | L4 | 0.575803 |
| 0 | L5 | 0.563890 |
| 1 | Default | 0.636456 |
| 1 | L1 | 0.635648 |
| 1 | L2 | 0.636039 |
| 1 | L3 | 0.588614 |
| 1 | L4 | 0.585324 |
| 1 | L5 | 0.575126 |
| 2 | Default | 0.638950 |
| 2 | L1 | 0.637737 |
| 2 | L2 | 0.638258 |
| 2 | L3 | 0.588575 |
| 2 | L4 | 0.587478 |
| 2 | L5 | 0.575672 |
| 3 | Default | 0.631195 |
| 3 | L1 | 0.631882 |
| 3 | L2 | 0.631324 |
| 3 | L3 | 0.585502 |
| 3 | L4 | 0.583511 |
| 3 | L5 | 0.573075 |
| 4 | Default | 0.633846 |
| 4 | L1 | 0.633855 |
| 4 | L2 | 0.633031 |
| 4 | L3 | 0.584430 |
| 4 | L4 | 0.580740 |
| 4 | L5 | 0.571776 |

## Interpretation boundary

This package audits selection optimism using the existing MC cache. It does not rerun MDM, replace the sealed E1/E2 artifacts, or convert L6 into an out-of-sample deployment estimate.
