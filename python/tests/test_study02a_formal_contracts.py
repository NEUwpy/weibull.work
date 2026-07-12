from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
MATRIX = STUDY_ROOT / "artifacts" / "pilot" / "G3-matrix" / "experiment_matrix.csv"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _trace(tmp_path: Path, module_id: str) -> tuple[Path, str, str]:
    run_id = f"G3-{module_id.replace('-', '')}-formal-v1"
    path = tmp_path / f"{module_id}-selection-trace.jsonl"
    path.write_text(
        json.dumps({"module_id": module_id, "run_id": run_id, "selected": "candidate-1"}) + "\n",
        encoding="utf-8",
    )
    return path, _sha256(path), run_id


def _kwargs(module_id: str, tmp_path: Path) -> dict:
    from study02a.formal_config import load_effective_formal_config

    kwargs = {
        "effective_config": load_effective_formal_config(STUDY_ROOT),
        "module_id": module_id,
        "run_id": f"G3-{module_id.replace('-', '')}-formal-v1",
        "code_commit": "a" * 40,
        "matrix_path": MATRIX,
        "role_namespaces": {"training": "study02/formal/train", "validation": "study02/formal/validation"},
        "screening_seeds": (420001, 420002, 420003),
        "formal_seeds": tuple(range(420101, 420111)),
    }
    if module_id == "A-E1":
        kwargs.update(rule_ids=("A-E1_historical",), fit_ids=("G3-fit-0000",), predecessor=None)
    elif module_id == "A-E3":
        path, digest, predecessor_run_id = _trace(tmp_path, "A-E1")
        kwargs.update(
            rule_ids=("A-E3_loss",),
            fit_ids=("G3-fit-0349",),
            predecessor={
                "module_id": "A-E1",
                "run_id": predecessor_run_id,
                "trace_path": path,
                "trace_sha256": digest,
            },
        )
    elif module_id == "A-E2":
        path, digest, predecessor_run_id = _trace(tmp_path, "A-E3")
        kwargs.update(
            rule_ids=("A-E2_training_size",),
            fit_ids=("G3-fit-0615",),
            predecessor={
                "module_id": "A-E3",
                "run_id": predecessor_run_id,
                "trace_path": path,
                "trace_sha256": digest,
            },
        )
    else:
        raise AssertionError(module_id)
    return kwargs


@pytest.mark.parametrize(
    ("module_id", "expected_predecessor"),
    [("A-E1", "none"), ("A-E3", "A-E1"), ("A-E2", "A-E3")],
)
def test_builds_complete_sealed_manifest_for_formal_sequence(tmp_path, module_id, expected_predecessor):
    from study02a.formal_contracts import build_formal_manifest

    manifest = build_formal_manifest(**_kwargs(module_id, tmp_path))

    assert manifest["module_id"] == module_id
    assert manifest["base_protocol"] == {
        "id": "A-G2-v1",
        "sha256": "f82e078051d760d7c9c11ece54b8fae7360c6db1aef3229a97b4fcd92ae01a11",
    }
    assert manifest["base_search"]["id"] == "A-G2-search-v1"
    assert manifest["amendment"]["id"] == "A-G3-pilot-amendment-v4"
    assert manifest["effective_config"]["max_epochs"] == 100
    assert manifest["effective_config"]["min_epochs"] == 50
    assert manifest["effective_config"]["patience"] == 40
    assert manifest["matrix"]["sha256"] == "fad701af2e2084bf7ce8f678d642410af58057b4ae33029c9150e50971fdf6b1"
    assert manifest["matrix"]["row_count"] == 820
    assert manifest["matrix"]["rule_ids"] == list(_kwargs(module_id, tmp_path)["rule_ids"])
    assert manifest["matrix"]["fit_ids"] == list(_kwargs(module_id, tmp_path)["fit_ids"])
    assert manifest["code_commit"] == "a" * 40
    assert manifest["role_namespaces"]["training"] != manifest["role_namespaces"]["validation"]
    assert manifest["seeds"]["screening"] == [420001, 420002, 420003]
    assert manifest["seeds"]["formal"] == list(range(420101, 420111))
    assert manifest["test_state"] == "sealed"
    assert manifest["predecessor"]["module_id"] == expected_predecessor


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("run_id", "", "run_id"),
        ("code_commit", "not-a-commit", "code_commit"),
        ("role_namespaces", {"training": "same", "validation": "same"}, "namespace"),
        ("screening_seeds", (), "screening"),
        ("formal_seeds", (), "formal"),
    ],
)
def test_missing_or_malformed_required_manifest_fields_reject(tmp_path, field, value, match):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs("A-E1", tmp_path)
    kwargs[field] = value
    with pytest.raises(ValueError, match=match):
        build_formal_manifest(**kwargs)


