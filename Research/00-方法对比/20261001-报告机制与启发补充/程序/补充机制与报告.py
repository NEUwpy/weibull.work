"""Figure 7 and report v2 from frozen results; no new samples or estimations.

Nature figure contract: show one actual compensation fit, then compare its
central and tail quantiles with the known generating distribution. The seven
Bernard points are plotting positions, not independent validation observations.
"""
import csv
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np

# Use project NumPy first; the available plotting runtime is supplemental.
PLOTTING_PACKAGES = Path(
    'C:/Users/36089/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages'
)
sys.path.append(str(PLOTTING_PACKAGES))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / '程序' / '输入快照'
OUT = ROOT / '结果'
DATA = OUT / '中间数据'
PREVIOUS_NAME = '20261001-高形状参数补偿报告'
FIGURE_NAME = '图7_不同参数的寿命曲线与分位点'
REPORT_NAME = '高形状参数下的位置与尺度补偿报告-v2.md'
TRUTH = (5.0, 1000.0, 500.0)
SWAPPED = (5.0, 500.0, 1000.0)
BLUE = '#345D7E'
WARM = '#B27448'
GREY = '#444A50'

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Microsoft YaHei', 'Arial', 'DejaVu Sans'],
    'font.size': 7, 'axes.titlesize': 7, 'axes.labelsize': 7,
    'xtick.labelsize': 6.5, 'ytick.labelsize': 6.5,
    'legend.fontsize': 6.2, 'axes.linewidth': .7,
    'axes.spines.right': False, 'axes.spines.top': False,
    'axes.unicode_minus': False, 'legend.frameon': False,
    'pdf.fonttype': 42, 'svg.fonttype': 'none',
})


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def cdf(t, parameters):
    beta, eta, gamma = parameters
    d = np.maximum(np.asarray(t) - gamma, 0.0)
    return -np.expm1(-(d / eta) ** beta)


def quantile(probabilities, parameters):
    beta, eta, gamma = parameters
    return gamma + eta * (-np.log1p(-np.asarray(probabilities))) ** (1.0 / beta)


