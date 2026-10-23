"""核对既有异常样本的判据剖面；--review将解释放回原HTML作前后对照。"""
from pathlib import Path
import argparse
import copy
import csv
import hashlib
import json
import shutil
import sys

STUDY = Path(__file__).resolve().parents[2]
REPO = STUDY.parents[1]
R00 = REPO / 'Research/00-方法对比/交付'
REVIEW = STUDY / 'reviewbyhtml/方法对比-v1.0'
OUTPUT = STUDY / '结果呈现/分析数据/异常判据剖面核验.json'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze():
    curves_path = R00 / '结果/报告2/数据/20261010-参照线精简图数据.csv'
    pairs_path = R00 / '结果/报告2/数据/20261010-配对图参照线精简核验.json'
    wmle_path = R00 / '程序/报告2/20261011-WMLE联合求解与尺度恢复-数据.json'
    mdm_path = R00 / '程序/报告2/20261011-MDM近真值对照.json'
    mmle_path = R00 / '程序/报告2/20261011-MMLE对数似然峰图.json'
    rows = list(csv.DictReader(curves_path.open(encoding='utf-8-sig', newline='')))
    pairs, wmle, mdm, mmle = map(read, [pairs_path, wmle_path, mdm_path, mmle_path])

    def point(label, panel, gamma, role='异常'):
        pool = [r for r in rows if r['example'] == label and r['panel'] == panel and r['role'] == role]
        row = min(pool, key=lambda r: abs(float(r['gamma']) - gamma))
        return {k: float(v) if k not in ('group',) else int(v)
                for k, v in row.items() if k in ['gamma', 'beta', 'loss', 'll_difference', 'group'] and v}

    profiles = {}
    for name, panel in [('LSE_zero', 'criterion'), ('MLE_high', 'profile')]:
        left, middle = point(name, panel, 0), point(name, panel, 250)
        assert left['group'] == middle['group'] == 36
        profiles[name] = {'gamma_0': left, 'gamma_about_251': middle}
    lse, mle = profiles['LSE_zero'], profiles['MLE_high']
    assert abs(lse['gamma_0']['loss'] - .01127222144) < 1e-9
    assert abs(lse['gamma_about_251']['loss'] - .011839) < 1e-6
    assert round(lse['gamma_0']['beta'], 2) == 21.70
    assert round(lse['gamma_about_251']['beta'], 2) == 12.33
    ll_drop = mle['gamma_0']['ll_difference'] - mle['gamma_about_251']['ll_difference']
    assert round(ll_drop, 3) == .012
    assert round(mle['gamma_0']['beta'], 2) == 23.54
    assert round(mle['gamma_about_251']['beta'], 2) == 13.64
    profiles['MLE_high']['log_likelihood_drop'] = ll_drop

    for label in ['LSE_right', 'LSE_zero', 'MLE_high', 'MMLE_high_deletion']:
        pair = pairs['pairs'][label]
        profiles.setdefault(label, {})['pairs'] = pair
    # Keep records aligned with the PNG generation cache, rather than an older pairing cache.
    profiles['MDM_low'] = mdm['pairs']['MDM_low']
    assert profiles['MDM_low']['normal']['group'] == 47
    assert profiles['MDM_low']['abnormal']['group'] == 35
    for role in ['normal', 'abnormal']:
        assert abs(profiles['MDM_low'][role]['at_original']['gradient'] - .2) < 1e-9
    profiles['WMLE_low'] = wmle['pairs']['WMLE_low']
    assert profiles['WMLE_low']['normal']['group'] == 3
    assert profiles['WMLE_low']['abnormal']['group'] == 11
    assert max(x['residual_sum'] for x in wmle['case_checks']) < 1e-16
    profiles['WMLE_low']['residual_checks'] = wmle['case_checks']
    profiles['MMLE_high_deletion'] = {'shape_profiles': {}}
    for role, curve in mmle['figures']['MMLE_high_deletion']['cases'].items():
        xs, ys = curve['beta'], curve['log_likelihood']
        maximum = max(ys)
        near = [x for x, y in zip(xs, ys) if y >= maximum - .1]
        profiles['MMLE_high_deletion']['shape_profiles'][role] = {
            'peak_beta': xs[ys.index(maximum)], 'drop_0_1_beta_range': [min(near), max(near)]}
    assert round(profiles['MMLE_high_deletion']['shape_profiles']['abnormal']['peak_beta'], 2) == 7.69

    source_files = [curves_path, pairs_path, wmle_path, mdm_path, mmle_path]
    figures = [
        ('LRE_zero', 'LRE：宽缓相关性峰与两类左侧高估', 'R00_异常剖面_LRE_zero.png'),
        ('MDM_low', 'MDM：梯度阈值交点移向右端', 'R00_异常剖面_MDM_low.png'),
        ('MLE_high', 'MLE：左侧高似然平台与形状高估', 'R00_异常剖面_MLE_high.png'),
        ('MMLE_high_deletion', 'MMLE：形状似然峰右移并展宽', 'R00_异常剖面_MMLE_high.png'),
    ]
    sources = {p.relative_to(REPO).as_posix(): sha(p) for p in source_files}
    for label, _, _ in figures:
        p = R00 / f'结果/报告2/配对情形_{label}.png'
        sources[p.relative_to(REPO).as_posix()] = sha(p)
    result = {'source_sha256': sources, 'profiles': profiles,
              'comparison_coordinates': '同一图中正常与异常曲线采用相同参数坐标',
              'new_samples': 0, 'new_estimates': 0,
              'conclusion': '低值/高值区宽缓、极值或交点偏移及参数恢复共同解释已展示的异常；旧MLE停点另属求解问题。'}
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result, figures


