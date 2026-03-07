"""Optimal-list generation workflow for silver-bar management."""

from __future__ import annotations

import traceback

from PyQt5.QtWidgets import QMessageBox

from ._host_proxy import HostProxy
from .silver_bar_optimization import find_optimal_combination


class SilverBarOptimizationController(HostProxy):
    """Generate optimized silver-bar lists from available stock."""

    def generate_optimal_list(self, dialog_cls):
        dialog = dialog_cls(self.host)
        if dialog.exec_() != dialog_cls.Accepted:
            return

        min_target = dialog.min_target
        max_target = dialog.max_target
        list_name = dialog.list_name
        optimization_type = dialog.optimization_type

        try:
            available_bars = self.db_manager.get_silver_bars(
                status="In Stock",
                unassigned_only=True,
            )

            if not available_bars:
                QMessageBox.information(
                    self.host,
                    "No Bars Available",
                    "No silver bars are available for list generation.",
                )
                return

            selected_bars = find_optimal_combination(
                available_bars,
                min_target,
                max_target,
                optimization_type,
            )

            if not selected_bars:
                QMessageBox.information(
                    self.host,
                    "No Solution",
                    f"Could not find a combination of bars within the range {min_target:.1f}g - {max_target:.1f}g.",
                )
                return

            new_list_id = self.db_manager.create_silver_bar_list(list_name)
            if not new_list_id:
                QMessageBox.critical(self.host, "Error", "Failed to create new list.")
                return

            selected_ids = [bar["bar_id"] for bar in selected_bars]
            added_count, failed_bars = self._bulk_assign_to_list(
                selected_ids,
                new_list_id,
            )

            actual_fine_weight = sum(bar["fine_weight"] for bar in selected_bars)
            message = "Optimal list created successfully!\n\n"
            message += f"List Name: {list_name}\n"
            message += f"Target Range: {min_target:.1f}g - {max_target:.1f}g\n"
            message += f"Actual Fine Weight: {actual_fine_weight:.1f}g\n"
            message += f"Bars Added: {added_count}\n"
            message += (
                "Optimization: Minimum bars"
                if optimization_type == "min_bars"
                else "Optimization: Maximum bars"
            )

            if failed_bars:
                message += (
                    "\n\nWarning: Failed to add "
                    f"{len(failed_bars)} bars: {', '.join(failed_bars)}"
                )

            QMessageBox.information(self.host, "List Generated", message)
            self.load_lists()
            self.load_available_bars()

            index = self.list_combo.findData(new_list_id)
            if index >= 0:
                self.list_combo.setCurrentIndex(index)

        except Exception as exc:
            self.logger.error("Failed to generate optimal list: %s", exc, exc_info=True)
            QMessageBox.critical(
                self.host,
                "Error",
                f"Failed to generate optimal list: {exc}\n{traceback.format_exc()}",
            )
