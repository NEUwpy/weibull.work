"""Diagnose LSE map-label errors without changing or tuning the classifier."""
from __future__ import annotations

import csv
import hashlib
import json

import numpy as np
from scipy.special import softmax
from scipy.stats import weibull_min
import torch

import b10_feature_selector as s
import b10_map_classifier as c
from b10_map_comparison import FIGURE_LABELS

DEST = c.OUT / 'lse_diagnosis'
REPORT = s.STUDY / 'B10方法选择-LSE错分诊断-v1.0.md'
SPEC = dict(
    question='Why are the four LSE map cells classified mostly as WMLE?',
    frozen='Original classifier, features, split, map and estimators unchanged',
    diagnostics=['Train/validation/test LSE recall and per-cell prediction probabilities',
                 'Fixed inverse training class-frequency probability correction, no tuning',
                 'Full-sample likelihood reference using known simulation eta/gamma and uniform beta-grid prior',
                 'Paired within-cell bootstrap of LSE/WMLE RMSE difference and champion stability'],
    bootstrap_repeats=1500, seed=2026102407,
    boundary='Post-hoc explanatory diagnostics on existing data, not new independent validation',
)


def raw_likelihood(data, manifest):
    betas = np.asarray(s.CONFIG['beta'], dtype=float)
    log_likelihood = np.full((len(data['x']), len(betas)), np.nan)
    for beta in betas:
        for n in s.CONFIG['n']:
            relative = f'结果/W{beta:g},1000,500/估计结果/n{n}.csv'
            path = s.STUDY / relative
            assert s.sha(path) == manifest['source_hashes'][relative]
            with path.open(encoding='utf-8-sig', newline='') as f:
                rows = list(csv.DictReader(f))
            ii = np.flatnonzero((data['beta'] == beta) & (data['n'] == n))
            sample = np.array([[float(row[f'观测值{k+1}']) for k in range(n)] for row in rows], dtype='<f8')
            assert [int(row['样本编号']) for row in rows] == data['rid'][ii].tolist()
            assert [hashlib.sha256(x.tobytes()).hexdigest() for x in sample] == data['hash'][ii].tolist()
            log_likelihood[ii] = weibull_min.logpdf(
                sample[:, None, :], betas[None, :, None], loc=500., scale=1000.).sum(axis=2)
            # Independent algebra check of the reference likelihood, not a new estimator.
            z = (sample[0] - 500.) / 1000.
            direct = n * np.log(betas / 1000.) + (betas - 1.) * np.log(z).sum() - (z[None, :] ** betas[:, None]).sum(axis=1)
            np.testing.assert_allclose(log_likelihood[ii[0]], direct, rtol=1e-12)
    assert np.isfinite(log_likelihood).all()
    return softmax(log_likelihood, axis=1)


