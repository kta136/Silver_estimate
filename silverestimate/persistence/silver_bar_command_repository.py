"""Transactional silver-bar command persistence component."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, cast

from silverestimate.persistence.repository_results import (
    RepositoryFailureKind,
    RepositoryResult,
)


class SilverBarCommandRepository:
    """Own list lifecycle and inventory mutation commands."""

    def __init__(self, backend: Any) -> None:
        self._backend = backend

    def generate_list_identifier(self) -> str:
        return str(self._backend.generate_list_identifier())

    def create_list(self, note: str | None = None) -> int | None:
        return cast(int | None, self._backend.create_list(note))

    def update_list_note(self, list_id: int, new_note: str) -> bool:
        return bool(self._backend.update_list_note(list_id, new_note))

    def mark_list_as_issued(self, *args: Any, **kwargs: Any) -> Any:
        return self._backend.mark_list_as_issued(*args, **kwargs)

    def reactivate_list(self, list_id: int) -> bool:
        return bool(self._backend.reactivate_list(list_id))

    def delete_list(self, list_id: int) -> tuple[bool, str]:
        result = self.delete_list_result(list_id)
        if result.succeeded:
            return True, result.unwrap()
        assert result.failure is not None
        return False, result.failure.message

    def delete_list_result(self, list_id: int) -> RepositoryResult[str]:
        success, message = cast(tuple[bool, str], self._backend.delete_list(list_id))
        detail = str(message or "Silver-bar list deletion failed.")
        if success:
            return RepositoryResult.success(detail)
        normalized = detail.casefold()
        kind = (
            RepositoryFailureKind.NOT_FOUND
            if "not found" in normalized
            else RepositoryFailureKind.CONFLICT
            if "cannot" in normalized or "assigned" in normalized
            else RepositoryFailureKind.STORAGE
        )
        return RepositoryResult.failed(kind, detail)

    def assign_bar_to_list(self, *args: Any, **kwargs: Any) -> Any:
        return self._backend.assign_bar_to_list(*args, **kwargs)

    def assign_bars_to_list_bulk(self, *args: Any, **kwargs: Any) -> Any:
        return self._backend.assign_bars_to_list_bulk(*args, **kwargs)

    def remove_bar_from_list(self, *args: Any, **kwargs: Any) -> Any:
        return self._backend.remove_bar_from_list(*args, **kwargs)

    def remove_bars_from_list_bulk(self, *args: Any, **kwargs: Any) -> Any:
        return self._backend.remove_bars_from_list_bulk(*args, **kwargs)

    def add_silver_bar(
        self, voucher_no: str, weight: float, purity: float
    ) -> int | None:
        return cast(
            int | None, self._backend.add_silver_bar(voucher_no, weight, purity)
        )

    def delete_bars_for_estimate(self, voucher_no: str) -> tuple[int, set[Any]]:
        return cast(
            tuple[int, set[Any]],
            self._backend.delete_bars_for_estimate(voucher_no),
        )

    def cleanup_empty_lists(self, list_ids: Iterable[int]) -> None:
        self._backend.cleanup_empty_lists(list_ids)


__all__ = ["SilverBarCommandRepository"]
