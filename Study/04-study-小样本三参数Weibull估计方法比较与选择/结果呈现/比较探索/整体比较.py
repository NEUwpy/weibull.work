"""七法整体比较、文章图表和可批注HTML；只读取Study04存档结果。"""
from __future__ import annotations
import argparse, base64, hashlib, html, itertools, json, math, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
STUDY = HERE.parent.parent
ROOT = STUDY.parent.parent
sys.path.insert(0, str(ROOT/'python'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap, Normalize
import numpy as np
import pandas as pd
from studies.common.metrics import summarize_standard_errors, quantile_true, quantile_est
from methods.mm import sample_weibull_moment

VERSION = 'study04-article-v04-20261020'
DATA = HERE.parent/'分析数据/比较论证-v0.4.json'
ARTICLE = STUDY/'其他/历史尝试/报告下（方法对比）-v0.4.md'
METHODS = ['MDM-0.1','LSE','LRE(Park)','WMLE','MLE','MMLE(KR)','MM']
LABELS = ['MDM','LSE','LRE','WMLE','MLE','MMLE','MM']
COLORS = ['#0072B2','#009E73','#CC79A7','#D55E00','#444444','#56B4E9','#E69F00']
BETAS = [1.5,2.,2.5,3.,3.5,4.,4.5,5.]
NS = [50,20,15,10,7]
PARAMS = ['beta','eta','gamma']
SYMBOLS = ['β','η','γ']
TARGETS = SYMBOLS+['B10','B1']

def stat(e):
    return summarize_standard_errors(e)

def load():
    stored=pd.read_csv(HERE.parent/'分析数据/参数指标.csv')
    arrays={s:{k:np.zeros((5,5,8,7)) for k in ['rmse','bias','sd','mae']}
            for s in ['own','common']}
    counts=np.zeros((5,8,7),int);common_counts=np.zeros((5,8),int)
    risk=np.zeros((5,8,7));sources={};cells={};checked=0;tails=[]
    for i,n in enumerate(NS):
        for j,beta in enumerate(BETAS):
            path=STUDY/f'结果/W{beta:g},1000,500/估计结果/n{n}.csv'
            sources[path.relative_to(STUDY).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
            df=pd.read_csv(path);assert len(df)==1200 and df['样本编号'].is_unique
            v=np.column_stack([df[m+'_状态'].eq('success') for m in METHODS])
            values=np.stack([df[[m+'_'+p+'估计' for p in ['形状','尺度','位置']]].to_numpy(float) for m in METHODS],axis=1)
            assert np.isfinite(values[v]).all()
            common=v.all(axis=1);common_counts[i,j]=common.sum();counts[i,j]=v.sum(axis=0)
            errors=np.full((1200,7,5),np.nan);errors[:,:,:3]=values-[beta,1000.,500.]
            for m in range(7):
                good=v[:,m]
                risk[i,j,m]=np.mean((values[good,m,0]<=beta/3)|(values[good,m,0]>=3*beta))*100
                for p,R in enumerate([.90,.99],3):
                    errors[good,m,p]=[quantile_est(*row,R)-quantile_true(beta,1000,500,R) for row in values[good,m]]
                for subset,mask in [('own',good),('common',common)]:
                    row=stored[(stored.n==n)&(stored.beta==beta)&(stored.method==METHODS[m])&(stored.subset==subset)].iloc[0]
                    assert int(row.effective_count)==int(mask.sum())
                    for p in range(5):
                        st=stat(errors[mask,m,p])
                        for key in arrays[subset]:
                            arrays[subset][key][p,i,j,m]=st[key]
                            if p<3:
                                assert np.isclose(st[key],row[f'{PARAMS[p]}_{key}'],rtol=2e-11,atol=1e-10)
                                checked+=1
                e=errors[good,m,0];share=float(np.max(e*e)/np.sum(e*e))
                pos=np.flatnonzero(good)[np.argmax(e*e)]
                tails.append(dict(share=share,i=i,j=j,m=m,pos=int(pos),sample=int(df.iloc[pos]['样本编号']),common=bool(common[pos])))
            cells[i,j]=dict(frame=df,valid=v,values=values,common=common,errors=errors)
    r=arrays['common']['rmse'];ratios=r/r.min(axis=-1,keepdims=True)
    med=np.median(ratios,axis=-1);worst=ratios.max(axis=-1)
    near=(ratios<=1.1).sum(axis=(1,2))
    growth=r[:,4]/r[:,0]
    relative_growth=ratios[:,4]/ratios[:,0]
    summaries=[]
    for m in range(7):
        summaries.append(dict(method=LABELS[m],near=[int(x) for x in near[:,m]],
            worst=[float(x) for x in ratios[:3,:,:,m].max(axis=(1,2))],
            beta_growth_range=[float(growth[0,:,m].min()),float(growth[0,:,m].max())],
            beta_relative_worse=int((relative_growth[0,:,m]>1).sum()),
            success_range=[float(counts[:,:,m].min()/12),float(counts[:,:,m].max()/12)]))
    own_winner=arrays['own']['rmse'].argmin(axis=-1)
    common_winner=r.argmin(axis=-1)
    tail=max(tails,key=lambda x:x['share'])
    tc=cells[tail['i'],tail['j']];tv=tc['values'][tail['pos'],tail['m']]
    beta=BETAS[tail['j']];n=NS[tail['i']]
    observations=tc['frame'].iloc[tail['pos']][[f'观测值{k+1}' for k in range(n)]].to_numpy(float)
    # Diagnostic identity for the already stored Cran estimate; no estimator call.
    moments=[sample_weibull_moment(observations,k) for k in [1,2,4]]
    d12=moments[0]-moments[1];d24=moments[1]-moments[2]
    tail.update(beta=beta,n=n,estimate=float(tv[0]),moment_ratio=d12/d24,
                denominator=float(math.log(d12)-math.log(d24)))
    assert np.isclose(math.log(2)/tail['denominator'],tail['estimate'],rtol=2e-6)
    kr=[]
    for (i,j),c in cells.items():
        obs=c['frame'][[f'观测值{k+1}' for k in range(NS[i])]].to_numpy(float)
        assert np.allclose(c['values'][:,5,2],obs.min(axis=1),rtol=0,atol=1e-8)
        if BETAS[j] in [1.5,5.] and NS[i] in [7,50]:
            b=BETAS[j];nn=NS[i]
            kr.append(dict(beta=b,n=nn,theory=1000*math.gamma(1+1/b)*nn**(-1/b),observed=float(c['errors'][:,5,2].mean())))
    c=cells[4,7];mle=c['valid'][:,4];e=c['errors'][:,:,4]
    audit=dict(mle_count=int(mle.sum()),mle_rmse=stat(e[mle,4])['rmse'],
        mdm_own=stat(e[:,0])['rmse'],mdm_on_mle=stat(e[mle,0])['rmse'],
        own_mle_wins=int((own_winner[4]==4).sum()),common_mle_wins=int((common_winner[4]==4).sum()),
        life_vs_shape=[int((common_winner[p]!=common_winner[0]).sum()) for p in [3,4]])
    model=dict(version=VERSION,created='2026-10-20',sources=sources,
        source_fingerprint=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest(),
        counts=counts.tolist(),common_counts=common_counts.tolist(),
        stats={s:{k:v.tolist() for k,v in a.items()} for s,a in arrays.items()},
        ratios=ratios.tolist(),median_gap=med.tolist(),worst_gap=worst.tolist(),
        risk=risk.tolist(),summaries=summaries,kr=kr,tail=tail,audit=audit,
        checks=dict(source_files=40,attempts=336000,stored_values_checked=checked,
                    kr_minimum_checked=48000,common_range=[int(common_counts.min()),int(common_counts.max())]))
    return model,cells

def save(fig,name):
    d=HERE/'图';d.mkdir(exist_ok=True)
    p=d/(name+'.png');fig.savefig(p,dpi=175,bbox_inches='tight',facecolor='white');plt.close(fig)
    return p.name

def configure():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False})

def plots(model,cells):
    ratio=np.array(model['ratios']);r=np.array(model['stats']['common']['rmse'])
    groups={}
    def option(name,label,caption):return dict(file=name,label=label,caption=caption)
    def axes_grid(ax):
        ax.set_xticks(range(8),[f'{b:g}' for b in BETAS]);ax.set_yticks(range(5),NS)
        ax.set_xlabel('β');ax.set_ylabel('n')
    # Separate colour scales preserve moderate differences as well as the MM extreme.
    fig,axs=plt.subplots(2,3,figsize=(13,6.8),layout='constrained')
    for row,fn in enumerate([np.median,np.max]):
        for p in range(3):
            a=fn(ratio[p],axis=-1);ax=axs[row,p]
            norm=Normalize(1,float(a.max()))
            im=ax.imshow(a,aspect='auto',cmap='YlGnBu',norm=norm)
            axes_grid(ax);ax.set_title(SYMBOLS[p]+(' · median / min' if row==0 else ' · max / min'))
            for i,j in itertools.product(range(5),range(8)):
                ax.text(j,i,f'{a[i,j]:.2f}' if a[i,j]<10 else f'{a[i,j]:.0f}',ha='center',va='center',fontsize=7.5,color='white' if norm(a[i,j])>.6 else '#17252e')
            fig.colorbar(im,ax=ax,shrink=.8).set_label('RMSE ratio')
    f=save(fig,'v04_01_整体差异区域')
    groups['global']=[option(f,'区域图：中间方法与最差方法分别看','每格使用七法共同有效样本。上排为七个RMSE的中位数／最小值，下排为最大值／最小值；三列依次为形状、尺度、位置。每个面板使用独立色标，格内标实际倍数。')]
    fig,axs=plt.subplots(1,3,figsize=(14,14),layout='constrained')
    bounds=[1,1.1,1.25,1.5,2,3,10,100,1000]
    cmap=plt.get_cmap('YlOrRd',len(bounds)-1);norm=BoundaryNorm(bounds,cmap.N,clip=True)
    for p,ax in enumerate(axs):
        a=ratio[p].reshape(40,7);ax.imshow(a,aspect='auto',cmap=cmap,norm=norm)
        ax.set_xticks(range(7),LABELS,rotation=45,ha='right')
        ax.set_yticks(range(40),[f'{n} / {b:g}' for n in NS for b in BETAS],fontsize=7)
        ax.set_ylabel('n / β');ax.set_title(SYMBOLS[p])
        for i,j in itertools.product(range(40),range(7)):
            ax.text(j,i,f'{a[i,j]:.2f}' if a[i,j]<10 else f'{a[i,j]:.0f}',ha='center',va='center',fontsize=6.3,color='white' if a[i,j]>=3 else '#222')
        for k in [7.5,15.5,23.5,31.5]:ax.axhline(k,color='white',lw=1.5)
    groups['global'].append(option(save(fig,'v04_01B_七法全条件误差比'),'全条件表：每种方法距离参照多远','七种方法全部保留；40行依次为五档n，每档内β从1.5到5。格内为本条件RMSE／七法最小RMSE。颜色按1、1.1、1.25、1.5、2、3、10、100、1000非等距分档；分档只为阅读，未定义工程优劣阈值。'))
    # All methods, all n, all beta: no preselected pair drives the main comparison.
    fig,axs=plt.subplots(7,3,figsize=(13,15),layout='constrained')
    ncolors=['#4c78a8','#72b7b2','#54a24b','#f58518','#e45756']
    for m in range(7):
        for p in range(3):
            ax=axs[m,p]
            for i,n in enumerate(NS):ax.plot(BETAS,ratio[p,i,:,m],marker='o',ms=2.5,color=ncolors[i],label=f'n={n}')
            ax.axhline(1,color='#777',ls=':',lw=.7);ax.set_yscale('log');ax.grid(alpha=.12)
            if m==0:ax.set_title(SYMBOLS[p])
            if p==0:ax.set_ylabel(LABELS[m]+'\nRMSE / min')
            if m==6:ax.set_xlabel('β')
    h,l=axs[0,0].get_legend_handles_labels();fig.legend(h,l,loc='outside lower center',ncol=5,frameon=False)
    groups['change']=[option(save(fig,'v04_02_全部方法条件响应'),'完整轨迹：保留五档样本量','每行一种方法、三列为三个参数，颜色对应n。纵轴为本方法RMSE／同条件七法最小RMSE，对数刻度，各面板独立量程；1表示点估计参照。曲线只连接已计算的八个β。')]
    growth=ratio[:,4]/ratio[:,0]
    fig,axs=plt.subplots(1,3,figsize=(13,4.1),layout='constrained')
    for p,ax in enumerate(axs):
        for m in range(7):ax.plot(BETAS,growth[p,:,m],color=COLORS[m],marker='o',ms=3,label=LABELS[m])
        ax.axhline(1,color='#777',ls=':',lw=1);ax.set_yscale('log');ax.set_title(SYMBOLS[p]);ax.set_xlabel('β');ax.grid(alpha=.15)
    axs[0].set_ylabel('(RMSE/min at n=7) / (RMSE/min at n=50)')
    h,l=axs[0].get_legend_handles_labels();fig.legend(h,l,loc='outside lower center',ncol=7,frameon=False)
    groups['change'].append(option(save(fig,'v04_02B_相对差距端点变化'),'端点对照：相对距离扩大还是缩小','数值大于1表示从n=50到7时，相对于各自条件最小RMSE的距离扩大，小于1表示缩小。七法全部保留；这是一种端点概括，中间三档请看方案A。共同有效集合随条件变化，另用自身有效结果核对方向。'))
    # Distribution view: all seven methods and both endpoint sample sizes.
    fig,axs=plt.subplots(2,3,figsize=(13,7),layout='constrained')
    for row,i in enumerate([0,4]):
        c=cells[i,7]
        for p,ax in enumerate(axs[row]):
            for m in range(7):
                e=c['errors'][c['common'],m,p]/(5 if p==0 else 1000)
                q=np.quantile(e,[.05,.25,.5,.75,.95])
                ax.plot([q[0],q[4]],[m,m],color=COLORS[m],lw=1)
                ax.plot([q[1],q[3]],[m,m],color=COLORS[m],lw=5,solid_capstyle='butt')
                ax.scatter(q[2],m,s=17,color=COLORS[m],zorder=3)
            ax.axvline(0,color='#777',ls=':',lw=.8);ax.set_yticks(range(7),LABELS);ax.invert_yaxis()
            ax.set_title(f'n={NS[i]} · '+SYMBOLS[p]);ax.set_xlabel('normalized signed error');ax.grid(axis='x',alpha=.15)
    groups['error']=[option(save(fig,'v04_03_偏移与波动分布'),'分布带：偏移和主体波动','固定β=5，n纵向、三参数横向。点为中位数，粗线为25%—75%，细线为5%—95%；共同有效集合。形状误差除以5，尺度与位置误差除以1000。该图显示中心90%，全部极端结果仍进入RMSE。')]
    fig,axs=plt.subplots(2,3,figsize=(13,7),layout='constrained')
    for row,i in enumerate([0,4]):
        c=cells[i,7]
        for p,ax in enumerate(axs[row]):
            for m in range(7):
                e=np.sort(abs(c['errors'][c['common'],m,p])/(5 if p==0 else 1000))
                ax.plot(e,np.arange(1,len(e)+1)/len(e),color=COLORS[m],label=LABELS[m])
            ax.set_xscale('log');ax.set_title(f'n={NS[i]} · '+SYMBOLS[p]);ax.set_xlabel('normalized absolute error (log)');ax.set_ylabel('empirical proportion');ax.grid(alpha=.15)
    h,l=axs[0,0].get_legend_handles_labels();fig.legend(h,l,loc='outside lower center',ncol=7,frameon=False)
    groups['error'].append(option(save(fig,'v04_03B_全误差累积曲线'),'累积曲线：从主体一直看到尾部','同一β、n和共同有效集合；全部绝对误差均保留，对数横轴容纳完整范围。曲线显示满足给定误差容限的有效样本比例，分母为共同有效数；全部尝试口径另见寿命部分。'))
    t=model['tail'];c=cells[t['i'],t['j']]
    fig,ax=plt.subplots(figsize=(11,3.8),layout='constrained')
    for m in range(7):
        e=c['errors'][c['valid'][:,m],m,0]**2;e=np.sort(e)[::-1]
        ax.plot(np.arange(1,len(e)+1),np.cumsum(e)/e.sum()*100,color=COLORS[m],label=LABELS[m])
    ax.set_xscale('log');ax.set_xlabel('number of largest squared errors (log)');ax.set_ylabel('share of total squared error (%)');ax.legend(ncol=7,frameon=False);ax.grid(alpha=.15)
    groups['tail']=[option(save(fig,'v04_04_极端结果贡献'),'平方误差贡献','β=5、n=15。各法从最大形状平方误差开始累计，分母为本方法全部有效结果的总平方误差；保留所有极端值，不删除后重新排名。')]
    fig,ax=plt.subplots(figsize=(10,3.5),layout='constrained')
    ngrid=np.linspace(7,50,100)
    for b,color in [(1.5,'#0072B2'),(5.,'#d55e00')]:
        ax.plot(ngrid,1000*math.gamma(1+1/b)*ngrid**(-1/b),color=color,label=f'β={b:g} · theory')
        ax.scatter(NS,[np.array(model['stats']['own']['bias'])[2,i,BETAS.index(b),5] for i in range(5)],color=color,marker='o')
    ax.set_xlabel('n');ax.set_ylabel('MMLE location Bias');ax.legend(frameon=False);ax.grid(alpha=.15)
    groups['mechanism']=[option(save(fig,'v04_05_最小值定位偏移'),'理论与实测','MMLE位置估计取样本最小值。曲线为未筛选总体的理论Bias，点为各条件全部1200次的实测Bias；取β域两端作对照。')]
    fig,axs=plt.subplots(1,2,figsize=(13,4.2),layout='constrained')
    for p,ax in zip([3,4],axs):
        a=r[p];order=np.argsort(a,axis=-1);w=order[:,:,0];second=np.take_along_axis(a,order[:,:,1,None],axis=-1)[:,:,0]
        best=a.min(axis=-1);gap=(second/best-1)*100
        ax.imshow(w,cmap=ListedColormap(COLORS),vmin=-.5,vmax=6.5,alpha=.16,aspect='auto')
        for i,j in itertools.product(range(5),range(8)):
            gap_label=f'+{gap[i,j]:.2f}%' if gap[i,j]<.1 else f'+{gap[i,j]:.1f}%'
            ax.text(j,i,LABELS[w[i,j]]+'\n'+gap_label,ha='center',va='center',fontsize=8)
        axes_grid(ax);ax.set_title(TARGETS[p]+' RMSE')
    groups['life']=[option(save(fig,'v04_06_寿命目标及候选差距'),'候选区域：同时看第二名差多少','统一使用七法共同有效样本。格内为最低RMSE方法；下行百分数为第二低RMSE比最低值高多少。颜色只区分方法。B10对应可靠度0.90，B1对应0.99，微小差距按点估计呈现。')]
    fig,axs=plt.subplots(2,2,figsize=(12,7),layout='constrained')
    for row,i in enumerate([0,4]):
        c=cells[i,7]
        for col,p in enumerate([3,4]):
            true=quantile_true(5,1000,500,[.9,.99][col]);tol=np.linspace(0,.75,151);ax=axs[row,col]
            for m in range(7):
                e=abs(c['errors'][:,m,p])/true
                y=[np.sum(c['valid'][:,m]&(e<=v))/12 for v in tol]
                ax.plot(tol,y,color=COLORS[m],label=LABELS[m])
            ax.set_title(f'n={NS[i]} · '+TARGETS[p]);ax.set_xlabel('relative absolute-error tolerance');ax.set_ylabel('valid and within tolerance (%)');ax.set_ylim(0,100);ax.grid(alpha=.15)
    h,l=axs[0,0].get_legend_handles_labels();fig.legend(h,l,loc='outside lower center',ncol=7,frameon=False)
    groups['life'].append(option(save(fig,'v04_06B_全部尝试寿命精度'),'全部尝试：返回且满足精度的比例','β=5，分母固定为全部1200次。分子为返回有效且寿命相对绝对误差不超过横轴容限的次数；没有给失败填零误差。容限用于阅读比较，尚未指定工程验收阈值。'))
    return groups

def article(model):
    source=ARTICLE.read_text(encoding='utf-8')
    model['content_fingerprint']=hashlib.sha256(source.encode()).hexdigest()
    lines=source.splitlines();blocks=[];i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line:i+=1;continue
        block={'id':f'b{len(blocks)+1:03d}'}
        if line.startswith('<!-- figure:'):
            key=re.fullmatch(r'<!-- figure:(\w+) -->',line).group(1)
            block.update(kind='figure',key=key)
            i+=1
            while i<len(lines) and not lines[i].strip():i+=1
            assert lines[i].startswith('![');i+=1
            while i<len(lines) and not lines[i].strip():i+=1
            assert lines[i].startswith('图注：');i+=1
        elif line.startswith('#'):
            level=len(line)-len(line.lstrip('#'));block.update(kind='heading',level=level,text=line[level:].strip());i+=1
        elif line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                row=[v.strip() for v in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',v) for v in row):rows.append(row)
                i+=1
            block.update(kind='table',rows=rows)
        else:
            p=[line];i+=1
            while i<len(lines) and lines[i].strip() and not lines[i].startswith(('#','|','<!--')):
                p.append(lines[i].strip());i+=1
            text=' '.join(p);block.update(kind='quote' if text.startswith('> ') else 'paragraph',text=text.removeprefix('> '))
        blocks.append(block)
    return blocks

def inline(s):
    s=html.escape(str(s));s=re.sub(r'`([^`]+)`',r'<code>\1</code>',s)
    return re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',s)

def block_html(block,model):
    key=block['id'];kind=block['kind']
    if kind=='heading':
        level=block['level'];return f'<h{level} id="{key}" data-anchor="{key}">{inline(block["text"])}</h{level}>'
    if kind in ['paragraph','quote']:
        tag='blockquote' if kind=='quote' else 'p'
        return f'<{tag} data-anchor="{key}">{inline(block["text"])}</{tag}>'
    if kind=='table':
        rows=[]
        for i,row in enumerate(block['rows']):
            tag='th' if i==0 else 'td'
            rows.append('<tr>'+''.join(f'<{tag} data-anchor="{key}-{i}-{j}">{inline(v)}</{tag}>' for j,v in enumerate(row))+ '</tr>')
        return '<div class="table-wrap"><table>'+''.join(rows)+'</table></div>'
    group=block['key'];variants=model['figures'][group];panels=[];buttons=[]
    for i,v in enumerate(variants):
        letter=chr(65+i);path=HERE/'图'/v['file']
        src='data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()
        panels.append(f'<div class="variant-panel" data-panel="{letter}"'+(' hidden' if i else '')+'>'+f'<img src="{src}" alt="{html.escape(v["label"])}" class="data-image"><figcaption data-anchor="fig-{group}-{letter}">{inline(v["caption"])}</figcaption></div>')
        if len(variants)>1:buttons.append(f'<button type="button" role="tab" data-choice="{letter}" aria-selected="{str(i==0).lower()}">{letter}　{html.escape(v["label"])}</button>')
    switch='<div class="switch" role="tablist" aria-label="选择本处呈现方案">'+''.join(buttons)+'</div>' if buttons else ''
    return f'<figure data-group="{group}" id="{key}">'+''.join(panels)+switch+(f'<div class="choice-status">当前预览A，尚未确定采用。</div>' if buttons else '')+f'<button class="figure-note" data-figure-note="{group}">批注此图</button></figure>'

def markdown(model,feedback=None):
    feedback=feedback or {};choices=feedback.get('choices',{});notes=feedback.get('notes',[]);out=[]
    for b in model['blocks']:
        k=b['kind']
        if k=='heading':out.append('#'*b['level']+' '+b['text'])
        elif k in ['paragraph','quote']:out.append(('> ' if k=='quote' else '')+b['text'])
        elif k=='table':
            rows=b['rows'];out.extend(['| '+' | '.join(rows[0])+' |','| '+' | '.join(['---']*len(rows[0]))+' |']+['| '+' | '.join(row)+' |' for row in rows[1:]])
        else:
            group=b['key'];idx=ord(choices.get(group,'A'))-65;v=model['figures'][group][idx]
            out.extend([f'![{v["label"]}]({(HERE/"图"/v["file"]).as_posix()})','',v['caption']])
        for note in notes:
            anchors=note.get('anchors',[])
            if not anchors:continue
            last=anchors[-1]['block']
            match=last.startswith(b['id']) or (k=='figure' and last.startswith('fig-'+b['key']+'-'))
            if match:out.extend(['',f'> 批注对象：{note.get("quote","")}','',note['text']])
        out.append('')
    if feedback.get('overall'):out.extend(['## 全文意见','',feedback['overall'],''])
    return '\n'.join(out).rstrip()+'\n'

def validate_feedback(model,feedback):
    for k in ['version','source_fingerprint','content_fingerprint']:
        if feedback.get(k)!=model[k]:raise ValueError('反馈表单与当前稿件版本或数据不匹配：'+k)
    for key,value in feedback.get('choices',{}).items():
        if key not in model['figures'] or value not in [chr(65+i) for i in range(len(model['figures'][key]))]:raise ValueError('未知图表方案')

def import_feedback(model,feedback):
    validate_feedback(model,feedback)
    output=ARTICLE.with_name('报告下（方法对比）-v0.4-批注整理.md')
    output.write_text(markdown(model,feedback),encoding='utf-8')
    print('已生成含所选图表和定位批注的Markdown：'+str(output))

def build(model):
    rendered='\n'.join(block_html(b,model) for b in model['blocks'])
    nav=''.join(f'<a href="#{b["id"]}">{html.escape(b["text"])}</a>' for b in model['blocks'] if b['kind']=='heading' and b['level']==2)
    payload=json.loads(json.dumps({k:model[k] for k in ['version','source_fingerprint','content_fingerprint','created','blocks','figures']}))
    for group,variants in payload['figures'].items():
        for v in variants:v['absolute_path']=(HERE/'图'/v['file']).as_posix()
    data=json.dumps(payload,ensure_ascii=False,allow_nan=False).replace('</','<\\/')
    template=(HERE/'批注页模板.html').read_text(encoding='utf-8')
    (HERE/'候选分析与批注.html').write_text(template.replace('__ARTICLE__',rendered).replace('__NAV__',nav).replace('__MODEL__',data),encoding='utf-8')
    (HERE/'候选分析方案.md').write_text('# 历史HTML审稿尝试\n\n此前未采用的[报告下v0.4](../../其他/历史尝试/报告下（方法对比）-v0.4.md)与[旧HTML](候选分析与批注.html)保留回看。当前讨论见[表达预览](表达方式发散.md)。\n',encoding='utf-8')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--analyze',action='store_true')
    p.add_argument('--verify',action='store_true')
    p.add_argument('--render',action='store_true',help='仅将当前Markdown重新编译为HTML')
    p.add_argument('--feedback',type=Path)
    args=p.parse_args()
    if args.verify or args.feedback or args.render:
        model=json.loads(DATA.read_text(encoding='utf-8'))
        for rel,h in model['sources'].items():assert hashlib.sha256((STUDY/rel).read_bytes()).hexdigest()==h
        if args.render:
            model['blocks']=article(model)
            DATA.write_text(json.dumps(model,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
            build(model);print('Markdown已重新编译为HTML。')
        elif args.feedback:
            feedback=json.loads(args.feedback.read_text(encoding='utf-8-sig'))
            import_feedback(model,feedback)
        else:
            assert model['content_fingerprint']==hashlib.sha256(ARTICLE.read_text(encoding='utf-8').encode()).hexdigest()
            assert len(model['figures'])==6 and len(model['blocks'])==52
            for group in model['figures'].values():
                for figure in group:assert (HERE/'图'/figure['file']).is_file()
            print(json.dumps(dict(status='PASS',**model['checks']),ensure_ascii=False))
        return
    model,cells=load()
    DATA.write_text(json.dumps(model,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    if not args.analyze:
        configure();model['figures']=plots(model,cells);model['blocks']=article(model)
        DATA.write_text(json.dumps(model,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        build(model)
    print(json.dumps(dict(status='BUILT',**model['checks']),ensure_ascii=False))

if __name__=='__main__':main()
