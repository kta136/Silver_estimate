"""Repository delegation mixin for the database manager."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


class DatabaseRepositoryFacadeMixin:
    """Expose repository operations through the legacy DatabaseManager API."""

    if TYPE_CHECKING:
        items_repo: Any
        estimates_repo: Any
        silver_bars_repo: Any
        _item_cache_controller: Any | None
        temp_db_path: str | None
        last_error: str | None

    def get_item_by_code(self, code):
        return self.items_repo.get_item_by_code(code)

    def start_preload_item_cache(self):
        """Warm up the item cache off the UI thread using a separate connection."""
        controller = getattr(self, "_item_cache_controller", None)
        if not controller:
            return
        controller.start_preload(self.temp_db_path)

    def search_items(self, search_term):
        return self.items_repo.search_items(search_term)

    def search_items_for_selection(self, search_term, limit=500):
        return self.items_repo.search_items_for_selection(search_term, limit=limit)

    def get_all_items(self):
        return self.items_repo.get_all_items()

    def add_item(self, code, name, purity, wage_type, wage_rate):
        return self.items_repo.add_item(code, name, purity, wage_type, wage_rate)

    def update_item(self, code, name, purity, wage_type, wage_rate):
        return self.items_repo.update_item(code, name, purity, wage_type, wage_rate)

    def delete_item(self, code):
        return self.items_repo.delete_item(code)

    def get_estimate_by_voucher(self, voucher_no):
        return self.estimates_repo.get_estimate_by_voucher(voucher_no)

    def generate_voucher_no(self):
        return self.estimates_repo.generate_voucher_no()

    def save_estimate_with_returns(
        self, voucher_no, date, silver_rate, regular_items, return_items, totals
    ):
        self.last_error = None
        return self.estimates_repo.save_estimate_with_returns(
            voucher_no,
            date,
            silver_rate,
            regular_items,
            return_items,
            totals,
        )

    def delete_all_estimates(self):
        return self.estimates_repo.delete_all_estimates()

    def delete_single_estimate(self, voucher_no):
        return self.estimates_repo.delete_single_estimate(voucher_no)

    def create_silver_bar_list(self, note=None):
        return self.silver_bars_repo.create_list(note)

    def get_silver_bar_lists(self, include_issued=True):
        return self.silver_bars_repo.get_lists(include_issued)

    def get_silver_bar_list_details(self, list_id):
        return self.silver_bars_repo.get_list_details(list_id)

    def update_silver_bar_list_note(self, list_id, new_note):
        return self.silver_bars_repo.update_list_note(list_id, new_note)

    def delete_silver_bar_list(self, list_id):
        return self.silver_bars_repo.delete_list(list_id)

    def assign_bar_to_list(
        self, bar_id, list_id, note="Assigned to list", perform_commit=True
    ):
        return self.silver_bars_repo.assign_bar_to_list(
            bar_id,
            list_id,
            note=note,
            perform_commit=perform_commit,
        )

    def remove_bar_from_list(
        self, bar_id, note="Removed from list", perform_commit=True
    ):
        return self.silver_bars_repo.remove_bar_from_list(
            bar_id,
            note=note,
            perform_commit=perform_commit,
        )

    def assign_bars_to_list_bulk(self, bar_ids, list_id, note="Assigned to list"):
        return self.silver_bars_repo.assign_bars_to_list_bulk(
            bar_ids,
            list_id,
            note=note,
        )

    def remove_bars_from_list_bulk(self, bar_ids, note="Removed from list"):
        return self.silver_bars_repo.remove_bars_from_list_bulk(
            bar_ids,
            note=note,
        )

    def get_bars_in_list(self, list_id, limit=None, offset=0):
        return self.silver_bars_repo.get_bars_in_list(
            list_id,
            limit=limit,
            offset=offset,
        )

    def get_available_silver_bars_page(
        self,
        *,
        weight_query=None,
        weight_tolerance=0.001,
        min_purity=None,
        max_purity=None,
        date_range=None,
        limit=None,
    ):
        return self.silver_bars_repo.get_available_bars_page(
            weight_query=weight_query,
            weight_tolerance=weight_tolerance,
            min_purity=min_purity,
            max_purity=max_purity,
            date_range=date_range,
            limit=limit,
        )

    def get_silver_bars_in_list_page(self, list_id, *, limit=None, offset=0):
        return self.silver_bars_repo.get_bars_in_list_page(
            list_id,
            limit=limit,
            offset=offset,
        )

    def search_silver_bar_history(
        self,
        *,
        voucher_term="",
        weight_text="",
        status_text="All Statuses",
        limit=2000,
    ):
        return self.silver_bars_repo.search_history_bars(
            voucher_term=voucher_term,
            weight_text=weight_text,
            status_text=status_text,
            limit=limit,
        )

    def count_silver_bars_by_list_ids(self, list_ids):
        return self.silver_bars_repo.count_bars_by_list_ids(list_ids)

    def mark_silver_bar_list_as_issued(self, list_id, issued_date=None):
        return self.silver_bars_repo.mark_list_as_issued(
            list_id,
            issued_date=issued_date,
        )

    def reactivate_silver_bar_list(self, list_id):
        return self.silver_bars_repo.reactivate_list(list_id)

    def sync_silver_bars_for_estimate(self, voucher_no, bars):
        return self.silver_bars_repo.sync_silver_bars_for_estimate(voucher_no, bars)

    def get_silver_bars(
        self,
        status=None,
        weight_query=None,
        estimate_voucher_no=None,
        unassigned_only=False,
        weight_tolerance=0.001,
        min_purity=None,
        max_purity=None,
        date_range=None,
        limit=None,
        offset=0,
    ):
        return self.silver_bars_repo.get_silver_bars(
            status=status,
            weight_query=weight_query,
            estimate_voucher_no=estimate_voucher_no,
            unassigned_only=unassigned_only,
            weight_tolerance=weight_tolerance,
            min_purity=min_purity,
            max_purity=max_purity,
            date_range=date_range,
            limit=limit,
            offset=offset,
        )

__all__ = ["DatabaseRepositoryFacadeMixin"]
