# Study1.5 Stage 1 — Final Report

> **Contract**: v0.1 frozen (`03-第一阶段执行合同.md`)
> **Status**: CONFIRM COMPLETE — both phases executed, analysis finalized

---

## 1. Execution Summary

| Phase | Seed(s) | Models | Completed | Status |
|-------|---------|--------|-----------|--------|
| Explore | 42 | 30 | 30/30 | complete |
| Confirm | 2026, 3407 | 60 | 60/60 | complete |
| **Total** | 42, 2026, 3407 | **90** | **90/90** | |

- **Source data**: sample_features.csv (SHA256 `75BB9A06...`), risk_curves.csv (`4B3AD2A3...`) — contract-matched.
- **Numerical environment**: OMP/OPENBLAS/MKL/NUMEXPR/VECLIB_NUM_THREADS=1.
- **No models failed, no non-finite predictions, no key misalignment.**
- **Independent per-sample recomputation**: selected loss max error `8.88e-16`; J1, mean/median/p95 regret, near5_hit all match to floating-point precision.

---

## 2. Evidence Distinction

| Evidence type | Seeds | Phase | Interpretive weight |
|---------------|-------|-------|---------------------|
| **Explored** | 42 | Explore | Structure discovery, pilot patterns |
| **Confirmed** | 2026, 3407 | Confirm | Study1.5-internal locked confirmatory evidence (same fixed TEST set, independent random seeds) |

Explore (seed 42) results were used to freeze the analysis plan. Confirm (seeds 2026, 3407) results are independent-seed replication on the same fixed TEST set under the frozen contract. This is Study1.5-internal evidence and does NOT belong to Study01 or Study02 formal evidence chain. The three-seed pooled bootstrap in `multi_seed_summary.csv` averages effects across seeds using the same 15-combo cluster-sampling indices per bootstrap iteration.

---

## 3. Scientific Conclusions

*Within the Study1.5 existing-grid Weibull domain (`n=7,10,20`), delta risk curve prediction task, and approximately equal-capacity MLP networks:*

### RQ1 — Input representation differences (F13 vs RAW)

F13 has small but systematic advantages over RAW. The three-seed pooled J1 difference (RAW−F13):

| test_n | RAW−F13 J1 | 95% CI |
|--------|-----------|--------|
| 7 | +0.00347 | [+0.00101, +0.00579] |
| 10 | +0.00429 | [+0.00084, +0.00785] |
| 20 | +0.00169 | [−0.00080, +0.00440] |

The difference is approximately 0.5%–0.8% of the F13 J1 magnitude. n=20 shows no stable difference (CI crosses zero). F13's advantage is small and task-specific; these results do NOT support a claim that statistical features are universally better than raw samples.

### RQ2 — Sample size information in features (F12 vs F13)

| test_n | F12−F13 J1 | 95% CI |
|--------|-----------|--------|
| 7 | +0.00285 | crosses zero |
| 10 | +0.00476 | crosses zero |
| 20 | +0.00447 | [+0.00045, +0.00837] |

Dropping explicit `n` (F12) slightly degrades J1. Only n=20 has a CI excluding zero. However, an n-probe logistic regression on F12 achieves **86.88% accuracy** (chance 33.3%) at identifying `n`. Conclusion: the remaining 12 statistical features already carry strong sample-size information; explicit `n` provides a small incremental benefit, clearest at n=20.

### RQ3 — Cross-sample-size generalization

All values below are three-seed pooled estimates from `multi_seed_summary.csv`.

#### Single-n transfer (T family)

All six directions for F13 and RAW show positive transfer cost (transfer model J1 > specialist S model J1 for the target n). F12 shows near-zero cost only from n=10 to n=7. **Different n values cannot be treated as interchangeable training domains.**

#### Joint training (J family vs S)

| test_n | F13 J−S | F12 J−S | RAW J−S |
|--------|---------|---------|---------|
| 7 | **−0.006862** | −0.004966 | −0.002352 |
| 10 | +0.004556 | +0.009483 | +0.007224 |
| 20 | +0.012120 | +0.015311 | +0.012116 |

