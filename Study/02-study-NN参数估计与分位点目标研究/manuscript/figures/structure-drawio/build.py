"""Current figure entry point; prior frame-only source is archived."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).with_name("build_neural.py")),run_name="__main__")
