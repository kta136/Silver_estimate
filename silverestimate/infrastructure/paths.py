"""
Utilities for resolving file system paths within the application.

These helpers provide a single place to figure out where bundled assets live
both during local development and in compiled/frozen application builds.
"""

from __future__ import annotations

import sys
from pathlib import Path


def get_app_root() -> Path:
    """
    Return the base directory where application resources are located.

    Nuitka resolves a compiled module's ``__file__`` beneath its standalone or
    one-file payload. During development this falls back to the repository root.
    """
    return Path(__file__).resolve().parents[2]


def get_runtime_root() -> Path:
    """Return the stable directory that owns writable application data."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    compiled = globals().get("__compiled__")
    containing_dir = getattr(compiled, "containing_dir", None)
    if containing_dir:
        return Path(containing_dir).resolve()
    return Path(__file__).resolve().parents[2]


def get_database_path() -> Path:
    """Return the canonical encrypted database path for this installation."""
    return get_runtime_root() / "database" / "estimation.db"


def get_asset_path(*relative_parts: str) -> Path:
    """
    Build an absolute path to an asset located beneath the repository root.

    Args:
        *relative_parts: Path components inside the assets tree.

    Returns:
        Fully-qualified Path pointing at the requested asset.
    """
    return get_app_root().joinpath(*relative_parts)


__all__ = [
    "get_app_root",
    "get_asset_path",
    "get_database_path",
    "get_runtime_root",
]
