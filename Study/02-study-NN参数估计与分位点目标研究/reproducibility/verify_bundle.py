"""Verify an extracted local archive, from any working directory."""
from pathlib import Path
import hashlib,json

root=Path(__file__).resolve().parents[3]
manifest=json.loads((root/'BUNDLE_MANIFEST.json').read_text(encoding='utf-8'))
for rel,expected in manifest['files'].items():
    p=(root/rel).resolve()
    assert p.is_relative_to(root),rel
    assert p.is_file(),rel
    assert hashlib.sha256(p.read_bytes()).hexdigest()==expected,rel
print('PASS',len(manifest['files']),'file hashes')
