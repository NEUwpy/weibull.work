"""One-time consolidation after Git snapshot c94d9dae.

Copies and adapts useful artifacts only. Deletions are performed separately with
checked native PowerShell paths. Old source directories must still exist.
"""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

WORKSPACE = Path('D:/weibull').resolve()
BASE = WORKSPACE / 'Research' / '00-方法对比'
MAIN = BASE / '20261001-高形状参数补偿报告'
SUPPLEMENT = BASE / '20261001-报告机制与启发补充'
INDEPENDENT = BASE / '20261001-高形状参数偏移研究'
SNAPSHOT = 'c94d9dae06d83e46bbc56ad43a4e3b857a0207fb'
REPORT_NAME = '高形状参数下的位置与尺度补偿报告.md'
RECORD = MAIN / '结果' / '中间数据' / '整理记录.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside_workspace(path):
    resolved = path.resolve()
    assert resolved.is_relative_to(BASE.resolve())
    return resolved


def main():
    for path in (MAIN, SUPPLEMENT, INDEPENDENT):
        inside_workspace(path)
        assert path.is_dir()
    assert not RECORD.exists(), 'One-time consolidation already recorded.'
    raw = subprocess.check_output(
        ['git', 'ls-tree', '-rz', '--full-tree', SNAPSHOT, '--', BASE.relative_to(WORKSPACE).as_posix()],
        cwd=WORKSPACE)
    snapshot_files = {}
    for entry in raw.split(b'\0'):
        if not entry:
            continue
        header, name = entry.split(b'\t', 1)
        snapshot_files[name.decode('utf-8')] = header.split()[2].decode()
    checked = 0
    for name, expected in snapshot_files.items():
        path = WORKSPACE / name
        if not (any(part.startswith('20261001-') for part in path.parts)
                or path.name.startswith('高形状参数下的位置与尺度补偿报告')):
            continue
        content = path.read_bytes()
        actual = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        assert actual == expected, name
        checked += 1
    assert checked == 242
    record = {
        'snapshot_commit': SNAPSHOT,
        'snapshot_verified_files': checked,
        'date': '2026-10-01',
        'scientific_scope_changed': False,
        'copies': [],
        'shared_dependency_hash_checks': [],
        'retained_independent_scan': {
            'samples': 1400, 'fits': 7000, 'seed_namespace': 2026100101,
            'groups_per_cell': 100, 'n_values': [7, 15],
            'beta_cells': [2, 2.5, 3, 3.5, 4, 4.5, 5],
            'cross_beta_pairing': False, 'lre': 'Park',
            'role': 'Separate supplemental data; not pooled into report paired statistics.',
        },
        'removed_from_worktree': [
            '20261001-报告机制与启发补充 (useful figure/source merged; other copies redundant)',
            '20261001-高形状参数偏移研究 (raw scan/needed code merged; alternative figures/pilot/old analyses stored in Git)',
            '高形状参数下的位置与尺度补偿报告-v2.md (latest body replaces stable report path)',
            'Excel inspection sidecar and workbook-development previews',
            'old hash seal copies and old generator variants; use snapshot Git commit for original versions',
            'Python caches inside these three task directories',
        ],
    }

    def copy(source, target):
        inside_workspace(source)
        inside_workspace(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert digest(source) == digest(target), f'Nonidentical collision: {target}'
        else:
            shutil.copy2(source, target)
        record['copies'].append({
            'source': source.relative_to(BASE).as_posix(),
            'target': target.relative_to(BASE).as_posix(),
            'sha256': digest(target),
        })

    for extension in ('png', 'pdf', 'svg'):
        name = '图7_不同参数的寿命曲线与分位点.' + extension
        copy(SUPPLEMENT / '结果' / name, MAIN / '结果' / name)
    for name in ('CDF对照.csv', '寿命分位点对照.csv', '代表样本绘图位置.csv',
                 '图7样本来源与核验.json'):
        copy(SUPPLEMENT / '结果' / '中间数据' / name, MAIN / '结果' / '中间数据' / name)

    # Preserve the independent raw scan, not its duplicate alternate figure set.
    for source in sorted((INDEPENDENT / '数据' / '扫描').rglob('*')):
        if source.is_file():
            copy(source, MAIN / '结果' / '独立种子扫描' /
                 source.relative_to(INDEPENDENT / '数据' / '扫描'))
    for name in ('扫描配置.json', '连续扫描统计.csv'):
        copy(INDEPENDENT / '数据' / name, MAIN / '结果' / '独立种子扫描' / name)

    # Reuse identical frozen dependencies; add the missing experiment runner.
    dependencies = INDEPENDENT / '程序' / '依赖快照'
    for source in sorted(dependencies.rglob('*')):
        if not source.is_file() or source.suffix not in {'.py', '.tsv'}:
            continue
        target = MAIN / '程序' / '依赖快照' / source.relative_to(dependencies)
        if target.exists():
            assert digest(source) == digest(target), f'Dependency collision: {target}'
            record['shared_dependency_hash_checks'].append(target.relative_to(MAIN).as_posix())
        else:
            copy(source, target)
    assert digest(INDEPENDENT / '程序' / 'diagnostic_profiles.py') == digest(MAIN / '程序' / '剖面母体.py')

    scan = (INDEPENDENT / '程序' / '连续形状扫描.py').read_text(encoding='utf-8')
    scan = scan.replace("BATCH / '数据' / '扫描'", "BATCH / '结果' / '独立种子扫描'")
    scan = scan.replace("BATCH / '数据' / 'pilot'", "BATCH / '结果' / '复核输出' / 'pilot'")
    scan = scan.replace("(BATCH/'数据'/'扫描配置.json')",
                        "(BATCH/'结果'/'独立种子扫描'/'扫描配置.json')")
    (MAIN / '程序' / '连续形状扫描.py').write_text(scan, encoding='utf-8')

    # Keep only the actual Figure 7 calculation, independent of old report text.
    plot = (SUPPLEMENT / '程序' / '补充机制与报告.py').read_text(encoding='utf-8')
    plot = plot.split('\ndef build_report():')[0]
    plot = plot.replace("PREVIOUS_NAME = '20261001-高形状参数补偿报告'\n", '')
    plot = plot.replace("REPORT_NAME = '高形状参数下的位置与尺度补偿报告-v2.md'\n", '')
    plot = plot.replace("('原案例估计.json', '原案例核验.json', '报告v1.md')",
                        "('原案例估计.json', '原案例核验.json')")
    plot = plot.replace('Figure 7 and report v2 from frozen results',
                        'Figure 7 from frozen results')
    plot += '''

def main():
    DATA.mkdir(parents=True, exist_ok=True)
    provenance = plot_and_save()
    print(json.dumps({'sample_id': provenance['sample_id'],
                      'quantile_errors': provenance['quantile_errors'],
                      'new_samples': 0, 'new_fits': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
'''
    (MAIN / '程序' / '绘制寿命对照图.py').write_text(plot, encoding='utf-8')

    report = (BASE / '高形状参数下的位置与尺度补偿报告-v2.md').read_text(encoding='utf-8')
    report = report.replace('> 研究小报告 · v2 · 2026-10-01',
                            '> 研究小报告 · 2026-10-01')
    report = report.replace(SUPPLEMENT.name + '/', MAIN.name + '/')
    begin = report.index('**数据与程序。**')
    end = report.index('\n\n**补充图。**', begin)
    report = report[:begin] + (
        f'**数据与程序。** [研究目录说明]({MAIN.name}/README.md)统一列出计算、绘图、'
        '报告生成和封存入口；保存本报告的原案例核验输入、700组共同随机分位点样本、'
        f'4200条估计及图1–7的源数据。[完整统计表]({MAIN.name}/结果/高形状参数补偿统计.xlsx)'
        '保存原案例分布、连续条件汇总、估计、配对端点与样本。另一批1400组、7000条估计的'
        '独立种子扫描单列保存，没有混入本报告的配对统计。图提供PNG、PDF与SVG；'
        '工作区保留最新报告，原版本和整理前布局由Git快照追溯。'
    ) + report[end:]
    (BASE / REPORT_NAME).write_text(report, encoding='utf-8')

    # Latest report source is self-contained; old generator is preserved in Git.
    generator = (
        '"""Generate the current three-chapter report; the latest reviewed body is frozen here."""\n'
        'import json\nfrom pathlib import Path\n\n'
        'ROOT = Path(__file__).resolve().parents[2]\n'
        'DATA = Path(__file__).resolve().parents[1] / "结果" / "中间数据"\n'
        'REPORT_TEXT = ' + repr(report) + '\n\n'
        'def main():\n'
        '    estimates = json.loads((DATA / "实际估计.json").read_text(encoding="utf-8"))\n'
        '    samples = json.loads((DATA / "样本.json").read_text(encoding="utf-8"))\n'
        '    assert len(estimates) == 4200 and len(samples) == 700\n'
        '    target = ROOT / ' + repr(REPORT_NAME) + '\n'
        '    target.write_text(REPORT_TEXT, encoding="utf-8")\n'
        '    print(str(target))\n\n'
        'if __name__ == "__main__":\n    main()\n'
    )
    (MAIN / '程序' / '生成报告.py').write_text(generator, encoding='utf-8')

    # The original experiment configuration stays valid; old seals live in Git.
    manifest_path = MAIN / '结果' / '中间数据' / 'manifest.json'
    config = json.loads(manifest_path.read_text(encoding='utf-8'))
    for key in ('code_hashes', 'input_hashes', 'output_hashes', 'document_hashes',
                'sealed_at_utc', 'seal_scope'):
        config.pop(key, None)
    config['original_git_snapshot'] = SNAPSHOT
    config['current_seal'] = '封存清单.json'
    config['note'] = 'Experiment configuration; current file hashes are separately sealed after consolidation.'
    manifest_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    RECORD.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({
        'snapshot_verified_files': checked, 'merged_files': len(record['copies']),
        'identical_dependency_count': len(record['shared_dependency_hash_checks']),
        'independent_estimates_retained': 7000, 'latest_report': REPORT_NAME,
        'deletions_performed_by_this_script': 0,
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
