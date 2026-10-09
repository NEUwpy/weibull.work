"""Read stored samples; diagnose criteria without running formal estimators or writing sources.

Usage: python -B 机理全量验证.py [output_directory]
Default outputs: sibling ../机理验证; controls are deterministic, up to 30 per cell.
"""
from pathlib import Path
import sys, json, csv, math, hashlib, collections
import numpy as np
from scipy.optimize import brentq, minimize_scalar
from scipy.special import logsumexp
from scipy.stats import rankdata

ROOT=Path(r'D:\weibull'); REPORT=Path(__file__).resolve().parents[2]
OUT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else REPORT/'附录/机理验证'
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/'python/methods'))
sys.path.insert(0,str(ROOT/'python'))
from lse import log_weibull_order_stat_means
TOL_PARAM=2e-5; TOL_GRAD=2e-6; SIGN_TOL=1e-10
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source_hash={}
def read_json(p):
    source_hash[str(p)]=sha(p); return json.loads(p.read_text(encoding='utf8'))
def read_csv(p):
    source_hash[str(p)]=sha(p)
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(name,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rows)
def ok(r):return all(v is not None and math.isfinite(v) for v in [r['beta_hat'],r['eta_hat'],r['gamma_hat']]) and r['beta_hat']>0 and r['eta_hat']>0
def flagged(r):return ok(r) and (r['beta_hat']>=10 or r['beta_hat']>=5*r['beta_truth']) and (abs(r['gamma_hat'])<=1e-6*r['sample_min'] or r['eta_hat']>=5*r['eta_truth'])
samples={}; records=[]
inventory=ROOT/'Research/00-方法对比/跨组合汇总/程序/20261007-新增五组合/13组合取数.json'
for s in read_json(inventory)['sources']:
    p=Path(s['program']);mat=p/'中间数据/matrix.json' if p.name=='程序' else p.parent/'完整矩阵/数据/matrix.json'
    m=read_json(mat); truth=m['config']['truth']; version='Bernard' if s['protocol']=='historical-eight' else 'Park Proposed+Plot'
    for sm in m['samples']:samples[('R00',s['combination'],int(sm['n']),int(sm['id']))]=np.array(sm['values'],float)
    for r in m['results']:
        k=('R00',s['combination'],int(r['n']),int(r['id'])); meth=f"MDM δ={r['delta']:.2f}" if r['method_id']=='mdm' else r['method_id'].upper()
        records.append(dict(project=k[0],combination=k[1],n=k[2],group=k[3],method=meth,lre_version=version,beta_truth=truth[0],eta_truth=truth[1],gamma_truth=truth[2],beta_hat=r['beta_hat'],eta_hat=r['eta_hat'],gamma_hat=r['gamma_hat'],sample_min=float(samples[k][0]),success=bool(r['converged'])))
for p in sorted((ROOT/'Research/09-Weibull参数估计方法谱系与比较基线/实验').glob('W(*)')):
    truth=read_json(p/'程序/config.json')['truth']
    for sm in read_csv(p/'数据/样本.csv'):
        k=('R09',p.name,int(sm['n']),int(sm['组号']));samples[k]=np.array([float(sm[f'x({i})']) for i in range(1,k[2]+1)])
    for r in read_csv(p/'数据/估计明细.csv'):
        k=('R09',p.name,int(r['n']),int(r['组号']))
        b,e,g=[float(r[q]) if r[q] else None for q in ['β估计','η估计','γ估计']]
        records.append(dict(project=k[0],combination=k[1],n=k[2],group=k[3],method=r['方法'],lre_version='',beta_truth=truth[0],eta_truth=truth[1],gamma_truth=truth[2],beta_hat=b,eta_hat=e,gamma_hat=g,sample_min=float(samples[k][0]),success=r['状态']=='成功'))
assert len(samples)==49950 and len(records)==159600
for r in records:r['flag']=flagged(r)
flags=[r for r in records if r['flag']]
old=read_csv(REPORT/'附录/逐条标记记录.csv')
key=lambda r:(r['project'],r['combination'],int(r['n']),int(r['group']),r['method'])
assert len(flags)==1700 and {key(r) for r in flags}=={key(r) for r in old}
for r in flags:
    q=next(q for q in old if key(q)==key(r))
    assert all(math.isclose(r[k],float(q[k]),rel_tol=5e-15,abs_tol=1e-12) for k in ['beta_hat','eta_hat','gamma_hat'])
cells=collections.defaultdict(list)
for r in records:
    if r['method'] in ['MLE','LSE','LRE'] and r['success'] and ok(r) and not r['flag']:cells[(r['project'],r['combination'],r['n'],r['method'])].append(r)
