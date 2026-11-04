"""Refresh the seven existing reviews with inspectable page prototypes.

Read the original boards/runs and current owning sources. Never change an
estimator. Keep original IDs, feedback and drafts; make one explicit revision.
"""
from pathlib import Path
import hashlib
import html
import importlib.util
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
SKILL = Path('C:/Users/36089/.codex/skills/review-html')
sys.path.insert(0, str(SKILL / 'scripts'))
from math_html import render_html_batch

spec = importlib.util.spec_from_file_location('previous_process_review', ROOT / 'build-process-reviews.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
CONFIG = previous.CONFIG
METHODS = ['mle', 'wmle', 'mdm', 'lse', 'lre', 'mm', 'mmle']
esc = lambda value: html.escape(str(value), quote=True)

CSS = """
.proposal{--green:#27624d;--ink:#18382c;--muted:#62756c;color:var(--ink);font:16px/1.65 'Microsoft YaHei',system-ui,sans-serif;background:#f4f7f5;border:1px solid #dbe4df;border-radius:16px;overflow:hidden;min-width:0;container-type:inline-size}
.proposal *{box-sizing:border-box;min-width:0}.proposal h2,.proposal h3,.proposal h4,.proposal p{margin:0}.proposal h2{font-size:25px}.proposal h3{font-size:19px}.proposal h4{font-size:17px}.proposal a{color:var(--green)}
.proposal .head{padding:22px 26px;background:white;border-bottom:1px solid #dbe4df}.proposal .eyebrow{color:var(--muted);font-size:14px;margin-bottom:8px}.proposal .subtitle{margin-top:8px;color:var(--muted)}
.proposal .tabs{display:flex;gap:22px;flex-wrap:wrap;padding:0 26px;background:white;border-bottom:1px solid #dbe4df}.proposal .tab{border:0;border-bottom:3px solid transparent;background:none;padding:13px 0;font:inherit;color:var(--muted);cursor:pointer}.proposal .tab.active{border-color:var(--green);color:var(--green);font-weight:700}
.proposal .body{padding:22px}.proposal .lead{border-left:3px solid #78a38d;background:#eaf1ec;padding:12px 16px;margin-bottom:18px}.proposal .muted{color:var(--muted);font-size:14px}.proposal .cols{display:grid;grid-template-columns:190px minmax(0,1fr) minmax(220px,.78fr);gap:16px;align-items:start}.proposal .card{background:white;border:1px solid #dbe4df;border-radius:12px;padding:18px}.proposal .steps{display:grid;gap:7px}.proposal .step{padding:11px 10px;border:0;border-radius:8px;background:none;color:var(--ink);text-align:left;font:inherit;cursor:pointer}.proposal .step.active{background:#dfece3;color:#174d36;font-weight:700}.proposal .step span{font-size:14px;color:var(--muted);display:block}
.proposal pre{font:14px/1.65 Consolas,monospace;background:#f5f7f6;padding:14px;overflow:auto;max-height:360px;white-space:pre;margin:12px -4px 0}.proposal .formula{overflow:auto;padding:12px 0;font-size:17px}.proposal .mapping{padding:8px 0;border-top:1px solid #e6ece8;font-size:14px}.proposal code{font:14px Consolas,monospace;overflow-wrap:anywhere}.proposal details{margin-top:14px}.proposal summary{cursor:pointer;font-size:14px;color:var(--green)}
.proposal .results{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0 20px}.proposal .result{background:white;border:1px solid #dbe4df;border-radius:10px;padding:10px 18px;flex:1}.proposal .result strong{display:block;font-size:25px;font-weight:600;font-variant-numeric:tabular-nums}.proposal .grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.proposal .chart{background:white;border:1px solid #dbe4df;border-radius:12px;padding:16px}.proposal .chart svg,.proposal .chart img{display:block;width:100%;height:auto}.proposal .chart.wide{grid-column:1/-1}.proposal .chart p{margin:8px 0}.proposal .chart-label{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:10px}.proposal .kicker{font-size:14px;color:#47745f}.proposal .recovery{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:16px}.proposal .recovery .card{padding:14px}.proposal .recovery .formula{font-size:15px}.proposal .row{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:14px}.proposal .pill{font:inherit;padding:7px 12px;border:1px solid #bacfc1;background:white;border-radius:8px;cursor:pointer;color:var(--green)}.proposal .pill.active{background:var(--green);color:white}.proposal .stagebar{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:16px}.proposal table{border-collapse:collapse;width:100%;font-size:14px}.proposal td,.proposal th{padding:9px;text-align:left;border-bottom:1px solid #e1e9e4}.proposal .warning{color:#8c591b;background:#fff6e7;padding:10px 14px;border-radius:8px;margin-bottom:14px}.proposal [hidden]{display:none!important}.proposal .sample{margin-bottom:16px}.proposal .sample p{overflow-wrap:anywhere}.proposal .final{margin-top:16px;padding:12px 16px;background:#e8f0eb;border-radius:8px}
@media(max-width:1050px){.proposal .cols{grid-template-columns:160px minmax(0,1fr)}.proposal .explain{grid-column:1/-1}.proposal .recovery{grid-template-columns:1fr}.proposal .explain .mapping{display:inline-block;vertical-align:top;margin-right:20px;max-width:100%}}
@media(max-width:680px){.proposal .head{padding:18px}.proposal .tabs{padding:0 18px;gap:16px}.proposal .body{padding:14px}.proposal .cols,.proposal .grid{grid-template-columns:1fr}.proposal .steps{grid-template-columns:repeat(2,minmax(0,1fr))}.proposal .explain{grid-column:auto}.proposal .result{padding:8px 12px}.proposal .result strong{font-size:21px}.proposal .chart{padding:12px}.proposal .chart.wide{grid-column:auto}.proposal h2{font-size:22px}}
@container(max-width:1050px){.proposal .cols{grid-template-columns:160px minmax(0,1fr)}.proposal .explain{grid-column:1/-1}.proposal .recovery{grid-template-columns:1fr}}
@container(max-width:680px){.proposal .cols,.proposal .grid{grid-template-columns:1fr}.proposal .steps{grid-template-columns:repeat(2,minmax(0,1fr))}.proposal .explain{grid-column:auto}.proposal .chart.wide{grid-column:auto}}
"""

def fmt(value):
    return f'{value:.7g}' if isinstance(value, (int, float)) else esc(value)

def formula(expression):
    return '<div class="formula">\\[' + expression + '\\]</div>'

def skin(body):
    return '<style>' + CSS + '</style><div class="proposal">' + body + '</div>'

def static_preview(markup):
    """Every apparent control in the inline snapshot opens its working view."""
    def anchor(match):
        attributes=match.group(1)
        destination='assets/proposed-page.html'
        if 'data-step=' in attributes:
            step=re.search(r'data-step="(\d+)"',attributes).group(1)
            destination+='?step='+step+'#program'
        elif 'data-tab="program"' in attributes:destination+='#program'
        elif 'data-layout="staged"' in attributes:destination+='?layout=staged#calculation'
        else:destination+='#calculation'
        return '<a'+attributes+' href="'+destination+'" target="_blank" rel="noopener">'
    return re.sub(r'<button([^>]*)>',anchor,markup).replace('</button>','</a>')

def mdm_sampling(run,assets):
    """Call the current implementation's own closures for auxiliary figures."""
    target=assets/'mdm-preview-sampling.json'
    if target.exists():return json.loads(target.read_text(encoding='utf8'))
    sys.path.insert(0,str(PROJECT/'python'))
    import numpy as np
    from methods.mdm import MDM
    functions={}
    def capture(frame,event,arg):
        if event=='return' and frame.f_code.co_name=='run' and frame.f_globals.get('__name__')=='methods.mdm':
            for key in ['calculate_eta_std','find_best_beta_for_gamma','profile_gradient']:
                functions[key]=frame.f_locals[key]
    original=sys.getprofile()
    try:
        sys.setprofile(capture)
        result=MDM(run['case']['observations']).run(trace=False,**run['case']['parameters'])
    finally:sys.setprofile(original)
    for actual,key in zip(result,['beta_hat','eta_hat','gamma_hat']):
        if not np.isclose(actual,run['result'][key],rtol=1e-11,atol=1e-10):raise RuntimeError('MDM fixture drift')
    data=np.sort(np.asarray(run['case']['observations']))
    final=run['result']['gamma_hat'];delta=run['calculation']['selection']['target_offset']
    gammas=[0., final*.65, final, final+(min(data)-final)*.5]
    locations=np.unique(np.r_[np.linspace(0,gammas[-1],80),gammas])
    gradients=[{'x':float(g),'y':functions['profile_gradient'](g)} for g in locations]
    entries=[]
    for i,gamma in enumerate(gammas):
        beta,sigma=functions['find_best_beta_for_gamma'](gamma)
        shape=[{'x':float(b),'y':functions['calculate_eta_std'](b,gamma,data)} for b in np.unique(np.r_[np.linspace(max(.1,beta*.5),min(15,beta*1.65),100),beta])]
        for suffix,chart in [
          ('shape',{'id':'shape-discrepancy','x':{'label':'形状参数 β'},'y':{'label':'伪尺度标准差 σ'},'series':[{'id':'aux-shape','label':'现行函数的辅助采样','kind':'line','points':shape}], 'selected':[{'x':float(beta),'y':float(sigma),'label':'该位置下的条件最小值'}],'references':[]}),
          ('location',{'id':'location-criterion','x':{'label':'位置参数 γ'},'y':{'label':'廓线梯度 g(γ)'},'series':[{'id':'aux-location','label':'现行梯度函数的辅助采样','kind':'line','points':gradients}], 'selected':[{'x':float(gamma),'y':functions['profile_gradient'](gamma),'label':'当前查看位置'}],'references':[{'axis':'y','value':delta,'label':'δ'}]})]:
            previous.make_plot(chart,assets/f'linked-{i}-{suffix}.svg','mdm')
        entries.append({'gamma':float(gamma),'beta':float(beta),'sigma':float(sigma),'gradient':functions['profile_gradient'](gamma),'selected_estimate':i==2,'shape':shape})
    sampling={'purpose':'Auxiliary sampling for the proposed linked display; not solver iterations or additional accepted estimates.','owning_source':'python/methods/mdm.py','source_sha256':hashlib.sha256((PROJECT/'python/methods/mdm.py').read_bytes()).hexdigest(),'entries':entries,'gradient_samples':gradients,'offset':delta}
    target.write_text(json.dumps(sampling,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    return sampling

def header(method, tab):
    config = CONFIG[method]
    return '<div class="head"><div class="eyebrow">参数估计方法 / '+method.upper()+'</div><h2>'+esc(config['name'])+'</h2><p class="subtitle">'+esc(config['story'])+'</p></div><div class="tabs"><button class="tab '+('active' if tab=='program' else '')+'" data-tab="program">程序流程</button><button class="tab '+('active' if tab=='calculation' else '')+'" data-tab="calculation">计算过程</button></div>'

def code_panel(step, files):
    parts = []
    for ref in step['sources']:
        source = files[ref['file']]
        lines = source['lines']
        code = '\n'.join(f'{n+1:>4}  {lines[n]}'.rstrip() for n in range(ref['start'], ref['end']))
        parts.append('<p class="muted">'+esc(ref['file'])+f' · L{ref["start"]+1}–{ref["end"]}</p><pre><code>'+esc(code)+'</code></pre>')
    return ''.join(parts)

LOOPS = {
 'mle':'每换一个候选位置 γ，就重复条件形状与尺度求解；最后比较合格位置的似然。',
 'wmle':'每个候选位置先解形状方程，再检查位置方程；两个残差共同约束同一组参数。',
 'mdm':'每个位置 γ 都对应一次形状寻优；位置判据与形状图显示同一个 γ。',
 'lse':'每个候选位置都完成一次 White 回归并得到 F 比；在选中位置恢复参数。',
 'lre':'每个候选位置都重新计算概率图的相关系数；选中位置后作最终回归。',
 'mm':'经验生存函数 → 三个 Weibull 矩 → 可采纳性检查 → 显式求参与位置处理。',
 'mmle':'最小值固定位置并删除一个观测；循环只发生在形状不动点迭代中。',
}

def program(method, run, selected=1, interactive=False):
    steps = run['flow']['steps']
    selected = min(selected, len(steps)-1)
    files = {s['path']:s for s in run['flow']['sources']}
    nav = '<nav class="card steps" aria-label="计算步骤">'
    for i, step in enumerate(steps):
        nav += f'<button class="step {"active" if i==selected else ""}" data-step="{i}">{i+1}　{esc(step["name"])}</button>'
    nav += '</nav>'
    panels=[]
    for i, step in enumerate(steps):
        if not interactive and i != selected:
            continue
        hidden=' hidden' if i!=selected else ''
        out='<section class="card code-panel" data-panel="'+str(i)+'"'+hidden+'><h3>'+esc(step['name'])+'</h3><p>'+esc(step['description'])+'</p>'+code_panel(step,files)+'</section>'
        explanation = '<aside class="card explain" data-panel="'+str(i)+'"'+hidden+'><h3>公式与变量</h3>'+formula(step['formula']['expression'])
        for label,key in [('输入','inputs'),('输出','outputs')]:
            explanation += '<h4>'+label+'</h4>'
            for v in step[key]:
                explanation += '<div class="mapping"><code>'+esc(v['code'])+'</code> · '+esc(v['meaning'])+'</div>'
        explanation += '<details><summary>依据与边界</summary><p>'+esc(step['basis'])+'</p><p>'+esc(step.get('notes',''))+'</p></details></aside>'
        panels.append(out+explanation)
    return '<div class="body"><p class="lead">'+LOOPS[method]+'</p><div class="cols">'+nav+''.join(panels)+'</div></div>'

def svg_asset(path):
    svg=path.read_text(encoding='utf8')
    return svg[svg.index('<svg'):]

def recoveries(method, run):
    trace=run['calculation']
    if method=='mdm':
        r=run['result'];s=trace['selection']
        recovery=[
          {'title':'位置判据','formula':r'g(\hat\gamma)=\delta','values':[{'label':'γ̂','value':r['gamma_hat']},{'label':'δ','value':s['target_offset']}]},
          {'title':'该位置下形状最优','formula':r'\hat\beta=\arg\min_\beta\sigma_\eta(\beta,\hat\gamma)','values':[{'label':'β̂','value':r['beta_hat']},{'label':'σ','value':s['sigma']}]},
          {'title':'伪尺度均值恢复尺度','formula':r'\hat\eta=\frac1n\sum_i\eta_i','values':[{'label':'η̂','value':r['eta_hat']}]}]
    else:
        recovery=trace['recovery']
    parts=[]
    for i,row in enumerate(recovery):
        parts.append('<div class="card" data-recovery="'+str(i)+'"><h4>'+esc(row['title'])+'</h4>'+formula(row['formula'])+'<p>'+ ' · '.join(esc(v['label'])+' = '+fmt(v['value']) for v in row['values'])+'</p></div>')
    return '<div class="recovery">'+''.join(parts)+'</div>'

def candidate_table(run):
    c=next(c for c in run['calculation']['charts'] if c['id']=='candidate-residuals')
    points=c['series'][0]['points']
    rows=''.join('<tr><td>'+str(i+1)+'</td><td>'+fmt(p.get('beta'))+'</td><td>'+fmt(p.get('gamma'))+'</td><td>'+fmt(p.get('t1'))+'</td><td>'+fmt(p.get('t2'))+'</td><td>'+('采用' if abs(p.get('gamma',-1)-run['result']['gamma_hat'])<1e-8 else '')+'</td></tr>' for i,p in enumerate(points))
    return '<table><thead><tr><th>候选</th><th>β</th><th>γ</th><th>T₁</th><th>T₂</th><th>结果</th></tr></thead><tbody>'+rows+'</tbody></table>'

def calculation(method,run,assets,embedded=False):
    r=run['result'];config=CONFIG[method]
    cards=[]
    for i,(chart_id,(title,description,note)) in enumerate(config['figures'].items()):
        if chart_id=='candidate-residuals':
            drawing=candidate_table(run)
        else:
            drawing=svg_asset(assets/('record-'+chart_id+'.svg')) if embedded else '<img src="record-'+chart_id+'.svg" alt="'+esc(title)+'">'
        wide=' wide' if method=='mle' and i==2 else ''
        caption = {
          'profile-likelihood':'在合格候选中比较似然；按位置排列的函数求值显示选中点附近的峰。',
          'location-score':'零线附近的位置得分，与上图同一位置的似然峰相对应。',
          'conditional-shape-equation':'固定 γ̂ = '+fmt(r['gamma_hat'])+'，查看形状方程；曲线包含同一方程的辅助采样。',
          'weighted-location-equation':'先满足条件形状方程，再查看位置方程 T₂ 的零点。',
          'candidate-residuals':'同一候选的两个方程残差及返回参数列在一起。',
          'shape-discrepancy':'固定 γ̂ = '+fmt(r['gamma_hat'])+'，伪尺度标准差最小点确定 β̂。',
          'location-criterion':'梯度 g(γ) 与偏移 δ 的关系决定位置；本例为普通括区求根。',
          'f-location':'F 比最大的候选位置用于下方 White 回归。',
          'white-regression':'X 为顺序统计量期望，Y 为 ln(t−γ̂)；斜率的倒数是 β̂，截距取指数得到 η̂。',
          'correlation-location':'选择相关系数最大的候选位置 γ̂；相关系数本身不构成模型检验。',
          'park-probability-regression':'X = ln(t−γ̂)，Y = ln[−ln(1−p)]；斜率是 β̂，截距用于恢复 η̂。',
          'weibull-moments':'经验生存函数 S、S²、S⁴ 的阶梯面积对应三个 Weibull 矩。',
          'moment-admissibility':'两组矩差的正值及次序决定显式求参是否可采纳。',
          'shape-fixed-point':'横轴为实际形状迭代序号，标出最后接受的 β̂。',
          'shape-step':'相邻形状估计的变化量达到停止容差后结束迭代。',
        }[chart_id]
        cards.append('<section class="chart'+wide+'" data-chart="'+str(i)+'"><div class="chart-label"><h3>'+str(i+1)+'　'+esc(title)+'</h3></div>'+drawing+'<p>'+esc(caption)+'</p></section>')
    warning='<p class="warning">计算过程页面尚未开放；这里是拟议效果原型，使用既有实现的运行记录。</p>' if method=='mmle' else ''
    if method=='mdm':
        warning+='<p class="muted">本例 δ=0。原型中的位置切换使用现行函数的辅助采样，展示双图联动效果。</p>'
    sample='<details class="sample"><summary>'+esc(run['case']['label'])+' · n='+str(run['case']['n'])+' · 查看本次样本</summary><p>'+', '.join(fmt(v) for v in run['case']['observations'])+'</p></details>'
    results='<div class="results">'+''.join('<div class="result"><span>'+name+'</span><strong>'+fmt(r[key])+'</strong></div>' for name,key in [('形状 β̂','beta_hat'),('尺度 η̂','eta_hat'),('位置 γ̂','gamma_hat')])+'</div>'
    toggle='<div class="row"><button class="pill active" data-layout="all">总览</button><button class="pill" data-layout="staged">分步阅读</button></div><div class="stagebar" hidden>'+''.join('<button class="pill" data-stage="'+str(i)+'">'+str(i+1)+' '+esc(item[0])+'</button>' for i,item in enumerate(config['figures'].values()))+'</div>' if method in ['mle','wmle'] else ''
    if method=='mdm' and not embedded:
        sampling=mdm_sampling(run,assets)
        toggle='<div class="row"><span>查看位置 γ：</span>'+''.join('<button class="pill'+(' active' if i==2 else '')+'" data-mdm="'+str(i)+'">'+fmt(e['gamma'])+('（估计值）' if i==2 else '')+'</button>' for i,e in enumerate(sampling['entries']))+'</div><p class="muted" id="mdm-reading">当前显示最终估计位置；其他位置仅供查看条件形状，不改变返回参数。</p>'
        cards=[card.replace('src="record-shape-discrepancy.svg"','id="linked-shape" src="linked-2-shape.svg"').replace('src="record-location-criterion.svg"','id="linked-location" src="linked-2-location.svg"') for card in cards]
    return '<div class="body">'+warning+sample+'<p class="lead">'+esc(LOOPS[method])+'</p>'+results+toggle+'<div class="grid">'+''.join(cards)+'</div>'+recoveries(method,run)+'</div>'

JS = """
const root=document.querySelector('.proposal');
function tab(which){document.querySelectorAll('[data-view]').forEach(v=>v.hidden=v.dataset.view!==which);root.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===which));history.replaceState(null,'','#'+which)}
root.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>tab(b.dataset.tab));
root.querySelectorAll('[data-step]').forEach(b=>b.onclick=()=>{root.querySelectorAll('[data-step]').forEach(x=>x.classList.toggle('active',x===b));root.querySelectorAll('[data-panel]').forEach(x=>x.hidden=x.dataset.panel!==b.dataset.step)});
let stage=0;
function setStage(i){stage=i;root.querySelectorAll('[data-chart]').forEach(x=>x.hidden=Number(x.dataset.chart)!==i);root.querySelectorAll('[data-stage]').forEach(x=>x.classList.toggle('active',Number(x.dataset.stage)===i))}
root.querySelectorAll('[data-layout]').forEach(b=>b.onclick=()=>{root.querySelectorAll('[data-layout]').forEach(x=>x.classList.toggle('active',x===b));const focus=b.dataset.layout==='staged';root.querySelector('.stagebar').hidden=!focus;root.querySelectorAll('[data-chart]').forEach(x=>x.hidden=false);if(focus)setStage(stage)});
root.querySelectorAll('[data-stage]').forEach(b=>b.onclick=()=>setStage(Number(b.dataset.stage)));
root.querySelectorAll('[data-mdm]').forEach(b=>b.onclick=()=>{root.querySelectorAll('[data-mdm]').forEach(x=>x.classList.toggle('active',x===b));document.querySelector('#linked-shape').src='linked-'+b.dataset.mdm+'-shape.svg';document.querySelector('#linked-location').src='linked-'+b.dataset.mdm+'-location.svg';document.querySelector('#mdm-reading').textContent='当前查看 γ = '+b.textContent+'；两图同步切换，最终返回参数保持上方同次估计值。';root.querySelector('[data-chart="0"] p').textContent='固定当前查看位置 γ = '+b.textContent+'，标记该位置下伪尺度标准差的条件最小值。';root.querySelector('[data-chart="1"] p').textContent='标记当前查看位置；梯度曲线与偏移线共同解释最终位置的判据。';});
tab(location.hash==='#program'?'program':'calculation');
const query=new URLSearchParams(location.search);
if(query.has('step'))root.querySelector('[data-step="'+Number(query.get('step'))+'"]').click();
if(query.get('layout')==='staged')root.querySelector('[data-layout="staged"]').click();
"""

def content_block(ident,markup,kind='text'):
    return {'id':ident,'kind':kind,'html':markup}

def refresh(method):
    folder=ROOT/('method-'+method);assets=folder/'assets'
    path=folder/'board.json';board=json.loads(path.read_text(encoding='utf8'))
    refreshed=board.get('presentation_refresh')=='2026-11-04'
    if refreshed and '--rebuild-before-delivery' not in sys.argv:
        raise SystemExit('Already refreshed; edit the same board without rerunning the revision migration')
    run=json.loads((assets/'process-run.json').read_text(encoding='utf8'))
    hashes=dict(run['source_sha256'])
    hashes.update({'python/'+s['path']:s['sha256'] for s in run['calculation']['run']['sources']})
    drift=[f for f,h in hashes.items() if hashlib.sha256((PROJECT/f).read_bytes()).hexdigest()!=h]
    if drift:raise RuntimeError('Owning source changed: '+str(drift))
    # Preserve the prior presentation, not just its Git object, and all feedback.
    old_copy=assets/'presentation-before-20261104.json'
    if not old_copy.exists():old_copy.write_text(path.read_text(encoding='utf8'),encoding='utf8')
    if not refreshed:board['revision']+=1
    board['presentation_refresh']='2026-11-04'
    board['units']=[u for u in board['units'] if u['id']!='calculation-density']
    units={u['id']:u for u in board['units']}
    def replace(ident,title,blocks):
        u=units[ident];u['title']=title;u['mode']='content';u['options'][0]['blocks']=blocks
    replace('identity','1 '+CONFIG[method]['name']+'：建议页面',[
      content_block('identity-body','<p><a href="assets/proposed-page.html" target="_blank" rel="noopener"><strong>打开可操作页面原型 ↗</strong></a>　·　<a href="assets/methods.html">切换七种方法</a></p><p>下面直接展示拟议的程序流程和计算页面。请看分阶段是否清楚、图能否解释参数如何确定；可直接批注要调整的地方。</p><p><mark>这是呈现原型，尚未应用到网站。</mark>数值沿用原审阅固定样本；已逐文件核对，相关源码与当前工作区一致。</p>')])
    replace('presentation-summary','2 计算过程：拟议页面',[
      content_block('proposed-calculation-page',static_preview(skin(header(method,'calculation')+calculation(method,run,assets,True))),'visual'),
      content_block('summary-assessment','<p><strong>推荐理由：</strong>'+esc(CONFIG[method]['conclusion'])+'</p>')])
    replace('program-presentation','3 程序流程：步骤、源码与公式',[
      content_block('program-assessment','<p>'+esc(CONFIG[method]['program'])+'</p><p><a href="assets/proposed-page.html#program" target="_blank" rel="noopener">打开原型，逐步切换源码与公式 ↗</a></p>'),
      content_block('proposed-program-page',static_preview(skin(header(method,'program')+program(method,run))),'visual'),
      content_block('program-order','<details><summary>查看原页面与完整核查依据</summary><p><a href="assets/current-process.png" target="_blank">原页面截图</a> · <a href="assets/process-evidence.html" target="_blank">完整步骤、源码、公式</a></p></details>')])
    replace('calculation-presentation','4 编排变化与原页面',[
      content_block('calculation-layout','<p>'+esc(CONFIG[method]['assessment'])+'</p><details><summary>查看修改前的计算页面</summary><p><a href="assets/current-calculation.png" target="_blank">打开原网站截图</a>（保留上一轮截图供对照。）</p></details>')])
    # The complete proposed layout appears above once; chart sections retain
    # their old IDs and remain precise annotation anchors, without duplicating it.
    for chart_id,(title,description,note) in CONFIG[method]['figures'].items():
        u=units['figure-'+chart_id]
        old_id=u['options'][0]['blocks'][0]['id']
        u['options'][0]['blocks']=[content_block(old_id,'<p><strong>'+esc(title)+'：</strong>'+esc(description)+'</p><p>'+esc(note)+'</p>')]
    sources=units['sources']['options'][0]['blocks'][0]
    sources['html']='<details><summary>样本、来源与核查材料</summary><p>固定运行记录读取时间：'+esc(run['checked_at'])+'。2026-11-04 已核对相关源码 SHA-256 全部一致；未重新运行批量实验。</p><p><a href="assets/process-run.json">完整输入与运行记录</a> · <a href="assets/process-evidence.html">源码与公式</a> · <a href="assets/prior-algorithm-review.html">此前原文核对</a> · <a href="assets/presentation-before-20261104.json">上一版汇报</a></p></details>'
    if method in ['mle','wmle']:
        choice={'id':'calculation-density','title':'2.1 默认展开方式','mode':'choices','inline':True,'selection_mode':'single','selected_ids':[],
          'context':'两种编排使用上方同一组图。原型可点“总览 / 分步阅读”直接比较；推荐总览，让判据关系同时可见。',
          'options':[
            {'id':'all-visible','label':'总览展开（推荐）','blocks':[content_block('all-layout','<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px"><div style="padding:18px;background:#e7f0e9;border:1px solid #b7cfbf">位置判据</div><div style="padding:18px;background:#e7f0e9;border:1px solid #b7cfbf">'+('位置得分' if method=='mle' else '形状方程')+'</div><div style="grid-column:1/-1;padding:12px;background:#f2f5f3">'+('条件形状方程' if method=='mle' else '接受候选小表')+' → 参数恢复</div></div><p><mark>关键图同时可见</mark>，阅读较长；手机依次纵排。</p>','visual')]},
            {'id':'staged-focus','label':'分步切换','blocks':[content_block('staged-layout','<div style="padding:9px;background:#f2f5f3">① 位置　→　② '+('位置得分' if method=='mle' else '形状')+'　→　③ '+('形状' if method=='mle' else '候选')+'</div><div style="padding:24px;background:#e7f0e9;border:1px solid #b7cfbf">当前只显示一幅判据图</div><p><mark>默认更短、更聚焦</mark>，对照图之间的关系需要切换。</p>','visual')]}]}
        pos=board['units'].index(units['presentation-summary'])+1
        board['units'].insert(pos,choice)
    prototype='<div class="head" style="border-bottom:0;background:#fff7e8"><p class="kicker">呈现原型 · 2026-11-04 · 固定样本预览</p><p><a href="../">返回本方法审阅与批注</a>　·　<a href="methods.html">切换方法</a></p></div>'+header(method,'calculation')+'<div data-view="program" hidden>'+program(method,run,interactive=True)+'</div><div data-view="calculation">'+calculation(method,run,assets)+'</div>'
    markup='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(CONFIG[method]['name'])+' · 呈现原型</title><style>body{margin:0;padding:24px;background:#eaf0ec}main{max-width:1500px;margin:auto}@media(max-width:680px){body{padding:8px}}</style><main>'+skin(prototype)+'</main><script>'+JS+'</script></html>'
    html_blocks=[b for u in board['units'] for o in u['options'] for b in o['blocks'] if 'html' in b]
    compiled=render_html_batch([b['html'] for b in html_blocks]+[markup])
    for b,rendered in zip(html_blocks,compiled):b['html']=rendered
    (assets/'proposed-page.html').write_text(compiled[-1],encoding='utf8')
    board['require_confirmation']=True
    for key in ['review_complete','completed_at','archive_pending']:board.pop(key,None)
    path.write_text(json.dumps(board,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    verify={'checked_at':'2026-11-04','source_checks':hashes,'source_drift':drift,'run_id':run['calculation']['run']['id'],'run_timestamp':run['calculation']['run']['completed_at'],'scope':'Presentation prototype; no estimator or website code changed.'}
    (assets/'presentation-check.json').write_text(json.dumps(verify,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    subprocess.run([sys.executable,str(SKILL/'scripts/review.py'),'render','--root',str(folder)],check=True,capture_output=True)
    print(json.dumps({'method':method,'revision':board['revision'],'source_files_verified':len(hashes)},ensure_ascii=False),flush=True)

if __name__=='__main__':
    for method in METHODS:refresh(method)
