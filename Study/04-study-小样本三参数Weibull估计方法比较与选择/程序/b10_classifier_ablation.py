"""Matched-seed feature deletion/refit for fixed B10-map classification."""
from __future__ import annotations

import csv
import hashlib
import json

import numpy as np
import torch

import b10_feature_selector as s
import b10_map_classifier as c

OUT = c.OUT / 'ablation'
REPORT = s.STUDY / 'B10方法选择-分类器特征消融-v1.0.md'
SEEDS = [42, 43, 44]
REMOVED = {
    'full': [],
    'no_n': s.GROUPS['n'],
    'no_level': s.GROUPS['level'],
    'no_quantiles': s.GROUPS['quantiles'],
    'no_moments': s.GROUPS['moments'],
    'no_spacing': s.GROUPS['spacing'],
    'no_shape': s.GROUPS['quantiles'] + s.GROUPS['moments'],
}
NAMES = dict(full='完整特征', no_n='删除样本量', no_level='删除位置尺度',
             no_quantiles='删除分位数', no_moments='删除矩与形状统计量',
             no_spacing='删除间距', no_shape='删除全部形状（分位数＋矩）')


def columns(variant):
    return [i for i, name in enumerate(s.FEATURES) if name not in REMOVED[variant]]


def metrics(probability, target, cells):
    pred = probability.argmax(axis=1)
    correct = pred == target
    class_count = probability.shape[1]
    recall = [float(correct[target == j].mean()) for j in range(class_count)]
    grid = []
    for cell in np.unique(cells):
        mask = cells == cell
        votes = np.bincount(pred[mask], minlength=class_count)
        majority = int(votes.argmax())
        grid.append(dict(cell=str(cell), rows=int(mask.sum()), map_class=int(target[mask][0]),
                         predicted_majority_class=majority, grid_match=bool(majority == target[mask][0]),
                         sample_agreement=float(correct[mask].mean()),
                         vote_tie=bool(np.sum(votes == votes.max()) > 1)))
    return dict(sample_agreement=float(correct.mean()),
                condition_equal_agreement=float(np.mean([r['sample_agreement'] for r in grid])),
                cross_entropy=float(np.mean([np.mean(-np.log(probability[cells == cell, target[cells == cell]].clip(1e-12))) for cell in np.unique(cells)])),
                class_recall=recall, macro_recall=float(np.mean(recall)),
                grid_hits=sum(r['grid_match'] for r in grid)), grid


