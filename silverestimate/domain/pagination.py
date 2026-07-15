"""Typed keyset-pagination primitives shared by repositories and UI loaders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

ItemT = TypeVar("ItemT")
CursorT = TypeVar("CursorT")


@dataclass(frozen=True)
class Page(Generic[ItemT, CursorT]):
    """A stable page of rows and the cursor needed to continue the query."""

    items: tuple[ItemT, ...]
    total: int
    next_cursor: CursorT | None = None

    @property
    def has_more(self) -> bool:
        return self.next_cursor is not None


@dataclass(frozen=True)
class ItemCursor:
    normalized_code: str
    code: str


@dataclass(frozen=True)
class AvailableBarCursor:
    date_added: str
    bar_id: int


@dataclass(frozen=True)
class BarListCursor:
    bar_id: int


@dataclass(frozen=True)
class EstimateHistoryCursor:
    voucher_no_int: int | None
    voucher_no: str


@dataclass(frozen=True)
class SilverBarHistoryCursor:
    date_added: str
    bar_id: int


__all__ = [
    "AvailableBarCursor",
    "BarListCursor",
    "EstimateHistoryCursor",
    "ItemCursor",
    "Page",
    "SilverBarHistoryCursor",
]
