# Writing record and terminology

This is a generic English research-paper draft based on the verified v2.7.0 Chinese manuscript. It is not a journal-specific submission package. No author identities, affiliations, funding, competing interests, or submission declarations have been inferred.

The argument is that, within the fixed-scale simulation domain, aligning a neural estimator with one Weibull life point modestly reduces pooled target risk while permitting parameter compensation and deterioration at other life points; parameter-recovery requirements can repair this behavior, but simple alternatives must be included when assessing the need for constrained optimization.

| Canonical term | Definition or writing decision |
|---|---|
| reliability life point, $x_R$ | Life at survival probability R; $x_{0.95}$ is the 5th failure-time percentile |
| RMSRE | Root mean squared relative error; replaces legacy rRMSE/B5 accuracy labels |
| P | Parameter-oriented training and validation selection |
| Q | Target-oriented training and validation selection, with three parameter outputs |
| QCP | Parameter-constrained target-oriented procedure |
| QP | Fixed-weight loss $L_Q+L_P$, with validation $L_Q$ selection |
| P_QSELECT | Parameter-loss training with validation $L_Q$ selection and early stopping |
| Q_FEAS | Feasible checkpoint selection within the native Q trajectory |
| QMULTI | Equal-weight relative squared losses at R=0.90, 0.95, and 0.99 |
| model unit | One sample-size/fold/training-seed combination; 200 per route |
| truth cell | One sample-size/shape/location-ratio combination; 160 in the design |
| parameter compensation | Within-prediction cancellation of exact parameter contributions |
| empirical interval | Paired fold-by-seed bootstrap approximation, conditional on this design |

The manuscript follows application → task mismatch → scalar-supervision freedom → paired evidence → repair and simpler controls → practical limits. Mathematical geometry concerns output errors, not the rank of the neural-network weight Hessian. Pooled risk, typical error, and computational cost remain separate criteria.

Claims are anchored to main Tables 1–3, Figures 1–4, and supplementary Tables B10 and F1–F2. The QP comparison does not establish equivalence. Supplementary controls reuse the existing simulation samples and do not constitute fresh-data confirmation. The study does not establish coverage-calibrated lower confidence bounds or deployment performance outside the fixed scale.

Missing inputs for a journal-specific final version: target journal and article type; author order, affiliations and corresponding-author details; verified contributions, funding and competing-interest statements; author approval of submission declarations; a public repository accession if the data are released. The local reproducibility bundle is prepared for inspection and has not been uploaded.