def summary(pred, y, mask, data, lse):
    hits = pred[mask] == y[mask]
    cells = data['cell'][mask]
    lm = y[mask] == lse
    return dict(rows=int(mask.sum()), hits=int(hits.sum()), sample_agreement=float(hits.mean()),
                condition_equal_agreement=float(np.mean([hits[cells == cell].mean() for cell in np.unique(cells)])),
                lse_rows=int(lm.sum()), lse_hits=int(hits[lm].sum()), lse_recall=float(hits[lm].mean()))


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    s.json_write(DEST / 'spec.json', SPEC)
    manifest = json.loads((s.OUT / 'manifest.json').read_text(encoding='utf-8'))
    assert s.sha(s.OUT / 'dataset.npz') == manifest['dataset_sha256']
    classifier_hash = s.sha(c.OUT / 'classifier.pt')
    data = s.load_data()
    y, methods = c.labels(data)
    lse, wmle = methods.index('LSE'), methods.index('WMLE')
    bundle = torch.load(c.OUT / 'classifier.pt', weights_only=True)
    probability = c.predict(bundle, data['x'])
    choice = probability.argmax(axis=1)
    train = data['split'] == 0
    class_mass = np.bincount(y[train], weights=s.weights(data, train), minlength=len(methods))
    class_prior = class_mass / class_mass.sum()
    # A fixed diagnostic rule; no threshold chosen from test outcomes.
    corrected = probability / class_prior
    corrected /= corrected.sum(axis=1, keepdims=True)
    corrected_choice = corrected.argmax(axis=1)
    beta_posterior = raw_likelihood(data, manifest)
    reference = np.zeros_like(probability)
    for n in s.CONFIG['n']:
        mask = data['n'] == n
        mapping = np.zeros((len(s.CONFIG['beta']), len(methods)))
        for j, method in enumerate(FIGURE_LABELS[n]):
            mapping[j, methods.index(method)] = 1.
        reference[mask] = beta_posterior[mask] @ mapping
    np.testing.assert_allclose(reference.sum(axis=1), 1., atol=1e-12)
    reference_choice = reference.argmax(axis=1)
    split_rows = []
    for k, split in enumerate(['train', 'validation', 'test']):
        mask = data['split'] == k
        for strategy, pred in [('frozen_classifier', choice), ('fixed_class_prior_correction', corrected_choice),
                               ('known_simulation_full_sample_reference', reference_choice)]:
            split_rows.append(dict(split=split, strategy=strategy, **summary(pred, y, mask, data, lse)))
    details = []
    for cell in np.unique(data['cell'][y == lse]):
        for k, split in enumerate(['train', 'validation', 'test']):
            mask = (data['cell'] == cell) & (data['split'] == k)
            votes = np.bincount(choice[mask], minlength=len(methods))
            row = dict(cell=str(cell), beta=float(data['beta'][mask][0]), n=int(data['n'][mask][0]),
                       split=split, rows=int(mask.sum()), lse_hits=int(np.sum(choice[mask] == lse)),
                       lse_recall=float(np.mean(choice[mask] == lse)),
                       wmle_prediction_rate=float(np.mean(choice[mask] == wmle)),
                       lse_mean_probability=float(probability[mask, lse].mean()),
                       wmle_mean_probability=float(probability[mask, wmle].mean()),
                       corrected_lse_recall=float(np.mean(corrected_choice[mask] == lse)),
                       reference_lse_recall=float(np.mean(reference_choice[mask] == lse)))
            row.update({m + '_votes': int(votes[j]) for j, m in enumerate(methods)})
            details.append(row)
    stability = []
    rng = np.random.default_rng(SPEC['seed'])
    lj, wj = s.METHODS.index('LSE'), s.METHODS.index('WMLE')
    for cell in np.unique(data['cell'][y == lse]):
        mask = (data['cell'] == cell) & data['valid'].all(axis=1)
        squared = data['e'][mask] ** 2
        mse = squared.mean(axis=0)
        boot = []
        for start in range(0, SPEC['bootstrap_repeats'], 100):
            draws = rng.integers(len(squared), size=(min(100, SPEC['bootstrap_repeats'] - start), len(squared)))
            boot.append(squared[draws].mean(axis=1))
        boot = np.concatenate(boot)
        difference = (np.sqrt(boot[:, wj] / boot[:, lj]) - 1.) * 100.
        limits = np.percentile(difference, [2.5, 97.5])
        rank = np.argsort(mse)
        row = dict(cell=str(cell), beta=float(data['beta'][mask][0]), n=int(data['n'][mask][0]),
                   common_rows=int(mask.sum()), lse_rmse=float(np.sqrt(mse[lj])), wmle_rmse=float(np.sqrt(mse[wj])),
                   wmle_vs_lse_rmse_increase_pct=float((np.sqrt(mse[wj] / mse[lj]) - 1.) * 100.),
                   gap_ci95_low=float(limits[0]), gap_ci95_high=float(limits[1]),
                   map_runner_up=s.METHODS[int(rank[1])],
                   lse_bootstrap_champion_rate=float(np.mean(boot.argmin(axis=1) == lj)),
                   wmle_bootstrap_champion_rate=float(np.mean(boot.argmin(axis=1) == wj)))
        assert rank[0] == lj
        for k, split in enumerate(['train', 'validation', 'test']):
            part = mask & (data['split'] == k)
            row[split + '_common_rows'] = int(part.sum())
            row[split + '_champion'] = s.METHODS[int(np.argmin(np.mean(data['e'][part] ** 2, axis=0)))]
        stability.append(row)
    result = dict(spec=SPEC, class_prior={m: float(v) for m, v in zip(methods, class_prior)},
                  split_metrics=split_rows, lse_cells=details, label_stability=stability,
                  classifier_unchanged=classifier_hash == s.sha(c.OUT / 'classifier.pt'),
                  fixed_classifier_sha256=classifier_hash,
                  reference='Known eta=1000, gamma=500; raw observations; beta grid uniform; sum beta posterior by fixed map labels')
    s.json_write(DEST / 'diagnosis.json', result)
    s.csv_write(DEST / 'split_metrics.csv', split_rows)
    s.csv_write(DEST / 'lse_cell_predictions.csv', details)
    s.csv_write(DEST / 'label_stability.csv', stability)
    orig, adj, ideal = [next(r for r in split_rows if r['split'] == 'test' and r['strategy'] == name)
                        for name in ['frozen_classifier', 'fixed_class_prior_correction', 'known_simulation_full_sample_reference']]
    lines = ['# 地图分类中LSE错分原因：诊断 v1.0', '', '2026-10-24。冻结原分类网络、标签、特征、数据划分和七法实现，不重新训练或用测试结果选阈值。', '',
             '**主要判断：标签已核对；原网络没有在训练集上充分分出LSE。LSE是少数且零散的地图类别，单组样本又难以判断其真实β，最大概率判决倾向合并概率更大的其他方法。原图中3个LSE冠军与WMLE相差不到0.2%，标签的最优方法解释也较脆弱。**', '',
             '## 先看是不是只在测试集上失败', '',
             '| 数据部分 | LSE命中 / 组数 | LSE召回率 | 总体条件等权一致率 |', '|---|---:|---:|---:|']
    for row in split_rows:
        if row['strategy'] == 'frozen_classifier':
            lines.append(f'| {row["split"]} | {row["lse_hits"]}/{row["lse_rows"]} | {row["lse_recall"]:.2%} | {row["condition_equal_agreement"]:.2%} |')
    lines += ['', '## 类别比例与判决规则的影响', '',
              f'原训练目标按40个条件等权，不按方法类别等权：LSE占10%，WMLE占45%。把冻结概率除以训练类别比例（固定倒数校正，无调参）后，测试LSE召回率从{orig["lse_recall"]:.2%}变为{adj["lse_recall"]:.2%}，总体逐组一致率从{orig["sample_agreement"]:.2%}变为{adj["sample_agreement"]:.2%}。', '',
              '这说明改变判决权重可以改变LSE被压低的程度；它不是重新训练的类别平衡模型，也不能把这一步的全部变化归为训练类别比例的因果效应。原网络常把LSE放在非首位，最终argmax仍只返回概率最高的类别。', '',
              '## 4格的具体表现与标签差距', '',
              '| β | n | 测试LSE召回率 | 平均P(LSE) | 平均P(WMLE) | WMLE相对LSE的RMSE增加 | 配对95%区间 | 重抽样仍为LSE冠军 |', '|---:|---:|---:|---:|---:|---:|---|---:|']
    for r in stability:
        p = next(p for p in details if p['cell'] == r['cell'] and p['split'] == 'test')
        lines.append(f'| {r["beta"]:g} | {r["n"]} | {p["lse_recall"]:.2%} | {p["lse_mean_probability"]:.3f} | {p["wmle_mean_probability"]:.3f} | {r["wmle_vs_lse_rmse_increase_pct"]:+.2f}% | [{r["gap_ci95_low"]:+.2f}%, {r["gap_ci95_high"]:+.2f}%] | {r["lse_bootstrap_champion_rate"]:.1%} |')
    lines += ['', 'RMSE按原图口径在七法共同有效集合上计算；区间和冠军保持率来自同一格内成对重抽样1500次，固定已有估计，不是新数据确认。分类概率与召回使用全部留出组。', '',
              '## 区分网络拟合不足与单组样本判别困难', '',
              '使用所有原始观测，额外告知诊断参照真实η=1000、γ=500，并给8个候选β相同先验。用Weibull联合似然计算β后验，按地图标签合并后验，再选择最大者。它在这些已知仿真假设及逐组0–1损失下是贝叶斯判决参照，输入信息比当前30维网络更多；实际应用并不知道这些真参数，不能作为部署模型，也不把有限测试集结果叫作精确上限。', '',
              f'该参照在测试集上的总体逐组一致率为{ideal["sample_agreement"]:.2%}，LSE召回率为{ideal["lse_recall"]:.2%}；原网络分别为{orig["sample_agreement"]:.2%}和{orig["lse_recall"]:.2%}。', '',
              '即使使用完整样本和已知仿真参数，追求总体一致率的参照规则也很少输出LSE。这支持“相邻条件的样本信息重叠与类别合并的判决取舍参与错分”，不能把全部问题归为网络容量或训练轮次不足；也不意味着已经严格测出了该网络的可达上限。', '',
              '本诊断用于判断小样本对相邻β条件的区分困难是否参与错分；若参照也难以识别LSE，不能把现象全部归咎于网络训练不足。相同n下，LSE对应的4个β分别为2.5、3、4、4.5，每格只占所在n的一个β位置，两侧条件都是其他类别；需要从有抽样波动的单组样本判断是否落在这些窄区域。', '',
              '## 解释与边界', '',
              '已明确区分三件事：是否学到LSE标签、输出判决是否偏向其他类、原地图冠军差距是否稳定。不能因为地图某格写LSE，就认为该格每组样本特征都带有可准确识别的LSE标记；也不能因为方法RMSE接近，就声称它直接导致分类交叉熵错分——当前分类损失只看硬标签，不读取误差差距。', '',
              '所有诊断复用原样本，结论是对现象的证据解释，不是完全分解各因素的因果占比；固定地图与原模型仍保留。', '',
              'Weibull密度与位置尺度约定核对[官方SciPy文档](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.weibull_min.html)。', '',
              '证据：[汇总JSON](结果/B10方法选择-v1/map_classifier/lse_diagnosis/diagnosis.json)、[训练/验证/测试对比](结果/B10方法选择-v1/map_classifier/lse_diagnosis/split_metrics.csv)、[4格预测分布](结果/B10方法选择-v1/map_classifier/lse_diagnosis/lse_cell_predictions.csv)、[冠军稳定性](结果/B10方法选择-v1/map_classifier/lse_diagnosis/label_stability.csv)、[程序](程序/b10_lse_diagnosis.py)。', '']
    REPORT.write_text('\n'.join(lines), encoding='utf-8')
    assert result['classifier_unchanged']
    assert orig['hits'] == 7053 and orig['lse_hits'] == 51
    s.json_write(DEST / 'verification.json', dict(passed=True, original_classifier_unchanged=True,
                 frozen_dataset_checked=True, original_source_csvs_hashed=40,
                 raw_sample_hashes_checked=len(data['x']), likelihood_algebra_checked=True,
                 frozen_test_hits_reproduced=orig['hits'], lse_cells_checked=len(stability),
                 classifier_sha256=classifier_hash, program_sha256=s.sha(__file__),
                 report_sha256=s.sha(REPORT)))
    print(json.dumps(dict(split_metrics=split_rows, label_stability=stability,
                          lse_test_cells=[r for r in details if r['split'] == 'test']), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
