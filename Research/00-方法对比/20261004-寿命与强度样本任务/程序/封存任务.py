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
            if path==root/NAME:
                continue
            result[path.relative_to(root).as_posix()]=dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    return result


def operate(root,verify):
    current=entries(root)
    manifest=root/NAME
    if verify:
        saved=json.loads(manifest.read_text(encoding='utf-8'))['files']
        if current!=saved:
            missing=sorted(set(saved)-set(current))
            added=sorted(set(current)-set(saved))
            changed=sorted(p for p in set(saved)&set(current) if saved[p]!=current[p])
            raise SystemExit(json.dumps(dict(folder=root.name,missing=missing,added=added,changed=changed),ensure_ascii=False))
    else:
        manifest.write_text(json.dumps(dict(folder=root.name,file_count=len(current),bytes=sum(r['bytes'] for r in current.values()),files=current),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('VERIFIED' if verify else 'SEALED',root.name,len(current),'files',flush=True)


if __name__=='__main__':
    verify='--verify' in sys.argv
    for case in sorted(ROOT.glob('W(*)')):
        operate(case,verify)
    operate(ROOT,verify)
