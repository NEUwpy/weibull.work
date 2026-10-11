"""交付路径与运行环境；估计方法仍由各批 runner/registry 调用。"""
from pathlib import Path
import os
import sys
import importlib.util


def load_conditional_profiles():
    """两报告调用方法系统的同一条件诊断函数，估计器仍走冻结快照。"""
    name = "r00_shared_conditional_profiles"
    if name not in sys.modules:
        path = ROOT.parents[1] / "python/methods/conditional_profiles.py"
        spec = importlib.util.spec_from_file_location(name, path)
        obj = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(obj)
        sys.modules[name] = obj
    return sys.modules[name]

PROGRAM = Path(__file__).resolve().parent
DELIVERY = PROGRAM.parent
ROOT = DELIVERY.parent
RESULT = Path(os.environ.get('R00_OUTPUT_DIR', DELIVERY / '结果')).resolve()


def matrix_path(source):
    return PROGRAM / source['matrix']


def snapshot_path(source):
    return PROGRAM / source['snapshot']


def setup_runtime():
    # 只补充已安装的绘图库和工作簿读取器，不从旧研究目录取依赖。
    paths = [
        Path('C:/Users/36089/AppData/Local/hermes/hermes-agent/venv/Lib/site-packages'),
        Path('C:/Users/36089/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/Lib/site-packages'),
    ]
    for path in paths:
        if path.exists() and str(path) not in sys.path:
            sys.path.append(str(path))
    os.environ.setdefault('MPLCONFIGDIR', str(Path(os.environ.get('TEMP', '.')) / 'research00-figures'))


def save_png(fig, path, dpi=450):
    """Replace a PNG atomically, including when its previous copy is previewed."""
    from io import BytesIO
    path = Path(path)
    buffer = BytesIO()
    fig.savefig(buffer, format='png', dpi=dpi, facecolor='white')
    write_atomic(path, buffer.getvalue())


def write_atomic(path, data):
    """Keep the previous artifact intact until its replacement is complete."""
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    try:
        temporary.write_bytes(data)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
