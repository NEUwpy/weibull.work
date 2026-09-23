"""Recover related WMLE/LSE row estimates from Research/05 without changing B2."""
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "python"))
from studies.common.sample import generate_sample  # noqa: E402

SOURCE = HERE / "research05_source_per_sample_losses.csv.gz"
MANIFEST = HERE / "research05_source_manifest.json"
SCAN = HERE.parent / "E01_固定偏移作用" / "候选扫描" / "mc_scan_raw.csv"
OUT = HERE / "research05_recovered.csv.gz"
KEYS = ["beta", "gamma_over_eta", "n", "repeat_id"]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    meta = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert sha(SOURCE) == meta["output_hashes"]["per_sample_losses.csv.gz"]
    assert sha(SCAN) == meta["input_hashes"]["mc_scan_raw"]
    df = pd.read_csv(SOURCE)
    df = df[df.method.isin(["WMLE", "LSE"])].copy()
    assert len(df) == 96000
    assert df.groupby("method").size().eq(48000).all()
    assert df.groupby("method")[KEYS].apply(lambda x: x.duplicated().sum()).eq(0).all()
    scan_keys = set()
    for chunk in pd.read_csv(SCAN, usecols=[*KEYS, "delta"], chunksize=100_000):
        chosen = chunk[chunk.delta.eq(0.1)]
        scan_keys.update(map(tuple, chosen[KEYS].itertuples(index=False, name=None)))
    assert len(scan_keys) == 48000
    for method in ("WMLE", "LSE"):
        restored_keys = set(map(tuple, df.loc[df.method.eq(method), KEYS].itertuples(index=False, name=None)))
        assert restored_keys == scan_keys
    df["eta_hat"] = df.eta_hat_norm * 1000.0
    df["gamma_hat"] = df.gamma_hat_norm * 1000.0
    df["eta"] = 1000.0
    df["gamma"] = df.gamma_over_eta * 1000.0
    df["valid"] = ~df.failed
    # The source stores a zero placeholder for failed estimates; remove it
    # from parameter estimates and keep the failure flag and reason.
    df.loc[df.failed, ["beta_hat", "eta_hat", "gamma_hat"]] = float("nan")
    df.to_csv(OUT, index=False, compression="gzip")
    output = {"status": "related row results recovered, original B2 estimation.csv still missing",
              "source": "Research/05-传统估计方法横向比较/artifacts/risk_landscape_v1/per_sample_losses.csv.gz",
              "local_copy": SOURCE.name, "source_sha256": sha(SOURCE),
              "source_manifest_sha256": sha(MANIFEST), "E01_scan_sha256": sha(SCAN),
              "rows": len(df), "sample_keys_per_method": 48000,
              "sample_key_match_E01": True,
              "sample_namespace": "study01_nrmc_v1", "unit_conversion": 1000,
              "difference_from_B2": "Research/05 re-estimated methods on the same keyed samples after fixed /1000 unit conversion; not the original B2 file",
              "implementation_hashes": {k: meta["input_hashes"][k] for k in ["wmle", "lse", "runner", "sample"]},
              "output_sha256": sha(OUT)}
    (HERE / "research05_recovery.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(df), "failures": df.groupby("method").failed.sum().to_dict(), "sha256": sha(OUT)}))


if __name__ == "__main__":
    main()