def review(result, figures):
    path = REVIEW / 'board.json'
    board = read(path)
    assert board['revision'] == 51 and not board.get('processing') and not board.get('review_complete')
    before = copy.deepcopy(board)
    unit = next(u for u in board['units'] if u['id'] == 'mechanism-boundary')
    ending = unit['options'][0]['blocks'][-1]
    original_summary = '<p>前两例应研究估计准则对样本结构的响应；后一例应改进求解与候选检查。异常表现相近，形成环节不同，改进方向也不同。</p>'
    assert ending['html'].endswith(original_summary)
    ending['html'] = ending['html'][:-len(original_summary)]
    slides = []
    for label, title, filename in figures:
        source = R00 / f'结果/报告2/配对情形_{label}.png'
        destination = REVIEW / 'assets' / filename
        shutil.copy2(source, destination)
        assert sha(source) == sha(destination)
        slides.append({'id': label, 'label': title, 'src': 'assets/' + filename,
                       'alt': title + '；上排正常样本，下排异常样本，复用Research00报告2判据过程图'})
    rows = [
        ('LSE、LRE', '左侧高估例中，LSE的低值区、LRE的高相关区向较低位置展开；LSE右侧低估例的最低点接近最小观测。', '左移压缩对数距离跨度，形状升高；右移拉大跨度，形状降低，位置变化经斜率传到形状和尺度。'),
        ('MDM', '梯度达到δ的交点右移；所选位置下，伪尺度标准差的最低点对应小形状。', '低估例的交点距最小观测仅3.91，条件形状由真位置下的1.68降至0.55，尺度随之降低。'),
        ('WMLE', '两条零残差曲线的共同交点向右下方移动。', '图中正常例的交点约为γ=508.70、β=5.35；低估例移至γ=573.51、β=1.10，缩小后的距离进一步给出较小尺度。'),
        ('MLE', '高估例的最高点落在左端，附近是一段宽缓的高似然平台。', '较低位置与较大形状、尺度相互配合；位置和条件形状变化很大，似然改善或损失很小。'),
        ('MMLE', '最小值定位后，保留距离集中的样本使形状似然峰向右移动，并在β坐标上展宽。', '正常例峰值约2.48，高估例峰值约7.69；大形状由这组保留距离的似然支持，尺度再由对应幂均值恢复。'),
    ]
    table = '<table><thead><tr><th>方法</th><th>判据剖面显示什么</th><th>怎样形成异常参数</th></tr></thead><tbody>'
    table += ''.join('<tr>' + ''.join('<td>' + cell + '</td>' for cell in row) + '</tr>' for row in rows) + '</tbody></table>'
    revised = [
        {'id': 'profile-summary-opening', 'kind': 'text', 'html': '<p>沿这些方法的判据剖面看，异常参数与优选区的形状、位置及参数恢复关系相连。<mark>宽缓的优选区使不同参数组合难以区分，极值或交点的移动给出偏移方向，随后的位置、形状和尺度恢复关系把偏移继续传递。</mark></p>'},
        {'id': 'profile-method-comparison', 'kind': 'visual', 'html': table},
        {'id': 'profile-flat-numbers', 'kind': 'text', 'html': '<p>在W(2,100,500)、n=15第36组中，候选位置从0移至约251：LSE的1−R²仅从0.01127升至0.01184，条件形状却从21.70降至12.33；MLE的对数似然仅下降约0.012，条件形状从23.54降至13.64。<mark>这两个剖面直接显示：准则值几乎不变，条件参数却可以大幅改变。</mark></p>'},
        {'id': 'profile-supplement-gallery', 'kind': 'gallery', 'aspect_ratio': 1.68, 'images': slides},
        {'id': 'profile-source-caption', 'kind': 'text', 'html': '<p><em>补充图复用Research00报告2的正常／异常样本剖面。LRE上排为W(2,1000,3000)、n=7第4组，下排并列同条件第5组与W(2,100,500)、n=15第36组；MDM为W(2,1000,3000)、n=7第47、35组，δ=0.20；MLE为W(2,100,500)、n=15第35、36组；MMLE为W(2,1000,3000)、n=7第4、5组。方法设置沿用原图，LSE和WMLE过程见本节前图。</em></p>'},
        {'id': 'profile-summary-ending', 'kind': 'text', 'html': '<p>因此，<mark>这些例子的共同过程是：样本间距和离散结构改变判据的优选区，极值或交点发生偏移，再经参数恢复形成明显高估或低估；其中，宽缓的优选区削弱了参数区分，使很大的参数变化只对应很小的准则变化。</mark>旧MLE的近零停点还说明求解环节的影响：程序可在宽缓区域过早停止，而剖面上仍存在更高似然的合格参数。</p>'},
    ]
    choice = {'id': 'anomaly-profile-explanation-review', 'title': '3.3 判据剖面解释：修改前与修改后',
              'mode': 'choices', 'inline': True, 'outline_level': 3, 'selection_mode': 'single',
              'state': 'open', 'selected': None, 'selected_ids': [], 'options': [
                  {'id': 'profile-explanation-before', 'label': '修改前', 'blocks': [{'id': 'profile-summary-original', 'kind': 'text', 'html': original_summary}]},
                  {'id': 'profile-explanation-after', 'label': '修改后', 'blocks': revised}]}
    index = board['units'].index(unit)
    board['units'].insert(index + 1, choice)
    assert board['units'][:index] == before['units'][:index] and board['units'][index + 2:] == before['units'][index + 1:]
    board['revision'] = 52
    board['review_phase'] = 'v2.3-anomaly-criterion-profile-review'
    board['chapter3_evidence']['anomaly_profiles'] = {'analysis_script': Path(__file__).relative_to(STUDY).as_posix(),
        'audit_file': OUTPUT.relative_to(STUDY).as_posix(), 'sources': result['source_sha256']}
    path.write_text(json.dumps(board, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    log = REVIEW / 'README.md'
    text = log.read_text(encoding='utf-8') + '\n第52轮：按用户“结合这些种方法的判据剖面来说”改写3.3的总结候选，直接比较LSE、LRE、MDM、WMLE、MLE、MMLE的低值区／高值区、极值／交点及参数恢复，补入四幅已有过程图。LSE与MLE同一高估样本的宽缓区由原图数据核对；MDM采用与现PNG对应的20261011近真值对照缓存，WMLE采用联合求解缓存。未新增抽样或估计，旧总结仍供选择。复现：`分析异常判据剖面.py`。\n'
    log.write_text(text, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', action='store_true')
    args = parser.parse_args()
    result, figures = analyze()
    if args.review:
        review(result, figures)
    print(json.dumps({'audit': str(OUTPUT), 'MLE_ll_drop': result['profiles']['MLE_high']['log_likelihood_drop'],
                      'new_samples': 0, 'new_estimates': 0, 'revision': 52 if args.review else None}, ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
