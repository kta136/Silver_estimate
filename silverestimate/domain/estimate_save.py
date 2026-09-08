"""Result of committing an estimate and its inventory as one operation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EstimateSaveResult:
    success: bool
    bars_added: int = 0
    bars_updated: int = 0
    bars_removed: int = 0
    error_detail: str | None = None
