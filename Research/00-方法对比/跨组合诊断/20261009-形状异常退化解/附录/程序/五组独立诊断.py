import sys
if len(sys.argv)!=2:raise SystemExit('需提供独立输出目录；仅复算保存的三组R00样本。')
from pathlib import Path
import sys,json,csv,math,collections
import numpy as np
from scipy.optimize import brentq,minimize,minimize_scalar
from scipy.special import logsumexp
from scipy import stats
O=Path(sys.argv[1]);O.mkdir(parents=True,exist_ok=True)
inputs=json.loads((Path(__file__).resolve().parent.parent/'五组输入.json').read_text(encoding='utf8'))
samples=inputs['samples'];records=inputs['records']
def log_weibull_order_stat_means(n):
 assert n==15
 return np.array(inputs['lse_reference_n15'])

def plain(v):
 if isinstance(v,dict):return {k:plain(x) for k,x in v.items()}
 if isinstance(v,(list,tuple,np.ndarray)):return [plain(x) for x in v]
 if isinstance(v,(np.floating,float)):return float(v) if np.isfinite(v) else None
 if isinstance(v,np.integer):return int(v)
 if isinstance(v,np.bool_):return bool(v)
 return v
def ll(x,b,e,g):
 if b<=0 or e<=0 or g>=x.min():return -np.inf
 z=np.log(x-g)-np.log(e);return float(len(x)*np.log(b)-len(x)*np.log(e)+(b-1)*z.sum()-np.exp(b*z).sum())
def scores(x,b,e,g):
 y=x-g;z=np.log(y/e);w=np.exp(b*z)
 return np.array([len(x)/b+z.sum()-np.dot(w,z),b/e*(w.sum()-len(x)),-(b-1)*np.sum(1/y)+b*np.sum(w/y)])
def profile(x,g,bmin=1.0):
 logs=np.log(x-g);center=logs.mean();d=logs-center;n=len(x)
 def score(b):
  w=np.exp(b*(d-d.max()));w/=w.sum();return 1/b-np.dot(w,d)
 if score(bmin)<=0:b=bmin
 else:
  hi=2.0
  while score(hi)>0:hi*=2
  b=brentq(score,bmin,hi,xtol=1e-11,rtol=1e-13)
 loge=center+(logsumexp(b*d)-np.log(n))/b;e=np.exp(loge)
 # Algebraically centered profile prevents catastrophic cancellation for large beta.
 lp=n*np.log(b)-n*center-n*(logsumexp(b*d)-np.log(n))-n
 return np.array([b,e,g]),float(lp)
def regression(x,g,kind):
 y=np.log(x-g);n=len(x)
 if kind=='LSE':
  z=log_weibull_order_stat_means(n);slope=np.dot(z-z.mean(),y-y.mean())/np.dot(z-z.mean(),z-z.mean());b=1/slope;e=np.exp(y.mean()-slope*z.mean())
 else:
  p=(np.arange(1,n+1)-.5)/n if n>=11 else (np.arange(1,n+1)-3/8)/(n+1/4);z=np.log(-np.log1p(-p));b=np.dot(z-z.mean(),y-y.mean())/np.dot(y-y.mean(),y-y.mean());e=np.exp(y.mean()-z.mean()/b)
 rho=float(np.corrcoef(y,z)[0,1]);return np.array([b,e,g]),1-rho*rho
