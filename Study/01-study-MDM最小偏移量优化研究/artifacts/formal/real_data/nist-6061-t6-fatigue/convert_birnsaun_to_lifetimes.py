"""
Study01 P6 — BIRNSAUN.DAT → lifetimes.csv conversion (deterministic)

This script is the ONLY authorised path from the original NIST data file
to the lifetimes.csv used by the admission gate and holdout pipeline.

Usage:
    python convert_birnsaun_to_lifetimes.py

The script reads BIRNSAUN.DAT from the same directory, extracts the 101
fatigue-life values, and writes lifetimes.csv. Output is deterministic:
same input → same output, verified by SHA256.
"""

import os
import re
import hashlib
import csv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(SCRIPT_DIR, "BIRNSAUN.DAT")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "lifetimes.csv")

# Frozen expected SHA256 of lifetimes.csv (LF-normalised)
EXPECTED_LIFETIMES_SHA256 = (
    "43c85155bdfeafd21e2366610e88a3f4e1a09e36466fb22d34729dc60418ee12"
)


def extract_values(text):
    """Extract all integer fatigue-life values from the BIRNSAUN.DAT text.

    The file has a header block (lines with metadata), then a data block
    starting after the '---...' separator line. Values are line-oriented
    (one per line in the data block).

    Returns:
        list[int]: 101 fatigue-life values in original file order.
    """
    lines = text.split('\n')
    in_data = False
    values = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('---'):
            in_data = True
            continue
        if in_data:
            # Only lines that are purely numeric (possibly indented)
            match = re.match(r'^\s*(\d+)\s*$', stripped)
            if match:
                values.append(int(match.group(1)))
    return values


def main():
    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"BIRNSAUN.DAT not found at {INPUT_FILE}. "
            "Download from: https://itl.nist.gov/div898/handbook/datasets/BIRNSAUN.DAT"
        )

    with open(INPUT_FILE, 'r', encoding='ascii') as f:
        text = f.read()

    values = extract_values(text)

    if len(values) != 101:
        raise ValueError(
            f"Expected 101 values from BIRNSAUN.DAT, extracted {len(values)}. "
            "File may be corrupted or format has changed."
        )

    # Write lifetimes.csv (Unix line endings for reproducibility)
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(['failure_time'])
        for v in values:
            writer.writerow([v])

    # Verify SHA256
    with open(OUTPUT_FILE, 'rb') as f:
        raw = f.read()
    sha = hashlib.sha256(raw).hexdigest()

    if sha != EXPECTED_LIFETIMES_SHA256:
        raise RuntimeError(
            f"lifetimes.csv SHA256 mismatch!\n"
            f"  Expected: {EXPECTED_LIFETIMES_SHA256}\n"
            f"  Got:      {sha}\n"
            "Conversion is not reproducing the frozen output. "
            "BIRNSAUN.DAT may have changed."
        )

    print(f"Converted {len(values)} values from BIRNSAUN.DAT → lifetimes.csv")
    print(f"SHA256 verified: {sha}")


if __name__ == '__main__':
    main()
