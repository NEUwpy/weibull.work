"""Refresh the review from the running grouped catalog, without submitting feedback."""
from pathlib import Path
import concurrent.futures
import html
import json
import shutil
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
DATA = Path('D:/weibull-data')
BASE = 'http://127.0.0.1:3000'
sys.path.insert(0, 'C:/Users/36089/.codex/skills/review-html/scripts')
from math_html import render_html_batch

def api(params=''):
    with urllib.request.urlopen(BASE + '/api/cases/catalog?' + params, timeout=90) as response:
        return json.load(response)

def escape(value):
    return html.escape('' if value is None else str(value))

page = api('limit=100')
rows = page['items']
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    details = dict(zip([row['id'] for row in rows], pool.map(lambda row: api('id=' + urllib.parse.quote(row['id'])), rows)))
legacy_ids = [member['id'] for row in rows for member in details[row['id']].get('group', {}).get('members', []) if not (DATA / 'cases/records' / (member['id'] + '.json')).exists()]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    legacy = dict(zip(legacy_ids, pool.map(lambda ident: api('id=' + urllib.parse.quote(ident))['item'], legacy_ids)))
manifest = json.loads((DATA / 'literature-source/library.json').read_text(encoding='utf-8-sig'))
source_dirs = {paper if isinstance(paper,str) else paper['id']: Path(source['root']) for source in manifest['sources'] for paper in source['papers']}

labels = {'observed':'实测数据', 'simulated':'蒙特卡洛数据', 'result':'估计结果'}

def member_html(summary, record):
    data = record['data']
    extra = '合并视图 · ' if summary.get('role') == 'derived' else ''
    name = escape(summary['name'])
    sample_url = BASE + '/?data=' + urllib.parse.quote(','.join(map(str, data))) if summary['can_calculate'] and isinstance(data, list) else ''
    calculate = f'<a class="case-calculate" href="{sample_url}" target="_blank" rel="noopener">带入本机威布尔计算器</a>' if sample_url else ''
    body = f'<header class="case-data-toolbar"><h3>{name}</h3>{calculate}</header>'
    body += '<p>' + escape(record['nature'].get('note', '')) + '</p>'
    if isinstance(data, list):
        body += '<pre style="white-space:pre-wrap;word-break:break-word">' + escape('，'.join(map(str,data))) + '</pre>'
        body += '<button class="copy-button" type="button" data-copy="' + escape('\n'.join(map(str, data))) + '">复制样本数据</button>'
    elif data['kind'] == 'table':
        body += '<div style="overflow:auto;max-width:100%">' + (data.get('html') or '<table><tbody>' + ''.join('<tr>' + ''.join('<td>' + escape(cell) + '</td>' for cell in row) + '</tr>' for row in data['rows']) + '</tbody></table>') + '</div>'
    elif data['kind'] == 'figure':
        source = next(source_dirs[source['paper_id']] / data['asset'] for source in record['sources'] if (source_dirs[source['paper_id']] / data['asset']).is_file())
        target = ROOT / 'assets' / (record['id'] + source.suffix)
        shutil.copyfile(source,target)
        body += '<figure><img src="' + escape(target.name) + '" alt="' + name + '"><figcaption>' + escape(data.get('caption','')) + '</figcaption></figure>'
    else:
        body += '<p>' + escape(data.get('description','')) + '</p>'
    for source in summary.get('sources',record.get('sources',[])):
        body += '<p style="font-size:.9em;color:#64748b">[' + escape(source['paper_id']) + '] ' + escape(source.get('title','')) + ' · ' + escape(source['location']) + (' · 经该文转引' if source['relation'] == 'secondary' else '')
        if source.get('original_reference'): body += '<br>原始文献线索：' + escape(source['original_reference'])
        body += '</p>'
    if not record.get('sources'): body += '<p>平台生成样本；关联论文说明方法，不表示样本摘自论文。</p>'
    return f'<section class="preview-detail" data-name="{name}" data-scale="{escape(extra + summary.get("scale", ""))}">{body}</section>'

cards, templates = [], []
for row in rows:
    kind = row['nature']['kind']
    if kind not in labels:
        continue
    ident = escape(row['id'])
    detail = details[row['id']]
    group = detail.get('group')
    description = group.get('description') if group else row['nature'].get('quantity') or row['nature'].get('note')
    members = group['members'] if group else [row]
    search = ' '.join([row['name'], row['id'], description or '', *[member['name'] for member in members],
                       *[source['paper_id'] for source in row['sources']]]).lower()
    cards.append(f'<button class="case-card" type="button" aria-haspopup="dialog" data-kind="{kind}" data-detail="{ident}" '
                 f'data-description="{escape(description)}" data-search="{escape(search)}">'
                 f'<span class="case-card-kind">{labels[kind]}</span><span class="case-card-title">{escape(row["name"])}</span>'
                 f'<span class="case-card-description">{escape(description)}</span>'
                 f'<span class="case-card-footer">{escape(row["scale"])}<span aria-hidden="true">↗</span></span></button>')
    content = []
    for member in members:
        file = DATA / 'cases/records' / (member['id'] + '.json')
        record = (json.loads(file.read_text(encoding='utf-8-sig')) if file.exists() else legacy[member['id']]) if group else detail['item']
        content.append(member_html(member, record))
    templates.append(f'<template id="{ident}">{"".join(content)}</template>')

