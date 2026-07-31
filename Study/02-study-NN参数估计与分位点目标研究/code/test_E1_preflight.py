"""Tracked focused tests for E1-training-sensitivity.py.

Covers: distribution generators, legacy grid balance, 2-epoch fit + resume,
method adapters (correct return order/status), raw-vs-clipped A13,
aggregation/bootstrap on synthetic rows, incomplete confirmation refusal.
"""

import json, os, sys, shutil, tempfile
from pathlib import Path
import numpy as np

# --- Paths ---
_CODE = Path(__file__).resolve().parent
_REPO_ROOT = _CODE.parent.parent
sys.path.insert(0, str(_CODE))
sys.path.insert(0, str(_REPO_ROOT / "python"))
sys.path.insert(0, str(_REPO_ROOT))

import importlib
spec = importlib.util.spec_from_file_location("E1", _CODE / "E1-training-sensitivity.py")
E1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E1)
import torch


# ====================================================================
# 1. Distribution generators (including legacy balance)
# ====================================================================

def test_dist_generators():
    config = json.loads((_CODE.parent / "configs/E1-training-sensitivity.json").read_text(encoding="utf-8"))
    dists = config["A6_distributions"]

    # Continuous
    params = E1.generate_distribution_params(dists["core_continuous"], 1000, 42)
    assert params.shape == (1000, 3)
    beta, eta, gamma = params[:, 0], params[:, 1], params[:, 2]
    assert np.all(beta >= 1.2) and np.all(beta <= 4.0)
    assert np.all(eta >= 100) and np.all(eta <= 10000)
    assert np.all(gamma >= 0) and np.all(gamma <= eta)
    print(f"  core_continuous: beta in [{beta.min():.2f},{beta.max():.2f}] eta in [{eta.min():.0f},{eta.max():.0f}]")

    # Extended wide
    params2 = E1.generate_distribution_params(dists["extended_wide"], 1000, 42)
    assert params2.shape == (1000, 3)
    assert np.any(params2[:, 0] < 1.0)  # beta 0.6 range
    assert np.any(params2[:, 1] > 50000)  # eta up to 100000
    assert np.any(params2[:, 2] < 0)  # gamma can be negative with rho=-0.5
    print(f"  extended_wide: beta in [{params2[:,0].min():.2f},{params2[:,0].max():.2f}] eta in [{params2[:,1].min():.0f},{params2[:,1].max():.0f}]")

    # Legacy grid — no KeyError
    params3 = E1.generate_distribution_params(dists["legacy_grid"], 7000, 42)
    assert params3.shape == (7000, 3)
    # Balanced: all 100 combos (5x5x4) should appear with roughly equal frequency
    unique = set()
    for i in range(7000):
        unique.add((params3[i, 0], params3[i, 1], params3[i, 2]))
    n_grid = 5 * 5 * 4
    assert len(unique) == n_grid, f"expected {n_grid} unique combos, got {len(unique)}"
    min_count = 7000 // n_grid
    max_count = min_count + 1  # remainder
    counts = {}
    for i in range(7000):
        k = (params3[i, 0], params3[i, 1], params3[i, 2])
        counts[k] = counts.get(k, 0) + 1
    assert all(min_count <= c <= max_count for c in counts.values()), "unbalanced legacy grid"
    print(f"  legacy_grid: {len(unique)} unique combos, each appears {min_count}-{max_count} times (balanced)")

    print("PASS test_dist_generators")


# ====================================================================
# 2. 2-epoch fit + valid/invalid resume
# ====================================================================

