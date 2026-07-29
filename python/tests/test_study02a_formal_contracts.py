from dataclasses import replace
import hashlib
import json
import os
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


def _read_trace(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _write_trace(path: Path, records: list[dict]) -> str:
    path.write_bytes(b"".join(
        (json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        for record in records
    ))
    return _sha256(path)


def _trace(tmp_path: Path, module_id: str) -> tuple[Path, str, str]:
    from study02a.selection import (
        CandidateSpec,
        DecisionSpec,
        FitEvaluation,
        SupportKey,
        build_selection_trace,
    )
    from study02a.formal_contracts import write_selection_trace

    run_id = f"G3-{module_id.replace('-', '')}-formal-v1"
    path = tmp_path / f"{module_id}-selection-trace.jsonl"
    keys = (SupportKey(10, 420001),)

    def candidate(candidate_id: str, score: float, checkpoint: str) -> CandidateSpec:
        fit_id = f"fit-{candidate_id}"
        return CandidateSpec(
            decision_id="baseline", candidate_id=candidate_id, selection_rule="lowest_aggregate",
            tie_break_key=(candidate_id,), support_keys=keys, expected_fit_ids=(fit_id,),
            fit_id_by_support={keys[0]: fit_id}, approved_seeds=(420001,),
        )

    spec = DecisionSpec(
        module_id=module_id, decision_id="baseline", axis="architecture",
        selection_rule="lowest_aggregate",
        candidates=(candidate("candidate-1", 0.125, "b" * 64), candidate("candidate-2", 0.25, "c" * 64)),
    )
    evaluations = {
        f"fit-{spec.candidates[0].candidate_id}": FitEvaluation(
            fit_id="fit-candidate-1", support_key=keys[0], failed=False,
            checkpoint_sha256="b" * 64, selection_score=0.125, failure_penalty=0.0),
        f"fit-{spec.candidates[1].candidate_id}": FitEvaluation(
            fit_id="fit-candidate-2", support_key=keys[0], failed=False,
            checkpoint_sha256="c" * 64, selection_score=0.25, failure_penalty=0.0),
    }
    records, _diagnostics = build_selection_trace(
        module_id=module_id, run_id=run_id, specs=(spec,), evaluations_by_fit=evaluations,
    )
    return path, write_selection_trace(path, records), run_id


def _predecessor_binding(tmp_path: Path, module_id: str) -> dict:
    from study02a.formal_config import load_effective_formal_config
    from study02a.formal_contracts import publish_selection_receipt

    trace_path, trace_sha256, run_id = _trace(tmp_path, module_id)
    receipt_path = tmp_path / f"{module_id}-selection-receipt.json"
    ledger_path = tmp_path / "formal-selection-ledger.jsonl"
    binding = publish_selection_receipt(
        receipt_path=receipt_path,
        ledger_path=ledger_path,
        module_id=module_id,
        run_id=run_id,
        trace_path=trace_path,
        trace_sha256=trace_sha256,
        effective_config=load_effective_formal_config(STUDY_ROOT),
        code_commit="b" * 40,
    )
    result = {
        "module_id": module_id,
        "run_id": run_id,
        "trace_path": trace_path,
        "trace_sha256": trace_sha256,
        "receipt_path": receipt_path,
        "receipt_sha256": binding["receipt_sha256"],
        "ledger_path": ledger_path,
        "selection_code_commit": "b" * 40,
    }
    # Control-plane v2: A-E1 and A-E3 predecessors publish a staged_resolution_ledger; the
    # downstream manifest binds its SHA. Publish a syntactically + cryptographically valid
    # chained ledger through the production primitives (``_build_stage_record`` +
    # ``_append_stage_record``) so ``_validate_predecessor`` exercises the real path.
    staged_ledger_path = _publish_valid_staged_ledger(
        tmp_path=tmp_path,
        module_id=module_id,
        run_id=run_id,
        trace_sha256=trace_sha256,
    )
    if staged_ledger_path is not None:
        result["staged_ledger_path"] = staged_ledger_path
        result["staged_ledger_sha256"] = _sha256(staged_ledger_path)
    return result


# Per-module canonical (stage, route) sequences for the staged ledger fixture (mirrors the
# FC ``_STAGED_LEDGER_SEQUENCES`` constant; duplicated here only to keep the contracts test
# free of import cycles with the executor). Each entry pairs with a minimal placeholder
# resolution payload that satisfies the chain validator (only A-E1's ``baseline_input``
# stage requires a specific resolution value: ``selected:F2_or_V`` in {F2, V}).
_STAGED_FIXTURE_SEQUENCES = {
    "A-E1": (
        ("stage1", "F2"), ("stage2", "F2"), ("winner_retrain", "F2"),
        ("stage1", "V"), ("stage2", "V"), ("winner_retrain", "V"),
        ("baseline_input", None), ("final_aliases", None),
    ),
    "A-E3": (
        ("loss", None),
        ("stage1", "F2_or_V"), ("stage2", "F2_or_V"),
        ("stage1", "S"), ("stage2", "S"),
        ("output_form", None),
        ("shared_winner_retrain", "S"),
        ("baseline_route", None),
        ("n_strategy", None),
        ("final_aliases", None),
    ),
}


def _publish_valid_staged_ledger(
    *, tmp_path: Path, module_id: str, run_id: str, trace_sha256: str,
) -> Path | None:
    """Publish a cryptographically valid staged_resolution_ledger for an A-E1 or A-E3 predecessor.

    Builds each record with the SAME canonical bytes + SHA discipline as the production
    ``formal_executor._build_stage_record`` (mirrored here so the contracts test stays free of
    the executor's heavy import chain). The validator in FC is the single authority: it must
    accept what the real resolver would write. Returns ``None`` for modules that do not publish
    a staged ledger (so legacy callers stay valid)."""
    from study02a.formal_config import load_effective_formal_config
    from study02a.formal_contracts import _canonical_json_bytes, _STAGED_LEDGER_RECORD_VERSION

    sequence = _STAGED_FIXTURE_SEQUENCES.get(module_id)
    if sequence is None:
        return None
    run_dir = tmp_path / module_id / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    effective = load_effective_formal_config(STUDY_ROOT)
    zero = "0" * 64

    def _record(stage: str, route: str | None, previous_sha: str,
                input_payload: dict, resolution: dict) -> dict:
        resolution_sha = hashlib.sha256(_canonical_json_bytes(dict(resolution))).hexdigest()
        core = {
            "record_version": _STAGED_LEDGER_RECORD_VERSION,
            "module_id": module_id,
            "run_id": run_id,
            "code_commit": ("b" * 40).lower(),
            "effective_config_sha256": effective.effective_config_sha256,
            "selection_trace_sha256": trace_sha256,
            "stage": stage,
            "route": route,
            "previous_record_sha256": previous_sha,
            "input": dict(input_payload),
            "resolution": dict(resolution),
            "resolution_sha256": resolution_sha,
        }
        record_sha = hashlib.sha256(_canonical_json_bytes(core)).hexdigest()
        return {**core, "record_sha256": record_sha}

    records: list[dict] = []
    previous_sha = zero
    for stage, route in sequence:
        if module_id == "A-E1" and stage == "baseline_input":
            resolution = {"selected:F2_or_V": "V"}
        elif module_id == "A-E1" and stage == "final_aliases":
            resolution = {
                "selected:A-E1_loss": "transformed_train_z_huber",
                "selected:A-E1_architecture": "m12",
                "selected:A-E1_optimizer": "o3",
            }
        elif module_id == "A-E1" and stage.startswith("stage"):
            resolution = {
                "selected_top_1": "m01", "selected_top_2": "m02",
                "selected_top_3": "m03", "selected_top_4": "m04",
            }
        elif module_id == "A-E1":
            resolution = {
                "selected:A-E1_loss": "transformed_train_z_huber",
                "selected:A-E1_architecture": "m12",
                "selected:A-E1_optimizer": "o3",
            }
        else:  # A-E3 placeholder resolutions (chain shape only; A-E3 resolver is wired in C4)
            resolution = {f"{stage}:{route or 'none'}": "placeholder"}
        record = _record(stage, route, previous_sha, {"fixture": "test_staged_ledger"}, resolution)
        records.append(record)
        previous_sha = record["record_sha256"]
    staged_ledger_path = run_dir / "staged_resolution_ledger.jsonl"
    staged_ledger_path.write_bytes(b"".join(_canonical_json_bytes(record) for record in records))
    return staged_ledger_path


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
        kwargs.update(
            rule_ids=("A-E3_loss",),
            fit_ids=("G3-fit-0349",),
            predecessor=_predecessor_binding(tmp_path, "A-E1"),
        )
    elif module_id == "A-E2":
        kwargs.update(
            rule_ids=("A-E2_training_size",),
            fit_ids=("G3-fit-0615",),
            predecessor=_predecessor_binding(tmp_path, "A-E3"),
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

    kwargs = _kwargs(module_id, tmp_path)
    manifest = build_formal_manifest(**kwargs)

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
    assert manifest["matrix"]["rule_ids"] == list(kwargs["rule_ids"])
    assert manifest["matrix"]["fit_ids"] == list(kwargs["fit_ids"])
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
    with pytest.raises(ValueError, match="exact frozen repository path"):
        build_formal_manifest(**kwargs)


def test_matrix_must_have_exactly_820_rows(tmp_path):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs("A-E1", tmp_path)
    kwargs["matrix_path"] = _copy_matrix(tmp_path)
    lines = kwargs["matrix_path"].read_text(encoding="utf-8").splitlines()
    kwargs["matrix_path"].write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="exact frozen repository path"):
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
    with pytest.raises(ValueError, match="exact frozen repository path"):
        build_formal_manifest(**kwargs)


def test_matrix_all_rows_must_remain_sealed(tmp_path):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs("A-E1", tmp_path)
    kwargs["matrix_path"] = _copy_matrix(tmp_path)
    text = kwargs["matrix_path"].read_text(encoding="utf-8")
    kwargs["matrix_path"].write_text(text.replace(",sealed\n", ",consumed\n", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="exact frozen repository path"):
        build_formal_manifest(**kwargs)


def test_predecessor_trace_hardlink_is_rejected(tmp_path):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs("A-E3", tmp_path)
    trace_path = Path(kwargs["predecessor"]["trace_path"])
    alias = tmp_path / "trace-hardlink.jsonl"
    os.link(trace_path, alias)
    try:
        with pytest.raises(ValueError, match="hardlinked|plain"):
            build_formal_manifest(**kwargs)
    finally:
        alias.unlink(missing_ok=True)


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


def test_selection_receipt_rejects_ownership_only_trace(tmp_path):
    from study02a.formal_config import load_effective_formal_config
    from study02a.formal_contracts import publish_selection_receipt

    trace_path = tmp_path / "selection-trace.jsonl"
    trace_path.write_text('{"module_id":"A-E1","run_id":"run-1"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="selection trace"):
        publish_selection_receipt(
            receipt_path=tmp_path / "receipt.json",
            ledger_path=tmp_path / "ledger.jsonl",
            module_id="A-E1",
            run_id="run-1",
            trace_path=trace_path,
            trace_sha256=_sha256(trace_path),
            effective_config=load_effective_formal_config(STUDY_ROOT),
            code_commit="b" * 40,
        )
    assert not (tmp_path / "receipt.json").exists()
    assert not (tmp_path / "ledger.jsonl").exists()


@pytest.mark.parametrize("case", ["duplicate_pair", "no_winner", "multiple_winners", "nonfinite_score"])
def test_selection_receipt_rejects_invalid_decision_contract(tmp_path, case):
    from study02a.formal_config import load_effective_formal_config
    from study02a.formal_contracts import publish_selection_receipt

    trace_path, _, run_id = _trace(tmp_path, "A-E1")
    records = _read_trace(trace_path)
    if case == "duplicate_pair":
        records.append(dict(records[0]))
    elif case == "no_winner":
        records[0]["selected"] = False
    elif case == "multiple_winners":
        records[1]["selected"] = True
    else:
        records[0]["validation_score"] = float("inf")
    digest = _write_trace(trace_path, records)

    with pytest.raises(ValueError, match="selection trace"):
        publish_selection_receipt(
            receipt_path=tmp_path / "receipt.json",
            ledger_path=tmp_path / "ledger.jsonl",
            module_id="A-E1",
            run_id=run_id,
            trace_path=trace_path,
            trace_sha256=digest,
            effective_config=load_effective_formal_config(STUDY_ROOT),
            code_commit="b" * 40,
        )


def test_selection_receipt_atomically_binds_trace_and_unique_ledger_entry(tmp_path):
    predecessor = _predecessor_binding(tmp_path, "A-E1")

    receipt = json.loads(predecessor["receipt_path"].read_text(encoding="utf-8"))
    ledger = [json.loads(line) for line in predecessor["ledger_path"].read_text(encoding="utf-8").splitlines()]
    assert receipt["selection_trace_sha256"] == predecessor["trace_sha256"]
    assert receipt["effective_config_sha256"] == "44fba47c7af66166e1d3f11890299a8bb5c352ac1abf3447cd00cfd3acf97449"
    assert receipt["code_commit"] == predecessor["selection_code_commit"]
    assert len(ledger) == 1
    assert ledger[0]["receipt_sha256"] == predecessor["receipt_sha256"]


@pytest.mark.parametrize("collision", ["ledger_trace", "ledger_receipt", "receipt_trace"])
def test_selection_publisher_rejects_identical_path_aliases_without_side_effects(tmp_path, collision):
    from study02a.formal_config import load_effective_formal_config
    from study02a.formal_contracts import publish_selection_receipt

    trace_path, trace_sha256, run_id = _trace(tmp_path, "A-E1")
    receipt_path = tmp_path / "receipt.json"
    ledger_path = tmp_path / "ledger.jsonl"
    if collision == "ledger_trace":
        ledger_path = trace_path
    elif collision == "ledger_receipt":
        ledger_path = receipt_path
    else:
        receipt_path = trace_path
    before_files = {path: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}

    with pytest.raises(ValueError, match="paths must be distinct"):
        publish_selection_receipt(
            receipt_path=receipt_path,
            ledger_path=ledger_path,
            module_id="A-E1",
            run_id=run_id,
            trace_path=trace_path,
            trace_sha256=trace_sha256,
            effective_config=load_effective_formal_config(STUDY_ROOT),
            code_commit="b" * 40,
        )

    assert {path: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()} == before_files
    assert trace_path.read_bytes() == before_files[trace_path]
    assert not list(tmp_path.glob("*.lock"))


def test_selection_publisher_rejects_relative_absolute_alias_before_writes(tmp_path, monkeypatch):
    from study02a.formal_config import load_effective_formal_config
    from study02a.formal_contracts import publish_selection_receipt

    trace_path, trace_sha256, run_id = _trace(tmp_path, "A-E1")
    receipt_path = Path("binding.json")
    ledger_path = (tmp_path / "binding.json").resolve()
    before_trace = trace_path.read_bytes()
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="paths must be distinct"):
        publish_selection_receipt(
            receipt_path=receipt_path,
            ledger_path=ledger_path,
            module_id="A-E1",
            run_id=run_id,
            trace_path=trace_path,
            trace_sha256=trace_sha256,
            effective_config=load_effective_formal_config(STUDY_ROOT),
            code_commit="b" * 40,
        )

    assert trace_path.read_bytes() == before_trace
    assert not (tmp_path / "binding.json").exists()
    assert not list(tmp_path.glob("*.lock"))


def test_selection_publisher_rejects_existing_hardlink_alias_without_trace_mutation(tmp_path):
    from study02a.formal_config import load_effective_formal_config
    from study02a.formal_contracts import publish_selection_receipt

    trace_path, trace_sha256, run_id = _trace(tmp_path, "A-E1")
    ledger_path = tmp_path / "ledger-hardlink.jsonl"
    try:
        import os

        os.link(trace_path, ledger_path)
    except OSError as exc:
        pytest.skip(f"hard links unavailable: {exc}")
    before_trace = trace_path.read_bytes()
    before_files = {path: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}

    with pytest.raises(ValueError, match="paths must be distinct"):
        publish_selection_receipt(
            receipt_path=tmp_path / "receipt.json",
            ledger_path=ledger_path,
            module_id="A-E1",
            run_id=run_id,
            trace_path=trace_path,
            trace_sha256=trace_sha256,
            effective_config=load_effective_formal_config(STUDY_ROOT),
            code_commit="b" * 40,
        )

    assert trace_path.read_bytes() == before_trace
    assert {path: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()} == before_files
    assert not list(tmp_path.glob("*.lock"))


@pytest.mark.parametrize("case", ["duplicate", "conflict"])
def test_selection_publisher_rejects_duplicate_or_conflicting_run_binding(tmp_path, case):
    from study02a.formal_config import load_effective_formal_config
    from study02a.formal_contracts import publish_selection_receipt

    predecessor = _predecessor_binding(tmp_path, "A-E1")
    trace_path = predecessor["trace_path"]
    trace_sha256 = predecessor["trace_sha256"]
    if case == "conflict":
        records = _read_trace(trace_path)
        records[0]["validation_score"] = 0.124
        trace_sha256 = _write_trace(trace_path, records)

    with pytest.raises(ValueError, match="binding"):
        publish_selection_receipt(
            receipt_path=tmp_path / "second-receipt.json",
            ledger_path=predecessor["ledger_path"],
            module_id="A-E1",
            run_id=predecessor["run_id"],
            trace_path=trace_path,
            trace_sha256=trace_sha256,
            effective_config=load_effective_formal_config(STUDY_ROOT),
            code_commit="b" * 40,
        )
    assert not (tmp_path / "second-receipt.json").exists()


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


def test_downstream_rejects_recomputed_trace_sha_for_same_receipted_run(tmp_path):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs("A-E3", tmp_path)
    predecessor = kwargs["predecessor"]
    records = _read_trace(predecessor["trace_path"])
    records[0]["validation_score"] = 0.124
    predecessor["trace_sha256"] = _write_trace(predecessor["trace_path"], records)

    with pytest.raises(ValueError, match="receipt"):
        build_formal_manifest(**kwargs)


@pytest.mark.parametrize("case", ["receipt_mismatch", "ledger_mismatch", "ledger_duplicate", "ledger_conflict"])
def test_downstream_rejects_receipt_or_ledger_binding_failure(tmp_path, case):
    from study02a.formal_contracts import build_formal_manifest

    kwargs = _kwargs("A-E3", tmp_path)
    predecessor = kwargs["predecessor"]
    if case == "receipt_mismatch":
        receipt = json.loads(predecessor["receipt_path"].read_text(encoding="utf-8"))
        receipt["selection_trace_sha256"] = "0" * 64
        predecessor["receipt_path"].write_text(json.dumps(receipt) + "\n", encoding="utf-8")
        predecessor["receipt_sha256"] = _sha256(predecessor["receipt_path"])
    else:
        ledger_path = predecessor["ledger_path"]
        rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
        if case == "ledger_mismatch":
            rows[0]["receipt_sha256"] = "0" * 64
        elif case == "ledger_duplicate":
            rows.append(dict(rows[0]))
        else:
            conflict = dict(rows[0])
            conflict["selection_trace_sha256"] = "0" * 64
            rows.append(conflict)
        ledger_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    with pytest.raises(ValueError, match="receipt|ledger|binding"):
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
