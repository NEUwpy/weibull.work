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
DATA = Path('D:/weibull-data')
BASE = 'http://127.0.0.1:3000'
sys.path.insert(0, 'C:/Users/36089/.codex/skills/review-html/scripts')
from math_html import render_html_batch

def api(params=''):
    with urllib.request.urlopen(BASE + '/api/cases/catalog?' + params, timeout=90) as response:
        return json.load(response)

def escape(value):
    return html.escape(str(value or ''))

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
    extra = ' · 合并视图，不另计独立样本' if summary.get('role') == 'derived' else ''
    body = '<p>' + escape(record['nature'].get('note', '')) + '</p>'
    if isinstance(data, list):
        body += '<pre style="white-space:pre-wrap;word-break:break-word">' + escape('，'.join(map(str,data))) + '</pre>'
    elif data['kind'] == 'table':
        body += '<div style="overflow:auto;max-width:100%">' + (data.get('html') or '<table><tbody>' + ''.join('<tr>' + ''.join('<td>' + escape(cell) + '</td>' for cell in row) + '</tr>' for row in data['rows']) + '</tbody></table>') + '</div>'
    elif data['kind'] == 'figure':
        source = next(source_dirs[source['paper_id']] / data['asset'] for source in record['sources'] if (source_dirs[source['paper_id']] / data['asset']).is_file())
        target = ROOT / 'assets' / (record['id'] + source.suffix)
        shutil.copyfile(source,target)
        body += '<figure><img src="assets/' + escape(target.name) + '" style="max-width:100%;height:auto" alt="' + escape(summary['name']) + '"><figcaption>' + escape(data.get('caption','')) + '</figcaption></figure>'
    else:
        body += '<p>' + escape(data.get('description','')) + '</p>'
    for source in summary.get('sources',record.get('sources',[])):
        body += '<p style="font-size:.9em;color:#64748b">[' + escape(source['paper_id']) + '] ' + escape(source.get('title','')) + ' · ' + escape(source['location']) + (' · 经该文转引' if source['relation'] == 'secondary' else '')
        if source.get('original_reference'): body += '<br>原始文献线索：' + escape(source['original_reference'])
        body += '</p>'
    if not record.get('sources'): body += '<p>平台生成样本；关联论文说明方法，不表示样本摘自论文。</p>'
    return '<details style="margin:.7em 0;padding:.6em;border:1px solid #e2e8f0;border-radius:8px"><summary style="cursor:pointer;font-weight:600">' + escape(summary['name']) + ' · ' + escape(summary.get('scale','')) + escape(extra) + '</summary>' + body + '</details>'

categories=[]
for kind,label in labels.items():
    fragments=[]
    for row in rows:
        if row['nature']['kind'] != kind: continue
        detail=details[row['id']]
        if 'group' in detail:
            group=detail['group']; body='<p>' + escape(group.get('description','')) + '</p>'
            for summary in group['members']:
                file=DATA / 'cases/records' / (summary['id'] + '.json')
                record=json.loads(file.read_text(encoding='utf-8-sig')) if file.exists() else legacy[summary['id']]
                body+=member_html(summary,record)
            fragments.append('<details style="padding:.75em;margin:.8em 0;border:1px solid #cbd5e1;border-radius:10px"><summary style="cursor:pointer;font-weight:700">' + escape(group['name']) + ' · ' + escape(group['scale']) + '</summary>' + body + '</details>')
        else:
            fragments.append(member_html(row,detail['item']))
    categories.append('<h3>'+label+'（'+str(page['counts'][kind])+'组）</h3>'+''.join(fragments))

