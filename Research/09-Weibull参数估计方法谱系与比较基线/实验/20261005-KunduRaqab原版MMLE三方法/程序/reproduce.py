"""Recompute the saved original KR method in a fresh directory, with frozen code."""
import argparse,datetime,shutil,subprocess,sys
from pathlib import Path
import pandas as pd
HERE=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workers',type=int,default=6);p.add_argument('--output',type=Path)
    args=p.parse_args();target=args.output or HERE/'复算'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    target=target.resolve();assert not target.exists(),'Choose a fresh output directory; no existing result is overwritten.'
    program=target/'程序';program.mkdir(parents=True);(target/'结果').mkdir()
    shutil.copytree(HERE/'source_snapshot',program/'source_snapshot')
    for name in ['config.json','输入样本.npz']:
        shutil.copy2(HERE/name,program/name)
    for name in ['compute.py','summarize.py','draw.py']:
        text=(HERE/name).read_text(encoding='utf-8')
        text=text.replace('REPO=BATCH.parents[3]',"REPO=HERE/'source_snapshot'")
        text=text.replace("PREVIOUS=BATCH.parent/'20261005-MMLEI参数域与求解复核'","PREVIOUS=HERE/'reuse'")
        (program/name).write_text(text,encoding='utf-8')
    reuse=program/'reuse/三方法原文口径';reuse.mkdir(parents=True)
    data=pd.read_csv(HERE/'per_sample.csv.gz');data[data.method_variant.isin(['MLE','WMLE'])].to_csv(reuse/'per_sample.csv.gz',index=False,compression='gzip')
    subprocess.run([sys.executable,str(program/'compute.py'),'--workers',str(args.workers)],check=True)
    subprocess.run([sys.executable,str(program/'summarize.py')],check=True)
    subprocess.run([sys.executable,str(program/'draw.py')],check=True)
    print('Recomputed KR and four PNG/CSV using frozen source. MLE/WMLE reused. Output:',target)
    print('For XLSX, run the saved workbook.mjs against the new summary JSON with the bundled Node runtime.')
if __name__=='__main__':main()
