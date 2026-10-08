"""Append five frozen batches to the existing package; preserve the eight old batches."""
import argparse,hashlib,json,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
R00=Path(__file__).resolve().parents[3]
PACKAGE=R00/'交付'
COMBOS=['W(1.5,100,500)','W(1.5,1000,500)','W(2,100,500)','W(3,100,500)','W(5,100,500)']
CROSS_SOURCE=R00/'跨组合汇总/程序/20261007-新增五组合'
CROSS_FILES=['13组合取数.json','跨参数核验.json','绘图核验.json','绘制跨参数对比.py','README.md','并入交付.py']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy_exact(source,target):
    if target.exists():
        assert target.is_file() and sha(target)==sha(source),f'Conflicting destination: {target}'
        return
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)
    assert sha(source)==sha(target)

def neutralize_readme(text):
    lines=text.splitlines()
    rows=[line for line in lines if line.startswith('| W')]
    positions=[i for i,line in enumerate(lines) if line.startswith('| W')]
    assert len(rows)==13
    rows.sort(key=lambda line:tuple(float(v) for v in line.split('|')[1].strip()[1:].split(',')))
    for i,line in zip(positions,rows):lines[i]=line.replace('20261007-暂存样本补齐','20261004')
    text='\n'.join(lines)+'\n'
    text=text.replace('| 源批次 |','| 样本批次 |')
    paragraphs=text.split('\n\n')
    note='抽样说明：η=100的四组与W1.5,1000,500使用种子20261004，同一n与组号跨β、η共用潜在指数变量，与其余八组不共用。各格按组合独立统计，不合并不同抽样协议；方法版本见对应程序说明。'
    paragraphs=[note if p.startswith('新增五组合复用20261004') else p for p in paragraphs]
    paragraphs=['程序目录保存对应脚本、冻结依赖、完整数据和核对材料；运行方式见各组合README。来源与逐文件SHA见[复制清单](程序/复制清单.json)，整理程序见[并入交付.py](程序/跨参数对比/并入交付.py)。' if p.startswith('程序目录保存对应脚本') else p for p in paragraphs]
    return '\n\n'.join(paragraphs)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--backup-dir',type=Path,required=True)
    args=parser.parse_args();args.backup_dir.mkdir(parents=True,exist_ok=True)
    assert PACKAGE.is_dir() and R00.name=='00-方法对比'
    # The only existing package files changed by this operation.
    for rel in ['README.md','程序/复制清单.json','结果/跨参数对比_有解率热图.png']:
        source=PACKAGE/rel;backup=args.backup_dir/rel
        if not backup.exists():backup.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,backup)
    mp=PACKAGE/'程序/复制清单.json';manifest=json.loads(mp.read_text(encoding='utf-8'))
    files=manifest['source_files'];matches=manifest['copy_matches'];added=[]
    def register(source,target,combo,block):
        rel=target.relative_to(PACKAGE).as_posix()
        if any(r['target']==rel for r in files):return
        stat=source.stat();digest=sha(source)
        files.append(dict(combination=combo,block=block,source=str(source),target=rel,
          bytes=stat.st_size,mtime_ns=stat.st_mtime_ns,sha256=digest,added_in_task='032'))
        matches.append(dict(target=rel,source_sha256=digest,copy_sha256=sha(target)))
        added.append(rel)
    for combo in COMBOS:
        batch=R00/combo/'20261007-暂存样本补齐';short=combo.replace('(','').replace(')','')
        seal=json.loads((batch/'程序/manifest_032.json').read_text(encoding='utf-8'))
        expected=seal['program_files']|{'manifest_032.json':sha(batch/'程序/manifest_032.json')}
        actual={p.relative_to(batch/'程序').as_posix():p for p in (batch/'程序').rglob('*') if p.is_file()}
        assert set(actual)==set(expected) and all(sha(actual[k])==v for k,v in expected.items())
        outputs={p.name:p for p in (batch/'结果').iterdir()};assert len(outputs)==12
        assert set(outputs)=={r['name'] for r in seal['outputs']}
        assert all(sha(outputs[r['name']])==r['sha256'] for r in seal['outputs'])
        for block in ['程序','结果']:
            for source in sorted((batch/block).rglob('*')):
                assert not source.is_symlink(),f'Unexpected link: {source}'
                if source.is_file():
                    target=PACKAGE/block/short/source.relative_to(batch/block)
                    copy_exact(source,target);register(source,target,short,block)
        if not any(r['combination']==short for r in manifest['combinations']):
            program=list((batch/'程序').rglob('*'));program=[p for p in program if p.is_file()]
            result=list((batch/'结果').iterdir());biggest=max(program,key=lambda p:p.stat().st_size)
            manifest['combinations'].append(dict(combination=short,source_batch=str(batch),
              program_files=len(program),program_bytes=sum(p.stat().st_size for p in program),
              program_directories=sorted(p.relative_to(batch/'程序').as_posix() for p in (batch/'程序').rglob('*') if p.is_dir()),
              result_files=len(result),result_bytes=sum(p.stat().st_size for p in result),
              largest_program_file=str(biggest),largest_program_file_bytes=biggest.stat().st_size,
              added_in_task='032',sampling_protocol='shared-latent-seed-20261004'))
        print('COPIED',short,len(actual),'program files; 1 xlsx + 11 PNG')
    for name in CROSS_FILES:
        source=CROSS_SOURCE/name;target=PACKAGE/'程序/跨参数对比'/name
        copy_exact(source,target);register(source,target,'cross13','程序')
    source=CROSS_SOURCE/'跨参数对比_有解率热图.png';target=PACKAGE/'结果'/source.name
    old=next(r for r in files if r['target']==target.relative_to(PACKAGE).as_posix())
    if 'before_032_source' not in old:
        old['before_032_source']=old['source'];old['before_032_sha256']=old['sha256']
    shutil.copy2(source,target);assert sha(source)==sha(target)
    old.update(source=str(source),sha256=sha(source),bytes=source.stat().st_size,mtime_ns=source.stat().st_mtime_ns,updated_in_task='032')
    next(r for r in matches if r['target']==old['target']).update(source_sha256=sha(source),copy_sha256=sha(target))
    # Retain the initial copy history, including the two CSV files removed in task 030.
    for row in files:
        row['currently_present']=(PACKAGE/row['target']).is_file()
    manifest['add_five_combinations_032']=dict(task_id='research00-add-stash-5combos-032',goal_version='g1',
      artifact_version='five-combos-v2',combination_count=13,added_combinations=COMBOS,
      reused_estimates=3750,new_estimates=2250,mmle=750,mdm_delta_010=750,mdm_delta_015=750,
      original_eight_untouched=True,new_samples=0,pooled_rates=False,
      csv_delivery_rule='Statistical summary CSV files remain internal; none in result folders.',
      recorded_source_rows=len(files),current_source_copies=sum(r['currently_present'] for r in files),
      operation_script='程序/跨参数对比/并入交付.py')
    mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    readme=PACKAGE/'README.md';text=readme.read_text(encoding='utf-8')
    text=text.replace('八个参数组合；','十三个参数组合；')
    if '| W1.5,100,500 |' not in text:
        marker='\n\n每份主Excel';pos=text.index(marker)
        rows=[]
        for combo in COMBOS:
            short=combo.replace('(','').replace(')','')
            rows.append(f'| {short} | [{short}.xlsx](结果/{short}/{short}.xlsx) | [图像](结果/{short}/) | [程序](程序/{short}/) | 20261007-暂存样本补齐 |')
        text=text[:pos]+'\n'+'\n'.join(rows)+text[pos:]
    protocol='抽样说明：η=100的四组与W1.5,1000,500使用种子20261004，同一n与组号跨β、η共用潜在指数变量，与其余八组不共用。各格按组合独立统计，不合并不同抽样协议；方法版本见对应程序说明。\n\n'
    if protocol not in text:text=text.replace('每份主Excel含',protocol+'每份主Excel含')
    text=text.replace('有解率按主Excel展示规则统计，含6条边界记录注记。','有解率沿用主Excel展示规则；完整状态及边界检查保存在程序目录。')
    oldline='程序目录完整复制各主批次的程序、依赖和复核材料；保留原路径与运行说明，工作表名称及相关配置已同步。复制来源、体积及逐文件SHA见[复制清单](程序/复制清单.json)，本次整理脚本为[copy_package.py](程序/copy_package.py)。'
    newline='程序目录保存对应脚本、冻结依赖、完整数据和核对材料。新增五组合各有`运行本组.ps1`入口，默认核对，加`-Generate`重建本组表图。来源与逐文件SHA见[复制清单](程序/复制清单.json)，新增并入脚本见[并入交付.py](程序/跨参数对比/并入交付.py)。`copy_package.py`保留初次八组合的复制记录。'
    text=neutralize_readme(text.replace(oldline,newline));readme.write_text(text,encoding='utf-8')
    counts={block:len([p for p in (PACKAGE/block).rglob('*') if p.is_file()]) for block in ['程序','结果']}
    assert counts['结果']==157
    print('PACKAGE_UPDATED',counts,'13 combinations; 312 conditional rate cells')
if __name__=='__main__':main()
