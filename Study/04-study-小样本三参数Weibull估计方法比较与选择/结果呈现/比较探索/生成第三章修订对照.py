"""开启第三章修改前后对照；沿用v1.0任务，原稿以Git 28494a2d为准。"""
from pathlib import Path
import csv
import hashlib
import json
import statistics
import subprocess

STUDY = Path(__file__).resolve().parents[2]
REPO = STUDY.parents[1]
ROOT = STUDY / 'reviewbyhtml/方法对比-v1.0'
BASE = '28494a2d'


def compare(before, after, highlights):
    marked = after
    for phrase in highlights:
        if phrase not in after:
            raise ValueError(phrase)
        marked = marked.replace(phrase, '<mark>' + phrase + '</mark>', 1)
    return (
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:24px">'
        '<div style="padding-right:16px;border-right:1px solid #dce3dd">'
        '<p style="font-size:13px;color:#65736a"><strong>修改前</strong></p>' + before + '</div>'
        '<div><p style="font-size:13px;color:#286442"><strong>修改后</strong></p>' + marked + '</div></div>'
    )


def main():
    path = ROOT / 'board.json'
    board = json.loads(path.read_text(encoding='utf-8'))
    if board['revision'] != 9 or not board.get('review_complete'):
        raise SystemExit('本入口仅从已存档的第9轮开启对照，后续修改请沿用当前board。')
    base_path = path.relative_to(REPO).as_posix()
    old = json.loads(subprocess.check_output(['git', 'show', BASE + ':' + base_path], cwd=REPO))
    units = {u['id']: u for u in board['units']}
    before_units = {u['id']: u for u in old['units']}
    metrics_path = STUDY / '结果呈现/分析数据/参数指标.csv'
    rows = list(csv.DictReader(metrics_path.open(encoding='utf-8-sig', newline='')))
    def metric(method, beta, n, subset='common'):
        return next(r for r in rows if r['method'] == method and float(r['beta']) == beta
                    and int(r['n']) == n and r['subset'] == subset)
    # Check the examples against both success-set conventions before using them in prose.
    for subset in ['own', 'common']:
        low = [float(metric('MMLE(KR)', 1.5, n, subset)['beta_rmse']) / 1.5 for n in [50, 7]]
        high = [float(metric('MMLE(KR)', 5, n, subset)['beta_rmse']) / 5 for n in [50, 7]]
        assert high[0] > low[0] and high[1] - high[0] < low[1] - low[0]
        a, b = [metric('WMLE', 5, n, subset) for n in [10, 7]]
        assert float(b['beta_sd']) < float(a['beta_sd'])
        assert abs(float(b['beta_bias'])) > abs(float(a['beta_bias']))
        assert float(b['beta_rmse']) > float(a['beta_rmse'])
    for beta, expanded in [(1.5, True), (2, True), (2.5, True), (3, True), (4.5, False), (5, False)]:
        for param in ['beta', 'eta', 'gamma']:
            values = [[float(r[param + '_rmse']) for r in rows if r['subset'] == 'common'
                       and float(r['beta']) == beta and int(r['n']) == n] for n in [50, 7]]
            gaps = [statistics.median(v) / min(v) - 1 for v in values]
            assert (gaps[1] > gaps[0]) == expanded

    def revise(unit_id, block_id, text, highlights):
        block = next(b for b in units[unit_id]['options'][0]['blocks'] if b['id'] == block_id)
        before = next(b['html'] for b in before_units[unit_id]['options'][0]['blocks'] if b['id'] == block_id)
        block['manuscript_html'] = text
        block['before_html'] = before
        block['html'] = compare(before, text, highlights)
        units[unit_id]['state'] = 'modify'

    units['law-rmse']['title'] = '3.1　误差水平与方法间差距'
    revise('law-rmse', 'report-481785e3f263',
        '<p>样本量从50减少到7时，主图六种方法的误差总体增大，但增幅不同。'
        '误差水平与样本减少带来的误差增量，需要分别判断。</p>'
        '<p>以K–R的形状相对RMSE为例，β=5时，n=50下的误差高于β=1.5；'
        '但从n=50减到7，β=1.5下的误差增量反而更大。'
        '某一条件下误差较大，并不意味着它对这次样本量减少的响应更强。</p>'
        '<p>方法间的相对差距也没有统一的变化方向。比较n=50和7两个端点，'
        'β=1.5—3时，三个参数的整体相对差距均扩大；β=4.5、5时则均缩小。'
        '高β下的相对差距缩小，与最低RMSE水平的相对增幅大于七法RMSE中位数有关，'
        '不表示估计更准确，也不能据此判断方法间的绝对误差差距缩小。</p>'
        '<p>最低RMSE对应的方法也可能改变。β=4.5、5时，形状估计随n减少，'
        '最低RMSE方法先后为WMLE、MDM和K–R；β=3、3.5时，MDM在五档n下均保持三参数的最低RMSE。'
        '样本量减少既会改变误差水平，也会改变方法之间的相对关系。</p>',
        ['误差水平与样本减少带来的误差增量，需要分别判断。',
         'β=1.5下的误差增量反而更大',
         '最低RMSE水平的相对增幅大于七法RMSE中位数'])
    foot = next(b for b in units['law-rmse']['options'][0]['blocks'] if b['id'] == 'report-96bac28ad30a')
    foot['html'] += ('<p><small>K–R例子的数值依据为自身有效结果，共同有效口径支持相同方向。'
                     '整体相对差距沿用第2章的七法RMSE中位数与最小值之比；端点比较不表示中间n单调变化。</small></p>')

    units['law-distribution']['title'] = '3.2　估计误差的不同表现'
    revise('law-distribution', 'report-521def6b8c6a',
        '<p>进一步观察重复估计的分布，可以辨别误差增加的具体表现。'
        '低β下，LSE、LRE的形状估计随样本减少明显变散，体现为重复估计波动扩大。</p>'
        '<p>随β增大，两种方法的尺度估计逐渐呈现双峰；n=7时，两个峰的分离更明显。'
        'β=5、n=50时，尺度估计均值仍接近真值，但两组结果已经分离。'
        '均值接近真值，不能表明估计结果集中在真值附近。</p>'
        '<p>MDM、WMLE和K–R则表现出位置偏高、尺度偏低的组合，形状估计也存在低估。'
        '这种有方向的系统偏移，与分布变散需要分别识别。</p>'
        '<p>β=5时，WMLE的形状RMSE从n=10到7继续上升，SD却有所下降，负偏差进一步加重。'
        '估计分布更集中，也可能更偏离真值。</p>'
        '<p>因此，RMSE增大可以伴随波动扩大、系统偏移加重或结果分化。'
        '结合估计分布与Bias、SD，可以进一步区分误差增长中的偏移与波动。</p>',
        ['均值接近真值，不能表明估计结果集中在真值附近。',
         '形状RMSE从n=10到7继续上升，SD却有所下降',
         '估计分布更集中，也可能更偏离真值。'])
    table = '<table><thead><tr><th>n</th><th>形状Bias</th><th>形状SD</th><th>形状RMSE</th></tr></thead><tbody>'
    for n in [10, 7]:
        r = metric('WMLE', 5, n)
        table += '<tr><td>' + str(n) + '</td>' + ''.join(
            f'<td>{float(r[key]):.3f}</td>' for key in ['beta_bias', 'beta_sd', 'beta_rmse']) + '</tr>'
    table += '</tbody></table>'
    units['law-distribution']['options'][0]['blocks'].extend([
        dict(id='wmle-bias-sd-evidence', kind='visual', html=table),
        dict(id='wmle-bias-sd-caption', kind='text', html=(
            '<p><em>表：WMLE，β=5；七法共同有效结果，Bias保留符号。'
            '自身有效结果也支持SD下降、负偏差加重和RMSE上升的方向。</em></p>'))])

    units['law-synthesis']['title'] = '3.3　主要性能规律'
    revise('law-synthesis', 'synthesis-phenomena-body',
        '<ol><li><p><strong>误差水平与误差增量需要分别判断。</strong>'
        '某一条件下误差较大，并不意味着减少样本时的误差增幅也更大。</p></li>'
        '<li><p><strong>方法间的相对差距和优势关系随条件改变。</strong>'
        '同样减少样本量，在不同β区域可以产生方向相反的相对差距变化，最低RMSE方法也可能改变。</p></li>'
        '<li><p><strong>精度变化具有不同的估计表现。</strong>'
        'RMSE增大可能伴随波动扩大、系统偏移或分布分化；均值接近真值、SD下降各自不足以判断估计质量。</p></li></ol>'
        '<p>少数极端输出还可能主导平方误差。MM在部分条件下的形状RMSE尖峰，'
        '反映了这类评价问题，后面结合异常频率与尾部贡献进一步讨论。</p>',
        ['误差水平与误差增量需要分别判断。', '方法间的相对差距和优势关系随条件改变。',
         '精度变化具有不同的估计表现。'])
    units['law-synthesis']['options'][0]['blocks'] = [
        b for b in units['law-synthesis']['options'][0]['blocks'] if b['id'] != 'synthesis-scope']
    board.update(revision=10, review_complete=False, processing=False,
        before_after_review=dict(base_commit=BASE, base_revision=9,
            changed_units=['law-rmse','law-distribution','law-synthesis']),
        chapter3_evidence=dict(source=str(metrics_path.relative_to(STUDY)).replace('\\','/'),
            sha256=hashlib.sha256(metrics_path.read_bytes()).hexdigest(),
            checked_subsets=['own','common']))
    for key in ['accepted_revision','accepted_at','archive_pending']:
        board.pop(key, None)
    board['archive_plan'] = (
        '保存本轮第三章修订：\n'
        '1. 根据最终批注更新报告下（方法对比）-v1.0.md；当前文件已写入本轮修订，其他章节保持原有内容。\n'
        '2. 确认后将HTML恢复为修改后的普通正文，保留本任务记录；修改前内容可由Git提交28494a2d恢复。\n'
        '3. 保留原有PNG与图组，本轮新增表格只引用既有参数指标，不新增抽样或正式估计。\n'
        '4. 更新相应README，提交并同步本轮相关成果。')
    path.write_text(json.dumps(board, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'revision':10,'compared_sections':3,'new_evidence_tables':1},ensure_ascii=False))


if __name__ == '__main__':
    main()