def paired_interval(effect, cells):
    rng = np.random.default_rng(2026102408)
    samples = np.zeros(1500)
    for cell in np.unique(cells):
        values = effect[cells == cell]
        draw = rng.integers(len(values), size=(len(samples), len(values)))
        samples += values[draw].mean(axis=1) / len(np.unique(cells))
    return (np.percentile(samples, [2.5, 97.5]) * 100.).tolist()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = s.load_data()
    y, methods = c.labels(data)
    tr, te = data['split'] == 0, data['split'] == 2
    cells, target = data['cell'][te], y[te]
    manifest = json.loads((s.OUT / 'manifest.json').read_text(encoding='utf-8'))
    assert s.sha(s.OUT / 'dataset.npz') == manifest['dataset_sha256']
    spec = dict(task='Feature deletion/refit for original B10 map-label matching',
                seeds=SEEDS, removed_features=REMOVED,
                frozen_dataset_sha256=s.sha(s.OUT / 'dataset.npz'),
                frozen_map_sha256=s.sha(s.OUT / 'map_comparison_cells.csv'),
                original_classifier_sha256=s.sha(c.OUT / 'classifier.pt'),
                training='Reuse b10_map_classifier.fit; two hidden SiLU layers width64; same optimizer, split, condition weights and early stopping',
                selection='Validation cross entropy only; do not choose a variant on test results',
                primary='Mean of 3 separate models condition-equal sample agreement, not ensemble agreement',
                interval='Paired within-cell bootstrap 1500 times, average matched-seed correctness differences; trained models fixed',
                interpretation='Group incremental predictive information under this training procedure; correlated features may substitute, contributions need not add',
                scope='Existing eta=1000, gamma=500, 40-cell map; no newly generated test data')
    spec_path = OUT / 'spec.json'
    if spec_path.exists():
        assert json.loads(spec_path.read_text(encoding='utf-8')) == spec
    else:
        s.json_write(spec_path, spec)
    predictions = np.empty((len(REMOVED), len(SEEDS), int(te.sum()), len(methods)))
    records, class_rows, cell_rows, n_rows, model_hashes = [], [], [], [], {}
    train_hash = hashlib.sha256(''.join(sorted(data['hash'][tr])).encode()).hexdigest()
    for v, variant in enumerate(REMOVED):
        idx = columns(variant)
        for j, seed in enumerate(SEEDS):
            destination = c.OUT if variant == 'full' and seed == 42 else OUT / 'models' / f'{variant}_s{seed}'
            bundle = c.fit(data, y, methods, output=destination, feature_columns=idx, seed=seed, variant=variant)
            assert bundle['train_hash'] == train_hash and bundle['train_rows'] == int(tr.sum())
            assert bundle['features'] == [s.FEATURES[k] for k in idx]
            np.testing.assert_allclose(bundle['center'], data['x'][tr][:, idx].mean(axis=0))
            scale = data['x'][tr][:, idx].std(axis=0)
            np.testing.assert_allclose(bundle['scale'], np.where(scale < 1e-10, 1., scale))
            p = c.predict(bundle, data['x'][te])
            assert np.isfinite(p).all()
            np.testing.assert_allclose(p.sum(axis=1), 1., atol=2e-7)
            predictions[v, j] = p
            metric, grid = metrics(p, target, cells)
            record = dict(variant=variant, seed=seed, kept_dimensions=len(idx),
                          best_epoch=bundle['best_epoch'], epochs_run=bundle['epochs_run'],
                          validation_cross_entropy=bundle['validation_cross_entropy'],
                          **{k: value for k, value in metric.items() if k != 'class_recall'})
            records.append(record)
            class_rows.extend(dict(variant=variant, seed=seed, method=method, recall=metric['class_recall'][k])
                              for k, method in enumerate(methods))
            cell_rows.extend(dict(variant=variant, seed=seed, **row) for row in grid)
            for n in np.unique(data['n']):
                selected_grid = [r for r in grid if int(data['n'][te][cells == r['cell']][0]) == n]
                n_rows.append(dict(variant=variant, seed=seed, n=int(n),
                                   condition_equal_agreement=float(np.mean([r['sample_agreement'] for r in selected_grid])),
                                   grid_hits=sum(r['grid_match'] for r in selected_grid)))
            model_hashes[str((destination / 'classifier.pt').relative_to(s.OUT))] = s.sha(destination / 'classifier.pt')
        latest = [r['condition_equal_agreement'] for r in records if r['variant'] == variant]
        print(f'{variant}: three-seed mean condition-equal agreement={np.mean(latest):.4%}', flush=True)
    np.savez_compressed(OUT / 'test_predictions.npz', probabilities=predictions,
                        variants=np.array(list(REMOVED)), seeds=np.array(SEEDS),
                        target=target, cells=cells, sample_hash=data['hash'][te], classes=np.array(methods))
    baseline = predictions[0].argmax(axis=2) == target[None, :]
    aggregate = []
    for v, variant in enumerate(REMOVED):
        selected = [r for r in records if r['variant'] == variant]
        correct = predictions[v].argmax(axis=2) == target[None, :]
        paired = baseline.astype(float) - correct.astype(float)
        effect = paired.mean(axis=0)
        drops = np.array([np.mean([row[cells == cell].mean() for cell in np.unique(cells)]) for row in paired]) * 100.
        low, high = paired_interval(effect, cells) if variant != 'full' else [0., 0.]
        recalls = [r['recall'] for r in class_rows if r['variant'] == variant and r['method'] == 'LSE']
        aggregate.append(dict(variant=variant, name=NAMES[variant], kept_dimensions=len(columns(variant)),
                              agreement_mean=float(np.mean([r['condition_equal_agreement'] for r in selected])),
                              agreement_min=float(min(r['condition_equal_agreement'] for r in selected)),
                              agreement_max=float(max(r['condition_equal_agreement'] for r in selected)),
                              sample_agreement_mean=float(np.mean([r['sample_agreement'] for r in selected])),
                              agreement_drop_pp=float(drops.mean()), drop_ci95_low_pp=low, drop_ci95_high_pp=high,
                              drop_seed_min_pp=float(drops.min()), drop_seed_max_pp=float(drops.max()),
                              grid_hits_mean=float(np.mean([r['grid_hits'] for r in selected])),
                              grid_hits_min=min(r['grid_hits'] for r in selected), grid_hits_max=max(r['grid_hits'] for r in selected),
                              lse_recall_mean=float(np.mean(recalls)),
                              macro_recall_mean=float(np.mean([r['macro_recall'] for r in selected])),
                              cross_entropy_mean=float(np.mean([r['cross_entropy'] for r in selected]))))
    result = dict(spec=spec, classes=methods, test_rows=int(te.sum()), summary=aggregate,
                  model_hashes=model_hashes, individual_runs=records)
    s.json_write(OUT / 'evaluation.json', result)
    s.csv_write(OUT / 'summary.csv', aggregate)
    s.csv_write(OUT / 'runs.csv', records)
    s.csv_write(OUT / 'class_recall.csv', class_rows)
    s.csv_write(OUT / 'cells.csv', cell_rows)
    s.csv_write(OUT / 'by_n.csv', n_rows)
    # These exact feature identities explain why group deletion is not independent attribution.
    f = {name: data['x'][:, j] for j, name in enumerate(s.FEATURES)}
    n_observed = np.exp(f['log_n'])
    reconstructed = dict(cv=np.exp(f['log_std'] - f['log_mean']),
                         z_mean=np.exp(f['log_mean'] - f['log_range']) - np.exp(f['log_min'] - f['log_range']),
                         z_std=np.exp(f['log_std'] - f['log_range']) * np.sqrt((n_observed - 1.) / n_observed))
    redundancy = {}
    for name, expected in reconstructed.items():
        np.testing.assert_allclose(expected, f[name], atol=1e-12, rtol=1e-12)
        redundancy[name + '_max_abs_reconstruction_error'] = float(np.max(np.abs(expected - f[name])))
    s.json_write(OUT / 'redundancy_check.json', redundancy)
    # Independent checks against the previously frozen seed42 result and stored probabilities.
    with (c.OUT / 'test_predictions.csv').open(encoding='utf-8-sig', newline='') as f:
        frozen = list(csv.DictReader(f))
    assert [r['hash'] for r in frozen] == data['hash'][te].tolist()
    for j, method in enumerate(methods):
        np.testing.assert_allclose(predictions[0, 0, :, j], [float(r[method + '_probability']) for r in frozen])
    assert int(baseline[0].sum()) == 7053
    assert spec['original_classifier_sha256'] == s.sha(c.OUT / 'classifier.pt')
    assert spec['frozen_dataset_sha256'] == s.sha(s.OUT / 'dataset.npz')
    s.verify_source_files()
    lines = ['# 地图分类器的样本特征消融 v1.0', '',
             '2026-10-24。直接针对“样本特征→既有B10地图方法类别”的分类器做删除信息并重新训练，不沿用误差预测网络的消融结论。', '',
             '## 怎样比较', '',
             '冻结48,000组样本、地图标签和哈希划分（训练28,807、验证9,551、测试9,642）；每种设置匹配42/43/44三个随机种子，隐藏层宽度64×64、优化器、条件等权交叉熵、预算与验证集早停规则相同。完整特征的种子42复用原模型，另外训练20个模型。各方法类别的训练权重没有改成类别等权。', '',
             '主结果是三个独立模型的40条件等权匹配率均值，不是三个模型集成后的结果。下降单位为百分点，正数表示删掉信息后更差；配对区间固定已训练模型，在条件内重抽样1500次，跨初始化的变化另存。每格由测试样本预测类别的多数票恢复地图。', '',
             '## 总体与LSE结果', '',
             '| 设置 | 保留维数 | 地图标签匹配率 | 比完整特征下降（百分点） | 下降的95%区间 | 恢复格数均值 / 40 | LSE召回率 |',
             '|---|---:|---:|---:|---|---:|---:|']
    for r in aggregate:
        lines.append(f'| {r["name"]} | {r["kept_dimensions"]} | {r["agreement_mean"]:.2%} | {r["agreement_drop_pp"]:+.2f} | [{r["drop_ci95_low_pp"]:+.2f}, {r["drop_ci95_high_pp"]:+.2f}] | {r["grid_hits_mean"]:.2f} | {r["lse_recall_mean"]:.2%} |')
    lines += ['', '完整特征与所有消融均报告3次初始化的平均结果；完整特征第42种子的逐组一致率仍为73.15%，与原报告一致。当前表的主列采用条件等权均值，因此数值可略有不同。', '',
              '## 各类别受到什么影响', '',
              '| 设置 | ' + ' | '.join(methods) + ' |', '|---|' + '---:|' * len(methods)]
    for variant in REMOVED:
        values = [np.mean([r['recall'] for r in class_rows if r['variant'] == variant and r['method'] == method]) for method in methods]
        lines.append('| ' + NAMES[variant] + ' | ' + ' | '.join(f'{v:.2%}' for v in values) + ' |')
    table = {r['variant']: r for r in aggregate}
    lines += ['', '## 得到了什么认识', '',
              f'位置尺度组显示最大的额外贡献：删除后匹配率下降{table["no_level"]["agreement_drop_pp"]:.2f}个百分点，三次初始化的下降范围为{table["no_level"]["drop_seed_min_pp"]:.2f}—{table["no_level"]["drop_seed_max_pp"]:.2f}个百分点；LSE召回率从{table["full"]["lse_recall_mean"]:.2%}降到{table["no_level"]["lse_recall_mean"]:.2%}。样本量的独立增量较小，约{table["no_n"]["agreement_drop_pp"]:.2f}个百分点。', '',
              f'分位数、矩和间距没有显示额外总体收益。删除间距后总体均值升到{table["no_spacing"]["agreement_mean"]:.2%}，但LSE召回率反而降到{table["no_spacing"]["lse_recall_mean"]:.2%}；整体匹配率和少数类别识别仍不是同一件事。所有设置的LSE召回率均不足7%，当前的组删除没有解决LSE问题。', '',
              '数据核对还确认了信息重叠：变异系数CV可由log_std与log_mean恢复；归一化均值可由均值、最小值、极差恢复；归一化标准差可由原标准差、极差和n恢复。48,000组样本中的重建误差均在浮点精度范围内。因此即使删除显式形状统计，保留特征中仍含有相应信息，不能据此说分类不需要形状。', '',
              '## 怎样解释', '',
              '删除组后明显下降，支持该组在当前训练流程与参数范围下提供额外分类信息；删除组影响很小，可能因为其他特征携带重叠信息，不能据此断言它与生成条件无关。删除后略有提高，可能反映有限样本训练与冗余信息的影响，不应把微小变化当作确定的新规律。', '',
              '样本量本身已知，但形状统计和间距也可能反映n；位置尺度组含绝对均值、标准差和极值，当前η、γ固定，它们可能同时提供β的线索。因此本消融不证明它们在未知尺度、位置条件下仍然最有用。各组共享信息，下降值不能相加归一成100%的贡献。', '',
              '原地图的标签保持不变；LSE只占4/40格。本轮不改变类别权重，不按测试结果挑选新模型，不能把消融自动当作解决LSE识别的方案。使用的是已反复检查过的原留出集，属于追加解释分析，没有新增独立测试确认。', '',
              '## 复现与产物', '',
              '- [程序](程序/b10_classifier_ablation.py)：`python "Study/04-study-小样本三参数Weibull估计方法比较与选择/程序/b10_classifier_ablation.py"`。已有同配置模型自动复用。',
              '- [消融汇总](结果/B10方法选择-v1/map_classifier/ablation/summary.csv)、[每次训练结果](结果/B10方法选择-v1/map_classifier/ablation/runs.csv)、[各类召回](结果/B10方法选择-v1/map_classifier/ablation/class_recall.csv)、[按样本量结果](结果/B10方法选择-v1/map_classifier/ablation/by_n.csv)。',
              '- [全部逐格结果](结果/B10方法选择-v1/map_classifier/ablation/cells.csv)、[配置](结果/B10方法选择-v1/map_classifier/ablation/spec.json)、[汇总JSON](结果/B10方法选择-v1/map_classifier/ablation/evaluation.json)、[特征重叠核对](结果/B10方法选择-v1/map_classifier/ablation/redundancy_check.json)、[核验](结果/B10方法选择-v1/map_classifier/ablation/verification.json)。', '']
    REPORT.write_text('\n'.join(lines), encoding='utf-8')
    s.json_write(OUT / 'verification.json', dict(passed=True, models=21, new_models=20,
                 original_classifier_unchanged=True, dataset_unchanged=True,
                 frozen_seed42_probabilities_reproduced=True, training_hash_matched=train_hash,
                 train_only_scaling_checked=True, selected_feature_columns_checked=True,
                 exact_redundant_feature_identities_checked=True,
                 method_implementations_unchanged=True, bootstrap_repeats=1500,
                 program_sha256=s.sha(__file__), classifier_program_sha256=s.sha(c.__file__),
                 report_sha256=s.sha(REPORT)))
    print(json.dumps(aggregate, ensure_ascii=True), flush=True)
    print('Verification passed: 21 matched-seed models; original model/data preserved.', flush=True)


if __name__ == '__main__':
    main()