def write_csv(name, header, rows):
    with (DATA / name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def select_example():
    estimates = json.loads((INPUT / '原案例估计.json').read_text(encoding='utf-8'))
    audit = json.loads((INPUT / '原案例核验.json').read_text(encoding='utf-8'))
    pool = [r for r in estimates if r['beta'] == 5 and r['n'] == 7
            and r['method'] == 'mdm' and r['converged']]
    center = float(np.median([r['gamma_hat'] for r in pool]))
    chosen = min(pool, key=lambda r: (abs(r['gamma_hat'] - center), r['sample_id']))
    sample = next(r for r in audit['samples'] if r['beta_true'] == 5
                  and r['n'] == 7 and r['sample_id'] == chosen['sample_id'])
    assert sample['regeneration_max_error'] == 0
    assert chosen['sample_id'] == 31
    fitted = tuple(float(chosen[p]) for p in ('beta_hat', 'eta_hat', 'gamma_hat'))
    observations = np.asarray(sample['observations'], dtype=float)
    positions = (np.arange(1, 8) - .3) / (7 + .4)
    assert fitted[2] < observations.min()
    provenance = {
        'purpose': 'Single-case illustration of compensation and quantile consequences.',
        'evidence_type': 'Known model CDFs and one archived actual fit; no new estimation.',
        'selection_rule': 'Minimize absolute gamma distance to the median of successful original beta=5,n=7,MDM returns; tie by sample_id.',
        'selection_pool_size': len(pool),
        'gamma_pool_median': center,
        'sample_id': chosen['sample_id'],
        'n': 7, 'seed': sample['seed'], 'method': 'MDM', 'delta': .1,
        'true_parameters_beta_eta_gamma': TRUTH,
        'fit_parameters_beta_eta_gamma': fitted,
        'literal_swapped_parameters_beta_eta_gamma': SWAPPED,
        'observations': observations.tolist(),
        'plotting_positions': positions.tolist(),
        'plotting_position_rule': '(i-0.3)/(n+0.4), Bernard; points are not independent validation.',
        'sample_regeneration_max_error': sample['regeneration_max_error'],
        'claim_limit': 'Only this fit shows central proximity and quantile discrepancies; no all-method tail-accuracy claim.',
        'input_hashes': {
            name: sha256(INPUT / name)
            for name in ('原案例估计.json', '原案例核验.json', '报告v1.md')
        },
    }
    return observations, positions, fitted, provenance


def plot_and_save():
    observations, positions, fitted, provenance = select_example()
    t = np.linspace(450.0, 2050.0, 1601)
    p = np.asarray([.01, .10, -np.expm1(-1.0), .90])
    true_q = quantile(p, TRUTH)
    fit_q = quantile(p, fitted)
    errors = fit_q - true_q
    assert abs(true_q[2] - (TRUTH[1] + TRUTH[2])) < 1e-10
    assert abs(fit_q[2] - (fitted[1] + fitted[2])) < 1e-10
    assert np.allclose(cdf(true_q, TRUTH), p, atol=1e-14)
    assert np.allclose(cdf(fit_q, fitted), p, atol=1e-14)
    assert np.all(np.diff(cdf(t, fitted)) >= 0)
    assert cdf([500], TRUTH)[0] == 0
    assert cdf([1000], SWAPPED)[0] == 0

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.35),
                            gridspec_kw={'width_ratios': [1.23, 1.0]})
    left, right = axes
    left.axvspan(observations.min(), observations.max(), color='#DDE4E8',
                 alpha=.58, linewidth=0, zorder=0)
    left.plot(t, cdf(t, TRUTH), color=GREY, lw=1.3)
    left.plot(t, cdf(t, fitted), color=BLUE, lw=1.5)
    left.plot(t, cdf(t, SWAPPED), color=WARM, lw=1.15, ls='--')
    left.scatter(observations, positions, facecolor='white', edgecolor='#23282D',
                 s=17, linewidth=.75, zorder=4)
    left.set(xlim=(450, 2050), ylim=(-.015, 1.025),
             xlabel='寿命 t', ylabel='累积失效概率 F(t)')
    left.set_xticks([500, 1000, 1500, 2000])
    left.set_yticks([0, .25, .5, .75, 1.0])
    left.set_title('实际偏移估计仍可贴近样本中部', loc='left', pad=12)
    left.text(.02, .965, 'W 的顺序：形状 β、尺度 η、位置 γ',
              transform=left.transAxes, fontsize=6, va='top')
    left.text(.02, .885, '真值：5，1000，500\nMDM：1.95，512，1015',
              transform=left.transAxes, fontsize=6, va='top',
              bbox={'facecolor': 'white', 'alpha': .7, 'edgecolor': 'none', 'pad': 2})
    left.text(.49, .035, '灰带：本组7个观测的范围',
              transform=left.transAxes, fontsize=6, color='#5E6670')

    for row, (a, b, difference) in enumerate(zip(true_q, fit_q, errors)):
        central = row == 2
        right.plot([a, b], [row, row], color=BLUE if central else '#AAB9C5',
                   lw=2 if central else 1.4, zorder=1)
        right.scatter(a, row, s=24, color=GREY, zorder=3)
        right.scatter(b, row, s=24, color=BLUE, zorder=3)
        right.text(max(a, b) + 22, row, f'+{difference:.0f}',
                   va='center', fontsize=7, color=BLUE,
                   weight='bold' if central else 'normal')
    right.set(xlim=(800, 2030), ylim=(3.6, -.6), xlabel='分位寿命 Q(p)')
    right.set_xticks([900, 1200, 1500, 1800])
    right.set_yticks(range(4), ['1%', '10%', '63.2%', '90%'])
    right.set_ylabel('累积失效概率 p')
    right.set_title('中部接近，尾部仍可能偏离', loc='left', pad=12)
    right.text(.015, .965, '标注 = 实际估计 − 真值',
               transform=right.transAxes, fontsize=6, va='top')
    right.text(.015, .04, '1%低于本组最低绘图位置9.46%',
               transform=right.transAxes, fontsize=6, color='#5E6670')
    for ax, tag in zip(axes, ('a', 'b')):
        ax.text(-.12, 1.11, tag, transform=ax.transAxes,
                fontsize=8, weight='bold')

    fig.legend([
        Line2D([], [], color=GREY, lw=1.3),
        Line2D([], [], color=BLUE, lw=1.5),
        Line2D([], [], color=WARM, lw=1.15, ls='--'),
        Line2D([], [], ls='', marker='o', markerfacecolor='white',
               markeredgecolor='#23282D', ms=4),
    ], [
        '真实 W(5,1000,500)', '实际 MDM 估计',
        '交换后 W(5,500,1000)', '样本的 Bernard 绘图位置',
    ], ncol=2, loc='lower center', bbox_to_anchor=(.5, .01), columnspacing=2.8)
    fig.subplots_adjust(left=.09, right=.985, top=.84, bottom=.28, wspace=.47)
    for ext in ('png', 'pdf', 'svg'):
        fig.savefig(OUT / f'{FIGURE_NAME}.{ext}', dpi=450, facecolor='white')
    plt.close(fig)

    write_csv('CDF对照.csv',
              ['t', 'true_cdf', 'actual_mdm_fit_cdf', 'literal_swapped_cdf'],
              zip(t, cdf(t, TRUTH), cdf(t, fitted), cdf(t, SWAPPED)))
    write_csv('寿命分位点对照.csv',
              ['p', 'true_quantile', 'actual_mdm_fit_quantile', 'fit_minus_true'],
              zip(p, true_q, fit_q, errors))
    write_csv('代表样本绘图位置.csv', ['order', 't', 'Bernard_p'],
              zip(range(1, 8), observations, positions))
    provenance.update({
        'quantile_probabilities': p.tolist(),
        'true_quantiles': true_q.tolist(),
        'fit_quantiles': fit_q.tolist(),
        'quantile_errors': errors.tolist(),
        'figure_dimensions_mm': [182.88, 85.09],
        'export': 'PNG 450 dpi; PDF embedded editable TrueType; SVG live text.',
        'cdf_quantile_identity_max_error': float(max(
            np.max(np.abs(cdf(true_q, TRUTH) - p)),
            np.max(np.abs(cdf(fit_q, fitted) - p)))),
    })
    (DATA / '图7样本来源与核验.json').write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return provenance