controls=[]
for cell,rows in sorted(cells.items()):
    rows=sorted(rows,key=lambda r:r['group']);idx=np.unique(np.linspace(0,len(rows)-1,min(30,len(rows))).round().astype(int))
    controls.extend(rows[i] for i in idx)
selected=flags+controls

from 准则关系 import cov, mle_profile, regression, warn_sample

diag=[];fail=[];checks=[];compensation=[]
cache={}
for i,r in enumerate(selected):
    sk=key(r)[:4];x=samples[sk];sd=float(x.std());g=r['gamma_hat'];meth=r['method'];ver=r['lre_version']
    fun=(lambda a:mle_profile(x,a)) if meth=='MLE' else (lambda a:regression(x,a,meth,ver))
    q=fun(g);z0=fun(0.);qt=fun(r['gamma_truth'])
    pres=max(abs(math.log(r['beta_hat']/q['b'])),abs(math.log(r['eta_hat']/q['e'])))
    grad=q['grad']*sd;curv=q['curv']*sd**2
    param_ok=pres<=TOL_PARAM;zero=(g==0.)
    if meth=='MLE':
        direction=(grad<-SIGN_TOL) if zero else (abs(grad)<=TOL_GRAD and curv<-SIGN_TOL)
        a0=(z0['b']>=1 and z0['grad']*sd<-SIGN_TOL)
    else:
        direction=(grad>SIGN_TOL) if zero else (abs(grad)<=TOL_GRAD and curv>SIGN_TOL)
        a0=(z0['grad']*sd>SIGN_TOL)
    local=bool(param_ok and direction and (meth!='MLE' or q['b']>=1))
    label=('boundary_local' if zero else 'interior_local') if local else 'not_confirmed'
    reason=[]
    if not param_ok:reason.append('conditional_parameter_mismatch')
    if not direction:reason.append('direction_or_curvature_not_met')
    d=dict(r,location_kind='exact_zero' if zero else 'positive_interior',local_class=label,local_conditions_pass=local,A0_pass=bool(a0),conditional_parameter_log_error=pres,normalized_gradient=grad,normalized_curvature=curv,conditional_beta=q['b'],conditional_eta=q['e'],beta_at_zero=z0['b'],zero_normalized_gradient=z0['grad']*sd,cv_zero=sd/x.mean(),cv_candidate=sd/(x.mean()-g),cv_true=sd/(x.mean()-r['gamma_truth']),log_sd_candidate=float(np.log(x-g).std()),eta_gamma_truth_ratio=r['eta_truth']/r['gamma_truth'],min_gap_over_eta=(x[0]-r['gamma_truth'])/r['eta_truth'],position_left_over_eta=(r['gamma_truth']-g)/r['eta_truth'],beta_ratio=r['beta_hat']/r['beta_truth'],eta_ratio=r['eta_hat']/r['eta_truth'],conditional_beta_derivative=q['beta_derivative'],conditional_logeta_derivative=q['logeta_derivative'],beta_zero_over_true_location=z0['b']/qt['b'],eta_zero_over_true_location=z0['e']/qt['e'],reason=';'.join(reason))
    warning=warn_sample(x,meth,ver)
    d.update(warning_score=warning['warning_score'],warning_high_risk=warning['high_risk'],warning_margin=warning['signed_boundary_margin'],potential_high_shape=warning['potential_high_shape'])
    diag.append(d)
    if r['flag'] and not local:fail.append(d)
    # Direct derivative cross-check; no change to stored estimates.
    if i<12 or (r['flag'] and not zero and len(checks)<45):
        h=min(sd*1e-4,(x[0]-g)*1e-4);a=fun(g+h);c=fun(g-h)
        num=(a['grad']-c['grad'])/(2*h)*sd**2
        checks.append(dict(project=r['project'],combination=r['combination'],n=r['n'],group=r['group'],method=meth,analytic_curvature=curv,finite_difference_curvature=num,relative_error=abs(curv-num)/max(abs(curv),1e-12)))
    if i%500==0:print('diagnosed',i,'/',len(selected),flush=True)

