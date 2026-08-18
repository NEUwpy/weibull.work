"""Build the submission figures and synchronize non-visual evidence files.

The sealed Study01 generator remains available for evidence regeneration, but
its evidence-grade PNG files never overwrite the manuscript submission figures.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
FIGURE_DIR = SCRIPT_DIR.parent
CONFIG_PATH = FIGURE_DIR / "figure_sources.json"


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def regenerate_formal(config: dict) -> None:
    generator = Path(config["canonical_generator"])
    if not generator.is_file():
        raise FileNotFoundError(f"Canonical generator not found: {generator}")
    subprocess.run([sys.executable, str(generator)], cwd=generator.parent, check=True)


def sync_evidence(config: dict) -> int:
    source_dir = Path(config["formal_paper_output"])
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Formal paper output not found: {source_dir}")

    copied = 0
    for group in ("tables", "provenance"):
        names = config["copy_groups"][group]
        target_dir = FIGURE_DIR / group
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            source = source_dir / name
            if not source.is_file():
                raise FileNotFoundError(f"Declared output missing: {source}")
            shutil.copy2(source, target_dir / name)
            copied += 1
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--regenerate-formal",
        action="store_true",
        help="Regenerate the sealed evidence-grade package before building.",
    )
    args = parser.parse_args()

    config = load_config()
    if args.regenerate_formal:
        regenerate_formal(config)
    copied = sync_evidence(config)
    subprocess.run([sys.executable, str(SCRIPT_DIR / "make_submission_figures.py")],
                   cwd=SCRIPT_DIR, check=True)
    subprocess.run([sys.executable, str(SCRIPT_DIR / "qa_submission_figures.py")],
                   cwd=SCRIPT_DIR, check=True)
    print(f"Built submission figures and synchronized {copied} evidence files.")


if __name__ == "__main__":
    main()
