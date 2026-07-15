"""Read-only silver-bar persistence component."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, cast

from silverestimate.domain.pagination import (
    AvailableBarCursor,
    BarListCursor,
    Page,
    SilverBarHistoryCursor,
)
from silverestimate.persistence.repository_results import (
    RepositoryFailureKind,
    RepositoryResult,
)


class SilverBarQueryRepository:
    """Own every silver-bar and list read behind the compatibility facade."""

    def __init__(self, backend: Any) -> None:
        self._backend = backend

    def get_lists(self, include_issued: bool = True) -> Any:
        return self._backend.get_lists(include_issued)

    def get_list_details(self, list_id: int) -> Any:
        result = self.get_list_details_result(list_id)
        return result.value if result.succeeded else None

    def get_list_details_result(self, list_id: int) -> RepositoryResult[dict[str, Any]]:
        details = self._backend.get_list_details(list_id)
        if isinstance(details, Mapping) or hasattr(details, "keys"):
            return RepositoryResult.success(dict(details))
        return RepositoryResult.failed(
            RepositoryFailureKind.NOT_FOUND,
            f"Silver-bar list {list_id} was not found.",
        )

    def get_available_bars_page(self, *args: Any, **kwargs: Any) -> Any:
        return self._backend.get_available_bars_page(*args, **kwargs)

    def get_available_bars_keyset_page(
        self,
        *args: Any,
        cursor: AvailableBarCursor | None = None,
        **kwargs: Any,
    ) -> Page[dict[str, Any], AvailableBarCursor]:
        return cast(
            Page[dict[str, Any], AvailableBarCursor],
            self._backend.get_available_bars_keyset_page(
                *args, cursor=cursor, **kwargs
            ),
        )

    def get_bars_in_list_page(self, *args: Any, **kwargs: Any) -> Any:
        return self._backend.get_bars_in_list_page(*args, **kwargs)

    def get_bars_in_list_keyset_page(
        self,
        *args: Any,
        cursor: BarListCursor | None = None,
        **kwargs: Any,
    ) -> Page[dict[str, Any], BarListCursor]:
        return cast(
            Page[dict[str, Any], BarListCursor],
            self._backend.get_bars_in_list_keyset_page(*args, cursor=cursor, **kwargs),
        )

    def get_bars_in_list(self, list_id: int, *args: Any, **kwargs: Any) -> Any:
        return self._backend.get_bars_in_list(list_id, *args, **kwargs)

    def get_available_bars(self) -> Any:
        return self._backend.get_available_bars()

    def search_history_bars(self, *args: Any, **kwargs: Any) -> Any:
        return self._backend.search_history_bars(*args, **kwargs)

    def search_history_bars_page(
        self,
        *args: Any,
        cursor: SilverBarHistoryCursor | None = None,
        **kwargs: Any,
    ) -> Page[dict[str, Any], SilverBarHistoryCursor]:
        return cast(
            Page[dict[str, Any], SilverBarHistoryCursor],
            self._backend.search_history_bars_page(*args, cursor=cursor, **kwargs),
        )

    def count_bars_by_list_ids(self, list_ids: Iterable[int]) -> dict[int, int]:
        return cast(dict[int, int], self._backend.count_bars_by_list_ids(list_ids))

    def get_silver_bars_for_estimate(self, voucher_no: str) -> Any:
        return self._backend.get_silver_bars_for_estimate(voucher_no)

    def get_silver_bars(self, *args: Any, **kwargs: Any) -> Any:
        return self._backend.get_silver_bars(*args, **kwargs)


__all__ = ["SilverBarQueryRepository"]
