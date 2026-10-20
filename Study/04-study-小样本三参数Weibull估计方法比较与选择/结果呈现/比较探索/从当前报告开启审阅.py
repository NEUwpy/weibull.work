"""显式从正式报告开启新轮审阅；保留任务、素材、图组ID及提交历史。"""
from pathlib import Path
from collections import Counter
import argparse
import copy
import hashlib
import json
import os
import re
import runpy
import subprocess
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent.parent
REPO = STUDY.parent.parent
ROOT = STUDY / 'reviewbyhtml/方法对比'
SOURCE = STUDY / '报告下（方法对比）-v0.4.md'
SKILL = Path.home() / '.codex/skills/review-html'

RENDER = r'''
import fs from 'node:fs';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import Markdown from 'react-markdown';
import {unified} from 'unified';
import parse from 'remark-parse';
import gfm from 'remark-gfm';
const source=JSON.parse(fs.readFileSync(0,'utf8'));
const ast=unified().use(parse).use(gfm).parse(source);
const nodes=ast.children.map(n=>{
  const raw=source.slice(n.position.start.offset,n.position.end.offset);
  const image=n.type==='paragraph'&&n.children.length===1&&n.children[0].type==='image'?n.children[0]:null;
  return {type:n.type,depth:n.depth,raw,
    html:renderToStaticMarkup(React.createElement(Markdown,{remarkPlugins:[gfm],children:raw})),
    image:image?{url:image.url,alt:image.alt}:null};
});
process.stdout.write(JSON.stringify(nodes));
'''


