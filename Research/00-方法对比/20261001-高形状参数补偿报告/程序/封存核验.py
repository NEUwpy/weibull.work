"""Seal the completed batch; --verify checks the existing SHA-256 manifest.

Run after the calculation, independent verification, workbook and report are final.
Runtime libraries and caches are excluded; actual local method/input files are kept.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / '结果' / '中间数据' / '封存清单.json'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def files_under(directory):
    for folder, dirs, files in os.walk(directory, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in {'node_modules', '__pycache__', '.git'})
        for filename in sorted(files):
            path = Path(folder) / filename
            if path != MANIFEST and path.suffix != '.pyc':
                yield path


def inventories():
    groups = {'code_hashes': {}, 'input_hashes': {}, 'output_hashes': {}, 'document_hashes': {}}
    for directory in ('程序', '结果'):
        for path in files_under(ROOT / directory):
            relative = path.relative_to(ROOT)
            if directory == '结果':
                group = 'output_hashes'
            elif relative.parts[1] == '输入快照':
                group = 'input_hashes'
            else:
                group = 'code_hashes'
            groups[group][relative.as_posix()] = digest(path)
    for path in sorted(ROOT.glob('*.md')):
        groups['document_hashes'][path.name] = digest(path)
    groups['document_hashes']['../README.md'] = digest(ROOT.parent / 'README.md')
    report = ROOT.parent / '高形状参数下的位置与尺度补偿报告.md'
    groups['document_hashes']['../高形状参数下的位置与尺度补偿报告.md'] = digest(report)
    return groups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    if args.verify and not MANIFEST.exists():
        raise SystemExit('No current seal exists; run sealing after final review.')
    saved = json.loads(MANIFEST.read_text(encoding='utf-8')) if MANIFEST.exists() else {
        'task': 'Consolidated beta compensation research',
        'original_snapshot_commit': 'c94d9dae06d83e46bbc56ad43a4e3b857a0207fb',
        'note': 'New seal after consolidation; original versions remain in Git.',
    }
    actual = inventories()
    if args.verify:
        errors = []
        for group, hashes in actual.items():
            previous = saved.get(group, {})
            for name in set(hashes) | set(previous):
                if hashes.get(name) != previous.get(name):
                    errors.append(f'{group}: {name}')
        if errors:
            raise SystemExit('Hash mismatch:\n' + '\n'.join(sorted(errors)))
    else:
        saved.update(actual)
        saved['sealed_at_utc'] = datetime.now(timezone.utc).isoformat()
        saved['seal_scope'] = 'All batch code, frozen inputs, outputs, batch Markdown, Research00 README and report; excluding runtime, caches and manifest itself.'
        MANIFEST.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'mode': 'verify' if args.verify else 'seal',
                      'files': {group: len(items) for group, items in actual.items()},
                      'hash_mismatches': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
