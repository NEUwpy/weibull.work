"""交付路径与运行环境；估计方法仍由各批 runner/registry 调用。"""
from pathlib import Path
import os
import sys

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
