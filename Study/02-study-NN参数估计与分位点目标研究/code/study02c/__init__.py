"""Study/02 C — mechanism analysis on existing B evidence.

Reuses B4/B5 row-level results, frozen checkpoints, and deterministic test
data; performs minimal *inference* (no refit) to obtain P parameter
predictions that were not persisted in B. No new training or data
generation. C2 questions:

- C2-1 n heterogeneity: why D wins at n=5,15,20 but not n=7,10
- C2-2 parameter->x0.95 error propagation for P, counterfactual attribution
- C2-3 target-alignment attribution strength and residual uncertainty
"""
