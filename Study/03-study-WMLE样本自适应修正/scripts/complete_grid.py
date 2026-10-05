"""Complete all historical n=30 cells and missing controlled-grid cells via shared pipeline."""
from pathlib import Path
import sys, json, subprocess
import pandas as pd
STUDY=Path(__file__).resolve().parents[1]; ROOT=STUDY.parents[1]
sys.path[:0]=[str(ROOT/'python'),str(STUDY/'scripts')]
from run_wmle_on_existing_cases import CASES
from studies.common.experiment import run_experiment

def main():
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    jobs=[]
    for c in CASES:
        if 30 not in c['sizes']:
            jobs.append((c['case_id'],[(c['beta'],c['eta'],c['gamma'])],[30],50,c['seed_namespace']))
    jobs.append(('controlled_missing',[(3.,1000.,500.),(3.,1000.,3000.),(5.,1000.,500.),(5.,1000.,3000.)],[7,15,30],100,20260922))
    for name,grid,ns,repeats,seed in jobs:
        dest=STUDY/'results/supplement_v1'/name
        if (dest/'results.csv').exists():
            d=pd.read_csv(dest/'results.csv'); assert len(d)==len(grid)*len(ns)*repeats
            print('Retained',name,len(d),flush=True);continue
        print('Running',name,flush=True)
        run_experiment(['wmle'],grid,ns,repeats,str(dest),seed_namespace=seed,code_version=head,run_label='Study03 initial baseline supplement '+name)
        print('Completed',name,flush=True)

if __name__=='__main__':main()
