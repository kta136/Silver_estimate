"""Repository delegation mixin for the database manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from silverestimate.domain.voucher_deletion import (
    VoucherDeletionPreview,
    VoucherDeletionRange,
    VoucherDeletionResult,
)

if TYPE_CHECKING:
    from silverestimate.infrastructure.item_cache import ItemCacheController
    from silverestimate.persistence.estimates_repository import EstimatesRepository
    from silverestimate.persistence.items_repository import ItemsRepository
    from silverestimate.persistence.silver_bar_command_repository import (
        SilverBarCommandRepository,
    )
    from silverestimate.persistence.silver_bar_query_repository import (
        SilverBarQueryRepository,
    )


class DatabaseRepositoryFacadeMixin:
    """Expose repository operations through the public DatabaseManager API."""

    if TYPE_CHECKING:
        _item_cache_controller: ItemCacheController | None
        database_path: str
        last_error: str | None

        @property
        def items_repo(self) -> ItemsRepository: ...

        @property
        def estimates_repo(self) -> EstimatesRepository: ...

        @property
        def silver_bar_query_repo(self) -> SilverBarQueryRepository: ...

        @property
        def silver_bar_command_repo(self) -> SilverBarCommandRepository: ...

    def get_item_by_code(self, code):
        return self.items_repo.get_item_by_code(code)

    def get_items_by_codes(self, codes):
        return self.items_repo.get_items_by_codes(codes)

    def start_preload_item_cache(self):
        """Warm up the item cache off the UI thread using a separate connection."""
        controller = getattr(self, "_item_cache_controller", None)
        if not controller:
            return
        controller.start_preload(getattr(self, "open_read_connection", None))

    def search_items(self, search_term):
        return self.items_repo.search_items(search_term)

    def search_items_page(self, search_term, *, cursor=None, limit=1000):
        return self.items_repo.search_items_page(
            search_term,
            cursor=cursor,
            limit=limit,
        )

    def search_items_for_selection(self, search_term, limit=500):
        return self.items_repo.search_items_for_selection(search_term, limit=limit)

    def get_all_items(self):
        return self.items_repo.get_all_items()

    def add_item(self, code, name, purity, wage_type, wage_rate, tunch=None):
        if tunch is None:
            return self.items_repo.add_item(code, name, purity, wage_type, wage_rate)
        return self.items_repo.add_item(
            code, name, purity, wage_type, wage_rate, tunch=tunch
        )

    def update_item(self, code, name, purity, wage_type, wage_rate, tunch=None):
        if tunch is None:
            return self.items_repo.update_item(code, name, purity, wage_type, wage_rate)
        return self.items_repo.update_item(
            code, name, purity, wage_type, wage_rate, tunch=tunch
        )

    def upsert_item_catalog(self, items, *, replace_existing=False):
        return self.items_repo.upsert_item_catalog(
            items, replace_existing=replace_existing
        )

    def delete_item(self, code):
        return self.items_repo.delete_item(code)

    def get_estimate_by_voucher(self, voucher_no):
        return self.estimates_repo.get_estimate_by_voucher(voucher_no)

    def get_estimate_history_page(
        self,
        *,
        date_from=None,
        date_to=None,
        voucher_search=None,
        cursor=None,
        limit=500,
    ):
        return self.estimates_repo.get_estimate_history_page(
            date_from=date_from,
            date_to=date_to,
            voucher_search=voucher_search,
            cursor=cursor,
            limit=limit,
        )

    def get_first_estimate_date(self):
        return self.estimates_repo.get_first_estimate_date()

    def generate_voucher_no(self):
        return self.estimates_repo.generate_voucher_no()

    def delete_all_estimates(self):
        return self.estimates_repo.delete_all_estimates()

    def preview_voucher_deletion(
        self, criteria: VoucherDeletionRange
    ) -> VoucherDeletionPreview:
        return self.estimates_repo.preview_voucher_deletion(criteria)

    def delete_voucher_range(
        self, preview: VoucherDeletionPreview
    ) -> VoucherDeletionResult:
        return self.estimates_repo.delete_voucher_range(preview)

    def save_estimate_atomic(
        self, voucher_no, date, silver_rate, regular_items, return_items, totals
    ):
        return self.estimates_repo.save_estimate_atomic(
            voucher_no, date, silver_rate, regular_items, return_items, totals
        )

    def delete_single_estimate(self, voucher_no):
        return self.estimates_repo.delete_single_estimate(voucher_no)

    def add_bars_to_list(self, bar_ids, list_id=None, note=""):
        return self.silver_bar_command_repo.add_bars_to_list(bar_ids, list_id, note)

    def remove_list_bars(self, list_id, bar_ids=None):
        return self.silver_bar_command_repo.remove_list_bars(list_id, bar_ids)

    def delete_active_list(self, list_id):
        return self.silver_bar_command_repo.delete_active_list(list_id)

    def save_active_list_note(self, list_id, note):
        return self.silver_bar_command_repo.save_active_list_note(list_id, note)

    def issue_printed_list(self, list_id, signature):
        return self.silver_bar_command_repo.issue_printed_list(list_id, signature)

    def get_silver_bar_list_snapshot(self, list_id):
        return self.silver_bar_query_repo.get_list_snapshot(list_id)

    def reactivate_silver_bar_list(self, list_id):
        return self.silver_bar_command_repo.reactivate_list(list_id)

    def get_silver_bars(
        self,
        status=None,
        estimate_voucher_no=None,
        unassigned_only=False,
    ):
        return self.silver_bar_query_repo.get_silver_bars(
            status=status,
            estimate_voucher_no=estimate_voucher_no,
            unassigned_only=unassigned_only,
        )


__all__ = ["DatabaseRepositoryFacadeMixin"]
