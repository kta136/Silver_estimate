"""Typography for Modern estimate and silver-bar printing."""

from __future__ import annotations

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

__all__ = ["MODERN_ESTIMATE_FORMAT_SPEC", "PrintFormatSpec"]