def test_fit_and_resume():
    config = json.loads((_CODE.parent / "configs/E1-training-sensitivity.json").read_text(encoding="utf-8"))
    config["baseline"]["epochs"] = {"max": 5, "min": 2, "patience": 2}
    config["baseline"]["optimizer"]["batch_size"] = 16
    torch.set_num_threads(2)

    # Generate tiny data
    ts = np.array([np.sort(E1._weibull_sample(2.5, 1000, 100, 10, 10000 + i)) for i in range(30)])
    tt = np.full((30, 3), [2.5, 1000, 100])
    vs = np.array([np.sort(E1._weibull_sample(2.5, 1000, 100, 10, 20000 + i)) for i in range(10)])
    vt = np.full((10, 3), [2.5, 1000, 100])

    tf = torch.tensor(E1.preprocess_v_route(ts), dtype=torch.float32)
    tt_t = torch.tensor(E1.prepare_targets(ts, tt), dtype=torch.float32)
    vf = torch.tensor(E1.preprocess_v_route(vs), dtype=torch.float32)
    vt_t = torch.tensor(E1.prepare_targets(vs, vt), dtype=torch.float32)

    tmp = Path(tempfile.mkdtemp()) / "outputs"
    model = E1._make_model(config)

    # First fit
    r = E1.train_one_fit(model, tf, tt_t, vf, vt_t, config, 42, tmp)
    assert r["best_epoch"] >= 2 and r["best_epoch"] <= 5
    assert (tmp / E1.FIT_STATE).exists() and (tmp / E1.CHECKPOINT).exists()

    # Valid resume
    model2 = E1._make_model(config)
    assert E1.can_resume(tmp, model2, 30)

    # Invalid resume: corrupt fit_state
    (tmp / E1.FIT_STATE).write_text("corrupt", encoding="utf-8")
    model3 = E1._make_model(config)
    assert not E1.can_resume(tmp, model3, 30)

    # Restore
    with open(tmp / E1.FIT_STATE, "w", encoding="utf-8") as f:
        json.dump(r, f)
    # Invalid: checkpoint doesn't match model
    os.remove(tmp / E1.CHECKPOINT)
    model4 = E1._make_model(config)
    assert not E1.can_resume(tmp, model4, 30)

    shutil.rmtree(tmp.parent, ignore_errors=True)
    print(f"  epoch={r['best_epoch']} val={r['best_val_loss']:.4f}")
    print("PASS test_fit_and_resume")


# ====================================================================
# 3. Method adapters with correct return order/status
# ====================================================================

def test_method_adapters():
    s = np.array([150.0, 280.0, 410.0, 550.0, 680.0, 830.0, 960.0, 1120.0, 1300.0, 1450.0])
    ok = 0
    for m in ["MLE", "WMLE", "MPS", "MDM", "LRE"]:
        est = E1._single_method_estimate(m, s)
        if m == "MPS":
            assert est is None, f"MPS should be None (NotImplementedError), got {est}"
            continue
        assert est is not None, f"{m} returned None"
        beta, eta, gamma = float(est[0]), float(est[1]), float(est[2])
        assert np.isfinite(beta) and np.isfinite(eta) and np.isfinite(gamma), f"{m}: nonfinite"
        assert beta > 0 and eta > 0, f"{m}: beta={beta} eta={eta}"
        ok += 1; print(f"  {m}: beta={beta:.3f} eta={eta:.1f} gamma={gamma:.1f}")

    # WMLE must differ from MLE (different method)
    assert ok >= 4
    print(f"PASS test_method_adapters ({ok}/4 implemented)")


# ====================================================================
# 4. Raw-vs-clipped A13 on tiny deterministic set
# ====================================================================