def test_test_state_cannot_be_caller_overridden(tmp_path):
    from study02a.formal_contracts import build_formal_manifest

    with pytest.raises(TypeError, match="test_state"):
        build_formal_manifest(**_kwargs("A-E1", tmp_path), test_state="consumed")


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("max_epochs", 500, "max_epochs"),
        ("min_epochs", 49, "min_epochs"),
        ("patience", 39, "patience"),
        ("effective_config_sha256", "bad", "effective_config_sha256"),
    ],
)
def test_effective_config_mismatch_rejects(tmp_path, field, value, match):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs("A-E1", tmp_path)
    kwargs["effective_config"] = replace(kwargs["effective_config"], **{field: value})
    with pytest.raises(ValueError, match=match):
        build_formal_manifest(**kwargs)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("base_protocol_id", "forged-protocol"),
        ("base_protocol_sha256", "0" * 64),
        ("base_search_id", "forged-search"),
        ("base_search_sha256", "1" * 64),
        ("amendment_id", "forged-amendment"),
        ("amendment_sha256", "2" * 64),
        ("effective_config_sha256", "3" * 64),
    ],
)
def test_well_formed_but_unapproved_provenance_rejects(tmp_path, field, value):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs("A-E1", tmp_path)
    kwargs["effective_config"] = replace(kwargs["effective_config"], **{field: value})
    with pytest.raises(ValueError, match=field):
        build_formal_manifest(**kwargs)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("screening_seeds", (420001, 420002), "screening"),
        ("formal_seeds", tuple(range(420101, 420110)), "formal"),
    ],
)
def test_seed_contract_mismatch_rejects(tmp_path, field, value, match):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs("A-E1", tmp_path)
    kwargs[field] = value
    with pytest.raises(ValueError, match=match):
        build_formal_manifest(**kwargs)


def _copy_matrix(tmp_path: Path) -> Path:
    path = tmp_path / "experiment_matrix.csv"
    shutil.copy2(MATRIX, path)
    return path


def test_matrix_byte_hash_mismatch_rejects(tmp_path):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs("A-E1", tmp_path)
    kwargs["matrix_path"] = _copy_matrix(tmp_path)
    kwargs["matrix_path"].write_bytes(kwargs["matrix_path"].read_bytes() + b"\n")
    with pytest.raises(ValueError, match="matrix SHA-256"):
        build_formal_manifest(**kwargs)


def test_matrix_must_have_exactly_820_rows(tmp_path):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs("A-E1", tmp_path)
    kwargs["matrix_path"] = _copy_matrix(tmp_path)
    lines = kwargs["matrix_path"].read_text(encoding="utf-8").splitlines()
    kwargs["matrix_path"].write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly 820"):
        build_formal_manifest(**kwargs)


