"""Reproducible descriptive counts of the explicitly reviewed comparison corpus.

This is a purposive 12-paper content-analysis sample, not all library records,
not a database search export, and not a prevalence estimate for the field.
Only explicitly confirmed indicators are coded; blank is not evidence of absence.
"""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LIB=Path('D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计')
# id, year label, observation stratum, main question, confirmed metric objects.
ROWS=[
 ('182-101','2009','3P_complete','broad_comparison',['parameter_bias','parameter_rmse','parameter_sd','joint_parameter_error']),
 ('182-096','2014','3P_complete','broad_comparison',['parameter_bias','parameter_rmse']),
 ('182-025','2024','3P_complete','shape_estimation_comparison',['parameter_bias','parameter_rmse']),
 ('182-030','2022_online_2023_issue','3P_complete','discrepancy_construction',['parameter_relative_error']),
 ('185-005','2023','3P_complete','small_sample_location_update',['parameter_mad','parameter_sd','life_error','runtime']),
 ('182-003','2025','3P_contamination','contamination_robustness',['parameter_rmse','joint_parameter_error']),
 ('184-009','2025','3P_complete','learning_estimation',['parameter_rmse','parameter_sd','life_error']),
 ('182-050','2025','3P_complete','small_sample_location_update',['parameter_bias','parameter_rmse','joint_parameter_error']),
 ('182-103','2026','3P_censored','censoring',['parameter_bias','parameter_rmse']),
 ('187-001','2025_doi_2026_issue','3P_complete','numerical_optimization',['parameter_bias','likelihood','runtime']),
 ('183-012','2025_online_2026_issue','2P_wind','learning_estimation',['distribution_rmse','distribution_mae','distribution_r2','ks']),
 ('182-111','2025','3P_complete','modified_likelihood_bias_reduction',['parameter_relative_bias','parameter_rmse','interval_coverage'])]
# Restricted to seven papers whose focal method and comparator list were extracted.
# Frequency retains paper labels, avoiding false equality of all regression/LS versions.
COMPARATORS={
 '182-025':['LS','MDM'], '182-030':['MLE','probability_plot_LS'],
 '185-005':['MLE','CCWP','PWM'], '182-003':['MLE','WMLE','MPS','MOM'],
 '184-009':['CCM','MDM'],'182-103':['MLE','conventional_LS'],
 '182-111':['MMLE','CMLE']}


def main():
    appendix=(ROOT/'附录A-文献证据.md').read_text(encoding='utf-8')
    papers=[]
    for pid,year,stratum,focus,metrics in ROWS:
        path=next(p for p in LIB.rglob(pid+'-pdf原文.md') if '历史' not in str(p))
        text=path.read_text(encoding='utf-8')
        # Appendix DOI entries have been identity-checked; DMMLE uses local header.
        lines=[line for line in appendix.splitlines() if line.startswith('| '+pid+' |') and 'https://doi.org/' in line]
        if lines:doi=re.search(r'https://doi.org/([^\s)]+)',lines[0]).group(1)
        else:
            candidates=re.findall(r'10\.3390/\s*e\d+',text[:12000],re.I)
            if not candidates:raise ValueError('Missing verified DOI for '+pid)
            doi=re.sub(r'\s+','',candidates[0])
        papers.append({'id':pid,'doi':doi.lower(),'year_label':year,'stratum':stratum,'main_question':focus,
                       'confirmed_metric_objects':metrics,'confirmed_comparators':COMPARATORS.get(pid),
                       'evidence_anchor':'Appendix A A1.2 or A4.1; partial relevant full-text extraction',
                       'source':str(path),'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    assert len({r['doi'] for r in papers})==len(papers)
    recent=[r for r in papers if r['id'] not in ['182-101','182-096']]
    out={'scope':'purposive reviewed comparison/method corpus only; not systematic literature prevalence',
         'deduplication':'12 distinct verified DOI identities; no claim to deduplicate all 203 library numbers',
         'excluded_from_this_denominator':['two reviews','WMLE original construction source','Park illustrative paper','Nagatsuka method-only extraction','Nassar model-only extraction','Cheng-Amin foundational paper'],
         'papers':papers,
         'counts':{'papers':len(papers),'observation_strata':dict(Counter(r['stratum'] for r in papers)),
                   'confirmed_metric_objects':dict(Counter(m for r in papers for m in r['confirmed_metric_objects'])),
                   'recent_papers_2022_to_2026':len(recent),
                   'recent_main_questions':dict(Counter(r['main_question'] for r in recent)),
                   'comparator_coding_denominator':len(COMPARATORS),
                   'confirmed_comparator_labels':dict(Counter(m for ms in COMPARATORS.values() for m in ms))},
         'limits':['No field-wide trend, annual growth rate or citation authority estimate',
                   'Recent subset includes 2026 update papers, not the ten-complete-year window',
                   'Counts are paper-level, multiple metrics allowed; absence from codes means not extracted',
                   'Shared authors and teams are not independent adoption events',
                   'No pooling of numerical effects or winner counts']}
    (ROOT/'evidence/coded_literature_summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out['counts'],ensure_ascii=True,indent=2))


if __name__=='__main__':main()
