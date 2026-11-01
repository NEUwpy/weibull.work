"""External result paths and versioned study-configuration boundaries."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import data_paths


def test_default_and_relative_data_roots_ignore_working_directory(tmp_path, monkeypatch):
    software = tmp_path / "release" / "weibull"
    software.mkdir(parents=True)
    unrelated = tmp_path / "elsewhere"
    unrelated.mkdir()
    monkeypatch.setattr(data_paths, "SOFTWARE_ROOT", software)
    monkeypatch.chdir(unrelated)
    monkeypatch.delenv("WEIBULL_DATA_ROOT", raising=False)
    assert data_paths.data_root() == software.parent / "weibull-data"
    monkeypatch.setenv("WEIBULL_DATA_ROOT", "../materials")
    assert data_paths.data_root() == software.parent / "materials"
    assert data_paths.study_config_path("mdm", "demo1") == (
        software / "public" / "studies" / "mdm" / "demo1" / "config.md"
    )
    assert not (software.parent / "materials").exists()


def test_absolute_root_and_escaping_child_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("WEIBULL_DATA_ROOT", str(tmp_path / "data"))
    assert data_paths.public_data_path("studies", "mdm", "demo1") == tmp_path / "data/public/studies/mdm/demo1"
    for parts in (("../outside",), (str(tmp_path / "outside"),), ("studies", "..", "outside")):
        with pytest.raises(ValueError, match="inside"):
            data_paths.data_path(*parts)
    with pytest.raises(ValueError):
        data_paths.study_config_path("mdm", "../outside")


@pytest.mark.parametrize("method", ["mdm", "mle", "wmle"])
def test_legacy_generator_keeps_config_in_git_and_uses_external_output(method, tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "studies" / method / "simulate.py"
    spec = importlib.util.spec_from_file_location(f"external_{method}_simulate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    software = tmp_path / "software"
    monkeypatch.setattr(data_paths, "SOFTWARE_ROOT", software)
    monkeypatch.setenv("WEIBULL_DATA_ROOT", str(tmp_path / "data"))
    config = data_paths.study_config_path(method, "demo1")
    config.parent.mkdir(parents=True)
    fixture = {
        "params": [{"id": "beta", "isVariable": True, "state": "discrete", "discreteValues": [2.0]}],
        "defaults": {"beta": 2.0, "eta": 1000, "gamma": 1000, "sampleSize": 7, "process": 0.1},
        "simulation": {"mcRuns": 1},
    }
    # Exercise file generation, merge and cleanup independently of scientific
    # success/failure rules in these deprecated entry points.
    estimator = {"mdm": "run_mdm_estimation", "mle": "run_mle_estimation", "wmle": "run_wmle_estimation"}[method]
    monkeypatch.setattr(module, estimator, lambda *args, **kwargs: (2.0, 1000.0, 1000.0, 1.0, True))
    config.write_text("---\n" + json.dumps(fixture) + "\n---\nfixture\n", encoding="utf-8")
    original_config = config.read_bytes()
    monkeypatch.setattr(sys, "argv", ["simulate.py", "demo1"])
    module.main()
    output = tmp_path / "data" / "public" / "studies" / method / "demo1"
    assert len(list((output / "chunks").glob("*.csv"))) == 1
    assert json.loads((output / "chunks/index.json").read_text(encoding="utf-8"))["stats"]["totalRuns"] == 1
    monkeypatch.setattr(sys, "argv", ["simulate.py", "demo1", "--merge"])
    module.main()
    assert (output / "data.csv").is_file()
    assert (output / "summary.json").is_file()
    monkeypatch.setattr(sys, "argv", ["simulate.py", "demo1", "--clean"])
    module.main()
    assert not (output / "data.csv").exists()
    assert config.read_bytes() == original_config
    assert list(config.parent.iterdir()) == [config]


def test_mdm_add_updates_versioned_config_after_output_separation(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "studies/mdm/simulate.py"
    spec = importlib.util.spec_from_file_location("external_mdm_add", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(data_paths, "SOFTWARE_ROOT", tmp_path / "software")
    monkeypatch.setenv("WEIBULL_DATA_ROOT", str(tmp_path / "data"))
    written = []
    monkeypatch.setattr(module, "update_config_md", lambda filename, config: written.append(filename))
    monkeypatch.setattr(module, "cmd_generate", lambda *args: None)
    config = {"params": [{"id": "beta", "state": "discrete", "discreteValues": [2.0]}]}
    output = data_paths.public_data_path("studies", "mdm", "demo1")
    module.cmd_add(SimpleNamespace(add="beta=3", study_id="demo1"), config, output, output / "chunks")
    assert written == [data_paths.study_config_path("mdm", "demo1")]
    assert config["params"][0]["discreteValues"] == [2.0, 3.0]


def test_chunk_rename_backup_stays_outside_software(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[1] / "studies/scripts/rename_chunks.py"
    spec = importlib.util.spec_from_file_location("external_rename_chunks", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("WEIBULL_DATA_ROOT", str(tmp_path / "data"))
    source = data_paths.public_data_path("studies", "mdm", "demo1", "chunks", "sample.csv")
    source.parent.mkdir(parents=True)
    source.write_text("sim_id,value\n1,42\n", encoding="utf-8")
    backup = tmp_path / "weibull-backups/chunks_backup/mdm/demo1/chunks/sample.csv"
    module.create_backup(dry_run=True)
    assert not backup.exists()
    module.create_backup(dry_run=False)
    assert backup.read_bytes() == source.read_bytes()