preview = (ROOT / 'card-preview.template.html').read_text(encoding='utf-8')
preview = preview.replace('__CATALOG_CSS__', (PROJECT / 'src/app/cases/case-catalog.css').read_text(encoding='utf-8'))
preview = preview.replace('__FILTERS__', ''.join(f'<button type="button" data-kind="{kind}">{label}</button>' for kind, label in labels.items()))
preview = preview.replace('__CARDS__', ''.join(cards)).replace('__DETAILS__', render_html_batch([''.join(templates)])[0])
(ROOT / 'assets/card-preview.html').write_text(preview, encoding='utf-8')

board_path=ROOT / 'board.json'
board=json.loads(board_path.read_text(encoding='utf-8-sig'))
board['revision']=5
board['title']='案例数据库 · 卡片与样本浮层'
board['archive_plan']='保存案例卡片、样本详情浮层、操作说明和本轮审阅记录。'
units={unit['id']:unit for unit in board['units']}
units['preview']['title']='1. 试用案例卡片'
blocks=units['preview']['options'][0]['blocks']
byid={block['id']:block for block in blocks}
byid['summary']['html']='<p><a href="assets/card-preview.html" target="_blank" rel="noopener"><strong>打开可操作的卡片试用页 ↗</strong></a></p><p>卡片按行列对齐，卡面显示数据对象、性质和规模。打开卡片后，可在同一浮层切换样本和结果。完整样本的计算入口就在数据标题旁。</p>'
byid['grouped-content']['html']='<p>试用页采用当前目录的真实数据。可试试打开“环氧树脂击穿电压试验”，从第1批切到第2批，再看合并样本或结果表。手机上用顶部的组内选择。计算入口指向本机站点，手机试用时可复制样本数值。</p>'
byid['catalog-preview']['images']=[{'id':'desktop','label':'本机页面 · 案例卡片网格','src':'assets/cards-grid.png','alt':'规整排列的实测数据卡片'}, {'id':'half','label':'本机页面 · 样本详情浮层','src':'assets/cards-dialog.png','alt':'组内样本切换与计算入口'}, {'id':'mobile','label':'本机页面 · 手机浮层','src':'assets/cards-mobile.png','alt':'手机顶部选择组内数据'}]
byid['preview-evidence']['html']='<p>电脑上可直接体验完整流程。<a href="http://127.0.0.1:3000/cases" target="_blank" rel="noreferrer">打开本机案例页 ↗</a></p>'
fmt={block['id']:block for block in units['format']['options'][0]['blocks']}
units['format']['title']='2. 数据与来源仍可引用'
fmt['ownership']['html']='<p>同一研究中成套使用的样本归为一组，相关估计表和拟合图收在组内；每份原始数据保留独立编号与来源，合并数据不重复计数。来源继续连接库中实际提供数据的文献，二引标明转引并保留原论文线索。</p><p>当前新增目录包含68项成员：16份原始数值样本、1份合并视图、46份表格、5份数据图，关联13项书单资料。另保留32份平台样本。样本可计算不代表论文的全部材料已核查完。</p>'
fmt['json-preview']['html']='<details><summary>看分组怎样连接原数据</summary><pre><code>'+escape(json.dumps({'id':'catalog-epoxy-breakdown','name':'环氧树脂击穿电压试验（五批）','kind':'observed','members':[{'id':'sample-hirose-1996-case-1','name':'第1批击穿电压（20点）','role':'sample'},{'id':'sample-hirose-1996-all','name':'五批合并视图（100点）','role':'derived'}]},ensure_ascii=False,indent=2))+'</code></pre><p>以上仅展示字段示例；完整组的五批、合并视图和结果表见第一节。</p></details>'
units['build']['title']='3. 范围与待补内容'
for block in units['build']['options'][0]['blocks']:
    if block['id']=='build-phases':
        block['html']='<p>现有目录包含20个展示条目。另有2,954条材料仍需筛选、核对和命名。当前已选结果材料核对了用途和原文位置，其中182-104的可复用结果完成了PDF逐格核查。</p>'
allblocks=[block for unit in board['units'] for option in unit['options'] for block in option['blocks'] if 'html' in block]
for block,markup in zip(allblocks,render_html_batch([block['html'] for block in allblocks])): block['html']=markup
board_path.write_text(json.dumps(board,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'revision':board['revision'],'groups':len(rows),'snapshot_members':page['records'],'board_bytes':board_path.stat().st_size},ensure_ascii=False))
