"""Train-selected structure relationships, checked on held-out observations."""
import json
import itertools
import numpy as np
from scipy.stats import rankdata
import b10_feature_selector as s


def within_cell_spearman(x,y,cells):
    correlations=[]
    for c in np.unique(cells):
        mask=cells==c
        a=rankdata(x[mask],axis=0)
        b=rankdata(y[mask],axis=0)
        a-=a.mean(axis=0);b-=b.mean(axis=0)
        denominator=np.sqrt(np.sum(a*a,axis=0)[:,None]*np.sum(b*b,axis=0)[None,:])
        correlations.append(np.divide(a.T@b,denominator,out=np.zeros_like(denominator),where=denominator>0))
    return np.mean(correlations,axis=0)


def main():
    data=s.load_data()
    common=data['valid'].all(axis=1)
    train=(data['split']==0)&common
    test=(data['split']==2)&common
    risks=s.training_rules(data,data['split']==0,s.subset(data,train))['fixed'][0]
    pair=np.argsort(risks)[:2]
    methods=[s.METHODS[i] for i in pair]
    target_names=['common_difficulty']+s.METHODS+[f'{methods[0]}_minus_{methods[1]}']
    def target(mask):
        loss=data['e'][mask]**2
        return np.column_stack([np.mean(loss/risks,axis=1),loss,loss[:,pair[0]]-loss[:,pair[1]]])
    train_corr=within_cell_spearman(data['x'][train],target(train),data['cell'][train])
    eligible=np.array([i for i,n in enumerate(s.FEATURES) if n!='log_n'])
    selected=eligible[np.argsort(np.abs(train_corr[eligible,-1]))[-3:][::-1]]
    difficult=eligible[np.argmax(np.abs(train_corr[eligible,0]))]
    s.json_write(s.OUT/'feature_discovery_selection.json',dict(pair=methods,
        pair_features=[s.FEATURES[i] for i in selected],difficulty_feature=s.FEATURES[difficult],
        selection_source='training only; average within beta*n Spearman',test_used_for_selection=False))
    test_corr=within_cell_spearman(data['x'][test],target(test),data['cell'][test])
    associations=[]
    for i,f in enumerate(s.FEATURES):
        for j,t in enumerate(target_names):
            associations.append(dict(feature=f,target=t,train_rho=float(train_corr[i,j]),test_rho=float(test_corr[i,j])))
    s.csv_write(s.OUT/'feature_risk_associations.csv',associations)
    distribution=[]
    for c in np.unique(data['cell']):
        mask=(data['cell']==c)&(data['split']==2)
        for i,f in enumerate(s.FEATURES):
            values=data['x'][mask,i]
            q=np.percentile(values,[25,50,75])
            distribution.append(dict(cell=c,beta=float(data['beta'][mask][0]),n=int(data['n'][mask][0]),
                feature=f,mean=float(values.mean()),sd=float(values.std(ddof=1)),
                p25=float(q[0]),median=float(q[1]),p75=float(q[2]),count=int(mask.sum())))
    s.csv_write(s.OUT/'feature_distributions_by_cell.csv',distribution)
    curves=[]
    for fi in selected:
        for c in np.unique(data['cell']):
            tm=train&(data['cell']==c)
            vm=test&(data['cell']==c)
            cuts=np.quantile(data['x'][tm,fi],[.25,.5,.75])
            bins=np.searchsorted(cuts,data['x'][vm,fi],side='right')
            errors=data['e'][vm][:,pair]
            for k in range(4):
                group=bins==k
                if not group.any():
                    continue
                mse=np.mean(errors[group]**2,axis=0)
                curves.append(dict(feature=s.FEATURES[fi],cell=c,bin=k+1,count=int(group.sum()),
                    method_a=methods[0],method_b=methods[1],mse_a=float(mse[0]),mse_b=float(mse[1]),
                    difference=float(mse[0]-mse[1])))
    s.csv_write(s.OUT/'feature_advantage_curves.csv',curves)
    summary=dict(pair=methods,pair_features=[dict(feature=s.FEATURES[i],train_rho=float(train_corr[i,-1]),
        test_rho=float(test_corr[i,-1])) for i in selected],
        difficulty_feature=dict(feature=s.FEATURES[difficult],train_rho=float(train_corr[difficult,0]),
            test_rho=float(test_corr[difficult,0])),
        statistic='Mean within-cell Spearman; association only, not causal effect',
        training_common_rows=int(train.sum()),test_common_rows=int(test.sum()))
    pairs=list(itertools.combinations(range(7),2))
    def pair_targets(mask):
        loss=data['e'][mask]**2
        return np.column_stack([loss[:,a]-loss[:,b] for a,b in pairs])
    pair_train=within_cell_spearman(data['x'][train],pair_targets(train),data['cell'][train])
    discovered=[]
    for j,(a,b) in enumerate(pairs):
        fi=int(eligible[np.argmax(np.abs(pair_train[eligible,j]))])
        discovered.append(dict(pair_index=j,feature_index=fi,feature=s.FEATURES[fi],
            method_a=s.METHODS[a],method_b=s.METHODS[b],train_rho=float(pair_train[fi,j])))
    discovered.sort(key=lambda r:abs(r['train_rho']),reverse=True)
    s.json_write(s.OUT/'all_pair_training_discovery.json',discovered)
    pair_test=within_cell_spearman(data['x'][test],pair_targets(test),data['cell'][test])
    for r in discovered:
        r['test_rho']=float(pair_test[r['feature_index'],r['pair_index']])
    # Fresh in-domain observations are never used to choose a pair or feature.
    from b10_fresh_validation import load_cohort,COHORTS
    fresh=load_cohort(COHORTS[0])
    good=fresh['valid'].all(axis=1)
    from scipy.stats import spearmanr
    for r in discovered:
        a=s.METHODS.index(r['method_a']);b=s.METHODS.index(r['method_b'])
        delta=fresh['e'][good,a]**2-fresh['e'][good,b]**2
        r['fresh_in_domain_rho']=float(spearmanr(fresh['x'][good,r['feature_index']],delta).statistic)
    s.csv_write(s.OUT/'all_pair_feature_relationships.csv',discovered)
    summary['all_pair_top3']=discovered[:3]
    selection=json.loads((s.OUT/'selection.json').read_text(encoding='utf-8'))
    risk_scope={}
    primary=s.subset(data,data['split']==2)
    forecasts=s.ensemble([s.OUT/p for p in selection['models']],primary['x'])
    scope_sets={'primary':(primary,forecasts)}
    for name in selection['holdouts']:
        mask=data['beta']==2.5 if name=='beta_2.5' else data['n']==int(name.split('_')[1])
        target=s.subset(data,mask)
        prediction=s.predict(__import__('torch').load(s.OUT/selection['holdout_models'][name],weights_only=True),target['x'])
        scope_sets[name]=(target,prediction)
    for name,(target,prediction) in scope_sets.items():
        records=[]
        for c in np.unique(target['cell']):
            for j,m in enumerate(s.METHODS):
                good=(target['cell']==c)&target['valid'][:,j]
                if not good.any():
                    continue
                pred_mean=float(prediction[good,j].mean());observed=float(np.mean(target['e'][good,j]**2))
                records.append(dict(cell=str(c),method=m,n=int(good.sum()),predicted_mse=pred_mean,
                    observed_mse=observed,ratio=pred_mean/observed))
        risk_scope[name]=records
    s.json_write(s.OUT/'risk_scope_diagnostics.json',risk_scope)
    extended_curves=[]
    for r in discovered[:3]:
        fi=r['feature_index'];a=s.METHODS.index(r['method_a']);b=s.METHODS.index(r['method_b'])
        for c in np.unique(data['cell']):
            tm=train&(data['cell']==c);vm=test&(data['cell']==c)
            cuts=np.quantile(data['x'][tm,fi],[.25,.5,.75])
            bins=np.searchsorted(cuts,data['x'][vm,fi],side='right')
            e=data['e'][vm][:,[a,b]]
            for k in range(4):
                if not np.any(bins==k):
                    continue
                risks=np.mean(e[bins==k]**2,axis=0)
                extended_curves.append(dict(feature=r['feature'],method_a=r['method_a'],method_b=r['method_b'],
                    cell=c,bin=k+1,count=int(np.sum(bins==k)),mse_a=float(risks[0]),mse_b=float(risks[1]),
                    difference=float(risks[0]-risks[1])))
    s.csv_write(s.OUT/'all_pair_top3_curves.csv',extended_curves)
    s.json_write(s.OUT/'feature_analysis.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