def build_report():
    text = (INPUT / '报告v1.md').read_text(encoding='utf-8')
    text = text.replace('> 研究小报告 · 2026-10-01',
                        '> 研究小报告 · v2 · 2026-10-01')
    text = text.replace(PREVIOUS_NAME + '/', ROOT.name + '/')
    intro = ('一个意外现象是：明明从W(5,1000,500)抽样，几种方法却估出'
             '“形状更小、尺度约500、位置约1000”的组合，看起来像把参数填反了。'
             '本报告先排除生成和映射错误，再用求解过程说明偏移从哪里产生、为什么还能拟合样本，'
             '以及这对后续研究有什么启发。\n\n')
    text = text.replace('### 1.1 原案例的样本和参数映射是正确的',
                        intro + '### 1.1 原案例的样本和参数映射是正确的')
    text = text.replace(
        'γ增加后，所有 $d_i=t_i-\\gamma$ 都减小，因而由这些距离得到的尺度也会下降；'
        '各方法同时调整β以匹配距离之间的比例。',
        'γ增加后，所有 $d_i=t_i-\\gamma$ 都减小；在β固定时，由这些距离得到的尺度会相应下降。'
        '自由估计还会调整β以匹配距离之间的比例，实际联动取决于方法准则。')
    bridge = (
        '把这种补偿落到一组实际数据上，就能看得更清楚。图7选取原β=5、n=7案例中'
        'MDM的γ最接近成功组中位数的一组（#31）。程序实际返回β=1.95、η=512、γ=1015，'
        '没有拼接三个参数各自的中位数。它与真分布、真正交换参数后的W(5,500,1000)是三条不同的曲线；'
        'γ抬高、η缩小，同时β下降，仍能接近这组样本的中部。\n\n'
        f'![图7　实际补偿估计的分布和分位寿命]({ROOT.name}/结果/{FIGURE_NAME}.png)\n\n'
        '**图7｜参数偏移不等于中部曲线明显失配，中部接近也不保证尾部准确。** '
        'a为真分布、同一组样本的实际MDM估计，以及单纯交换尺度和位置后的分布。'
        '圆点为7个观测对应的Bernard绘图位置，灰带为观测范围；这些点参与了估计，'
        '不是独立验证。b比较同一实际估计与已知真分布的分位寿命，数字为“估计−真值”。'
        '63.2%按精确概率1−exp(−1)计算。1%低于本组最低绘图位置9.46%，'
        '用于说明观测范围之外的尾部差异，不能当作本组已验证的尾部性能。\n\n'
        '这一组的63.2%分位寿命由真实1500估成1527，只差27；'
        '1%分位寿命却由899估成1063，差165，90%分位寿命也由1682估成1801，差119。'
        '**这解释了为什么一组“看起来不对”的参数仍可在样本中部表现接近，'
        '也提醒我们不能只凭中部拟合判断寿命预测是否可靠。** 这里只展示该实际估计的后果，'
        '不推断所有方法的尾部误差都相同。\n\n'
    )
    text = text.replace('## 第三章　结论',
                        bridge + '## 第三章　结论与启发\n\n### 3.1 原因已经解释到哪一步')
    meaning = (
        '### 3.2 这个意外现象带来的启发\n\n'
        '这项发现把“参数像填反了”的疑问转成了更具体的问题：'
        '**小样本缺少位置附近的观测时，方法靠什么确定分布起点？** '
        '同一识别困难经过不同准则，既可产生位置高估，也可产生反向偏移或零边界；'
        '同一批样本上多种方法方向一致，不能单独证明这一方向具有普遍性。\n\n'
        '它也提示，参数解释和寿命预测应一起评价。'
        '若γ+η接近真值而两个参数分别偏离，中部寿命点仍可能准确，尾部则需要单独检验。'
        '已经看清的阈值交点、加权方程和边界选择，为改进提供了明确对象。\n\n'
        '### 3.3 接下来先研究什么\n\n'
        '1. **先检验是否稳定。** 用少量独立随机批次和更大的样本量，'
        '验证MDM/WMLE趋势及其他方法的批次差异，同时单列漏解、近似解和边界结果。\n'
        '2. **再寻找实际可用的诊断。** 从下尾间距、位置准则的平坦程度等可观测信号，'
        '判断什么时候位置估计不稳定；不能用未知真β或真γ直接作应用中的判断条件。\n'
        '3. **最后针对机制改进。** 分别检验MDM阈值、WMLE权重与求解容差的贡献，'
        '区分统计准则改变和数值求解修复；同时检查三个参数、目标寿命点和成功率。\n\n'
    )
    text = text.replace('---\n\n**数据与程序。**', meaning + '---\n\n**数据与程序。**')
    text = text.replace(
        '列出专用脚本、冻结方法程序、输入与复核入口；',
        '列出本次专用脚本、冻结方法程序、输入与复核入口；原6幅主图、2幅补充图和统计表'
        '按原字节复用，图7另存实际代表样本、曲线与分位点源数据。'
        f'[前批次原计算]({PREVIOUS_NAME}/README.md)保留完整模拟和准则曲线源数据；')
    assert text.count('## 第一章') == 1 and text.count('## 第二章') == 1
    assert text.count('## 第三章') == 1 and text.count('![图7') == 1
    assert '接下来先研究什么' in text
    (ROOT.parent / REPORT_NAME).write_text(text, encoding='utf-8')
    return text


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    provenance = plot_and_save()
    report = build_report()
    previous = json.loads((INPUT / '前批次封存清单.json').read_text(encoding='utf-8'))
    reused = {name: sha256(OUT / Path(name).name)
              for name, expected in previous['output_hashes'].items()
              if Path(name).parent.as_posix() == '结果'
              and Path(name).suffix in {'.png', '.pdf', '.svg', '.xlsx'}}
    assert all(value == previous['output_hashes'][name] for name, value in reused.items())
    manifest = {
        'task': 'Report reflection: actual CDF compensation illustration, significance and next research.',
        'date': '2026-10-01', 'new_sample_groups': 0, 'new_fits': 0,
        'report': '../' + REPORT_NAME,
        'source_batch': '../' + PREVIOUS_NAME,
        'source_manifest_sha256': sha256(INPUT / '前批次封存清单.json'),
        'reused_outputs_with_source_hash': reused,
        'new_figure': FIGURE_NAME,
        'representative_sample_id': provenance['sample_id'],
        'runtime': {'python': platform.python_version(), 'numpy': np.__version__,
                    'matplotlib': matplotlib.__version__, 'executable': sys.executable},
        'checks': {'reused_output_count': len(reused), 'reused_hash_mismatches': 0,
                   'cdf_quantile_identity_max_error': provenance['cdf_quantile_identity_max_error'],
                   'three_chapters': True, 'new_estimation_results_replaced': 0},
    }
    # Sealing is a separate, explicit final step after figure/report review.
    (DATA / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                                      encoding='utf-8')
    print(json.dumps({'figure': FIGURE_NAME, 'sample_id': provenance['sample_id'],
                      'quantile_errors': provenance['quantile_errors'],
                      'reused_outputs': len(reused), 'report_characters': len(report),
                      'checks': manifest['checks']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