board_path=ROOT / 'board.json'
board=json.loads(board_path.read_text(encoding='utf-8-sig'))
board['revision']=4
board['title']='案例数据库 · 样本组与收录范围修订'
board['archive_plan']='保存本轮按样本组组织的本机案例页面、中文选材目录、规范及验证记录；保留原数据与未整理清单。全库参数估计材料继续逐篇整理，本轮不部署NAS或公网案例站。'
units={unit['id']:unit for unit in board['units']}
units['preview']['title']='1. 按样本组查阅'
blocks=units['preview']['options'][0]['blocks']
byid={block['id']:block for block in blocks}
byid['summary']['html']='<p>已按本次意见改为<mark>实测数据、蒙特卡洛数据、估计结果</mark>三个入口，先看组，再展开组内成员。Hirose五批试件归为一组；100点合并只作派生视图；平台30次抽样也收在一个组内。</p><p>下方是当前目录的全部20个展示条目，可展开查看实际数值、表格和出处。它包含17个新整理组及3个既有条目；底层仍按数据、性质、来源保存。名称统一为中文。</p>'
newblock={'id':'grouped-content','kind':'visual','html':''.join(categories)}
blocks[:]=[block for block in blocks if block['id'] != 'grouped-content']
blocks.insert(1,newblock)
byid['catalog-preview']['images']=[{'id':'desktop','label':'实际页面：五批样本收在同一组','src':'assets/cases-desktop.png','alt':'实测样本组与派生视图'}, {'id':'half','label':'实际页面：蒙特卡洛样本组','src':'assets/cases-half.png','alt':'按组查看平台重复抽样'}, {'id':'mobile','label':'实际页面：手机宽度','src':'assets/cases-mobile.png','alt':'手机宽度中的中文样本组'}]
byid['preview-evidence']['html']='<p><a href="http://127.0.0.1:3000/cases" target="_blank" rel="noreferrer">打开本机实际案例页</a>。上方内容快照与配图来自本轮实际目录；计算、复制和下载在实际案例页操作。NAS与公网案例站尚未部署。</p>'
fmt={block['id']:block for block in units['format']['options'][0]['blocks']}
units['format']['title']='2. 数据与来源仍可引用'
fmt['ownership']['html']='<p>同一研究中成套使用的样本归为一组，相关估计表和拟合图收在组内；每份原始数据保留独立编号与来源，合并数据不重复计数。来源继续连接库中实际提供数据的文献，二引标明转引并保留原论文线索。</p><p>当前新增目录包含68项成员：16份原始数值样本、1份合并视图、46份表格、5份数据图，关联13项书单资料。另保留32份平台样本。样本可计算不代表论文的全部材料已核查完。</p>'
fmt['json-preview']['html']='<details><summary>看分组怎样连接原数据</summary><pre><code>'+escape(json.dumps({'id':'catalog-epoxy-breakdown','name':'环氧树脂击穿电压试验（五批）','kind':'observed','members':[{'id':'sample-hirose-1996-case-1','name':'第1批击穿电压（20点）','role':'sample'},{'id':'sample-hirose-1996-all','name':'五批合并视图（100点）','role':'derived'}]},ensure_ascii=False,indent=2))+'</code></pre><p>以上仅展示字段示例；完整组的五批、合并视图和结果表见第一节。</p></details>'
units['build']['title']='3. 范围与待补内容'
for block in units['build']['options'][0]['blocks']:
    if block['id']=='build-phases':
        block['html']='<p>已从展示范围排除93项深度学习、神经网络等无关资料的1,731条记录。其余2,954条材料仍需判断是否属于参数估计数据、核对结构和中文命名；原件保留在后台清单。扫描总量不再当作案例完成量。</p><p>已选结果材料核对了用途和原文位置；只有182-104的全部可复用结果完成PDF逐格核查，其余结果表仍待逐格核查。错挂图题、跨页碎表和可疑表头暂缓展示，具体位置已登记。</p><p>24项案例、数据与计算器回归、9项导入回归、目录一致性检查、类型检查和生产构建通过。默认不实时监听，网页提交后通知本对话即可。</p>'
allblocks=[block for unit in board['units'] for option in unit['options'] for block in option['blocks'] if 'html' in block]
for block,markup in zip(allblocks,render_html_batch([block['html'] for block in allblocks])): block['html']=markup
board_path.write_text(json.dumps(board,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'revision':board['revision'],'groups':len(rows),'snapshot_members':page['records'],'board_bytes':board_path.stat().st_size},ensure_ascii=False))
