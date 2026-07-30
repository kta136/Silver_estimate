"""Structural database contracts shared across persistence and application layers."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Protocol

from silverestimate.persistence.database_driver import (
    Connection,
    Cursor,
    ReadConnection,
)

DatabaseRecord = Mapping[str, Any]
ReadConnectionFactory = Callable[[], ReadConnection]


class ItemCacheBoundary(Protocol):
    """Cache operations used by the item repository."""

    def get(self, code: str) -> object | None: ...

    def store(self, code: str, value: object) -> None: ...

    def invalidate(self, code: str) -> None: ...

    def replace_all(self, rows: Iterable[object] | None) -> None: ...


class SilverBarDeletionBoundary(Protocol):
    """Silver-bar commands needed while deleting an estimate."""

    def delete_bars_for_estimate(
        self,
        estimate_voucher_no: str,
    ) -> tuple[int, set[int]]: ...

    def cleanup_empty_lists(self, list_ids: Iterable[int]) -> None: ...


class RepositoryDatabase(Protocol):
    """Low-level writer session exposed only to concrete repositories."""

    logger: logging.Logger
    conn: Connection | None
    cursor: Cursor | None
    last_error: str | None

    @property
    def item_cache_controller(self) -> ItemCacheBoundary: ...

    @property
    def silver_bar_command_repo(self) -> SilverBarDeletionBoundary: ...


class ItemCatalogDatabase(Protocol):
    """Catalog operations used by native import/export services."""

    def get_all_items(self) -> list[DatabaseRecord]: ...

    def upsert_item_catalog(
        self,
        items: list[dict[str, Any]],
        *,
        replace_existing: bool = False,
    ) -> dict[str, int]: ...


class MainCommandsDatabase(ItemCatalogDatabase, Protocol):
    """Maintenance surface used by main-window commands."""

    def drop_tables(self) -> bool: ...

    def setup_database(self) -> None: ...

    def delete_all_estimates(self) -> bool: ...

    def open_read_connection(self) -> ReadConnection: ...


class EstimateDataSource(Protocol):
    """Persistence operations consumed by the estimate application adapter."""

    last_error: str | None

    def get_item_by_code(self, code: str) -> DatabaseRecord | None: ...

    def get_items_by_codes(
        self,
        codes: Iterable[str],
    ) -> Mapping[str, DatabaseRecord]: ...

    def generate_voucher_no(self) -> str: ...

    def get_estimate_by_voucher(
        self,
        voucher_no: str,
    ) -> DatabaseRecord | None: ...

    def save_estimate_with_returns(  # noqa: PLR0913 - existing persistence API
        self,
        voucher_no: str,
        date: str,
        silver_rate: float,
        regular_items: list[DatabaseRecord],
        return_items: list[DatabaseRecord],
        totals: dict[str, Any],
    ) -> bool: ...

    def sync_silver_bars_for_estimate(
        self,
        voucher_no: str,
        bars: list[DatabaseRecord],
    ) -> tuple[int, int]: ...

    def delete_single_estimate(self, voucher_no: str) -> bool: ...


class StartupDatabase(Protocol):
    """Lifecycle surface used during startup and shutdown."""

    def start_preload_item_cache(self) -> None: ...

    def close(self) -> None: ...


class ApplicationDatabase(
    MainCommandsDatabase,
    EstimateDataSource,
    StartupDatabase,
    Protocol,
):
    """Combined composition-root contract; feature code uses narrower protocols."""

    def set_flush_status_callbacks(
        self,
        *,
        on_queued: Callable[[], None] | None = None,
        on_done: Callable[[], None] | None = None,
    ) -> None: ...


__all__ = [
    "ApplicationDatabase",
    "DatabaseRecord",
    "EstimateDataSource",
    "ItemCacheBoundary",
    "ItemCatalogDatabase",
    "MainCommandsDatabase",
    "ReadConnectionFactory",
    "RepositoryDatabase",
    "SilverBarDeletionBoundary",
    "StartupDatabase",
]