write('全部标记与分层对照.csv',diag)
write('未通过局部条件的标记.csv',fail if fail else [dict(note='none')])
write('解析导数交叉检查.csv',checks)
freq=read_csv(REPORT/'附录/全条件筛查计数.csv')
freq=[dict(r,beta_truth=float(r['combination'][2:-1].split(',')[0]),eta_gamma_ratio=float(r['combination'][2:-1].split(',')[1])/float(r['combination'][2:-1].split(',')[2]),rate=int(r['flagged'])/int(r['total'])) for r in freq if r['method'] in ['MLE','LSE','LRE']]
write('标记频率与参数条件.csv',freq)
metrics=[]
for project,meth in sorted({(d['project'],d['method']) for d in diag}):
    rs=[d for d in diag if (d['project'],d['method'])==(project,meth)];f=[d for d in rs if d['flag']];u=[d for d in rs if not d['flag']]
    for field,negative in [('cv_zero',True),('cv_candidate',True),('min_gap_over_eta',False)]:
        a=np.array([r[field] for r in f]);b=np.array([r[field] for r in u]);v=np.r_[-a,-b] if negative else np.r_[a,b];ranks=rankdata(v);auc=(ranks[:len(a)].sum()-len(a)*(len(a)+1)/2)/(len(a)*len(b))
        numerator=denom=0.
        for cell in sorted({(r['combination'],r['n']) for r in rs}):
            aa=np.array([r[field] for r in f if (r['combination'],r['n'])==cell]);bb=np.array([r[field] for r in u if (r['combination'],r['n'])==cell])
            if not len(aa) or not len(bb):continue
            vv=np.r_[-aa,-bb] if negative else np.r_[aa,bb];rr=rankdata(vv);numerator+=rr[:len(aa)].sum()-len(aa)*(len(aa)+1)/2;denom+=len(aa)*len(bb)
        # Fixed, disclosed illustrative threshold: raw or shifted CV <= .1.
        hit=sum(r[field]<=.1 for r in f)/len(f) if field.startswith('cv_') else None
        fp=sum(r[field]<=.1 for r in u)/len(u) if field.startswith('cv_') else None
        metrics.append(dict(project=project,method=meth,indicator=field,flagged=len(f),controls=len(u),flagged_median=float(np.median(a)),control_median=float(np.median(b)),pooled_auc=float(auc),within_cell_auc=float(numerator/denom),low_cv_threshold=.1 if field.startswith('cv_') else None,flag_hit_rate=hit,control_positive_rate=fp))
write('代理指标分离度.csv',metrics)
counts=[]
for project,meth in sorted({(d['project'],d['method']) for d in diag}):
    for flagged_value in [True,False]:
        rr=[d for d in diag if d['project']==project and d['method']==meth and d['flag']==flagged_value]
        counts.append(dict(project=project,method=meth,flagged=flagged_value,total=len(rr),exact_zero=sum(d['location_kind']=='exact_zero' for d in rr),boundary_local=sum(d['local_class']=='boundary_local' for d in rr),interior_local=sum(d['local_class']=='interior_local' for d in rr),not_confirmed=sum(d['local_class']=='not_confirmed' for d in rr),A0_pass=sum(d['A0_pass'] for d in rr),beta_left_monotonic=sum(d['conditional_beta_derivative']<0 for d in rr),eta_left_monotonic=sum(d['conditional_logeta_derivative']<0 for d in rr)))
write('准则复核汇总.csv',counts)
warning_counts=[]
for project,meth in sorted({(d['project'],d['method']) for d in diag}):
    rs=[d for d in diag if d['project']==project and d['method']==meth];f=[d for d in rs if d['flag']];u=[d for d in rs if not d['flag']]
    warning_counts.append(dict(project=project,method=meth,flagged=len(f),hit=sum(d['warning_high_risk'] for d in f),miss=sum(not d['warning_high_risk'] for d in f),hit_rate=sum(d['warning_high_risk'] for d in f)/len(f),controls=len(u),false_positive=sum(d['warning_high_risk'] for d in u),false_positive_rate=sum(d['warning_high_risk'] for d in u)/len(u)))
