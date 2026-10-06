"""工单026专用入口：读取原样本，续抽缺失n30，补算与核验完整矩阵。"""
import sys
from pathlib import Path
directory = Path(__file__).resolve().parent
sys.path.insert(0, str(directory))
from fill_matrix import main
if __name__ == '__main__':
    main(directory)