def test_matrix_fit_ids_must_be_unique(tmp_path):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs("A-E1", tmp_path)
    kwargs["matrix_path"] = _copy_matrix(tmp_path)
    lines = kwargs["matrix_path"].read_text(encoding="utf-8").splitlines()
    duplicate = lines[1].split(",")
    final = lines[-1].split(",")
    final[0] = duplicate[0]
    lines[-1] = ",".join(final)
    kwargs["matrix_path"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unique fit_id"):
        build_formal_manifest(**kwargs)


def test_matrix_all_rows_must_remain_sealed(tmp_path):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs("A-E1", tmp_path)
    kwargs["matrix_path"] = _copy_matrix(tmp_path)
    text = kwargs["matrix_path"].read_text(encoding="utf-8")
    kwargs["matrix_path"].write_text(text.replace(",sealed\n", ",consumed\n", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="sealed"):
        build_formal_manifest(**kwargs)


@pytest.mark.parametrize(
    ("rule_ids", "fit_ids", "match"),
    [
        ((), (), "non-empty"),
        (("missing-rule",), ("G3-fit-0000",), "rule"),
        (("A-E1_historical",), ("missing-fit",), "fit"),
        (("A-E1_controlled",), ("G3-fit-0000",), "agree"),
        (("A-E3_loss",), ("G3-fit-0349",), "module"),
    ],
)
def test_requested_rule_and_fit_subset_must_exist_and_agree(tmp_path, rule_ids, fit_ids, match):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs("A-E1", tmp_path)
    kwargs.update(rule_ids=rule_ids, fit_ids=fit_ids)
    with pytest.raises(ValueError, match=match):
        build_formal_manifest(**kwargs)


def test_ae1_requires_exactly_no_predecessor(tmp_path):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs("A-E1", tmp_path)
    path, digest, predecessor_run_id = _trace(tmp_path, "A-E1-upstream")
    kwargs["predecessor"] = {
        "module_id": "A-E1",
        "run_id": predecessor_run_id,
        "trace_path": path,
        "trace_sha256": digest,
    }
    with pytest.raises(ValueError, match="no predecessor"):
        build_formal_manifest(**kwargs)


@pytest.mark.parametrize(("module_id", "wrong_module"), [("A-E3", "A-E3"), ("A-E2", "A-E1")])
def test_downstream_dependency_rejects_wrong_predecessor_module(tmp_path, module_id, wrong_module):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs(module_id, tmp_path)
    kwargs["predecessor"]["module_id"] = wrong_module
    with pytest.raises(ValueError, match="predecessor module"):
        build_formal_manifest(**kwargs)


@pytest.mark.parametrize("case", ["missing", "malformed_sha", "mismatch", "changed"])
def test_downstream_dependency_rejects_missing_or_unbound_trace(tmp_path, case):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs("A-E3", tmp_path)
    predecessor = kwargs["predecessor"]
    if case == "missing":
        predecessor["trace_path"].unlink()
        match = "trace"
    elif case == "malformed_sha":
        predecessor["trace_sha256"] = "bad"
        match = "SHA-256"
    elif case == "mismatch":
        predecessor["trace_sha256"] = "0" * 64
        match = "SHA-256 mismatch"
    else:
        predecessor["trace_path"].write_text('{"changed":true}\n', encoding="utf-8")
        match = "SHA-256 mismatch"
    with pytest.raises((ValueError, FileNotFoundError), match=match):
        build_formal_manifest(**kwargs)


@pytest.mark.parametrize("case", ["binary", "invalid_json", "wrong_module", "wrong_run"])
def test_downstream_dependency_rejects_malformed_or_misattributed_trace_content(tmp_path, case):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs("A-E3", tmp_path)
    predecessor = kwargs["predecessor"]
    if case == "binary":
        predecessor["trace_path"].write_bytes(b"\xff\xfe")
    elif case == "invalid_json":
        predecessor["trace_path"].write_text("not-json\n", encoding="utf-8")
    elif case == "wrong_module":
        predecessor["trace_path"].write_text(
            json.dumps({"module_id": "A-E2", "run_id": predecessor["run_id"]}) + "\n",
            encoding="utf-8",
        )
    else:
        predecessor["trace_path"].write_text(
            json.dumps({"module_id": "A-E1", "run_id": "different-run"}) + "\n",
            encoding="utf-8",
        )
    predecessor["trace_sha256"] = _sha256(predecessor["trace_path"])

    with pytest.raises(ValueError, match="trace"):
        build_formal_manifest(**kwargs)


def test_validation_failure_writes_nothing_and_cannot_reuse_changed_trace(tmp_path):
    from study02a.formal_contracts import build_and_write_formal_manifest

    destination = tmp_path / "formal" / "manifest.json"
    kwargs = _kwargs("A-E3", tmp_path)
    kwargs["predecessor"]["trace_path"].write_text('{"changed":true}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        build_and_write_formal_manifest(destination, **kwargs)

    assert not destination.exists()
    assert not destination.parent.exists()


def test_atomic_writer_refuses_existing_destination(tmp_path):
    from study02a.formal_contracts import build_and_write_formal_manifest

    destination = tmp_path / "manifest.json"
    destination.write_text("sentinel", encoding="utf-8")
    with pytest.raises(FileExistsError):
        build_and_write_formal_manifest(destination, **_kwargs("A-E1", tmp_path))
    assert destination.read_text(encoding="utf-8") == "sentinel"