write('样本预警性能.csv',warning_counts)
write('预警漏报标记.csv',[d for d in diag if d['flag'] and not d['warning_high_risk']])
exceptions=[]
for d in fail:
    x=samples[key(d)[:4]];sd=float(x.std());g=d['gamma_hat'];meth=d['method'];ver=d['lre_version']
    def objective(a):
        q=mle_profile(x,a) if meth=='MLE' else regression(x,a,meth,ver)
        if meth=='MLE' and q['b']<1:
            e=float(np.mean(x-a));q.update(b=1.,e=e,ll=-len(x)*math.log(e)-len(x))
        return q
    q=objective(g)
    if meth=='MLE':
        direction=np.sign(d['normalized_gradient']);step=min(sd*.05,(x.min()-g)*.01)
        nearby=float(max(0,min(x.min()*(1-1e-8),g+direction*step)))
    else:nearby=0. if d['normalized_gradient']>0 else min(g+.01*sd,x.min()*(1-1e-8))
    nq=objective(nearby);gain=(nq['ll']-q['ll']) if meth=='MLE' else (q['loss']-nq['loss'])
    grid=np.unique(np.r_[0.,g,np.linspace(0,x.min()*.99,121),x.min()-x.min()*np.geomspace(1e-9,.01,30)])
    qs=[objective(a) for a in grid];ys=np.array([-a['ll'] if meth=='MLE' else a['loss'] for a in qs]);candidates=[qs[int(ys.argmin())]]
    for j in range(1,len(grid)-1):
        if ys[j]<=ys[j-1] and ys[j]<=ys[j+1]:
            opt=minimize_scalar(lambda a:-objective(a)['ll'] if meth=='MLE' else objective(a)['loss'],bounds=(grid[j-1],grid[j+1]),method='bounded',options={'xatol':1e-9})
            candidates.append(objective(opt.x))
    best=min(candidates,key=lambda a:-a['ll'] if meth=='MLE' else a['loss'])
    bestgain=best['ll']-q['ll'] if meth=='MLE' else q['loss']-best['loss']
    if meth=='MLE':
        z=np.log(x-g)-math.log(d['eta_hat']);b=d['beta_hat'];original_ll=len(x)*math.log(b)-len(x)*math.log(d['eta_hat'])+(b-1)*z.sum()-np.exp(b*z).sum()
        storedgain=float(nq['ll']-original_ll);storedbestgain=float(best['ll']-original_ll)
    else:storedgain=gain;storedbestgain=bestgain
    exceptions.append(dict(project=d['project'],combination=d['combination'],n=d['n'],group=d['group'],method=meth,original_gamma=g,original_beta=d['beta_hat'],nearby_gamma=nearby,nearby_gain=gain,nearby_gain_vs_stored=storedgain,scan_best_gamma=best['g'],scan_best_beta=best['b'],scan_best_eta=best['e'],scan_gain=bestgain,scan_gain_vs_stored=storedbestgain,interpretation='可行方向改善：存档点不是准则局部极值' if storedgain>1e-9 else ('与下界候选在1e-9诊断容差内等价；不称严格内部极值' if d['A0_pass'] and g>0 and g<=1e-6*x.min() else '方向不满足；数值改善未超诊断阈值')))
write('例外方向与局部复核.csv',exceptions)
warning_sensitivity=[]
for cut in [8.,10.,12.]:
    f=[d for d in diag if d['flag']];u=[d for d in diag if not d['flag']]
    warning_sensitivity.append(dict(shape_threshold=cut,flagged=len(f),hits=sum(d['warning_score']>=cut for d in f),hit_rate=sum(d['warning_score']>=cut for d in f)/len(f),controls=len(u),false_positives=sum(d['warning_score']>=cut for d in u),false_positive_rate=sum(d['warning_score']>=cut for d in u)/len(u)))
write('预警阈值敏感性.csv',warning_sensitivity)
summary=dict(flagged=len(flags),controls=len(controls),diagnosed=len(diag),strata=len(cells),control_selection='最多30条/来源×组合×n×方法；在有解未标记的排序组号中等距取索引，无新抽样',tolerances=dict(parameter_log=TOL_PARAM,normalized_gradient=TOL_GRAD,strict_sign=SIGN_TOL),counts=counts,metrics=metrics,warning_counts=warning_counts,all_flagged_original_success=all(r['success'] for r in flags),mle_shape_derivative_negative=all(d['conditional_beta_derivative']<0 for d in diag if d['method']=='MLE'),mle_scale_derivative_negative=all(d['conditional_logeta_derivative']<0 for d in diag if d['method']=='MLE'),source_sha256=source_hash,program_sha256=sha(Path(__file__)))
summary['exceptions']=dict(total=len(exceptions),clear_local_improvement=sum(e['nearby_gain_vs_stored']>1e-9 for e in exceptions),near_boundary_equivalent=sum(e['interpretation'].startswith('与下界') for e in exceptions),other=sum(e['interpretation'].startswith('方向不满足') for e in exceptions))
summary['warning_sensitivity']=warning_sensitivity
summary['potential_warning']=dict(hits=sum(d['potential_high_shape'] for d in diag if d['flag']),flagged=1700,false_positives=sum(d['potential_high_shape'] for d in diag if not d['flag']),controls=len(controls))
summary['criteria_program_sha256']=sha(Path(__file__).with_name('准则关系.py'))
for p,h in source_hash.items():assert sha(Path(p))==h,p
(OUT/'汇总.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
print(json.dumps({k:summary[k] for k in ['flagged','controls','diagnosed','strata','exceptions','potential_warning']},ensure_ascii=False,indent=2),flush=True)
