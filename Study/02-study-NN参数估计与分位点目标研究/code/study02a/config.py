"""Load and verify the frozen Study/02 G2 configuration."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


PROTOCOL_NAME = "A-g2-protocol-v1.json"
SEARCH_NAME = "A-g2-search-v1.json"
HASH_NAME = "A-g2-configs.sha256"


@dataclass(frozen=True)
class FrozenConfig:
    protocol: dict[str, Any]
    search: dict[str, Any]
    protocol_sha256: str
    search_sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_frozen_hashes(study_root: Path) -> dict[str, str]:
    config_dir = Path(study_root) / "configs"
    expected: dict[str, str] = {}
    for line in (config_dir / HASH_NAME).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, filename = line.split(" *", maxsplit=1)
        expected[filename] = digest.lower()

    required = {PROTOCOL_NAME, SEARCH_NAME}
    if set(expected) != required:
        raise ValueError(f"Frozen hash manifest must contain exactly {sorted(required)}")

    for filename, digest in expected.items():
        actual = _sha256(config_dir / filename)
        if actual != digest:
            raise ValueError(f"SHA-256 mismatch for {filename}: expected {digest}, got {actual}")
    return expected


def load_frozen_config(study_root: Path) -> FrozenConfig:
    study_root = Path(study_root)
    hashes = verify_frozen_hashes(study_root)
    config_dir = study_root / "configs"
    protocol = json.loads((config_dir / PROTOCOL_NAME).read_text(encoding="utf-8"))
    search = json.loads((config_dir / SEARCH_NAME).read_text(encoding="utf-8"))
    if protocol.get("status") != "frozen_oracle_approved":
        raise ValueError("Study02 protocol is not frozen and oracle-approved")
    if protocol.get("protocol_id") != "A-G2-v1" or search.get("search_id") != "A-G2-search-v1":
        raise ValueError("Unexpected Study02 frozen configuration identifiers")
    return FrozenConfig(
        protocol=protocol,
        search=search,
        protocol_sha256=hashes[PROTOCOL_NAME],
        search_sha256=hashes[SEARCH_NAME],
    )
