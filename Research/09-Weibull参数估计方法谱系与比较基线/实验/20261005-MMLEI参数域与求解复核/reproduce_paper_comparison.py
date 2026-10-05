"""Recompute the supplemented main comparison in a new directory."""
import argparse,hashlib,json,shutil
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ORIGINAL=HERE/'三方法原文口径'
def job(args):
    output,n,b,hashes=args
    import run_paper_comparison as program
    program.DEST=Path(output)
    return program.block((n,b,hashes))
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=6);p.add_argument('--smoke',action='store_true');args=p.parse_args()
    output=args.output.resolve();assert not output.exists() and output!=HERE
    source=json.loads((ORIGINAL/'运行核验.json').read_text(encoding='utf-8'))['source_sha256']
    for path,sha in source.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha,path
    output.mkdir(parents=True);shutil.copy2(ORIGINAL/'config.json',output/'config.json')
    import run_paper_comparison as program
    program.DEST=output;hashes=program.sources();program.DEST=ORIGINAL
    pairs=[(7,0)] if args.smoke else [(n,b) for n in program.CFG['n_values'] for b in range(12)]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for future in as_completed([pool.submit(job,(str(output),n,b,hashes)) for n,b in pairs]):print(future.result(),flush=True)
    d=pd.concat([pd.read_csv(output/'blocks'/f'n{n:02d}_block{b:02d}/results.csv') for n,b in pairs],ignore_index=True)
    d.to_csv(output/'per_sample.csv.gz',index=False,compression='gzip')
    if args.smoke:
        old=pd.read_csv(ORIGINAL/'per_sample.csv.gz');old=old[(old.n==7)&(old.block==0)]
        keys=['method_variant','repeat_id'];x=d.sort_values(keys);y=old.sort_values(keys)
        assert x.status.tolist()==y.status.tolist() and x.sample_sha256.tolist()==y.sample_sha256.tolist()
        for field in ['beta_hat','eta_hat','gamma_hat']:assert np.allclose(x[field],y[field],rtol=1e-10,atol=1e-8,equal_nan=True)
    else:
        import summarize_paper_comparison as summary
        summary.DEST=output;summary.main()
        import draw_paper_comparison as drawing
        drawing.DEST=output;drawing.main()
    (output/'复算检查.json').write_text(json.dumps(dict(rows=len(d),samples=d.sample_sha256.nunique(),smoke=args.smoke,all_passed=True),ensure_ascii=False,indent=2),encoding='utf-8')
    print('Reproduction passed:',output)
if __name__=='__main__':main()