cases=[('R00','W(2,100,500)',15,36),('R00','W(2,100,500)',15,27),('R00','W(5,100,500)',15,36)]
summary=[];curves=[];fixedcurves=[];origcompare=[];optimizations=[];direction=[]
for project,comb,n,sid in cases:
 key=f'{project}|{comb}|{n}|{sid}';x=np.array(samples[key]);truth=np.array([float(v) for v in comb[2:-1].split(',')]);smin=x.min();rr=[r for r in records if (r['project'],r['combination'],int(r['n']),int(r['group']))==(project,comb,n,sid)]
 mle=next(r for r in rr if r['method']=='MLE');stored=np.array([float(mle[p+'_hat']) for p in ['beta','eta','gamma']]);storedll=ll(x,*stored)
 # Dense independent gamma profiles, including the exact lower bound and near-x1 points.
 gs=np.unique(np.r_[np.linspace(0,smin*.999,1501),smin-smin*np.geomspace(1e-12,1e-3,200)])
 profiles=[profile(x,g) for g in gs];ls=np.array([p[1] for p in profiles]);peaks=[i for i in range(1,len(gs)-1) if ls[i]>=ls[i-1] and ls[i]>=ls[i+1]]
 cand=[profiles[0],profiles[-1],profiles[int(np.argmax(ls))]]
 for i in peaks:
  opt=minimize_scalar(lambda g:-profile(x,g)[1],bounds=(gs[i-1],gs[i+1]),method='bounded',options={'xatol':1e-9});cand.append(profile(x,opt.x))
 best,bestll=max(cand,key=lambda p:p[1]);score=scores(x,*best)
 # From-scratch 2D bounded optimization of beta and gamma, eta profiled analytically.
 def twoobj(t):
  b=np.exp(t[0]);g=smin*t[1];logs=np.log(x-g);d=logs-logs.mean();return -(n*np.log(b)-n*logs.mean()-n*(logsumexp(b*d)-np.log(n))-n)
 for b0,u0 in [(1.1,0),(2,.25),(5,.5),(20,0),(50,.8),(100,.95)]:
  opt=minimize(twoobj,[np.log(b0),u0],method='L-BFGS-B',bounds=[(0,np.log(1e4)),(0,1-1e-10)],options={'ftol':1e-14,'gtol':1e-9,'maxiter':3000})
  b=np.exp(opt.x[0]);g=opt.x[1]*smin;logeta=logsumexp(b*np.log(x-g))/b-np.log(n)/b
  optimizations.append(dict(case=key,start_beta=b0,start_location=u0*smin,beta=b,eta=np.exp(logeta),gamma=g,ll=-opt.fun,success=bool(opt.success),message=str(opt.message)))
 regbest={}
 if project=='R00':
  for kind in ['LSE','LRE']:
   losses=np.array([regression(x,g,kind)[1] for g in gs]);rc=[regression(x,gs[0],kind),regression(x,gs[-1],kind),regression(x,gs[int(losses.argmin())],kind)]
   for i in range(1,len(gs)-1):
    if losses[i]<=losses[i-1] and losses[i]<=losses[i+1]:
     opt=minimize_scalar(lambda g:regression(x,g,kind)[1],bounds=(gs[i-1],gs[i+1]),method='bounded',options={'xatol':1e-9});rc.append(regression(x,opt.x,kind))
   p,loss=min(rc,key=lambda r:r[1]);orig=next(r for r in rr if r['method']==kind);q=np.array([float(orig[a+'_hat']) for a in ['beta','eta','gamma']]);original_loss=regression(x,q[2],kind)[1]
   h=.001;grad=(regression(x,p[2]+h,kind)[1]-regression(x,max(0,p[2]-h),kind)[1])/(h if p[2]==0 else 2*h)
   regbest[kind]=dict(stored=q,independent=p,loss=loss,stored_loss=original_loss,loss_improvement=original_loss-loss,location_derivative=grad)
   origcompare.append(dict(case=key,method=kind,beta=q[0],eta=q[1],gamma=q[2],likelihood=ll(x,*q),own_loss=original_loss,independent_beta=p[0],independent_eta=p[1],independent_gamma=p[2],own_loss_best=loss))
 for r in rr:
  if r['excel_success']=='True':
   p=np.array([float(r[a+'_hat']) for a in ['beta','eta','gamma']]);origcompare.append(dict(case=key,method=r['method'],beta=p[0],eta=p[1],gamma=p[2],likelihood=ll(x,*p),own_loss=None,independent_beta=None,independent_eta=None,independent_gamma=None,own_loss_best=None))
 # Expanded negative-location domain; quantitative link to Gumbel minimum limit.
 neg=-np.r_[truth[1]*np.geomspace(.01,1e6,120)];negp=[profile(x,g) for g in neg]
 mu,sigma=stats.gumbel_l.fit(x);gv=(x-mu)/sigma;gll=float(stats.gumbel_l.logpdf(x,loc=mu,scale=sigma).sum());delta=float(np.sum((np.exp(gv)-1)*gv*gv/2-gv))
 selected=[0.0,float(truth[2]),float(smin*(1-1e-6))]
 for g in selected:
  p,l=profile(x,g);direction.append(dict(case=key,branch='beta_ge_1',gamma=g,beta=p[0],eta=p[1],ll=l))
 for rel in [1e-2,1e-4,1e-6,1e-8,1e-10,1e-12]:
  g=smin-smin*rel;p,l=profile(x,g,bmin=.00001);direction.append(dict(case=key,branch='all_beta_profile',gamma=g,beta=p[0],eta=p[1],ll=l))
  direction.append(dict(case=key,branch='fixed_beta_0.5',gamma=g,beta=.5,eta=truth[1],ll=ll(x,.5,truth[1],g)))
 for g,p in zip(neg,negp):direction.append(dict(case=key,branch='negative_location',gamma=g,beta=p[0][0],eta=p[0][1],ll=p[1]))
 for b in [stored[0]*.5,stored[0],stored[0]*2,stored[0]*5,stored[0]*10]:
  e=np.exp((logsumexp(b*np.log(x))-np.log(n))/b);fixedcurves.append(dict(case=key,beta=b,eta=e,gamma=0,ll=ll(x,b,e,0)))
 for g,p in zip(gs,profiles):curves.append(dict(case=key,gamma=g,beta=p[0][0],eta=p[0][1],ll=p[1],lse_loss=regression(x,g,'LSE')[1] if project=='R00' else None,lre_loss=regression(x,g,'LRE')[1] if project=='R00' else None))
 summary.append(dict(case=key,truth=truth,stored=stored,stored_ll=storedll,independent=best,independent_ll=bestll,improvement=bestll-storedll,score=score,sample_min=smin,sample_max=x.max(),sample_mean=x.mean(),sample_sd=x.std(),sample_cv=x.std()/x.mean(),shifted_cv=x.std()/(x.mean()-truth[2]),minimum_minus_true_location=smin-truth[2],regression=regbest,gumbel=dict(mu=mu,sigma=sigma,ll=gll,first_order_weibull_minus_embedded=delta),negative_best=max(negp,key=lambda p:p[1]),grid_points=len(gs),interior_peaks=len(peaks)))
 print(key,'stored',stored,'independent',best,'delta_ll',bestll-storedll,'score',score,'gumbel',gll,'delta',delta,flush=True)
 for k,v in regbest.items():print(' ',k,plain(v),flush=True)
def write(name,rows):
 with (O/name).open('w',encoding='utf8',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(plain(rows))
for name,rows in [('profiles.csv',curves),('fixed_gamma_shape.csv',fixedcurves),('original_likelihoods.csv',origcompare),('independent_optimizations.csv',optimizations),('boundary_directions.csv',direction)]:write(name,rows)
(O/'diagnostics.json').write_text(json.dumps(plain(summary),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
