"""将既有第三章对照材料整理为普通候选；保留原稿、修订稿和共用图表。"""
from copy import deepcopy
from pathlib import Path
import json

STUDY = Path(__file__).resolve().parents[2]
ROOT = STUDY / 'reviewbyhtml/方法对比-v1.0'


def main():
    path = ROOT / 'board.json'
    board = json.loads(path.read_text(encoding='utf-8'))
    if board['revision'] != 14 or not board.get('processing'):
        raise SystemExit('仅用于第14轮材料整理；后续直接编辑普通候选。')
    units = []
    count = 0
    for unit in board['units']:
        changed = [(option, block) for option in unit['options'] for block in option['blocks']
                   if 'before_html' in block]
        if not changed:
            units.append(unit)
            continue
        if len(changed) != 1 or len(unit['options']) != 1:
            raise ValueError('请先核对该处已有材料：' + unit['id'])
        option, block = changed[0]
        shared = [deepcopy(item) for item in option['blocks'] if item is not block]
        if shared:
            unit['options'][0]['blocks'] = shared
            unit.update(mode='content', state='open', selected=None, selected_ids=[])
            units.append(unit)
            candidate = dict(id=unit['id'] + '-wording', title='文字表述',
                             inline=True, outline_level=3)
        else:
            candidate = deepcopy(unit)
        candidate.update(mode='choices', state='open', selection_mode='single',
                         selected=None, selected_ids=[], options=[
            dict(id=option['id'] + '-original', label='A　原稿', blocks=[
                dict(id=block['id'], kind=block['kind'], html=block['before_html'])]),
            dict(id=option['id'], label='B　修订稿', blocks=[
                dict(id=block['id'], kind=block['kind'], html=block['manuscript_html'])]),
        ])
        units.append(candidate)
        count += 1
    if count != 3:
        raise ValueError(f'预计整理三处文字，实际为{count}处。')
    board['units'] = units
    board.pop('before_after_review', None)
    board['review_runtime'] = '0.6.2'
    path.write_text(json.dumps(board, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'revision': board['revision'], 'wording_choices': count}, ensure_ascii=False))


if __name__ == '__main__':
    main()
