"""Reuse E09's diagnostic solver on all remaining WMLE failures.

Relaxed-location solutions are evidence about the constraint, never substitute
estimates. Sources and the unchanged primary protocol remain in manifest.json.
"""
from concurrent.futures import ProcessPoolExecutor
import json
import pandas as pd

from run import HERE, CONFIG
from audit_wmle import inspect_row


def main():
    data=pd.read_csv(HERE/'per_sample.csv.gz')
    rejected=data[data.method_variant.eq('wmle_checked') & data.status.ne('success')]
    rows=[]
    with ProcessPoolExecutor(max_workers=2) as pool:
        for count, row in enumerate(pool.map(inspect_row,rejected.to_dict('records')),1):
            rows.append(row)
            if count%50==0:print({'boundary_probes':count,'total':len(rejected)},flush=True)
    out=pd.DataFrame(rows)
    out['positive_root_found']=(out.positive_retry_objective<=1e-8) & out.positive_retry_shape.lt(9.99)
    out['negative_root_found']=(out.relaxed_objective<=1e-8) & out.relaxed_shape.lt(9.99) & out.relaxed_location.lt(0)
    out.to_csv(HERE/'wmle_boundary_audit.csv',index=False)
    result={'rejected':len(out),'bounded_candidate_near_zero':int(out.bounded_location.abs().lt(.01).sum()),
        'positive_root_found':int(out.positive_root_found.sum()),
        'negative_root_found':int(out.negative_root_found.sum()),
        'neither_root_found':int((~out.positive_root_found & ~out.negative_root_found).sum()),
        'diagnostic_only':True,'location_relaxed_not_part_of_primary_estimator':True}
    (HERE/'wmle_boundary_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    # Partition the benefit of CW's paper domain into observed location/shape changes.
    main_cw=data[data.method_variant.eq('cw_i_nonnegative')]
    paper=data[data.method_variant.eq('cw_i_paper_domain')]
    keys=['cell_id','repeat_id','n']
    merged=main_cw[keys+['status']].merge(paper[keys+['status','beta_hat','gamma_hat']],
                                       on=keys,suffixes=('_main','_paper'),validate='one_to_one')
    extra=merged[merged.status_main.ne('success') & merged.status_paper.eq('success')].copy()
    extra['negative_location']=extra.gamma_hat.lt(0)
    extra['shape_above_main_bound']=extra.beta_hat.ge(9.99)
    extra.groupby(['n','negative_location','shape_above_main_bound']).size().rename('count').reset_index().to_csv(
        HERE/'cw_domain_effects.csv',index=False)
    print(result,flush=True)


if __name__=='__main__':main()
