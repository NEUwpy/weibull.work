"""将当前Markdown与实际图表接入review-html；已有审批只恢复，不重置。"""
from pathlib import Path
import hashlib
import json
import runpy
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent / 'reviewbyhtml/方法对比'

def typeset_board(board):
    helper = Path.home() / '.codex/skills/review-html/scripts/math_html.py'
    renderer = runpy.run_path(str(helper))['render_html_batch']
    blocks = [b for u in board['units'] for o in u['options'] for b in o['blocks'] if 'html' in b]
    for block, markup in zip(blocks, renderer([b['html'] for b in blocks])):
        block['html'] = markup
    return board


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    target = ROOT / 'board.json'
    if target.exists():
        print('已有审阅，请用review.py resume恢复：' + str(ROOT))
        return
    api = runpy.run_path(str(HERE / '整体比较.py'))
    model = json.loads(api['DATA'].read_text(encoding='utf-8'))
    model['blocks'] = api['article'](model)
    assets = ROOT / 'assets'
    assets.mkdir(exist_ok=True)
    titles = {
        'b009': '从整体差距识别需要追究的问题',
        'b016': '不同方法对样本减少的响应',
        'b026': '偏移与重复波动的不同代价',
        'b031': '极端结果与返回情况怎样影响判断',
        'b042': '构造能够解释哪些现象',
        'b048': '从评价目标走向条件性选择',
    }
    figure_titles = {
        'global': '七种方法的整体差异',
        'change': 'n与β怎样改变相对差距',
        'error': '差距表现为偏移、波动还是尾部',
        'tail': '极端结果对总误差的贡献',
        'mechanism': 'K–R位置偏移的构造解释',
        'life': '寿命目标下的方法表现',
    }
    contexts = {
        'global': 'A概括差异集中在哪些区域；B保留七种方法在40个条件下的完整距离。',
        'change': 'A保留五档样本量的全部轨迹；B集中比较n=50到7时相对距离的变化。',
        'error': 'A便于辨认偏移和主体波动；B保留全部绝对误差，便于观察容限和尾部。',
        'life': 'A比较共同有效集合的RMSE及候选间差距；B比较全部尝试中返回且满足寿命精度的比例。',
    }
    units = []
    pending = []

    def flush():
        if not pending:
            return
        first = pending[0]
        title = first['text'] if first['kind'] == 'heading' else titles.get(first['id'], '比较结果与分析')
        blocks = []
        for block in pending:
            if block is first and block['kind'] == 'heading':
                continue
            markup = api['block_html'](block, model)
            blocks.append({'id': block['id'], 'kind': 'visual' if block['kind'] == 'table' or block.get('text', '').startswith('$$') else 'text', 'html': markup})
        if blocks:
            units.append({'id': 'text-' + first['id'], 'title': title, 'mode': 'content', 'state': 'open',
                          'selected': None, 'options': [{'id': 'current', 'label': '当前正文', 'blocks': blocks}]})
        pending.clear()

    for block in model['blocks']:
        if block['kind'] == 'heading' and block['level'] == 1:
            continue
        if block['kind'] != 'figure':
            if block['kind'] == 'heading' and block['level'] == 2:
                flush()
            pending.append(block)
            continue
        flush()
        group = block['key']
        options = []
        for index, variant in enumerate(model['figures'][group]):
            letter = chr(65 + index)
            src = HERE / '图' / variant['file']
            dst = assets / src.name
            shutil.copy2(src, dst)
            assert hashlib.sha256(src.read_bytes()).digest() == hashlib.sha256(dst.read_bytes()).digest()
            options.append({'id': letter, 'label': letter + ' · ' + variant['label'], 'blocks': [
                {'id': block['id'] + '-image', 'kind': 'image', 'src': 'assets/' + src.name, 'alt': variant['label']},
                {'id': block['id'] + '-caption', 'kind': 'text', 'html': '<p>' + api['inline'](variant['caption']) + '</p>'},
            ]})
        unit = {'id': 'figure-' + group, 'title': figure_titles[group],
                'mode': 'choices' if len(options) > 1 else 'content', 'inline': True,
                'state': 'open', 'selected': None, 'options': options}
        if len(options) > 1:
            unit['context'] = contexts[group]
        units.append(unit)
    flush()
    board = {'id': 'study04-comparison-v04', 'title': '七种方法的性能差异、条件规律与选择启示',
             'document': True, 'revision': 1, 'source': '../../../其他/历史尝试/报告下（方法对比）-v0.4.md',
             'source_fingerprint': model['source_fingerprint'], 'content_fingerprint': model['content_fingerprint'],
             'units': units}
    target.write_text(json.dumps(typeset_board(board), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / '.gitignore').write_text('/session.json\n/server.log\n/draft.json\n/draft.previous.json\n*.tmp\n__pycache__/\n', encoding='utf-8')
    print(json.dumps({'root': str(ROOT), 'units': len(units),
                      'choice_units': sum(u['mode'] == 'choices' for u in units)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
