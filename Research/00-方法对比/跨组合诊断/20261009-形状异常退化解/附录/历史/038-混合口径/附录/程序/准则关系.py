"""Read-only criterion profiles and sample-only warning; no formal estimator calls.

CLI: python -B 准则关系.py --sample-json sample.json --method MLE
sample.json must contain a JSON array of observations. LRE defaults to Park;
use --version Bernard for that historical method. Thresholds are diagnostics.
"""
from pathlib import Path
import sys, json, argparse
import numpy as np
from scipy.optimize import brentq
from scipy.special import logsumexp
ROOT=Path(r'D:\weibull')
sys.path.insert(0,str(ROOT/'python/methods'));sys.path.insert(0,str(ROOT/'python'))
from lse import log_weibull_order_stat_means

def cov(a,b):return float(np.mean((a-a.mean())*(b-b.mean())))
def mle_profile(x,g):
    t=np.log(x-g);mt=t.mean();z=t-mt;n=len(x)
    def score(b):
        w=np.exp(b*(z-z.max()));w/=w.sum();return 1/b-float(w@z)
    hi=2.
    while score(hi)>0:hi*=2.
    b=brentq(score,1e-8,hi,xtol=1e-11,rtol=2e-14)
    w=np.exp(b*(z-z.max()));w/=w.sum();wt=float(w@t);h=1/(x-g);wh=float(w@h)
    v=float(w@((t-wt)**2));cht=float(w@((t-wt)*(h-wh)))
    sb=-1/b**2-v;sg=wh-h.mean()+b*cht;bg=-sg/sb
    loge=mt+(logsumexp(b*z)-np.log(n))/b
    ge=b*wh-(b-1)*h.mean()
    gg=b*(1-b)*float(w@(h*h))+b*b*wh*wh-(b-1)*np.mean(h*h)-sg*sg/sb
    eg=-wh+(wt-loge)*bg/b
    lp=n*np.log(b)-n*mt-n*(logsumexp(b*z)-np.log(n))-n
    return dict(b=b,e=float(np.exp(loge)),g=float(g),ll=float(lp),grad=float(ge),curv=float(gg),beta_derivative=float(bg),logeta_derivative=float(eg),weighted_logvar=v,score_beta_derivative=sb)
def reference(n,method,version):
    if method=='LSE':return log_weibull_order_stat_means(n)
    ranks=np.arange(1,n+1,dtype=float)
    p=(ranks-.3)/(n+.4) if version=='Bernard' else ((ranks-3/8)/(n+1/4) if n<=10 else (ranks-.5)/n)
    return np.log(-np.log1p(-p))
def regression(x,g,method,version):
    t=np.log(x-g);h=1/(x-g);z=reference(len(x),method,version)
    c=cov(t,z);v=cov(t,t);vz=cov(z,z);cp=-cov(h,z);cpp=-cov(h*h,z);vp=-2*cov(t,h);vpp=2*cov(h,h)-2*cov(t,h*h)
    r2=c*c/(v*vz);k=2*cp/c-vp/v;kp=2*(cpp/c-(cp/c)**2)-(vpp/v-(vp/v)**2)
    if method=='LSE':b=vz/c;bg=-vz*cp/c**2
    else:b=c/v;bg=cp/v-c*vp/v**2
    loge=t.mean()-z.mean()/b;eg=-h.mean()+z.mean()*bg/b**2
    return dict(b=float(b),e=float(np.exp(loge)),g=float(g),loss=float(1-r2),grad=float(-r2*k),curv=float(-r2*(k*k+kp)),beta_derivative=float(bg),logeta_derivative=float(eg))
def warn_sample(values,method,version='Park Proposed+Plot',shape_threshold=10.,direction_tolerance=1e-10):
    x=np.sort(np.asarray(values,float))
    if method not in ['MLE','LSE','LRE']:raise ValueError('Only MLE/LSE/LRE criteria are covered')
    if x.size<3 or not np.all(np.isfinite(x)) or x.min()<=0 or x.std()==0:raise ValueError('Requires at least 3 positive, finite, nonconstant observations')
    q=mle_profile(x,0.) if method=='MLE' else regression(x,0.,method,version)
    # Positive B supports the method's lower-bound local optimum.
    bdir=(-1 if method=='MLE' else 1)*q['grad']*x.std()
    supports=bdir>direction_tolerance
    risk=bool(supports and q['b']>=shape_threshold)
    return dict(method=method,n=len(x),version=version if method=='LRE' else '',beta_at_zero=q['b'],signed_boundary_margin=float(bdir),warning_score=float(q['b'] if supports else 0.),high_risk=risk,potential_high_shape=bool(q['b']>=shape_threshold),shape_threshold=shape_threshold,direction_tolerance=direction_tolerance,message='存在高形状下界局部候选：高风险' if risk else ('有高形状潜势；边界条件不成立，需检查内部极值与求解过程' if q['b']>=shape_threshold else '未检出本类风险；不排除相对偏差或数值停点'))
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--sample-json',type=Path,required=True);ap.add_argument('--method',choices=['MLE','LSE','LRE'],required=True);ap.add_argument('--version',default='Park Proposed+Plot',choices=['Park Proposed+Plot','Bernard']);a=ap.parse_args()
    print(json.dumps(warn_sample(json.loads(a.sample_json.read_text(encoding='utf-8-sig')),a.method,a.version),ensure_ascii=False,indent=2))
