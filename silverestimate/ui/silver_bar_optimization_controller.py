"""Generate a separate list in one transaction without assignment dialogs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QDialog

from .silver_bar_optimization import find_optimal_combination

if TYPE_CHECKING:
    from .silver_bar_management import SilverBarDialog


class SilverBarOptimizationController:
    def __init__(self, host: SilverBarDialog) -> None:
        self.host = host

    def generate_optimal_list(self, dialog_cls) -> None:
        dialog = dialog_cls(self.host)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            bars = self.host.db_manager.get_silver_bars(
                status="In Stock", unassigned_only=True
            )
            selected = find_optimal_combination(
                bars, dialog.min_target, dialog.max_target, dialog.optimization_type
            )
            if not selected:
                self.host.set_status(
                    "No combination of available bars fits this range."
                )
                return
            result = self.host.db_manager.add_bars_to_list(
                [bar["bar_id"] for bar in selected], note=dialog.list_name
            )
            if self.host.accept_change(result):
                self.host.weight_search_edit.clear()
                self.host.set_status("Optimal list created · Saved automatically.")
                self.host.focus_weight()
        except Exception as exc:
            self.host.logger.exception("Optimal-list generation failed")
            self.host.set_status(f"Could not generate list: {exc}", error=True)
