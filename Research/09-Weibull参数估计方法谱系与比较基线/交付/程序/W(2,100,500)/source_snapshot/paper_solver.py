"""Cohen-Whitten MLE and Cousineau WMLE equations in the paper location window."""
import sys
from pathlib import Path
import numpy as np
from scipy.optimize import brentq,minimize_scalar
from scipy.special import logsumexp
REPO=Path(__file__).resolve().parent
sys.path.insert(0,str(REPO/'python'))
from methods.wmle import get_weight_j1,get_weight_j2,get_weight_j3

def solve(raw,method,shape_lower=None,step=.025):
    x=np.sort(np.asarray(raw,float))/1000;n=len(x);xmin=x[0];delta=x-xmin
    low_gamma=float(x.mean()-10*x.std(ddof=1));lo=np.log(1e-7);hi=np.log(xmin-low_gamma)
    j1=get_weight_j1(n) if method=='WMLE' else 1.;j2=get_weight_j2(n) if method=='WMLE' else 1.
    shape_lower=(1.01 if method=='MLE' else .1) if shape_lower is None else shape_lower
    cache={}
    def profile(t):
        t=float(t)
        if t in cache:return cache[t]
        d=np.exp(t);logs=np.log1p(delta/d);s=logs[-1];u=logs/s
        def shape_score(k):
            w=np.exp(k*(u-1));return k*(w@u/w.sum()-u.mean())-j2
        right=float(2*n)
        while shape_score(right)<0:right*=2
        k=brentq(shape_score,1e-10,right,xtol=1e-12,rtol=1e-12);b=k/s
        w=np.exp(k*(u-1));w/=w.sum();q=np.exp(-logs);meanq=q.mean()
        r=float(b*(w@(q-meanq))+meanq) if method=='MLE' else float(meanq/(w@q)-get_weight_j3(n,b))
        cache[t]=(b,r,d,logs,w);return cache[t]
    grid=np.linspace(lo,hi,int(np.ceil((hi-lo)/step))+1)
    ds=np.exp(grid);logs=np.log1p(delta[None,:]/ds[:,None]);ss=logs[:,-1];us=logs/ss[:,None]
    means=us.mean(axis=1);left=np.zeros(len(grid));right=np.full(len(grid),float(2*n));ks=(left+right)/2
    def vector_score(ks):
        ws=np.exp(ks[:,None]*(us-1));ws/=ws.sum(axis=1)[:,None];mu=(ws*us).sum(axis=1)
        a=mu-means;variance=(ws*(us-mu[:,None])**2).sum(axis=1)
        return ks*a-j2,a+ks*variance,ws
    while True:
        score,_,_=vector_score(right);bad=score<0
        if not bad.any():break
        right[bad]*=2
    ks=(left+right)/2
    for _ in range(80):
        scores,derivative,ws=vector_score(ks)
        if np.max(np.abs(scores))<2e-12:break
        left=np.where(scores<0,ks,left);right=np.where(scores>=0,ks,right)
        proposed=ks-scores/derivative;ks=np.where((proposed>left)&(proposed<right),proposed,(left+right)/2)
    bs=ks/ss;qs=np.exp(-logs);mq=qs.mean(axis=1);ewq=(ws*qs).sum(axis=1)
    residuals=bs*(ws*(qs-mq[:,None])).sum(axis=1)+mq if method=='MLE' else mq/ewq-np.array([get_weight_j3(n,float(b)) for b in bs])
    for i,t in enumerate(grid):cache[float(t)]=(float(bs[i]),float(residuals[i]),float(ds[i]),logs[i],ws[i])
    # Add every interpolation knot of the saved WMLE weight table to the root brackets.
    if method=='WMLE':
        knots=[]
        for b in np.arange(.1,5.01,.1):
            hit=np.where((bs[:-1]-b)*(bs[1:]-b)<0)[0]
            for i in hit:knots.append(brentq(lambda t:profile(t)[0]-b,grid[i],grid[i+1],xtol=1e-12))
        grid=np.unique(np.r_[grid,knots]);residuals=np.array([profile(t)[1] for t in grid])
    roots=[]
    for i in range(len(grid)-1):
        if residuals[i]*residuals[i+1]<0:roots.append(brentq(lambda t:profile(t)[1],grid[i],grid[i+1],xtol=1e-12,rtol=1e-12))
        if abs(residuals[i])<1e-12:roots.append(float(grid[i]))
    extrema=0
    for i in range(1,len(grid)-1):
        if max(abs(residuals[i]-residuals[i-1]),abs(residuals[i]-residuals[i+1]))<=1e-9:continue
        minimum=residuals[i]<=residuals[i-1] and residuals[i]<=residuals[i+1]
        maximum=residuals[i]>=residuals[i-1] and residuals[i]>=residuals[i+1]
        if not (minimum or maximum):continue
        sign=1 if minimum else -1
        result=minimize_scalar(lambda t:sign*profile(t)[1],bounds=(grid[i-1],grid[i+1]),method='bounded',options={'xatol':1e-11})
        t=float(result.x);r=profile(t)[1];extrema+=1
        for edge in [grid[i-1],grid[i+1]]:
            if profile(edge)[1]*r<0:roots.append(brentq(lambda z:profile(z)[1],min(t,edge),max(t,edge),xtol=1e-12))
        if abs(r)<1e-10:roots.append(t)
    distinct=[]
    for t in sorted(roots):
        if not distinct or abs(t-distinct[-1])>1e-7:distinct.append(t)
    candidates=[]
    for t in distinct:
        b,r,d,logs,w=profile(t);g=xmin-d
        logeta=np.log(d)+(logsumexp(b*logs)-np.log(n)-np.log(j1))/b;eta=np.exp(logeta)
        z=x-g;ll=float(n*np.log(b)-n*b*logeta+(b-1)*np.log(z).sum()-np.sum((z/eta)**b))
        shape_res=float(j2/b+logs.mean()-w@logs)
        local_max=profile(t-1e-5)[1]<0 and profile(t+1e-5)[1]>0 if method=='MLE' else True
        objective=shape_res**2+r**2
        candidates.append(dict(beta=b,eta=eta*1000,gamma=g*1000,log_gap=t,log_likelihood=ll,
                               objective=objective,local_maximum=bool(local_max),in_shape_domain=bool(shape_lower<b<15),
                               low_shape_author_excluded=bool(.1<b<=1.01)))
    valid=[c for c in candidates if c['in_shape_domain'] and c['local_maximum'] and c['objective']<=1e-8]
    if method=='MLE':selected=max(valid,key=lambda c:c['log_likelihood']) if valid else None
    else:
        def proximity(c):return np.log(c['beta']/2)**2+((c['gamma']/1000-.9*xmin)/max(xmin,1.))**2
        selected=min(valid,key=proximity) if valid else None
    status='ok' if selected else 'root_outside_author_shape_domain' if candidates else 'no_stationary_root_in_paper_location_domain'
    if not selected and any(c['in_shape_domain'] and not c['local_maximum'] for c in candidates):status='no_likelihood_maximum_root'
    return dict(status=status,estimate=selected,candidates=candidates,shape_bounds=[shape_lower,15],
                location_lower=low_gamma*1000,location_upper=(xmin-1e-7)*1000,log_gap_step=step,
                grid_points=len(grid),extrema_checks=extrema,weights=dict(J1=j1,J2=j2),
                selection='highest likelihood among finite stationary maxima' if method=='MLE' else 'root nearest original (beta=2,gamma=.9*xmin) heuristic',
                no_boundary_or_nonzero_residual_substitution=True)
