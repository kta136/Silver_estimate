"""Shared print-format specifications and renderer strategy contracts."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PrintFormatSpec:
    key: str
    document_kind: str
    table_mode: bool
    font_family: str
    font_size: float
    line_height: float


class PrintRendererStrategy(Protocol):
    @property
    def spec(self) -> PrintFormatSpec: ...

    def render(self, payload: object) -> str: ...


@dataclass(frozen=True)
class FunctionRendererStrategy:
    spec: PrintFormatSpec
    renderer: Callable[[object], str]

    def render(self, payload: object) -> str:
        return self.renderer(payload)


ESTIMATE_FORMAT_SPECS: Mapping[str, PrintFormatSpec] = {
    "old": PrintFormatSpec("old", "estimate", False, "Courier New", 7.0, 1.0),
    "new": PrintFormatSpec("new", "estimate", False, "Courier New", 7.0, 1.0),
    "thermal": PrintFormatSpec("thermal", "estimate", False, "Courier New", 7.0, 1.0),
}
def build_estimate_strategies(
    *,
    render_old: Callable[[object], str],
    render_new: Callable[[object], str],
    render_thermal: Callable[[object], str],
) -> dict[str, PrintRendererStrategy]:
    return {
        "old": FunctionRendererStrategy(ESTIMATE_FORMAT_SPECS["old"], render_old),
        "new": FunctionRendererStrategy(ESTIMATE_FORMAT_SPECS["new"], render_new),
        "thermal": FunctionRendererStrategy(
            ESTIMATE_FORMAT_SPECS["thermal"], render_thermal
        ),
    }


__all__ = [
    "ESTIMATE_FORMAT_SPECS",
    "FunctionRendererStrategy",
    "PrintFormatSpec",
    "PrintRendererStrategy",
    "build_estimate_strategies",
]
