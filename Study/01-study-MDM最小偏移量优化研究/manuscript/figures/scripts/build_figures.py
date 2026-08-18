"""Build and check the submission figures from declared sealed evidence."""

from __future__ import annotations

import argparse
import json
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
    subprocess.run([sys.executable, str(SCRIPT_DIR / "make_submission_figures.py")],
                   cwd=SCRIPT_DIR, check=True)
    subprocess.run([sys.executable, str(SCRIPT_DIR / "qa_submission_figures.py")],
                   cwd=SCRIPT_DIR, check=True)
    print("Built and checked submission figures from declared evidence sources.")


if __name__ == "__main__":
    main()
