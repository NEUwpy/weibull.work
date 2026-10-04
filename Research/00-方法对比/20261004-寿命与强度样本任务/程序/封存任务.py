"""Seal or verify this task and its independently movable parameter folders."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
SKIP={'node_modules','__pycache__','检查预览'}
NAME='封存清单.json'


def entries(root):
    result={}
    for parent,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=sorted(d for d in dirs if d not in SKIP)
        for name in sorted(files):
            path=Path(parent)/name
            if path==ROOT/'程序'/NAME:
                continue
            result[path.relative_to(root).as_posix()]=dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    return result


def operate(manifest,current,verify,label):
    if verify:
        saved=json.loads(manifest.read_text(encoding='utf-8'))['files']
        if current!=saved:
            missing=sorted(set(saved)-set(current))
            added=sorted(set(current)-set(saved))
            changed=sorted(p for p in set(saved)&set(current) if saved[p]!=current[p])
            raise SystemExit(json.dumps(dict(folder=label,missing=missing,added=added,changed=changed),ensure_ascii=False))
    else:
        manifest.write_text(json.dumps(dict(folder=label,paths_relative_to='task root',file_count=len(current),bytes=sum(r['bytes'] for r in current.values()),files=current),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('VERIFIED' if verify else 'SEALED',label,len(current),'files',flush=True)


if __name__=='__main__':
    verify='--verify' in sys.argv
    for case in sorted((ROOT/'程序').glob('W(*)')):
        manifest=case/NAME
        key=manifest.relative_to(ROOT).as_posix()
        files={p:r for p,r in entries(ROOT).items() if p!=key and any(p.startswith(f'{part}/{case.name}/') for part in ('程序','结果'))}
        operate(manifest,files,verify,case.name)
    operate(ROOT/'程序'/NAME,entries(ROOT),verify,ROOT.name)
