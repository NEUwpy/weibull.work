"""Shared filesystem contract for external result data.

Relative WEIBULL_DATA_ROOT values are relative to the software root, never CWD.
Resolving paths does not create directories or copy any data.
"""

from __future__ import annotations

import os
from pathlib import Path


SOFTWARE_ROOT = Path(__file__).resolve().parent.parent


def data_root() -> Path:
    configured = os.environ.get("WEIBULL_DATA_ROOT", "").strip()
    root = Path(configured).expanduser() if configured else SOFTWARE_ROOT.parent / "weibull-data"
    if not root.is_absolute():
        root = SOFTWARE_ROOT / root
    return root.resolve()


def _within(root: Path, *parts: str) -> Path:
    for part in parts:
        value = Path(part)
        if value.is_absolute() or ".." in value.parts:
            raise ValueError("Data paths must stay inside the configured root")
    path = root.joinpath(*parts).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Data paths must stay inside the configured root")
    return path


def data_path(*parts: str) -> Path:
    """Data-root path; categories such as studies/cases retain their URL layout."""
    return _within(data_root(), *parts)


def public_data_path(*parts: str) -> Path:
    """Published result files share the frontend's <data root>/public layout."""
    return data_path("public", *parts)


def study_config_path(method: str, study_id: str) -> Path:
    """Versioned configuration stays in the software repository."""
    return _within(SOFTWARE_ROOT / "public" / "studies", method, study_id, "config.md")