def digest(value):
    return hashlib.sha256(value).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start-round', action='store_true', required=True)
    parser.parse_args()
    path = ROOT / 'board.json'
    board = json.loads(path.read_text(encoding='utf-8'))
    if not board.get('review_complete'):
        raise SystemExit('当前轮尚未结束；请恢复并处理原审阅，不重新导入。')
    feedback = json.loads((ROOT / 'feedback.json').read_text(encoding='utf-8'))
    assert feedback['submission_id'] == board['last_applied_submission_id'], '先处理待提交意见。'
    history_before = (ROOT / 'history.jsonl').read_bytes()
    source_bytes = SOURCE.read_bytes()
    source = source_bytes.decode('utf-8')
    result = subprocess.run(['node', '--input-type=module', '-e', RENDER], cwd=REPO,
                            input=json.dumps(source, ensure_ascii=False), capture_output=True,
                            encoding='utf-8', check=True)
    nodes = json.loads(result.stdout)
    old_units = {u['id']: u for u in board['units']}
    image_blocks = {}
    for unit in board['units']:
        for option in unit['options']:
            for block in option['blocks']:
                if block['kind'] == 'image':
                    image_blocks[Path(block['src']).name] = block
    gallery_units = {'figure-change', 'figure-error'}
    galleries = {key: copy.deepcopy(next(b for b in old_units[key]['options'][0]['blocks']
                                         if b['kind'] == 'gallery')) for key in gallery_units}
    gallery_files = {Path(slide['src']).name: key for key, block in galleries.items()
                     for slide in block['images']}
    sections = {
        '1': ('evidence-base', 'current'), '2': ('figure-global', 'A'),
        '3': ('figure-change', 'C'), '4': ('figure-error', 'C'),
        '4.2': ('figure-tail', 'B'), '5': ('figure-mechanism', 'A'),
        '6': ('figure-life', 'A'), '7': ('closing-slot', 'current'),
    }
    units = []
    covered = []
    source_images = []
    gallery_raw = {key: [] for key in galleries}
    gallery_seen = set()
    current = None

    def begin(unit_id, option_id, title):
        nonlocal current
        current = {'id': unit_id, 'title': title, 'mode': 'content', 'state': 'open',
                   'selected': old_units[unit_id].get('selected'),
                   'options': [{'id': option_id, 'label': '当前正文', 'blocks': []}]}
        units.append(current)

    def blocks():
        return current['options'][0]['blocks']

    def resolve_links(markup):
        def replace(match):
            href = match[1]
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', href) or href.startswith('#'):
                return match[0]
            local, _, fragment = href.partition('#')
            target = (SOURCE.parent / unquote(local)).resolve()
            assert target.is_file(), f'报告链接不存在：{target}'
            return 'href="' + target.as_uri() + ('#' + fragment if fragment else '') + '"'
        return re.sub(r'href="([^"]+)"', replace, markup)

    # 报告标题由页面顶栏呈现，版本行作为正文首节标题。
    assert nodes[0]['type'] == 'heading' and nodes[0]['depth'] == 1
    board['title'] = re.sub(r'^#\s+', '', nodes[0]['raw'])
    covered.append(nodes[0]['raw'])
    version = nodes[1]['raw'].strip('*')
    begin('text-b002', 'current', version)
    covered.append(nodes[1]['raw'])
    for node in nodes[2:]:
        raw = node['raw']
        covered.append(raw)
        if node['type'] == 'heading':
            label = re.sub(r'^#+\s+', '', raw)
            section = re.match(r'^(\d+(?:\.\d+)?)\s', label)
            key = section[1] if section else None
            if node['depth'] == 2 or key == '4.2':
                unit_id, option_id = sections[key]
                begin(unit_id, option_id, label)
                continue
            if node['depth'] == 4 and re.match(r'^(?:n|β)\s*=', label):
                gallery_raw[current['id']].append(raw)
                continue
        if node['image']:
            filename = Path(node['image']['url']).name
            image = image_blocks.get(filename)
            source_images.append(filename)
            assert (ROOT / 'assets' / filename).is_file()
            if filename in gallery_files:
                key = gallery_files[filename]
                assert key == current['id']
                gallery_raw[key].append(raw)
                if key not in gallery_seen:
                    blocks().append(galleries[key])
                    gallery_seen.add(key)
            else:
                assert image, f'未匹配原图片ID：{filename}'
                image = copy.deepcopy(image)
                image['markdown'] = raw
                blocks().append(image)
            continue
        # 新正文采用新块ID，避免把旧探索文本的批注错误迁到改写段落。
        blocks().append({'id': 'report-' + digest(raw.encode())[:12],
                         'kind': 'visual' if node['type'] == 'table' else 'text',
                         'html': resolve_links(node['html']), 'markdown': raw})
    for key, block in galleries.items():
        block['markdown'] = '\n\n'.join(gallery_raw[key])
    markups = [b for u in units for o in u['options'] for b in o['blocks'] if 'html' in b]
    render_math = runpy.run_path(str(SKILL / 'scripts/math_html.py'))['render_html_batch']
    for block, markup in zip(markups, render_math([b['html'] for b in markups])):
        block['html'] = markup
    # 验证全文顺序与所有图均保留；标题折入单元、连续条件图折入图组。
    assert re.sub(r'\s+', '', '\n\n'.join(covered)) == re.sub(r'\s+', '', source)
    rendered_images = [Path(im['src']).name for u in units for o in u['options'] for b in o['blocks']
                       for im in (b['images'] if b['kind'] == 'gallery' else [b] if b['kind'] == 'image' else [])]
    assert Counter(rendered_images) == Counter(source_images)
    assert len(source_images) == 21 and sorted(len(b['images']) for b in galleries.values()) == [5, 8]
    for unit in units:
        ids = [b['id'] for b in unit['options'][0]['blocks']]
        assert len(ids) == len(set(ids))
    board.update(units=units, revision=board['revision'] + 1, review_complete=False,
                 processing=False, source='../../' + SOURCE.name,
                 source_fingerprint=digest(source_bytes), stage='report-revision',
                 content_fingerprint=digest(json.dumps(units, ensure_ascii=False).encode()))
    for key in ('accepted_revision', 'accepted_at', 'archive_pending'):
        board.pop(key, None)
    board['archive_plan'] = (
        '将本轮确认的修改写回当前正式报告：\n'
        f'1. 更新 {SOURCE.as_posix()}，沿用v0.4；此前内容通过Git保留。\n'
        '2. 已归档的v0.3及“其他/历史尝试”中的旧稿保留原处。\n'
        '3. 同步必要的README和引用，保留当前任务HTML、图片、批注及历史记录；审阅镜像不替代正式报告。\n'
        '4. 核验正文、图片与链接后提交本轮相关Git修改；草稿、会话和日志继续留在本地。')
    path.write_text(json.dumps(board, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # 镜像忠实保留正式底稿；后续由批注修订，不再沿用探索卡片的说明。
    def mirror_link(match):
        href = match[2]
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', href) or href.startswith('#'):
            return match[0]
        local, _, fragment = href.partition('#')
        relative = Path(os.path.relpath((SOURCE.parent / local).resolve(), HERE)).as_posix()
        return match[1] + relative + ('#' + fragment if fragment else '') + ')'
    mirror = re.sub(r'(\]\()([^\n)]+)\)', mirror_link, source)
    (HERE / '表达方式发散.md').write_text(
        '> 当前基于[正式报告v0.4](../../报告下（方法对比）-v0.4.md)审阅；'
        '本文件为HTML正文镜像，修改尚待审阅落地。\n\n' + mirror, encoding='utf-8')
    assert SOURCE.read_bytes() == source_bytes
    assert (ROOT / 'history.jsonl').read_bytes() == history_before
    print(json.dumps({'revision': board['revision'], 'units': len(units), 'images': len(source_images),
                      'galleries': [len(galleries[k]['images']) for k in sorted(galleries)],
                      'source_sha256': digest(source_bytes), 'history_unchanged': True}, ensure_ascii=False))


if __name__ == '__main__':
    main()
