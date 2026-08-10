"""数据量学习曲线拆分与训练覆盖的最小回归测试。"""

from __future__ import annotations

import numpy as np

from . import data as DATA
from . import data_scale_pilot as PILOT
from . import training as TR


def _tiny_master(repeats: int):
    return DATA.build_master(
        beta_grid=[1.5], gamma_grid=[100.0], n_grid=[7], repeats=repeats,
        seed_namespace="study02_data_scale_test",
    )


def _keys(master, rows):
    return master.keys[np.asarray(rows, dtype=np.int64)]


def test_data_scale_fixed_eval_counts_nested_and_disjoint(monkeypatch):
    master = _tiny_master(1200)
    monkeypatch.setattr(DATA.CFG, "BETA_GRID", [1.5])
    monkeypatch.setattr(DATA.CFG, "GAMMA_GRID", [100.0])
    splits = {}
    for level in (180, 360, 720):
        tr, va, te = DATA.split_data_scale_fixed_eval(master, 7, 0, level)
        assert (len(tr), len(va), len(te)) == (level, 60, 60)
        assert not set(tr) & set(va)
        assert not set(tr) & set(te)
        splits[level] = (tr, va, te)
    assert np.array_equal(_keys(master, splits[180][1]), _keys(master, splits[720][1]))
    assert np.array_equal(_keys(master, splits[180][2]), _keys(master, splits[720][2]))
    assert set(map(tuple, _keys(master, splits[180][0]))) <= set(
        map(tuple, _keys(master, splits[360][0])))
    assert set(map(tuple, _keys(master, splits[360][0]))) <= set(
        map(tuple, _keys(master, splits[720][0])))


def test_level_180_matches_iid_v1_keys(monkeypatch):
    master = _tiny_master(300)
    monkeypatch.setattr(DATA.CFG, "BETA_GRID", [1.5])
    monkeypatch.setattr(DATA.CFG, "GAMMA_GRID", [100.0])
    got = DATA.split_data_scale_fixed_eval(master, 7, 2, 180)
    want = DATA.split_repeat_fold(master, 7, 2)
    for g, w in zip(got, want):
        assert np.array_equal(_keys(master, g), _keys(master, w))


def test_train_one_fit_accepts_explicit_rows(monkeypatch):
    master = _tiny_master(300)
    monkeypatch.setattr(DATA.CFG, "BETA_GRID", [1.5])
    monkeypatch.setattr(DATA.CFG, "GAMMA_GRID", [100.0])
    rows = DATA.split_data_scale_fixed_eval(master, 7, 0, 180)
    result = TR.train_one_fit(
        7, 0, 42, "Q", master, max_epochs=1, batch_size=64, patience=1,
        hidden=[8], split_strategy="data_scale_fixed_eval", split_rows=rows,
    )
    assert result["meta"]["n_train"] == 180
    assert result["meta"]["n_val"] == 60
    assert result["meta"]["n_test"] == 60
    assert result["meta"]["split_strategy"] == "data_scale_fixed_eval"
    assert result["meta"]["n_support_viol"] == 0


def test_text_sha_is_portable_across_line_endings(tmp_path):
    lf = tmp_path / "lf.json"
    crlf = tmp_path / "crlf.json"
    lf.write_bytes(b'{"x": 1}\n')
    crlf.write_bytes(b'{"x": 1}\r\n')
    assert PILOT._sha(lf) == PILOT._sha(crlf)