At n=7, F13 joint training significantly outperforms the specialist (CI excludes zero). F12 also shows improvement but CI crosses zero. RAW CI crosses zero at n=7. At n=10 and n=20, all three representations' J−S CIs are strictly above zero. **Joint training does not uniformly benefit all sample sizes**; mixed-n training shows task competition or negative transfer at larger n under fixed model capacity.

#### Leave-one-n-out generalization (L family)

| holdout n | F13 L−S | F12 L−S | RAW L−S |
|-----------|---------|---------|---------|
| 7 | −0.002569 | **−0.009549** | +0.114431 |
| 10 | +0.011204 | +0.011700 | +0.065708 |
| 20 | +0.082307 | +0.029211 | +0.113255 |

At holdout n=7, F12 significantly improves over the specialist (CI excludes zero); F13 is near the specialist. RAW degrades severely. At holdout n=10 and n=20, all three representations show positive transfer cost. **Statistical features enable more transferable structure than padded RAW encoding**, but leave-one-n-out generalization is limited and does not support universal extrapolation to unobserved sample sizes.

### Supplementary 2×2 interaction — representation × training organization

This bounded post-hoc analysis reuses the same 90 frozen models and fixed TEST predictions; no model was retrained. It separates the representation contrast (`RAW−F13`) from the training-organization contrast (joint `J` versus sample-size-specific `S`). The interaction is

\[
(\mathrm{RAW}_J-\mathrm{F13}_J)-(\mathrm{RAW}_S-\mathrm{F13}_S).
\]

Positive values mean that RAW is penalized more than F13 by joint training. Intervals use the same paired 15-combination cluster bootstrap and are descriptive because this contrast was specified after the Stage 1 confirmatory results were available.

| test_n | F13 J | RAW J | F13 S | RAW S | interaction in J1 | 95% CI |
|--------|------:|------:|------:|------:|------------------:|:------:|
| 7 | 0.640496 | 0.643962 | 0.647358 | 0.646315 | +0.004510 | [+0.000009, +0.009115] |
| 10 | 0.534961 | 0.539250 | 0.530406 | 0.532026 | +0.002668 | [−0.000252, +0.005530] |
| 20 | 0.397721 | 0.399409 | 0.385601 | 0.387293 | −0.000004 | [−0.004062, +0.004162] |

The specialist F13 and RAW models are nearly equivalent at every tested n (absolute J1 differences 0.0010–0.0017, with no consistent direction). At n=20, the interaction is essentially zero: the joint-training penalty is the same for F13 and RAW, so it cannot be attributed to feature extraction. At n=10 the interaction is positive but its interval crosses zero. At n=7 the point estimates favor joint training for both representations, but only F13's `J−S` interval excludes zero; the interaction interval only narrowly excludes zero and one of three seed-specific effects is negative, so this is boundary evidence rather than a general interaction claim.

The result therefore does **not** show that switching to RAW would solve the mixed-n training problem. It shows instead that representation choice and training organization are separate design decisions: sample-size-specific training removes most of the observed F13-versus-RAW difference, while joint training has n-dependent benefits and costs regardless of representation.

---

## 4. Permitted Conclusions (contract §13)

- Specified-task representation differences under equal-capacity MLP.
- Transfer direction and cost for existing-grid n=7,10,20.
- Linear identifiability of n from F12 features and explicit n's task increment.
- Operational net benefit/cost of joint training.
- Applicability boundaries of Study01's current input scheme.

---

## 5. Prohibited Extrapolations (contract §13)

- 13 features are sufficient statistics, lossless, or universally optimal.
- RAW results represent all raw-sample neural networks.
- Conclusions apply to untested n, continuous n, out-of-grid parameters, or real data.
- Results validate or substitute Study02.
- Study1.5 artifacts belong to Study01 formal evidence chain.
