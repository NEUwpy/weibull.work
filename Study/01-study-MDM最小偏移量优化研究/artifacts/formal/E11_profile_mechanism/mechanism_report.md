# E11 MDM profile-gradient mechanism diagnostic

Status: `FORMAL_SUPPORTING_MECHANISM_EVIDENCE`

## Question

Within the same true-parameter cell, why can the realised low-risk offset change
from one random sample to another?

## Design

The diagnostic uses four parameter-domain corners plus the centre, crossed with
all four trained sample sizes: 20 cells and
2000 untouched confirmation samples.  It reuses the
frozen 26-point loss scan and regenerates only one MDM profile trace per sample.

## Result

- Median within-cell Spearman correlation between `g(0)` and the L6 offset:
  **0.652**
  (IQR 0.549 to 0.779; range
  -0.038 to 0.845).
- Positive association in 95.0% of cells.
- Median within-cell correlation between the default-offset location estimate
  and the L6 offset: **-0.765**
  (IQR -0.803 to
  -0.609); the direction is negative in
  100.0% of cells.
- Conditional pooled excess-loss minima for low/middle/high within-cell default
  location estimates:
  0.10, 0.04,
  0.02.
- L6 solutions at the `gamma=0` boundary: 7.10%;
  default-offset boundary solutions: 5.75%.

## Interpretation

The sample-specific phenomenon is not adequately described as a boundary switch.
Even within a fixed `(beta, gamma/eta, n)` cell, random lower-order statistics move
the empirical profiled MDM gradient curve.  The offset solves an intersection
condition on that curve, so the corresponding MDM estimates and their coupled
three-parameter loss change with the sample.  `g(0)` is a compact diagnostic of
that displacement: its within-cell ordering also orders the low-risk region of
the realised offset-loss curve.

This explains why L5, which chooses one average offset per parameter cell, cannot
match L6 sample by sample.  It does not make L6 deployable and does not identify
an exact Bayes rule from observable data.

## Boundaries

- The analysis uses 20 predeclared cells, not all 160 design cells.
- L6 remains a 26-point hindsight reference and is not a deployable decision rule.
- Associations diagnose a numerical mechanism; they do not prove a closed-form causal decomposition.
