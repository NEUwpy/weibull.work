"""Recompute in a new output directory; original results remain read-only."""
import argparse,hashlib,json,shutil
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import pandas as pd
HERE=Path(__file__).resolve().parent

def estimator_job(args):
    output,n,b,hashes=args
    import run_domains as program
    program.HERE=Path(output)
    return program.run_block((n,b,hashes))

def certificate_job(args):
    output,sha,n=args
    import certify_no_root as program
    program.HERE=Path(output)
    return program.certificate((sha,n))

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=6)
    p.add_argument('--smoke',action='store_true',help='Recompute one 100-sample block and its certificates; no full summary')
    args=p.parse_args();output=args.output.resolve()
    assert output!=HERE and not output.exists(),'Use a new output directory'
    # Verify the exact source/shared dependency versions saved for the original run.
    saved=json.loads((HERE/'运行核验.json').read_text(encoding='utf-8'))['source_sha256']
    for path,sha in saved.items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha,path
    if (HERE/'manifest.json').exists():
        manifest=json.loads((HERE/'manifest.json').read_text(encoding='utf-8'))
        for name,sha in manifest['shared_sources'].items():
            assert hashlib.sha256((HERE.parents[3]/name).read_bytes()).hexdigest()==sha,name
        for name,sha in manifest['outputs_sha256'].items():
            if '/' not in name and name.endswith(('.py','config.json')):
                assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==sha,name
    output.mkdir(parents=True)
    for source in [*HERE.glob('*.py'),HERE/'config.json',HERE/'原主目录保护.json']:
        shutil.copy2(source,output/source.name)
    import run_domains as program
    original=program.HERE;program.HERE=output;hashes=program.sources();program.HERE=original
    pairs=[(7,0)] if args.smoke else [(n,b) for n in program.CFG['n_values'] for b in range(program.CFG['blocks'])]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for f in as_completed([pool.submit(estimator_job,(str(output),n,b,hashes)) for n,b in pairs]):print(f.result(),flush=True)
    d=pd.concat([pd.read_csv(output/'blocks'/f'n{n:02d}_block{b:02d}/results.csv') for n,b in pairs],ignore_index=True)
    d.to_csv(output/'per_sample.csv.gz',index=False,compression='gzip')
    cases=[(str(output),r.sample_sha256,int(r.n)) for r in d[d.method_variant=='cw_engineering'].itertuples()
           if not json.loads(r.extra)['solution_info']['diagnostic']['candidates']]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        certificates=[f.result() for f in as_completed([pool.submit(certificate_job,c) for c in cases])]
    pd.DataFrame(certificates).to_csv(output/'无根证书索引.csv',index=False)
    if not args.smoke:
        import summarize_domains as summary
        summary.HERE=output;summary.main()
        import draw_domains as drawing
        drawing.HERE=output;drawing.main()
    else:
        original_rows=pd.read_csv(HERE/'per_sample.csv.gz');original_rows=original_rows[(original_rows.n==7)&(original_rows.block==0)]
        sort=['method_variant','repeat_id'];x=d.sort_values(sort);y=original_rows.sort_values(sort)
        assert x.status.tolist()==y.status.tolist()
        for name in ['beta_hat','eta_hat','gamma_hat']:
            import numpy as np
            assert np.allclose(x[name],y[name],rtol=1e-10,atol=1e-8,equal_nan=True)
        assert all(c['certified'] for c in certificates)
    (output/'复算检查.json').write_text(json.dumps(dict(output=str(output),rows=len(d),samples=d.sample_sha256.nunique(),
       certificates=len(certificates),smoke=args.smoke,all_passed=True),ensure_ascii=False,indent=2),encoding='utf-8')
    print('Reproduction passed:',output)
if __name__=='__main__':main()