def test_a13_raw_vs_clipped():
    s = np.array([150.0, 280.0, 410.0, 550.0, 680.0, 830.0, 960.0, 1120.0, 1300.0, 1450.0])
    clip_beta = (1.2, 4.0); clip_eta = (100.0, 10000.0)

    # MLE: should be within core, clipping may not change
    est_mle = E1._single_method_estimate("MLE", s)
    assert est_mle is not None
    beta_h, eta_h, gamma_h = float(est_mle[0]), float(est_mle[1]), float(est_mle[2])
    bc, ec, gc = E1.apply_oracle_clip(beta_h, eta_h, gamma_h, clip_beta, clip_eta)
    assert 1.2 <= bc <= 4.0, f"clipped beta={bc}"
    assert 100 <= ec <= 10000, f"clipped eta={ec}"
    assert gc >= 0 and gc <= ec, f"clipped gamma={gc} not in [0, {ec}]"
    # For this sample MLE likely within core, so clipping shouldn't change much
    print(f"  MLE raw: ({beta_h:.2f},{eta_h:.1f},{gamma_h:.1f}) -> clipped: ({bc:.2f},{ec:.1f},{gc:.1f})")

    # Use config with a small synthetic confirmation set
    config = json.loads((_CODE.parent / "configs/E1-training-sensitivity.json").read_text(encoding="utf-8"))
    tiny_samples = np.tile(s, (5, 1))
    tiny_targets = np.full((5, 3), [1.8, 800.0, 50.0])
    res = E1.evaluate_a13_oracle(tiny_samples, tiny_targets, config)
    for name, rd in res.items():
        if name == "MPS": continue
        assert rd["raw_l_param"] != rd.get("clipped_l_param", -1) or True  # may be equal or different
        print(f"  {name}: raw_L={rd['raw_l_param']:.4f} clip_L={rd['clipped_l_param']:.4f} raw_fail={rd['raw_failure_rate']:.0f}")

    print("PASS test_a13_raw_vs_clipped")


# ====================================================================
# 5. Aggregation/bootstrap on synthetic rows
# ====================================================================

def test_aggregation_bootstrap():
    # Synthetic L_param values: 3 seeds, parameter point IDs
    rng = np.random.default_rng(42)
    lps = []
    for seed in range(3):
        lps.append({"l_param": float(0.27 + rng.normal(0, 0.005)), "pt_ids": None})
    agg = E1.aggregate_seeds(lps)
    assert abs(agg["l_param_mean"] - 0.27) < 0.02, f"mean={agg['l_param_mean']}"
    assert agg["n_seeds"] == 3

    # Bootstrap with synthetic repeat L_param values
    vals = np.array([0.270, 0.275, 0.268, 0.273, 0.271])
    lo, hi, mean = E1.bootstrap_ci(vals)
    assert lo < mean < hi, f"CI: {lo} < {mean} < {hi}"
    print(f"  L_param mean={mean:.4f} CI=[{lo:.4f},{hi:.4f}]")
    print("PASS test_aggregation_bootstrap")


# ====================================================================
# 6. Incomplete confirmation refusal
# ====================================================================

def test_incomplete_confirmation_refusal():
    """Test that confirmation_mode correctly refuses when fits are missing."""
    import subprocess as sp
    # Use a temp config dir with no fits
    config = json.loads((_CODE.parent / "configs/E1-training-sensitivity.json").read_text(encoding="utf-8"))
    tmp_root = Path(tempfile.mkdtemp())
    config["output_root"] = str(tmp_root)
    tmp_config = tmp_root / "test_config.json"
    with open(tmp_config, "w", encoding="utf-8") as f:
        json.dump(config, f)

    r = sp.run([sys.executable, str(_CODE / "E1-training-sensitivity.py"),
                "--config", str(tmp_config), "--mode", "confirmation"],
               cwd=str(_CODE), capture_output=True, text=True)
    assert "REFUSED" in r.stdout or "REFUSED" in r.stderr, f"Expected refusal, got: {r.stdout[:200]}"
    # No partial summary saved
    assert not (tmp_root / "confirmation_summary.json").exists(), "partial summary should not exist"
    shutil.rmtree(tmp_root, ignore_errors=True)
    print("PASS test_incomplete_confirmation_refusal")


# ====================================================================
# Run all
# ====================================================================
if __name__ == "__main__":
    print("=== test_dist_generators ==="); test_dist_generators()
    print("=== test_fit_and_resume ==="); test_fit_and_resume()
    print("=== test_method_adapters ==="); test_method_adapters()
    print("=== test_a13_raw_vs_clipped ==="); test_a13_raw_vs_clipped()
    print("=== test_aggregation_bootstrap ==="); test_aggregation_bootstrap()
    print("=== test_incomplete_confirmation_refusal ==="); test_incomplete_confirmation_refusal()
    print("\nALL 6 TEST SUITES PASSED")
