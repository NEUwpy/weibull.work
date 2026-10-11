"""Restore the baseline-centered MLE display without adding a numbered formula.

Reuse the saved profiles and estimates. Subtract each sample's profile value
at gamma=500; this additive shift preserves all likelihood differences and
peak locations. Export only the two current MLE PNGs.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('r1_mle_display_checks', HERE / '20261011-MLE原始对数似然图.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
checks.QA = HERE / (Path(__file__).stem + '核验.json')


def render():
    return checks.render(centered=True)


def revise():
    checks.revise(centered=True)


def verify():
    checks.verify(centered=True)
    qa = checks.base.read(checks.QA)
    qa['script_sha256'] = checks.base.sha(__file__)
    qa['verification_program_sha256'] = checks.base.sha(checks.__file__)
    checks.base.write(checks.QA, qa)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['render', 'revise', 'verify', 'all'], nargs='?', default='verify')
    action = parser.parse_args().action
    for name in ['render', 'revise', 'verify'] if action == 'all' else [action]:
        globals()[name]()
