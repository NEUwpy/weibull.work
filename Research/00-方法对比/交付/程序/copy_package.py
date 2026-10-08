"""Task029: copy the saved delivery plan without changing any source file."""
import argparse,hashlib,json,shutil
from pathlib import Path

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def save_plan(dest,plan):
    (dest/'程序/复制清单.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def prepare(plan,dest):
    root=Path(plan['source_root']).resolve();dest=dest.resolve()
    assert dest.is_relative_to(root) and dest!=root,'Destination must stay inside the designated R00 folder'
    assert not plan.get('over_50MB'),'>50MB requires the task-specified confirmation'
    targets=[r['target'] for r in plan['source_files']]
    assert len(set(targets))==len(targets)==657
    allowed=set(targets)|{'README.md','程序/copy_package.py','程序/复制清单.json'}
    if dest.exists():
        stored=dest/'程序/复制清单.json'
        assert stored.exists(),'Existing unrelated delivery directory: stop without overwriting'
        previous=json.loads(stored.read_text(encoding='utf-8'))
        assert previous['task_id']==plan['task_id'] and previous['source_files']==plan['source_files']
        unexpected=[p.relative_to(dest).as_posix() for p in dest.rglob('*') if p.is_file() and p.relative_to(dest).as_posix() not in allowed]
        assert not unexpected,unexpected
    for row in plan['source_files']:
        source=Path(row['source']).resolve();target=(dest/row['target']).resolve()
        assert source.is_relative_to(root) and not source.is_relative_to(dest)
        assert target.is_relative_to(dest) and source.stat().st_size==row['bytes']
        assert sha(source)==row['sha256'],f'Source changed: {source}'
    (dest/'程序').mkdir(parents=True,exist_ok=True);(dest/'结果').mkdir(exist_ok=True)
    save_plan(dest,plan)

def copy_group(plan,dest,name):
    rows=[r for r in plan['source_files'] if r['combination']==name]
    assert rows
    combo=next((c for c in plan['combinations'] if c['combination']==name),None)
    if combo:
        for directory in combo['program_directories']:
            target=(dest/'程序'/name/directory).resolve()
            assert target.is_relative_to(dest.resolve())
            target.mkdir(parents=True,exist_ok=True)
    for row in rows:
        source=Path(row['source']);target=dest/row['target']
        assert sha(source)==row['sha256'] and source.stat().st_mtime_ns==row['mtime_ns']
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            assert sha(target)==row['sha256'],f'Refuse to overwrite different bytes: {target}'
        else:shutil.copy2(source,target)
        assert sha(target)==sha(source)==row['sha256']
    return dict(combination=name,files=len(rows),bytes=sum(r['bytes'] for r in rows),SHA_match=True)

def readme(plan):
    text='# R00方法对比交付\n\n'
    text+='八个参数组合；n=7、15、30，每档50组。方法：MDM δ=0.10、0.15、0.20，LSE、LRE、MLE、WMLE、MMLE。\n\n'
    text+='| 组合 | 主表 | 结果目录 | 程序目录 | 源批次 |\n|---|---|---|---|---|\n'
    for combo in plan['combinations']:
        name=combo['combination'];date=Path(combo['source_batch']).name
        text+=f'| {name} | [{name}.xlsx](结果/{name}/{name}.xlsx) | [图像](结果/{name}/) | [程序](程序/{name}/) | {date} |\n'
    text+='\n每个结果目录共12个文件：上述主Excel与以下11张PNG。\n\n'
    text+='- `01_估计分布小提琴.png`\n- `02_有解率.png`（方法×n热力图）\n'
    for n in [7,15,30]:
        text+='- '+ '、'.join(f'`样本量{n}_偏移量{delta:.2f}.png`' for delta in [.1,.15,.2])+'\n'
    text+='\n跨参数文件直接放在结果根目录：\n\n'
    for filename in ['跨参数对比_有解率热图.png','R00_统计汇总.csv','R00_跨参数统计.csv']:
        text+=f'- [{filename}](结果/{filename})\n'
    text+='\n有解率按主Excel展示规则统计，含6条边界记录注记。\n\n'
    text+='程序目录完整复制各主批次的程序、依赖和复核材料；保留原路径与运行说明，未改写入口。复制来源、体积及逐文件SHA见[复制清单](程序/复制清单.json)，本次整理脚本为[copy_package.py](程序/copy_package.py)。\n'
    return text

def complete(plan,dest):
    matches=[]
    for row in plan['source_files']:
        source=Path(row['source']);target=dest/row['target']
        original=sha(source);copied=sha(target)
        assert original==copied==row['sha256'] and source.stat().st_mtime_ns==row['mtime_ns']
        matches.append(dict(target=row['target'],source_sha256=original,copy_sha256=copied))
    for combo in plan['combinations']:
        name=combo['combination'];result=dest/'结果'/name
        expected={Path(r['target']).name for r in plan['source_files'] if r['block']=='结果' and r['combination']==name}
        assert {p.name for p in result.iterdir()}==expected and len(expected)==12
        assert sum(p.suffix=='.xlsx' for p in result.iterdir())==1
        assert sum(p.suffix=='.png' for p in result.iterdir())==11
    output=dest/'结果'
    assert {p.name for p in output.iterdir()}=={c['combination'] for c in plan['combinations']}|{
        '跨参数对比_有解率热图.png','R00_统计汇总.csv','R00_跨参数统计.csv'}
    plan.update(copy_complete=True,copy_matches=matches,source_copy_files=len(matches))
    save_plan(dest,plan)
    (dest/'README.md').write_text(readme(plan),encoding='utf-8')
    script=Path(__file__).resolve();saved=dest/'程序/copy_package.py'
    if script!=saved.resolve():shutil.copy2(script,saved)
    print('PACKAGE_READY',len(matches),'source-copy SHA matches;',dest,flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,default=Path(__file__).resolve().parent/'复制清单.json')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();plan=json.loads(args.plan.read_text(encoding='utf-8'))
    dest=args.output or Path(plan['source_root'])/'交付'
    prepare(plan,dest)
    for combo in plan['combinations']:print(copy_group(plan,dest,combo['combination']),flush=True)
    print(copy_group(plan,dest,'cross'),flush=True);complete(plan,dest)

if __name__=='__main__':main()
