"""Replace figure 2's lower histograms with exact minimum-density curves.

The original six observation panels remain unchanged. The new curves follow
the known iid Weibull model, rather than smoothing the fifty observed minima.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
from scipy.integrate import quad
from scipy.stats import weibull_min


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PREVIOUS = HERE / '20261010-导入图补入n30.json'
RECORD = Path(__file__).with_suffix('.json')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sync_density_derivation():
    report = ROOT.parent / '报告1：高形状参数下的估计偏移.md'
    text = report.read_text(encoding='utf-8')
    chapter1, methods = text.split('## 第二章')[0], text.split('### 2.1 MDM', 1)[1]
    anchor = '![图2　样本观测与真实起点]'
    addition = (
        '最小观测超过t，要求n个独立观测都超过t，故其生存概率为$[1-F(t)]^n$；对t取负导数，得到：\n\n'
        '$$f_{t_1}(t)=n[1-F(t)]^{n-1}f(t).$$\n\n'
        '其中，fₜ₁(t)为最小观测的概率密度。图2下方据此叠加n=7、15、30的理论分布。\n\n'
    )
    # The reviewed report may keep this derivation in supplementary material.
    if '$$f_{t_1}(t)=n[1-F(t)]^{n-1}f(t).$$' not in text:
        assert text.count(anchor) == 1
        text = text.replace(anchor, addition + anchor)
        report.write_text(text, encoding='utf-8', newline='\n')
    generator_path = HERE / '生成报告.py'
    source = generator_path.read_bytes()
    marker = b'REPORT_TEXT = r' + b'"' * 3
    start = source.index(marker) + len(marker)
    end = source.index(b'"' * 3, start)
    newline = '\r\n' if b'\r\n' in source[start:end] else '\n'
    generator_path.write_bytes(source[:start] + text.replace('\n', newline).encode('utf-8') + source[end:])
    spec = importlib.util.spec_from_file_location('reviewed_report', generator_path)
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    generator.main()
    assert report.read_text(encoding='utf-8') == text == generator.REPORT_TEXT
    assert text.split('## 第二章')[0] == chapter1
    assert text.split('### 2.1 MDM', 1)[1] == methods
    return {'report_sha256': digest(report), 'generator_sha256': digest(generator_path)}


def main():
    seal = json.loads((ROOT / '结果/中间数据/封存清单.json').read_text(encoding='utf-8'))
    protected = {**seal['input_hashes'], **seal['output_hashes']}
    protected.pop('结果/图2_样本与真实起点.png')
    for name, expected in protected.items():
        assert digest(ROOT / name) == expected, name
    report_record = sync_density_derivation()
    previous = json.loads(PREVIOUS.read_text(encoding='utf-8'))
    spec = importlib.util.spec_from_file_location('saved_n30_source', HERE / '20261010-导入图补入n30.py')
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    entry.main(minimum_distributions='theoretical')
    result = json.loads(RECORD.read_text(encoding='utf-8'))
    assert result['panels'] == previous['panels']
    assert result['total_panel_count'] == 8
    checks = []
    for panel in result['minimum_distribution_panels']:
        beta = panel['beta']
        assert panel['source_kind'] == 'analytic_minimum_distribution'
        for series in panel['series']:
            n = series['n']
            grid = np.array(series['grid'])
            density = np.array(series['density'])
            parent = weibull_min(beta, loc=500., scale=1000.)
            expected = n * parent.sf(grid)**(n-1) * parent.pdf(grid)
            scaled = weibull_min(beta, loc=500., scale=1000.*n**(-1./beta))
            assert np.allclose(density, expected, rtol=1e-12, atol=1e-15)
            assert np.allclose(density, scaled.pdf(grid), rtol=1e-12, atol=1e-15)
            integral, _ = quad(scaled.pdf, 500., np.inf, epsabs=1e-10)
            assert abs(integral-1.) < 1e-9
            checks.append(dict(beta=beta, n=n, normalized_mass=integral,
                               plotted_mass=scaled.cdf(grid[-1])-scaled.cdf(grid[0]),
                               median=float(scaled.median()),
                               max_scipy_pdf_error=float(np.max(np.abs(expected-density)))))
    for name, expected in protected.items():
        assert digest(ROOT / name) == expected, name
    result.update(task='2026-10-10: exact smooth minimum densities under figure 2',
                  previous_observation_record=PREVIOUS.relative_to(ROOT).as_posix(),
                  previous_observation_record_sha256=digest(PREVIOUS),
                  six_observation_panels_unchanged=True,
                  revision_new_samples=0, protected_input_and_output_files=len(protected),
                  minimum_values_reused=300, density_formula_checks=checks,
                  graph_note_count_added=0, figure_sha256=digest(ROOT / result['figure']),
                  figure_contract=dict(
                      conclusion='Higher beta and smaller n leave a larger gap between gamma and the minimum.',
                      archetype='quantitative grid', backend='Python/matplotlib',
                      evidence='a-f: saved observations; g-h: exact iid minimum densities.',
                      source_kind='known generating distribution, not empirical KDE',
                      export='PNG only, 450 dpi; existing dimensions and upper panels preserved.',
                      limitations='Theory describes repeated sampling, not the realized fifty-group histogram.'))
    result.update(report_record)
    RECORD.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                      encoding='utf-8', newline='\n')
    print(json.dumps(dict(six_observation_panels_unchanged=True, theoretical_curves_checked=6,
                         max_pdf_error=max(c['max_scipy_pdf_error'] for c in checks),
                         new_random_draws=0, new_fits=0), ensure_ascii=False))


if __name__ == '__main__':
    main()
