"""Reusable mutable state for keyset-paged UI loaders."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

from silverestimate.domain.pagination import Page

RowT = TypeVar("RowT")
CursorT = TypeVar("CursorT")


@dataclass
class PagedLoadState(Generic[RowT, CursorT]):
    """Accumulate pages while leaving query and presentation policy to callers."""

    rows: list[RowT] = field(default_factory=list)
    cursor: CursorT | None = None
    total: int = 0

    @property
    def loaded(self) -> int:
        return len(self.rows)

    @property
    def has_more(self) -> bool:
        return self.cursor is not None

    def reset(self) -> None:
        self.rows.clear()
        self.cursor = None
        self.total = 0

    def apply(
        self,
        page: Page[RowT, CursorT],
        *,
        append: bool = False,
    ) -> list[RowT]:
        page_rows = list(page.items)
        if append:
            self.rows.extend(page_rows)
        else:
            self.rows = page_rows
        self.cursor = page.next_cursor
        self.total = max(0, int(page.total))
        return self.rows


__all__ = ["PagedLoadState"]
