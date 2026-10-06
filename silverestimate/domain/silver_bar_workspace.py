"""Values shared by keyboard bar entry, persistence, and print confirmation."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from .numeric_policy import sum_values


def normalize_weight_prefix(text: str) -> str:
    """Accept decimal prefixes, including a trailing decimal point."""
    text = text.strip()
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]{0,2})?", text):
        raise ValueError("Enter a weight using digits and up to two decimal places.")
    whole, dot, fraction = text.partition(".")
    return (whole.lstrip("0") or "0") + dot + fraction


@dataclass(frozen=True)
class BarWeightCursor:
    weight: float
    bar_id: int


@dataclass(frozen=True)
class BarListSnapshot:
    details: dict[str, Any]
    bars: tuple[dict[str, Any], ...]

    @property
    def list_id(self) -> int:
        return int(self.details["list_id"])

    @property
    def issued(self) -> bool:
        return bool(self.details.get("issued_date"))

    @property
    def weight(self) -> float:
        return sum_values(bar["weight"] for bar in self.bars)

    @property
    def fine_weight(self) -> float:
        return sum_values(bar["fine_weight"] for bar in self.bars)

    @property
    def signature(self) -> str:
        content = json.dumps(
            [self.details, self.bars], sort_keys=True, ensure_ascii=True
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
