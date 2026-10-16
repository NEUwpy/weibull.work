"""Study04的日常表格与计算存档位置；兼容存档中记录的整理前路径。"""
import json
from pathlib import Path

STUDY = Path(__file__).resolve().parents[1]
ROOT = STUDY.parents[1]
RESULTS = STUDY / '结果'
ARCHIVE = STUDY / '计算存档'
METADATA = ARCHIVE / '参数表元数据'


def batch_path(run_id):
    archived = ARCHIVE / run_id
    return archived if archived.exists() else RESULTS / run_id


def current_batch():
    pointer = ARCHIVE / '当前批次.json'
    if not pointer.exists():
        pointer = RESULTS / '当前批次.json'
    run_id = json.loads(pointer.read_text(encoding='utf-8'))['run_id']
    return batch_path(run_id)


def saved_path(relative):
    """只转译本Study原结果目录下的存档路径，不修改历史清单及其指纹。"""
    original = ROOT / relative
    try:
        suffix = original.relative_to(RESULTS)
    except ValueError:
        return original
    relocated = ARCHIVE / suffix
    return original if original.exists() else relocated


def parameter_file(name, relative):
    visible = RESULTS / name / relative
    return visible if visible.exists() else METADATA / name / relative
