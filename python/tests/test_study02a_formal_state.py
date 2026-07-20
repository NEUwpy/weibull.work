from concurrent.futures import ThreadPoolExecutor
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_CODE = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究" / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))

SHA = "a" * 64
COMMIT = "b" * 40
CONFIG_SHA = "c" * 64


def _canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _bundle(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    ceiling = tmp_path / "ceiling.json"
    leakage = tmp_path / "leakage.json"
    oracle = tmp_path / "oracle-review.json"
    ceiling.write_bytes(b"ceiling-evidence\n")
    leakage.write_bytes(b"leakage-evidence\n")
    oracle.write_bytes(b"oracle-review-evidence\n")
    bundle = {
        "bundle_version": "study02-pre-unseal-v3",
        "code_commit": COMMIT,
        "effective_config_sha256": CONFIG_SHA,
        "module_run_ids": {"A-E1": "run-1"},
        "selection_trace_hashes": {"A-E1": "d" * 64},
        "artifact_hashes": {
            str(ceiling): hashlib.sha256(ceiling.read_bytes()).hexdigest(),
            str(leakage): hashlib.sha256(leakage.read_bytes()).hexdigest(),
        },
        "test_state": "sealed",
    }
    path = tmp_path / "bundle.json"
    path.write_bytes(_canonical(bundle))
    return path, bundle


def _approval_kwargs(bundle_path, bundle):
    return dict(
        approval_version="study02-test-unseal-approval-v1",
        decision="APPROVE test unseal",
        code_commit=COMMIT,
        effective_config_sha256=CONFIG_SHA,
        pre_unseal_bundle_sha256=hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
        selection_trace_hashes=bundle["selection_trace_hashes"],
        ceiling_report_sha256=hashlib.sha256((bundle_path.parent / "ceiling.json").read_bytes()).hexdigest(),
        leakage_audit_sha256=hashlib.sha256((bundle_path.parent / "leakage.json").read_bytes()).hexdigest(),
        oracle_review_artifact_sha256=hashlib.sha256((bundle_path.parent / "oracle-review.json").read_bytes()).hexdigest(),
        issued_at="2026-07-13T10:00:00+08:00",
    )


def _initialized(tmp_path):
    from study02a.formal_state import initialize_formal_state, publish_oracle_approval

    bundle_path, bundle = _bundle(tmp_path)
    state_path = tmp_path / "state.json"
    approval_path = tmp_path / "approval.json"
    initialize_formal_state(
        state_path=state_path, bundle_path=bundle_path, run_family_id="G3-formal",
        code_commit=COMMIT, effective_config_sha256=CONFIG_SHA,
        timestamp="2026-07-13T09:00:00+08:00",
    )
    publish_oracle_approval(approval_path=approval_path, **_approval_kwargs(bundle_path, bundle))
    return state_path, bundle_path, approval_path, tmp_path / "ledger.jsonl"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _evidence(bundle_path):
    return {
        "ceiling_report_path": bundle_path.parent / "ceiling.json",
        "leakage_audit_path": bundle_path.parent / "leakage.json",
        "oracle_review_path": bundle_path.parent / "oracle-review.json",
    }


def _call(function, **kwargs):
    for name, path in _evidence(kwargs["bundle_path"]).items():
        kwargs.setdefault(name, path)
    return function(**kwargs)


def test_valid_lifecycle_is_canonical_and_accesses_test_exactly_once(tmp_path):
    from study02a.formal_state import authorize_test_once, consume_test_once

    state, bundle, approval, ledger = _initialized(tmp_path)
    authorized = _call(authorize_test_once,
        state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger,
        timestamp="2026-07-13T11:00:00+08:00",
    )
    approval_sha = hashlib.sha256(approval.read_bytes()).hexdigest()
    assert authorized["state"] == "unsealed_once"
    assert authorized["transition_seq"] == 1
    assert authorized["test_access_count"] == 1
    assert authorized["approval_sha256"] == approval_sha
    assert state.read_bytes() == _canonical(authorized)

    consumed = _call(consume_test_once,
        state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger,
        result_receipt_sha256="2" * 64, failure_receipt_sha256=None,
        timestamp="2026-07-13T12:00:00+08:00",
    )
    assert consumed["state"] == "consumed"
    assert consumed["transition_seq"] == 2
    assert consumed["test_access_count"] == 1
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert [row["transition"] for row in rows] == ["authorize_test_once", "consume_test_once"]
    assert rows[0]["before_state_sha256"] == hashlib.sha256(_canonical({**authorized, "state": "sealed", "transition_seq": 0, "approval_sha256": None, "test_access_count": 0, "updated_at": "2026-07-13T09:00:00+08:00"})).hexdigest()
    assert rows[1]["result_receipt_sha256"] == "2" * 64


def test_initialization_requires_exact_canonical_sealed_bundle_and_no_replace(tmp_path):
    from study02a.formal_state import initialize_formal_state

    bundle_path, bundle = _bundle(tmp_path)
    state = tmp_path / "state.json"
    bundle_path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    with pytest.raises(ValueError, match="canonical"):
        initialize_formal_state(state_path=state, bundle_path=bundle_path, run_family_id="r", code_commit=COMMIT, effective_config_sha256=CONFIG_SHA, timestamp="t")
    assert not state.exists()
    bundle_path.write_bytes(_canonical(bundle))
    initialize_formal_state(state_path=state, bundle_path=bundle_path, run_family_id="r", code_commit=COMMIT, effective_config_sha256=CONFIG_SHA, timestamp="t")
    with pytest.raises(FileExistsError):
        initialize_formal_state(state_path=state, bundle_path=bundle_path, run_family_id="r", code_commit=COMMIT, effective_config_sha256=CONFIG_SHA, timestamp="t")


@pytest.mark.parametrize("mutation", ["decision", "extra", "trace", "bundle", "malformed_sha"])
def test_approval_or_bundle_mismatch_fails_closed(tmp_path, mutation):
    from study02a.formal_state import authorize_test_once

    state, bundle, approval, ledger = _initialized(tmp_path)
    if mutation == "bundle":
        payload = _load(bundle); payload["module_run_ids"]["A-E1"] = "drift"; bundle.write_bytes(_canonical(payload))
    else:
        payload = _load(approval)
        if mutation == "decision": payload["decision"] = "approve"
        elif mutation == "extra": payload["extra"] = True
        elif mutation == "trace": payload["selection_trace_hashes"]["A-E1"] = "0" * 64
        else: payload["ceiling_report_sha256"] = "bad"
        approval.write_bytes(_canonical(payload))
    before = state.read_bytes()
    with pytest.raises(ValueError):
        _call(authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t")
    assert state.read_bytes() == before
    assert not ledger.exists()
    assert not list(tmp_path.glob("*.lock"))


def test_repeat_authorize_and_repeat_consume_fail_closed(tmp_path):
    from study02a.formal_state import authorize_test_once, consume_test_once

    state, bundle, approval, ledger = _initialized(tmp_path)
    _call(authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t1")
    with pytest.raises(ValueError, match="sealed"):
        _call(authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t2")
    _call(consume_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, result_receipt_sha256=None, failure_receipt_sha256="3" * 64, timestamp="t3")
    with pytest.raises(ValueError, match="unsealed_once"):
        _call(consume_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, result_receipt_sha256="4" * 64, failure_receipt_sha256=None, timestamp="t4")


@pytest.mark.parametrize("result,failure", [(None, None), ("2" * 64, "3" * 64), ("bad", None)])
def test_consumption_requires_exactly_one_full_receipt_sha(tmp_path, result, failure):
    from study02a.formal_state import authorize_test_once, consume_test_once

    state, bundle, approval, ledger = _initialized(tmp_path)
    _call(authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t1")
    before = state.read_bytes()
    with pytest.raises(ValueError, match="exactly one|SHA-256"):
        _call(consume_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, result_receipt_sha256=result, failure_receipt_sha256=failure, timestamp="t2")
    assert state.read_bytes() == before


@pytest.mark.parametrize("collision", ["state_bundle", "approval_ledger"])
def test_path_aliases_reject_before_side_effects(tmp_path, collision):
    from study02a.formal_state import authorize_test_once

    state, bundle, approval, ledger = _initialized(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    if collision == "state_bundle": bundle = state.resolve()
    else: ledger = approval
    with pytest.raises(ValueError, match="distinct"):
        _call(authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t")
    assert {p: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before


def test_hardlink_alias_rejects(tmp_path):
    from study02a.formal_state import authorize_test_once

    state, bundle, approval, ledger = _initialized(tmp_path)
    try: os.link(approval, ledger)
    except OSError as exc: pytest.skip(str(exc))
    before = state.read_bytes()
    with pytest.raises(ValueError, match="distinct"):
        _call(authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t")
    assert state.read_bytes() == before


def test_concurrent_double_authorize_has_exactly_one_success(tmp_path):
    from study02a.formal_state import authorize_test_once

    state, bundle, approval, ledger = _initialized(tmp_path)
    def call():
        try:
            _call(authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t")
            return "ok"
        except ValueError:
            return "rejected"
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: call(), range(2)))
    assert sorted(outcomes) == ["ok", "rejected"]
    assert _load(state)["test_access_count"] == 1
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1


def test_ledger_failure_leaves_recoverable_journal_and_never_second_authorization(tmp_path, monkeypatch):
    import study02a.formal_state as formal_state

    state, bundle, approval, ledger = _initialized(tmp_path)
    real_append = formal_state._append_ledger
    monkeypatch.setattr(formal_state, "_append_ledger", lambda *_: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(RuntimeError, match="journal"):
        _call(formal_state.authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t1")
    assert _load(state)["state"] == "unsealed_once"
    journal = state.with_name(state.name + ".journal")
    assert journal.exists()
    monkeypatch.setattr(formal_state, "_append_ledger", real_append)
    with pytest.raises(ValueError, match="sealed"):
        _call(formal_state.authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t2")
    assert not journal.exists()
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1


def test_malformed_state_and_conflicting_duplicate_ledger_reject(tmp_path):
    from study02a.formal_state import authorize_test_once

    state, bundle, approval, ledger = _initialized(tmp_path)
    state.write_text("not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="state"):
        _call(authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t")
    state, bundle, approval, ledger = _initialized(tmp_path / "second")
    _call(authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t1")
    row = json.loads(ledger.read_text(encoding="utf-8")); row["after_state_sha256"] = "0" * 64
    with ledger.open("ab") as handle: handle.write(_canonical(row))
    with pytest.raises(ValueError, match="ledger"):
        _call(authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t2")


def test_ledger_cannot_alias_internal_state_artifacts(tmp_path):
    from study02a.formal_state import authorize_test_once

    state, bundle, approval, _ = _initialized(tmp_path)
    before = state.read_bytes()
    with pytest.raises(ValueError, match="distinct"):
        _call(authorize_test_once,
            state_path=state, bundle_path=bundle, approval_path=approval,
            ledger_path=state.with_name(state.name + ".lock"), timestamp="t",
        )
    assert state.read_bytes() == before
    assert not state.with_name(state.name + ".lock").exists()


def test_canonical_but_invalid_ledger_event_contract_rejects(tmp_path):
    from study02a.formal_state import authorize_test_once

    state, bundle, approval, ledger = _initialized(tmp_path)
    _call(authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t1")
    row = json.loads(ledger.read_text(encoding="utf-8"))
    row["transition_version"] = "forged"
    ledger.write_bytes(_canonical(row))
    with pytest.raises(ValueError, match="ledger"):
        _call(authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t2")


@pytest.mark.parametrize("case", ["rollback", "skip", "extra", "noncanonical"])
def test_rollback_state_skipping_and_noncanonical_state_reject(case, tmp_path):
    from study02a.formal_state import authorize_test_once

    state, bundle, approval, ledger = _initialized(tmp_path)
    payload = _load(state)
    if case == "rollback":
        payload["test_access_count"] = 1
    elif case == "skip":
        payload["state"] = "consumed"; payload["transition_seq"] = 2
    elif case == "extra":
        payload["extra"] = True
    else:
        state.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if case != "noncanonical":
        state.write_bytes(_canonical(payload))
    with pytest.raises(ValueError, match="state"):
        _call(authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t")


def test_changed_valid_approval_sha_rejects_consumption(tmp_path):
    from study02a.formal_state import authorize_test_once, consume_test_once

    state, bundle, approval, ledger = _initialized(tmp_path)
    _call(authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t1")
    payload = _load(approval); payload["issued_at"] = "different-but-valid"; approval.write_bytes(_canonical(payload))
    with pytest.raises(ValueError, match="same approval"):
        _call(consume_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, result_receipt_sha256="2" * 64, failure_receipt_sha256=None, timestamp="t2")


def test_missing_input_and_existing_lock_fail_without_transition(tmp_path):
    from study02a.formal_state import authorize_test_once

    state, bundle, approval, ledger = _initialized(tmp_path)
    before = state.read_bytes(); approval.unlink()
    with pytest.raises(FileNotFoundError):
        _call(authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t")
    assert state.read_bytes() == before
    approval.write_bytes(b"unused")
    lock = state.with_name(state.name + ".lock"); lock.write_text("held", encoding="utf-8")
    with pytest.raises(ValueError, match="locked"):
        _call(authorize_test_once, state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t")
    assert state.read_bytes() == before and lock.read_text(encoding="utf-8") == "held"


def test_state_machine_interface_cannot_receive_or_open_test_data():
    from study02a.formal_state import authorize_test_once, consume_test_once

    assert "test_path" not in inspect.signature(authorize_test_once).parameters
    assert "test_path" not in inspect.signature(consume_test_once).parameters
    for function in (authorize_test_once, consume_test_once):
        for name in ("ceiling_report_path", "leakage_audit_path", "oracle_review_path"):
            assert inspect.signature(function).parameters[name].default is inspect.Parameter.empty


@pytest.mark.parametrize("case", ["role_swap", "unrelated_artifact", "oracle_mismatch"])
def test_transition_binds_each_named_evidence_path_to_exact_bytes(case, tmp_path):
    from study02a.formal_state import authorize_test_once

    state, bundle, approval, ledger = _initialized(tmp_path)
    evidence = _evidence(bundle)
    if case == "role_swap":
        evidence["ceiling_report_path"], evidence["leakage_audit_path"] = (
            evidence["leakage_audit_path"], evidence["ceiling_report_path"]
        )
    elif case == "unrelated_artifact":
        unrelated = tmp_path / "unrelated.json"
        unrelated.write_bytes(evidence["ceiling_report_path"].read_bytes())
        evidence["ceiling_report_path"] = unrelated
    else:
        evidence["oracle_review_path"].write_bytes(b"changed oracle review\n")
    with pytest.raises(ValueError, match="ceiling|leakage|oracle"):
        authorize_test_once(
            state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger,
            timestamp="t", **evidence,
        )
    assert _load(state)["state"] == "sealed"


def test_sealed_state_rejects_forged_existing_seq1(tmp_path):
    from study02a.formal_state import authorize_test_once

    source = _initialized(tmp_path / "source")
    authorize_test_once(
        state_path=source[0], bundle_path=source[1], approval_path=source[2], ledger_path=source[3],
        timestamp="t1", **_evidence(source[1]),
    )
    state, bundle, approval, ledger = _initialized(tmp_path / "target")
    ledger.write_bytes(source[3].read_bytes())
    before = state.read_bytes()
    with pytest.raises(ValueError, match="ledger chain"):
        authorize_test_once(
            state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger,
            timestamp="t2", **_evidence(bundle),
        )
    assert state.read_bytes() == before


def test_unsealed_state_rejects_state_chain_mismatch_before_consume(tmp_path):
    from study02a.formal_state import authorize_test_once, consume_test_once

    state, bundle, approval, ledger = _initialized(tmp_path)
    authorize_test_once(
        state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger,
        timestamp="t1", **_evidence(bundle),
    )
    row = json.loads(ledger.read_text(encoding="utf-8"))
    row["after_state_sha256"] = "0" * 64
    ledger.write_bytes(_canonical(row))
    before = state.read_bytes()
    with pytest.raises(ValueError, match="ledger chain"):
        consume_test_once(
            state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger,
            result_receipt_sha256="2" * 64, failure_receipt_sha256=None,
            timestamp="t2", **_evidence(bundle),
        )
    assert state.read_bytes() == before


def test_existing_next_sequence_rejects_before_state_change(tmp_path):
    from study02a.formal_state import authorize_test_once, consume_test_once

    source = _initialized(tmp_path / "source")
    authorize_test_once(state_path=source[0], bundle_path=source[1], approval_path=source[2], ledger_path=source[3], timestamp="s1", **_evidence(source[1]))
    consume_test_once(state_path=source[0], bundle_path=source[1], approval_path=source[2], ledger_path=source[3], result_receipt_sha256="2" * 64, failure_receipt_sha256=None, timestamp="s2", **_evidence(source[1]))
    source_rows = source[3].read_text(encoding="utf-8").splitlines(keepends=True)

    state, bundle, approval, ledger = _initialized(tmp_path / "target")
    authorize_test_once(state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t1", **_evidence(bundle))
    with ledger.open("ab") as handle:
        handle.write(source_rows[1].encode("utf-8"))
    before = state.read_bytes()
    with pytest.raises(ValueError, match="ledger chain"):
        consume_test_once(state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, result_receipt_sha256="3" * 64, failure_receipt_sha256=None, timestamp="t2", **_evidence(bundle))
    assert state.read_bytes() == before


def test_journal_before_state_replace_is_discarded_and_retry_authorizes_once(tmp_path, monkeypatch):
    import study02a.formal_state as formal_state

    state, bundle, approval, ledger = _initialized(tmp_path)
    real_replace = formal_state._atomic_replace
    monkeypatch.setattr(formal_state, "_atomic_replace", lambda *_: (_ for _ in ()).throw(OSError("crash before replace")))
    with pytest.raises(OSError, match="before replace"):
        formal_state.authorize_test_once(state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t1", **_evidence(bundle))
    assert _load(state)["state"] == "sealed"
    monkeypatch.setattr(formal_state, "_atomic_replace", real_replace)
    result = formal_state.authorize_test_once(state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t2", **_evidence(bundle))
    assert result["state"] == "unsealed_once"
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1


def test_partial_ledger_tail_is_repaired_from_journal_without_second_authorize(tmp_path, monkeypatch):
    import study02a.formal_state as formal_state

    state, bundle, approval, ledger = _initialized(tmp_path)
    real_append = formal_state._append_ledger
    def partial(entry, path):
        with path.open("ab") as handle:
            handle.write(_canonical(entry)[:23])
        raise OSError("partial append")
    monkeypatch.setattr(formal_state, "_append_ledger", partial)
    with pytest.raises(RuntimeError, match="journal"):
        formal_state.authorize_test_once(state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t1", **_evidence(bundle))
    monkeypatch.setattr(formal_state, "_append_ledger", real_append)
    with pytest.raises(ValueError, match="sealed"):
        formal_state.authorize_test_once(state_path=state, bundle_path=bundle, approval_path=approval, ledger_path=ledger, timestamp="t2", **_evidence(bundle))
    assert len(ledger.read_text(encoding="utf-8").splitlines()) == 1
