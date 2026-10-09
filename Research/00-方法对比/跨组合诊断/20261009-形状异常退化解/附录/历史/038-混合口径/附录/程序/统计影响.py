if __name__ == '__main__' and len(__import__('sys').argv) != 2:
 raise SystemExit('需提供独立输出目录；不会修改源实验。')
import sys
from pathlib import Path
import csv,json,collections,math
import numpy as np
O=Path(sys.argv[1]); O.mkdir(parents=True, exist_ok=True)
with (O/'all_records.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
groups=collections.defaultdict(list)
for r in rows:
 for k in ['n','group']:r[k]=int(r[k])
 for k in ['beta_truth','eta_truth','gamma_truth','beta_hat','eta_hat','gamma_hat','sample_min']:r[k]=float(r[k]) if r[k] else None
 for k in ['flag','converged','excel_success']:r[k]=r[k]=='True'
 groups[r['project'],r['combination'],r['n'],r['method']].append(r)
def write(name,data):
 with (O/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
metrics=[]
for key,rr in sorted(groups.items()):
 ok=[r for r in rr if r['excel_success']];keep=[r for r in ok if not r['flag']];flag=[r for r in ok if r['flag']]
 for p in ['beta','eta','gamma']:
  a=np.array([r[p+'_hat']-r[p+'_truth'] for r in ok]);k=np.array([r[p+'_hat']-r[p+'_truth'] for r in keep]);d=np.array([r[p+'_hat']-r[p+'_truth'] for r in flag])
  metrics.append(dict(zip(['project','combination','n','method'],key),parameter=p,total=len(rr),success=len(ok),flagged_success=len(flag),raw_rate=len(ok)/len(rr),sensitivity_valid_rate=len(keep)/len(rr),bias=float(a.mean()),sd=float(a.std()),rmse=float(np.sqrt(np.mean(a*a))),sensitivity_bias=float(k.mean()) if len(k) else None,sensitivity_sd=float(k.std()) if len(k) else None,sensitivity_rmse=float(np.sqrt(np.mean(k*k))) if len(k) else None,flagged_share_squared_error=float(np.sum(d*d)/np.sum(a*a)) if np.sum(a*a)>0 else 0))
write('sensitivity_metrics.csv',metrics)
mi={(m['project'],m['combination'],m['n'],m['method'],m['parameter']):m for m in metrics};comp=[]
for key in sorted(groups):
 if key[0]=='R00' and key[2]==15:
  for p in ['beta','eta','gamma']:
   a=mi[*key,p];b=mi[key[0],key[1],30,key[3],p]
   comp.append(dict(combination=key[1],method=key[3],parameter=p,n15_success=a['success'],n30_success=b['success'],n15_flagged=a['flagged_success'],n30_flagged=b['flagged_success'],n15_rmse=a['rmse'],n30_rmse=b['rmse'],raw_n30_worse=b['rmse']>a['rmse'],sensitivity_n15_rmse=a['sensitivity_rmse'],sensitivity_n30_rmse=b['sensitivity_rmse'],sensitivity_n30_worse=b['sensitivity_rmse']>a['sensitivity_rmse']))
write('n30_vs_n15.csv',comp)
locator=[]
for project,comb,n,g in [('R00','W(2,100,500)',15,36),('R00','W(2,100,500)',15,27),('R09','W(2,100,500)',15,25),('R09','W(2,100,500)',15,100),('R09','W(2,100,500)',15,702),('R09','W(2,100,500)',15,494),('R09','W(2,100,500)',15,525)]:locator.extend(r for r in rows if (r['project'],r['combination'],r['n'],r['group'])==(project,comb,n,g))
write('location_verified.csv',locator)
maxima=[]
for key,rr in sorted(groups.items()):
 if key[2]==15:
  ok=[r for r in rr if r['excel_success']];v=max(ok,key=lambda r:r['beta_hat']);maxima.append(dict(zip(['project','combination','n','method'],key),max_shape=v['beta_hat'],group=v['group'],eta=v['eta_hat'],gamma=v['gamma_hat']))
write('n15_shape_maxima.csv',maxima)
summary=dict(flagged_by_project_method={str(k):sum(r['flag'] for r in rr) for k,rr in collections.defaultdict(list).items()})
c=collections.Counter((r['project'],r['method']) for r in rows if r['flag']);print('FLAGS',c)
for project in ['R00','R09']:
 for n in [15,30] if project=='R00' else [15,50]:
  for meth in ['LSE','LRE','MLE']:
   a=[m for m in metrics if m['project']==project and m['combination']=='W(2,100,500)' and m['n']==n and m['method']==meth and m['parameter']=='beta']
   if a:print(a[0])
betac=[m for m in comp if m['parameter']=='beta' and m['method'] in ['LSE','LRE','MLE']];print('N30 worse beta',sum(m['raw_n30_worse'] for m in betac),'/',len(betac),'removed',sum(m['raw_n30_worse'] and not m['sensitivity_n30_worse'] for m in betac))
