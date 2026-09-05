# Study02 v2.7.0 local reproducibility bundle

The ZIP in this directory is a local, reviewable bundle, not a public deposition. Its accompanying manifest gives every included path and SHA256. It preserves the repository-relative `Study/02-study-NN参数估计与分位点目标研究/` layout and the shared sample generator under `python/studies/common/`.

The bundle contains the current bilingual manuscripts and figure sources, study Python code and configurations, protocols, the prediction/metadata evidence needed by the reported main and supplementary analyses, analysis summaries, and saved supplementary checkpoints. It excludes unrelated studies, environment files, credentials, repository history, and superseded manuscript snapshots. Historical predictions that support the paper are included under their original paths. Original main-fit weights were not saved; their paired predictions and metadata are retained. Supplementary fits include selected weights and validation histories.

## Verify before analysis

Extract into a fresh directory. From the extracted repository root, run:

```powershell
python Study/02-study-NN参数估计与分位点目标研究/reproducibility/verify_bundle.py
```

The verifier checks the internal `BUNDLE_MANIFEST.json`, including file counts and hashes. It does not require model training. The ZIP-level SHA256 is recorded beside the archive. Hashes document the exact local inputs; they are not an independent scientific replication.

## Recalculate quantitative controls

Use the recorded environment versions in `environment.json`. NumPy, pandas, PyTorch and matplotlib are required; pytest is used for implementation checks. From the extracted Study02 `code` directory:

```powershell
$env:PQ_PROTOCOL='iid-v1'
python -m study02pq.submission_controls_analysis
```

From the Study02 root:

```powershell
python manuscript/tools/qp_comparison_v270.py
python manuscript/tools/figures_v270.py
python manuscript/tools/audit_zero_orphan.py
```

The analysis rechecks all 200 paired model units, exact reproduction of the original Q target metric and chosen epochs, matched sample keys, and finite predictions. Each route comprises 480,000 prediction rows over 48,000 samples and ten training seeds. Repeated rows across seeds are not independent samples. Crossed-bootstrap intervals condition on the existing simulation design.

The figure generator creates Chinese and English figures from the same plotting objects and evidence. Microsoft YaHei is used for Chinese labels when available; install a CJK font and adjust the font list if unavailable. English output uses DejaVu Sans. Different font/rendering-library versions can change image bytes without changing numerical data. Existing PDF/SVG/PNG outputs are included.

## Training and scientific boundaries

Protocol `25-投稿修订补充对照.md` defines the three supplemental trajectories and their validation rules. To inspect or resume the same matrix, from `code` use `PQ_PROTOCOL=iid-v1` and `python -m study02pq.submission_controls --workers 4`. Existing fit records are reused. For genuinely fresh retraining, use an isolated copy and change its output directory; preserve the bundled evidence. A one-unit smoke run is available with `--smoke --workers 1`.

The main common-budget comparison and subsequent controls reuse simulation samples whose earlier test results had been inspected. They are supplemental/sensitivity evidence, not fresh-data confirmation. Q_FEAS availability concerns only the native Q early-stopping trajectory. QMULTI directly supervises all three assessed points and is not a cross-point generalization test. No public repository URL or license has been assumed; authors must decide the release terms before distribution.
