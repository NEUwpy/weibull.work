"""2026-10-10: summarize archived Figure 1 estimates and revise Chapter 1.

No resampling, refitting, or figure changes. Full successful estimates are used,
including values outside Figure 1's display windows. Output stays with code.
"""
import ast
import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BATCH = HERE.parent
REPORT = BATCH.parent / '报告1：高形状参数下的估计偏移.md'
GENERATOR = HERE / '生成报告.py'
BOUNDARY = '## 第二章　机制分析与对照实验'
METHODS = ['mdm', 'lse', 'lre', 'wmle', 'mle']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reviewed_text(code):
    for node in ast.parse(code).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'REPORT_TEXT' for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('REPORT_TEXT not found')


def main():
    source = HERE / '输入快照/原案例估计.json'
    figure_data = BATCH / '结果/中间数据/图1小提琴数据与核验.json'
    protected = [source, figure_data, BATCH / '结果/图1_原案例参数分布.png',
                 BATCH / '结果/高形状参数补偿统计.xlsx',
                 BATCH / '结果/中间数据/实际估计.json',
                 BATCH / '结果/中间数据/样本.json',
                 BATCH / '结果/中间数据/逐法过程曲线.json']
    hashes = {str(p): digest(p) for p in protected}
    rows = json.loads(source.read_text(encoding='utf-8'))
    panels = json.loads(figure_data.read_text(encoding='utf-8'))['panels']
    summaries = []
    for n in (7, 15):
        for method in METHODS:
            attempts = [r for r in rows if r['beta'] == 5 and r['n'] == n and r['method'] == method]
            success = sorted((r for r in attempts if r['converged']), key=lambda r: r['sample_id'])
            assert len(attempts) == 50
            quartiles = {}
            for parameter in ('beta_hat', 'eta_hat', 'gamma_hat'):
                values = np.asarray([r[parameter] for r in success], float)
                assert np.isfinite(values).all()
                q = np.quantile(values, [.25, .5, .75])
                panel = next(p for p in panels if (p['n'], p['method'], p['parameter']) == (n, method, parameter))
                assert np.array_equal(values, np.asarray(panel['values']))
                assert np.allclose(q, panel['quartiles'], rtol=0, atol=1e-12)
                quartiles[parameter] = q.tolist()
            summaries.append(dict(n=n, method=method, attempts=50, success=len(success),
                                  failed=50-len(success), quartiles=quartiles,
                                  gamma_zero=sum(r['gamma_hat'] == 0 for r in success),
                                  joint_gamma_high_eta_beta_low=sum(r['gamma_hat'] > 500 and r['eta_hat'] < 1000 and r['beta_hat'] < 5 for r in success)))
    index = {(r['n'], r['method']): r for r in summaries}

    def median_range(n, parameter, decimals):
        values = sorted(index[n, m]['quartiles'][parameter][1] for m in ('mdm', 'wmle'))
        return f'{values[0]:.{decimals}f}–{values[1]:.{decimals}f}'

    current = REPORT.read_text(encoding='utf-8')
    generator_bytes = GENERATOR.read_bytes()
    generator = GENERATOR.read_text(encoding='utf-8')
    assert current == reviewed_text(generator), 'Report and generator differ; preserve manual edits before revision'
    heading, tail = current.split(BOUNDARY, 1)
    title = heading.split('## 第一章　问题描述', 1)[0]
    chapter = f'''## 第一章　问题描述

对真参数β=5、η=1000、γ=500生成的样本进行估计，发现多种方法得到的γ偏高、η和β偏低，部分估计呈现出位置接近1000、尺度接近500的现象。样本生成与参数对应关系已核验正确。图1展示n=7、15各50组样本的估计分布。

![图1　原β=5案例的估计分布](20261001-高形状参数补偿报告/结果/图1_原案例参数分布.png)

**图1｜高β样本的估计出现位置高估、尺度与形状低估，偏移程度因方法而异。**

n=7时，MDM和WMLE的成功估计中位数为β≈{median_range(7, 'beta_hat', 1)}、η≈{median_range(7, 'eta_hat', 0)}、γ≈{median_range(7, 'gamma_hat', 0)}，与真值相比形成明显的共同偏移。LSE、LRE和MLE的中位数也沿同一方向偏移，但估计分布更宽，同时存在γ低估和γ=0的结果，说明同一方法在不同样本上的偏移方向与程度并不一致。

样本量由7增至15后，五种方法的γ、η中位数均向真值靠近。MDM和WMLE仍有明显偏移：β中位数约为{median_range(15, 'beta_hat', 1)}、η约为{median_range(15, 'eta_hat', 0)}、γ约为{median_range(15, 'gamma_hat', 0)}。LSE、LRE和MLE的分布仍较宽，增大样本量并未消除样本间的估计差异。

'''
    updated = title + chapter + BOUNDARY + tail
    start = generator_bytes.index('## 第一章　问题描述'.encode('utf-8'))
    end = generator_bytes.index(BOUNDARY.encode('utf-8'), start)
    old_block = generator_bytes[start:end]
    line_ending = b'\r\n' if b'\r\n' in old_block else b'\n'
    new_block = chapter.encode('utf-8').replace(b'\n', line_ending)
    updated_generator_bytes = generator_bytes[:start] + new_block + generator_bytes[end:]
    updated_generator = updated_generator_bytes.decode('utf-8')
    assert reviewed_text(updated_generator) == updated
    assert updated.split(BOUNDARY, 1)[1] == tail
    for method in METHODS:
        for parameter, truth in [('gamma_hat', 500), ('eta_hat', 1000)]:
            before = abs(index[7, method]['quartiles'][parameter][1]-truth)
            after = abs(index[15, method]['quartiles'][parameter][1]-truth)
            assert after < before
    REPORT.write_text(updated, encoding='utf-8', newline='\n')
    GENERATOR.write_bytes(updated_generator_bytes)
    assert all(digest(Path(p)) == h for p, h in hashes.items())
    audit = dict(scope='Original beta=5 batch; n=7/15; five methods; archived successful estimates only',
                 statistics_source='All successful estimates, including values outside the display window',
                 samples_per_n=50, parameters_true=dict(beta=5, eta=1000, gamma=500),
                 summaries=summaries, chapter1=chapter,
                 protected_sha256=hashes, scientific_inputs_and_figure_unchanged=True,
                 chapters2_and3_unchanged=True, generator_matches_report=True)
    (HERE / '第一章偏移统计与修订.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(chapter)
    print('PASS: full archived statistics match Figure 1; data, figure, later chapters unchanged')


if __name__ == '__main__':
    main()
