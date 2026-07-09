# E3b Acceptance Report

## Verdict

**APPROVE**

- Best vector candidate is Vector-MLP-L6 with J1=0.547003; L2 J1=0.632541; improvement=0.085538.
- Tabular-L6 J1=0.557849; gap to best vector=0.010847.
- Combo holdout shows clear pooled J1 improvement over L2.
- Strong NN signal: Vector-MLP is within 0.01 J1 of or better than Tabular-L6.

## Data Integrity

- expected_rows: 1170000
- actual_rows: 1170000
- duplicate_rows: 0
- unique_combos: 45
- delta_points: 26
- repeat_min/repeat_max: 1000/1000
- non_success_rate: 0.000000

## Combo Holdout Pooled

| model | J1 | failure_rate | n_samples | J1_n7 | J1_n10 | J1_n20 |
|---|---:|---:|---:|---:|---:|---:|
| L6-hindsight | 0.494530 | 0.000000 | 45000 | 0.591115 | 0.503582 | 0.361479 |
| Vector-MLP-L6 | 0.547003 | 0.000000 | 45000 | 0.657558 | 0.549815 | 0.403679 |
| Tabular-L6 | 0.557849 | 0.000000 | 45000 | 0.666695 | 0.563795 | 0.413813 |
| L5-oracle | 0.571170 | 0.000000 | 45000 | 0.676581 | 0.579700 | 0.429992 |
| L4-oracle | 0.582090 | 0.000000 | 45000 | 0.685935 | 0.591759 | 0.442494 |
| L3-oracle | 0.585068 | 0.000000 | 45000 | 0.690009 | 0.592188 | 0.447339 |
| Vector-MLP-L5 | 0.596829 | 0.000000 | 45000 | 0.708311 | 0.605144 | 0.448010 |
| Vector-MLP-L4 | 0.606229 | 0.000000 | 45000 | 0.712337 | 0.617645 | 0.462204 |
| L2 | 0.632541 | 0.000000 | 45000 | 0.739286 | 0.644520 | 0.488235 |
| L1 | 0.632913 | 0.000000 | 45000 | 0.739733 | 0.645104 | 0.488235 |
| Default | 0.633219 | 0.000000 | 45000 | 0.739286 | 0.644520 | 0.490866 |

## Random Split (Sanity Check)

| model | J1 | failure_rate | n_samples | J1_n7 | J1_n10 | J1_n20 |
|---|---:|---:|---:|---:|---:|---:|
| L6-hindsight | 0.488683 | 0.000000 | 9000 | 0.584927 | 0.495707 | 0.355694 |
| Vector-MLP-L6 | 0.535083 | 0.000000 | 9000 | 0.640288 | 0.538514 | 0.395711 |
| L2 | 0.629074 | 0.000000 | 9000 | 0.736934 | 0.639136 | 0.482359 |
| L1 | 0.629698 | 0.000000 | 9000 | 0.739827 | 0.637615 | 0.482359 |
| Default | 0.629815 | 0.000000 | 9000 | 0.736934 | 0.639136 | 0.485284 |

## Split Preview

| fold | test_beta | test_gamma_over_eta | test_n |
|---|---:|---:|---:|
| combo_fold_1 | 1.5 | 0.1 | 7 |
| combo_fold_1 | 1.5 | 0.5 | 20 |
| combo_fold_1 | 2.0 | 0.1 | 10 |
| combo_fold_1 | 2.0 | 1.0 | 7 |
| combo_fold_1 | 2.5 | 0.1 | 20 |
| combo_fold_1 | 2.5 | 1.0 | 10 |
| combo_fold_1 | 4.0 | 0.5 | 7 |
| combo_fold_1 | 4.0 | 1.0 | 20 |
| combo_fold_1 | 5.0 | 0.5 | 10 |
| combo_fold_2 | 1.5 | 0.1 | 10 |

_Split rows recorded: 45._

## Endpoint Diagnostics (Pooled)

| model | category | P_delta_0 | P_delta_0.5 | P_extreme |
|---|---|---:|---:|---:|
| Vector-MLP-L6 | pooled | 0.1408 | 0.0106 | 0.4881 |
| Vector-MLP-L5 | pooled | 0.1124 | 0.0015 | 0.1844 |
| Vector-MLP-L4 | pooled | 0.0000 | 0.0145 | 0.0411 |
| Tabular-L6 | pooled | 0.1814 | 0.0042 | 0.3722 |
| L2 | pooled | 0.0000 | 0.0000 | 0.0000 |
| L6-hindsight | pooled | 0.4746 | 0.0657 | 0.6474 |

## Seed Stability (Vector-MLP-L6, 5-fold combo holdout pooled)

| seed | pooled_J1 | J1_n7 | J1_n10 | J1_n20 | endpoint_rate |
|---:|---:|---:|---:|---:|---:|
| 42 | 0.547003 | 0.657558 | 0.549815 | 0.403679 | 0.4881 |
| 2026 | 0.546133 | 0.657899 | 0.549735 | 0.399680 | 0.4884 |
| 3407 | 0.544009 | 0.657170 | 0.545974 | 0.397339 | 0.5624 |

## Feature Ablation (Vector-MLP-L6, fold 1, seed 42)

| group | n_features | pooled_J1 | endpoint_rate | near_5pct |
|---|---:|---:|---:|---:|
| full | 13 | 0.528518 | 0.4883 | 0.4112 |
| n_only | 1 | 0.606215 | 0.0000 | 0.2120 |
| scale_quantile | 10 | 0.535027 | 0.5538 | 0.3990 |
| shape | 4 | 0.544438 | 0.5744 | 0.4033 |

## Near-Optimal / Regret Summary (Combo Holdout Pooled)

| model | mean_regret | mean_rel_regret | near_1% | near_2% | near_5% |
|---|---:|---:|---:|---:|---:|
| Vector-MLP-L6 | 0.054652 | 2.155035 | 0.3138 | 0.3481 | 0.4090 |
| Tabular-L6 | 0.066636 | 3.173833 | 0.2854 | 0.3083 | 0.3587 |
| L2 | 0.155548 | 7.427484 | 0.0919 | 0.1221 | 0.1878 |
