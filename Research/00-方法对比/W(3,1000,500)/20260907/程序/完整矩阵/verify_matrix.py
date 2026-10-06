"""Verify this batch's stored hashes and 150-by-8 keyed matrix, read only."""
import hashlib,json
from pathlib import Path
d=Path(__file__).resolve().parent
cfg=json.loads((d/'config.json').read_text(encoding='utf-8'))
m=json.loads((d/'manifest.json').read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
for rel,s in cfg['source_files'].items():assert sha(d.parent.parent/rel)==s
for rel,s in cfg['dependency_hashes'].items():assert sha(d.parent/'依赖快照/python'/rel)==s
data=json.loads((d/'数据/matrix.json').read_text(encoding='utf-8'))
assert len(data['samples'])==150 and len(data['results'])==1200
assert len({(r['n'],r['id'],r['method_id'],r['delta']) for r in data['results']})==1200
for f in m['figures']:assert sha(f['path'])==f['sha256']
assert sha(m['workbook']['path'])==m['workbook']['sha256']
assert sha(d/'数据/matrix.json')==m['matrix_sha256']
assert sha(d/'config.json')==m['config_sha256']
assert sha(d/'build_matrix.mjs')==m['builder_sha256']
for rel,s in m['script_hashes'].items():assert sha(d/rel)==s
print(cfg['combination'],'150 samples / 1200 estimate records / hashes passed')
