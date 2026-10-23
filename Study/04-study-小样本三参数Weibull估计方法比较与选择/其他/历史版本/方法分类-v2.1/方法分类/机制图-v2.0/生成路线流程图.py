"""生成五条路线的可视流程；图像、步骤和差异位置均为原生draw.io对象。"""
from pathlib import Path
import runpy

ROOT=Path(__file__).resolve().parent

if __name__=='__main__':
    for name in ['生成似然可视流程.py','生成分布统计可视流程.py','生成后验学习可视流程.py']:
        runpy.run_path(str(ROOT/name),run_name='__main__')
    print('generated five visual principle flows')
