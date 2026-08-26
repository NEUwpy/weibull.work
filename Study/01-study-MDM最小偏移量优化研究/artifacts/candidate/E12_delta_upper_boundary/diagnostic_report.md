# E12 delta candidate upper-bound diagnostic

## Scope

The frozen 0.00--0.50 scan is retained. Only the 2,186
samples whose loss was still decreasing from 0.48 to 0.50 were evaluated at
0.52--1.00 using the same sample generator, MDM implementation and loss.

## Result

- Selected at the old upper edge: 2,186 / 48,000
  (4.55%).
- Improved beyond 0.50: 2,063 samples.
- Still best at the new upper edge 1.00: 590 samples.
- L6 J1 on the full 48,000 samples: 0.492297115
  (0.00--0.50) -> 0.490847862 (0.00--1.00).
- Relative reduction in L6 risk R: 0.588%.

## Boundary of interpretation

This result diagnoses the hindsight reference. It does not alter the trained
selector, its deployment grid, or the already reported selector-versus-Default
comparison. If many samples remain best at 1.00, the extended reference is
still right-censored and 1.00 should not be called an unconstrained optimum.
