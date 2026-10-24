"""Learn the existing B10 map's method labels from observable sample features."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import time

import numpy as np
import torch
from torch import nn

import b10_feature_selector as s
from b10_map_comparison import FIGURE_LABELS

OUT = s.OUT / 'map_classifier'
REPORT = s.STUDY / 'B10方法选择-地图分类匹配-v1.0.md'
SPEC = dict(
    objective='Reproduce the fixed original B10 map labels, not individual error minima',
    inputs=s.FEATURES, label_source='FIGURE_LABELS, checked against map_comparison_cells.csv',
    split='Reuse the frozen sample-hash 60/20/20 split; all 48000 samples eligible',
    architecture='Two SiLU hidden layers, width 64, logits for map-present classes',
    seed=42, epochs=160, patience=22, batch_size=1024,
    learning_rate=.001, weight_decay=.0001,
    selection='Minimum condition-equal validation cross entropy; test never used for selection',
    primary='Condition-equal fraction of individual sample-group predictions matching map labels',
    recovered_map='Majority vote over individual test predictions within each beta*n cell',
    baselines=['Training condition-equal majority class', 'Training majority class by observable n'],
    boundary='Agreement with a fixed original map; not independent validation of map optimality',
)


class Classifier(nn.Module):
    def __init__(self, dim, classes):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(dim, 64), nn.SiLU(), nn.Linear(64, 64),
                                 nn.SiLU(), nn.Linear(64, classes))

    def forward(self, x):
        return self.net(x)


def labels(data):
    table = {}
    with (s.OUT / 'map_comparison_cells.csv').open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            table[row['cell']] = row['report_map_method']
            expected = FIGURE_LABELS[int(row['n'])][s.CONFIG['beta'].index(float(row['beta']))]
            assert table[row['cell']] == expected
    assert len(table) == 40 and set(table) == set(data['cell'])
    methods = [m for m in s.METHODS if m in set(table.values())]
    y = np.array([methods.index(table[c]) for c in data['cell']], dtype=np.int64)
    return y, methods


def fit(data, y, methods, *, output=OUT, feature_columns=None, seed=None, variant='full'):
    idx = list(range(len(s.FEATURES))) if feature_columns is None else list(feature_columns)
    feature_names = [s.FEATURES[j] for j in idx]
    seed = SPEC['seed'] if seed is None else seed
    spec = dict(SPEC, inputs=feature_names, seed=seed)
    if variant != 'full':
        spec['variant'] = variant
    path = output / 'classifier.pt'
    if path.exists():
        bundle = torch.load(path, weights_only=True)
        assert bundle['dataset_sha256'] == s.sha(s.OUT / 'dataset.npz')
        assert bundle['map_sha256'] == s.sha(s.OUT / 'map_comparison_cells.csv')
        assert bundle['spec'] == spec and bundle['classes'] == methods
        assert bundle['features'] == feature_names
        return bundle
    output.mkdir(parents=True, exist_ok=True)
    s.json_write(output / 'spec.json', spec)
    tr, va = data['split'] == 0, data['split'] == 1
    x = data['x'][:, idx]
    center, scale = x[tr].mean(axis=0), x[tr].std(axis=0)
    scale = np.where(scale < 1e-10, 1., scale)
    tx = torch.tensor((x[tr] - center) / scale, dtype=torch.float32)
    vx = torch.tensor((x[va] - center) / scale, dtype=torch.float32)
    ty, vy = torch.tensor(y[tr]), torch.tensor(y[va])
    tw, vw = [torch.tensor(s.weights(data, mask), dtype=torch.float32) for mask in [tr, va]]
    torch.manual_seed(seed)
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    model = Classifier(len(idx), len(methods))
    optimizer = torch.optim.AdamW(model.parameters(), lr=spec['learning_rate'],
                                 weight_decay=spec['weight_decay'])
    generator = torch.Generator().manual_seed(seed + 10000)
    best, best_epoch, history = math.inf, 0, []
    started = time.monotonic()
    for epoch in range(1, spec['epochs'] + 1):
        model.train()
        for batch in torch.randperm(len(tx), generator=generator).split(spec['batch_size']):
            terms = nn.functional.cross_entropy(model(tx[batch]), ty[batch], reduction='none')
            loss = (terms * tw[batch]).sum() / tw[batch].sum()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 10.)
            optimizer.step()
        model.eval()
        with torch.no_grad():
            logits = model(vx)
            score = float((nn.functional.cross_entropy(logits, vy, reduction='none') * vw).sum() / vw.sum())
            accuracy = float(((logits.argmax(axis=1) == vy) * vw).sum() / vw.sum())
        assert math.isfinite(score)
        history.append(dict(epoch=epoch, validation_cross_entropy=score, validation_accuracy=accuracy))
        if score < best - 1e-6:
            best, best_epoch, best_state = score, epoch, copy.deepcopy(model.state_dict())
        if epoch - best_epoch >= spec['patience']:
            break
    bundle = dict(state=best_state, center=center.tolist(), scale=scale.tolist(),
                  classes=methods, features=feature_names, columns=idx, spec=spec,
                  train_rows=int(tr.sum()), validation_rows=int(va.sum()),
                  best_epoch=best_epoch, epochs_run=epoch, validation_cross_entropy=best,
                  seconds=time.monotonic() - started, dataset_sha256=s.sha(s.OUT / 'dataset.npz'),
                  map_sha256=s.sha(s.OUT / 'map_comparison_cells.csv'),
                  train_hash=hashlib.sha256(''.join(sorted(data['hash'][tr])).encode()).hexdigest())
    torch.save(bundle, path)
    s.json_write(output / 'training.json', {k: v for k, v in bundle.items() if k != 'state'} | dict(history=history))
    print(f'{variant} seed={seed}: best epoch={best_epoch}/{epoch}, val CE={best:.5f}, seconds={bundle["seconds"]:.1f}', flush=True)
    return bundle


def predict(bundle, x):
    model = Classifier(len(bundle['features']), len(bundle['classes']))
    model.load_state_dict(bundle['state'])
    model.eval()
    idx = bundle.get('columns', list(range(len(bundle['features']))))
    z = (x[:, idx] - np.asarray(bundle['center'])) / np.asarray(bundle['scale'])
    with torch.no_grad():
        return torch.softmax(model(torch.tensor(z, dtype=torch.float32)), dim=1).numpy().astype(float)


def evaluate(data, y, methods, bundle):
    tr, te = data['split'] == 0, data['split'] == 2
    cells, target = data['cell'][te], y[te]
    proba = predict(bundle, data['x'][te])
    chosen = proba.argmax(axis=1)
    wtr = s.weights(data, tr)
    majority = int(np.bincount(y[tr], weights=wtr, minlength=len(methods)).argmax())
    n_rule = {}
    for n in np.unique(data['n']):
        mask = data['n'][tr] == n
        n_rule[int(n)] = int(np.bincount(y[tr][mask], weights=wtr[mask], minlength=len(methods)).argmax())
    predictions = dict(classifier=chosen, majority=np.full(len(target), majority),
                       n_only=np.array([n_rule[int(n)] for n in data['n'][te]]))
    summaries = {}
    for name, pred in predictions.items():
        equal_rate = float(np.mean([np.mean(pred[cells == c] == target[cells == c]) for c in np.unique(cells)]))
        summaries[name] = dict(hits=int(np.sum(pred == target)), rows=len(target),
                               sample_rate=float(np.mean(pred == target)), condition_equal_rate=equal_rate)
    cell_rows = []
    for c in np.unique(cells):
        mask = cells == c
        i = np.flatnonzero(te & (data['cell'] == c))[0]
        votes = np.bincount(chosen[mask], minlength=len(methods))
        mode = int(votes.argmax())
        cell_rows.append(dict(cell=str(c), beta=float(data['beta'][i]), n=int(data['n'][i]),
                              rows=int(mask.sum()), map_method=methods[int(target[mask][0])],
                              predicted_majority_method=methods[mode],
                              map_match=bool(mode == target[mask][0]),
                              vote_tie=bool(np.sum(votes == votes.max()) > 1),
                              sample_agreement=float(np.mean(chosen[mask] == target[mask]))))
    confusion = np.zeros((len(methods), len(methods)), dtype=int)
    np.add.at(confusion, (target, chosen), 1)
    by_class = [dict(method=m, rows=int(confusion[j].sum()), hits=int(confusion[j, j]),
                     recall=float(confusion[j, j] / confusion[j].sum()),
                     map_cells=sum(r['map_method'] == m for r in cell_rows)) for j, m in enumerate(methods)]
    by_n = [dict(n=int(n), rows=int(np.sum(data['n'][te] == n)),
                 condition_equal_rate=float(np.mean([r['sample_agreement'] for r in cell_rows if r['n'] == n])),
                 grid_hits=sum(r['map_match'] for r in cell_rows if r['n'] == n), grid_total=8)
            for n in np.unique(data['n'])]
    result = dict(task='Fixed-map label imitation', classes=methods,
                  absent_map_methods=[m for m in s.METHODS if m not in methods],
                  split_rows=np.bincount(data['split']).tolist(), metrics=summaries,
                  grid_hits=sum(r['map_match'] for r in cell_rows), grid_total=len(cell_rows),
                  vote_ties=sum(r['vote_tie'] for r in cell_rows), by_class=by_class, by_n=by_n,
                  confusion_true_rows_pred_columns=confusion.tolist(),
                  majority_method=methods[majority], n_only_methods={n: methods[j] for n, j in n_rule.items()},
                  best_epoch=bundle['best_epoch'], single_seed=SPEC['seed'],
                  original_map_uses_all_1200_per_cell=True,
                  scope='Existing beta*n grid at eta=1000, gamma=500; match rate is not actual-best accuracy')
    s.json_write(OUT / 'evaluation.json', result)
    s.csv_write(OUT / 'cells.csv', cell_rows)
    s.csv_write(OUT / 'by_class.csv', by_class)
    s.csv_write(OUT / 'by_n.csv', by_n)
    rows = []
    for i, original in enumerate(np.flatnonzero(te)):
        row = dict(hash=str(data['hash'][original]), cell=str(cells[i]),
                   map_method=methods[int(target[i])], predicted_method=methods[int(chosen[i])],
                   match=bool(target[i] == chosen[i]))
        row.update({m + '_probability': float(proba[i, j]) for j, m in enumerate(methods)})
        rows.append(row)
    s.csv_write(OUT / 'test_predictions.csv', rows)
    lines = ['# 样本特征到B10地图类别：分类匹配 v1.0', '',
             '2026-10-24。按最新目标，直接学习已有B10性能地图的推荐方法标签，评价是否匹配原地图。', '',
             '## 怎么做', '',
             '输入沿用30维可观测样本特征（含样本量），输出地图中出现的5个方法类别；真β、η、γ、样本编号、七法估计值和误差均不作为输入。每个β×n条件的1200组样本共享原地图标签。', '',
             f'复用原样本哈希划分：训练{int(tr.sum()):,}、验证{bundle["validation_rows"]:,}、测试{int(te.sum()):,}组；不要求七法全部成功。使用两层64单元SiLU分类网络、交叉熵、条件等权、种子42，验证集选择早停轮次（第{bundle["best_epoch"]}轮），测试集只作最终评价。只有1次初始化，未作多模型筛选。', '',
             '## 匹配结果', '', '| 策略 | 测试命中组数 | 逐组一致率 | 40条件等权一致率 |', '|---|---:|---:|---:|']
    for name, title in [('majority', '始终预测训练多数类'), ('n_only', '只按样本量查训练多数类'), ('classifier', '样本特征分类网络')]:
        item = summaries[name]
        lines.append(f'| {title} | {item["hits"]:,}/{item["rows"]:,} | {item["sample_rate"]:.2%} | {item["condition_equal_rate"]:.2%} |')
    lines += ['', f'把每格测试样本的预测类别作多数投票后，恢复原图 **{result["grid_hits"]}/40格（{result["grid_hits"]/40:.1%}）**。多数票平局{result["vote_ties"]}格；若平局按存档类别顺序选取。', '',
              '本轮样本特征比只看样本量提供了额外的地图匹配能力，但尚未完整恢复原图：4个LSE格的多数票全部判成WMLE，另有1个MLE格判成WMLE。LSE逐组召回率只有5.18%，总体一致率不能代替逐类判断。', '',
              '![原地图与样本特征预测图](结果/B10方法选择-v1/map_classifier/map_match.png)', '',
              '| 样本量 n | 条件等权逐组一致率 | 多数投票恢复格数 |', '|---|---:|---:|']
    lines += [f'| {r["n"]} | {r["condition_equal_rate"]:.2%} | {r["grid_hits"]}/8 |' for r in by_n]
    lines += ['', '| 原地图类别 | 地图格数 | 测试组数 | 该类别召回率 |', '|---|---:|---:|---:|']
    lines += [f'| {r["method"]} | {r["map_cells"]} | {r["rows"]} | {r["recall"]:.2%} |' for r in by_class]
    lines += ['', '## 原图与预测图逐格对照', '',
              '下表每格为“原图 → 测试多数票”，加粗表示一致。', '',
              '| n / β | ' + ' | '.join(f'{b:g}' for b in s.CONFIG['beta']) + ' |',
              '|---|' + '---|' * len(s.CONFIG['beta'])]
    for n in [50, 20, 15, 10, 7]:
        cells_text = []
        for beta in s.CONFIG['beta']:
            r = next(r for r in cell_rows if r['n'] == n and r['beta'] == beta)
            text = r['map_method'] + ' → ' + r['predicted_majority_method']
            cells_text.append('**' + text + '**' if r['map_match'] else text)
        lines.append(f'| {n} | ' + ' | '.join(cells_text) + ' |')
    lines += ['', '## 结论边界', '',
              '本轮直接回答“从一组样本特征能否复现所在条件的地图推荐”。地图冠军来自整格平均误差，分类标签由已有地图冻结；这里的一致率可以称为地图标签预测准确率，不能称为选中当前样本真实最优方法的概率。原地图使用每格全部1200组估计结果，包含测试样本的误差；本轮是对既定地图的模仿，不是地图本身最优性的独立验证。', '',
              '当前证据限已有40个β×n条件、η=1000与γ=500。测试是相同条件中的留出样本，尚未说明新β、新n或新尺度、位置条件的地图复现能力。MMLE(KR)与MM没有成为原地图冠军，本轮没有这两类的正标签。', '',
              '输入特征既有单组抽样波动，也反映生成条件；匹配较差的格子及类别应直接保留，不通过修改原图或查看测试结果反复调参来抬高一致率。', '',
              '## 复现与证据', '',
              '- [分类程序](程序/b10_map_classifier.py)：`python "Study/04-study-小样本三参数Weibull估计方法比较与选择/程序/b10_map_classifier.py" run`。',
              '- [逐格结果](结果/B10方法选择-v1/map_classifier/cells.csv)、[逐组预测](结果/B10方法选择-v1/map_classifier/test_predictions.csv)、[指标及混淆矩阵](结果/B10方法选择-v1/map_classifier/evaluation.json)。',
              '- [训练配置](结果/B10方法选择-v1/map_classifier/spec.json)、[训练记录](结果/B10方法选择-v1/map_classifier/training.json)、[核验记录](结果/B10方法选择-v1/map_classifier/verification.json)。',
              '- [原地图对照说明](B10方法选择-性能地图对照补充-v1.0.md)。本轮另存分类模型，不覆盖原风险预测模型。', '']
    REPORT.write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False), flush=True)


def verify(data, y, methods, bundle):
    manifest = json.loads((s.OUT / 'manifest.json').read_text(encoding='utf-8'))
    assert s.sha(s.OUT / 'dataset.npz') == manifest['dataset_sha256']
    for name, expected in manifest['model_sha256'].items():
        assert s.sha(s.OUT / name) == expected
    s.verify_source_files()
    assert bundle['features'] == s.FEATURES and len(bundle['features']) == 30
    for a in range(3):
        for b in range(a):
            assert set(data['hash'][data['split'] == a]).isdisjoint(set(data['hash'][data['split'] == b]))
    tr, te = data['split'] == 0, data['split'] == 2
    np.testing.assert_allclose(bundle['center'], data['x'][tr].mean(axis=0))
    expected_scale = data['x'][tr].std(axis=0)
    np.testing.assert_allclose(bundle['scale'], np.where(expected_scale < 1e-10, 1., expected_scale))
    with (OUT / 'test_predictions.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    assert [r['hash'] for r in rows] == data['hash'][te].tolist()
    probability = predict(bundle, data['x'][te])
    np.testing.assert_allclose(probability.sum(axis=1), 1., atol=2e-7)
    for j, method in enumerate(methods):
        np.testing.assert_allclose([float(r[method + '_probability']) for r in rows], probability[:, j])
    result = json.loads((OUT / 'evaluation.json').read_text(encoding='utf-8'))
    independently_counted = sum(r['predicted_method'] == r['map_method'] for r in rows)
    assert independently_counted == result['metrics']['classifier']['hits']
    for c in np.unique(data['cell']):
        assert len(np.unique(y[data['cell'] == c])) == 1
    s.json_write(OUT / 'verification.json', dict(passed=True, test_rows=len(rows),
                 checked='Frozen data and risk checkpoints, split separation, train-only scaling, map labels, prediction reload and agreement counts',
                 classifier_sha256=s.sha(OUT / 'classifier.pt'),
                 program_sha256=s.sha(__file__), report_sha256=s.sha(REPORT)))
    print('Verification passed: original data/models unchanged; classification predictions and match counts reproduced.', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['run', 'verify', 'predict'])
    parser.add_argument('--sample', nargs='+', type=float)
    args = parser.parse_args()
    if args.action == 'predict':
        if args.sample is None:
            parser.error('predict requires --sample')
        bundle = torch.load(OUT / 'classifier.pt', weights_only=True)
        probability = predict(bundle, s.features(args.sample)[None, :])[0]
        print(json.dumps(dict(predicted_map_method=bundle['classes'][int(probability.argmax())],
                              map_class_probabilities=dict(zip(bundle['classes'], probability.tolist())),
                              scope='Fixed-map label prediction at eta=1000, gamma=500'), ensure_ascii=False, indent=2))
        return
    data = s.load_data()
    y, methods = labels(data)
    if args.action == 'run':
        bundle = fit(data, y, methods)
        evaluate(data, y, methods, bundle)
    else:
        bundle = torch.load(OUT / 'classifier.pt', weights_only=True)
    verify(data, y, methods, bundle)


if __name__ == '__main__':
    main()
