"""W(3,1000,500); n=7/15/30, 50 groups, MDM delta=0.20."""
import argparse
from pathlib import Path
from 计算母体 import calculate

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output", help="Independent rerun directory")
    args=parser.parse_args()
    calculate(Path(__file__).resolve().parent,args.output)
