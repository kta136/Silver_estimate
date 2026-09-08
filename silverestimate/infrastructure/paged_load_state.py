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
    last_page_rows: list[RowT] = field(default_factory=list)
    max_rows: int = 20_000
    limit_reached: bool = False
    cursor: CursorT | None = None
    total: int | None = 0

    @property
    def loaded(self) -> int:
        return len(self.rows)

    @property
    def has_more(self) -> bool:
        return self.cursor is not None

    def reset(self) -> None:
        self.rows.clear()
        self.last_page_rows.clear()
        self.limit_reached = False
        self.cursor = None
        self.total = 0

    def apply(
        self,
        page: Page[RowT, CursorT],
        *,
        append: bool = False,
    ) -> list[RowT]:
        remaining = max(0, self.max_rows - (len(self.rows) if append else 0))
        page_rows = list(page.items[:remaining])
        self.last_page_rows = page_rows
        self.limit_reached = len(page.items) > remaining or (
            len(page_rows) == remaining and page.has_more
        )
        if append:
            self.rows.extend(page_rows)
        else:
            self.rows = page_rows
        self.cursor = None if self.limit_reached else page.next_cursor
        self.total = max(0, int(page.total)) if page.total is not None else None
        return self.rows


__all__ = ["PagedLoadState"]
