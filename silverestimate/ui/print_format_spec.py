"""Shared specifications for Classic and Modern estimate printing."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class PrintFormatSpec:
    key: str
    font_family: str
    font_size: float
    line_height: float


MODERN_ESTIMATE_FORMAT_SPEC = PrintFormatSpec(
    "modern",
    "Arial",
    8.0,
    1.0,
)
CLASSIC_ESTIMATE_FORMAT_SPEC = PrintFormatSpec(
    "classic",
    "Courier New",
    7.0,
    1.0,
)
ESTIMATE_FORMAT_SPECS: Mapping[str, PrintFormatSpec] = {
    "classic": CLASSIC_ESTIMATE_FORMAT_SPEC,
    "modern": MODERN_ESTIMATE_FORMAT_SPEC,
}
ESTIMATE_FORMAT_LABELS: Mapping[str, str] = {
    "classic": "Classic",
    "modern": "Modern",
}
DEFAULT_ESTIMATE_FORMAT = "modern"


def normalize_estimate_format(value: object) -> str:
    """Return a supported estimate format, defaulting invalid values to Modern."""
    normalized = str(value or "").strip().lower()
    return (
        normalized if normalized in ESTIMATE_FORMAT_SPECS else DEFAULT_ESTIMATE_FORMAT
    )


__all__ = [
    "CLASSIC_ESTIMATE_FORMAT_SPEC",
    "DEFAULT_ESTIMATE_FORMAT",
    "ESTIMATE_FORMAT_LABELS",
    "ESTIMATE_FORMAT_SPECS",
    "MODERN_ESTIMATE_FORMAT_SPEC",
    "PrintFormatSpec",
    "normalize_estimate_format",
]
