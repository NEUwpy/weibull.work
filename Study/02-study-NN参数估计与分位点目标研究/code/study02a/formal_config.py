"""Fail-closed loader for the approved Study/02 formal training contract."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .config import load_frozen_config


AMENDMENT_NAME = "A-g3-pilot-amendment-v4.json"
AMENDMENT_HASH_NAME = "A-g3-pilot-amendment-v4.sha256"
APPROVED_AMENDMENT_ID = "A-G3-pilot-amendment-v4"
APPROVED_AMENDMENT_SHA256 = "164e72658669dbb57f6dab8b1fc80099bd319f1fa327d5dda60cb61cb929ee38"
APPROVED_OVERRIDE_PATH = "search.training.max_epochs"
APPROVED_BASE_MAX_EPOCHS = 500
APPROVED_MAX_EPOCHS = 100
APPROVED_MIN_EPOCHS = 50
APPROVED_PATIENCE = 40

_REVISION_KEYS = {
    "base_search_id",
    "override",
    "old_value",
    "new_value",
    "unchanged",
    "ceiling_hit_rule",
    "requires_oracle_approval_before_formal",
}


@dataclass(frozen=True)
class EffectiveFormalConfig:
    """Immutable provenance and epoch contract for every Study/02 formal fit."""

    base_protocol_id: str
    base_protocol_sha256: str
    base_search_id: str
    base_search_sha256: str
    amendment_id: str
    amendment_sha256: str
    effective_config_sha256: str
    max_epochs: int
    min_epochs: int
    patience: int
    base_max_epochs: int
    approved_override_paths: tuple[str, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"Missing approved amendment {label}: {path.name}")


def _validate_amendment_semantics(amendment: dict[str, Any], base_search_id: str) -> None:
    if amendment.get("amendment_id") != APPROVED_AMENDMENT_ID:
        raise ValueError("Unexpected amendment ID")

    revision = amendment.get("protocol_revision")
    if not isinstance(revision, dict):
        raise ValueError("Missing amendment protocol revision")

    extra_keys = set(revision) - _REVISION_KEYS
    if extra_keys:
        raise ValueError(f"Unapproved additional override metadata: {sorted(extra_keys)}")
    missing_keys = _REVISION_KEYS - set(revision)
    if missing_keys:
        raise ValueError(f"Missing amendment protocol revision fields: {sorted(missing_keys)}")

    if revision.get("base_search_id") != base_search_id:
        raise ValueError("Unexpected base search ID in amendment")
    if revision.get("override") != APPROVED_OVERRIDE_PATH:
        raise ValueError("Unexpected override path")
    if revision.get("old_value") != APPROVED_BASE_MAX_EPOCHS:
        raise ValueError("Unexpected override old value")
    if revision.get("new_value") != APPROVED_MAX_EPOCHS:
        raise ValueError("Unexpected override new value")

    unchanged = revision.get("unchanged")
    if not isinstance(unchanged, dict):
        raise ValueError("Missing unchanged training contract")
    if unchanged.get("min_epochs") != APPROVED_MIN_EPOCHS:
        raise ValueError("Unexpected unchanged min_epochs")
    if unchanged.get("early_stopping_patience") != APPROVED_PATIENCE:
        raise ValueError("Unexpected unchanged early_stopping_patience")


def _verify_amendment(config_dir: Path, base_search_id: str) -> tuple[dict[str, Any], str]:
    amendment_path = config_dir / AMENDMENT_NAME
    manifest_path = config_dir / AMENDMENT_HASH_NAME
    _require_file(amendment_path, "file")
    _require_file(manifest_path, "SHA manifest")

    try:
        amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid approved amendment file: {exc}") from exc
    if not isinstance(amendment, dict):
        raise ValueError("Approved amendment must be a JSON object")
    _validate_amendment_semantics(amendment, base_search_id)

    fields = manifest_path.read_text(encoding="utf-8").split()
    if len(fields) != 2 or fields[1].lstrip("*") != AMENDMENT_NAME:
        raise ValueError("Approved amendment SHA manifest must contain exactly the amendment file")
    manifest_digest = fields[0].lower()
    actual_digest = _sha256(amendment_path)
    if manifest_digest != APPROVED_AMENDMENT_SHA256 or actual_digest != APPROVED_AMENDMENT_SHA256:
        raise ValueError(
            "Amendment SHA-256 mismatch: "
            f"approved {APPROVED_AMENDMENT_SHA256}, manifest {manifest_digest}, actual {actual_digest}"
        )
    return amendment, actual_digest


def _canonical_effective_hash(protocol: dict[str, Any], search: dict[str, Any]) -> str:
    canonical = json.dumps(
        {"protocol": protocol, "search": search},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def load_effective_formal_config(
    study_root: Path,
    *,
    requested_max_epochs: int | None = None,
) -> EffectiveFormalConfig:
    """Load the sole approved Study/02 formal config without writing any files."""

    if requested_max_epochs not in (None, APPROVED_MAX_EPOCHS):
        raise ValueError(
            f"requested_max_epochs must be None or exactly {APPROVED_MAX_EPOCHS}; "
            f"got {requested_max_epochs!r}"
        )

    study_root = Path(study_root)
    frozen = load_frozen_config(study_root)
    protocol_id = frozen.protocol.get("protocol_id")
    search_id = frozen.search.get("search_id")
    if not isinstance(protocol_id, str) or not isinstance(search_id, str):
        raise ValueError("Frozen Study02 config identifiers are missing")

    training = frozen.search.get("training")
    if not isinstance(training, dict):
        raise ValueError("Frozen Study02 search training contract is missing")
    if training.get("max_epochs") != APPROVED_BASE_MAX_EPOCHS:
        raise ValueError("Frozen Study02 base max epochs must be 500")
    if training.get("min_epochs") != APPROVED_MIN_EPOCHS:
        raise ValueError("Frozen Study02 base min epochs must be 50")
    if training.get("early_stopping_patience") != APPROVED_PATIENCE:
        raise ValueError("Frozen Study02 base patience must be 40")

    amendment, amendment_sha256 = _verify_amendment(study_root / "configs", search_id)
    effective_search = deepcopy(frozen.search)
    effective_search["training"]["max_epochs"] = amendment["protocol_revision"]["new_value"]
    effective_max_epochs = effective_search["training"]["max_epochs"]
    if effective_max_epochs == APPROVED_BASE_MAX_EPOCHS or effective_max_epochs != APPROVED_MAX_EPOCHS:
        raise ValueError("Effective formal config retains an unapproved max epochs value")

    return EffectiveFormalConfig(
        base_protocol_id=protocol_id,
        base_protocol_sha256=frozen.protocol_sha256,
        base_search_id=search_id,
        base_search_sha256=frozen.search_sha256,
        amendment_id=amendment["amendment_id"],
        amendment_sha256=amendment_sha256,
        effective_config_sha256=_canonical_effective_hash(frozen.protocol, effective_search),
        max_epochs=effective_max_epochs,
        min_epochs=training["min_epochs"],
        patience=training["early_stopping_patience"],
        base_max_epochs=training["max_epochs"],
        approved_override_paths=(APPROVED_OVERRIDE_PATH,),
    )
