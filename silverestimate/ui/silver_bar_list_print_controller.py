"""Print-preview workflow for silver-bar lists."""

from __future__ import annotations

import logging
import traceback
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from .silver_bar_management import SilverBarDialog
from .preview_build_worker import PreviewBuildController

_LOGGER = logging.getLogger(__name__)


class SilverBarListPrintController:
    """Handle list preview preparation and cleanup for silver-bar management."""

    def __init__(self, host: SilverBarDialog) -> None:
        self.host = host
        self._preview_builder: PreviewBuildController | None = None

    def print_selected_list(self) -> None:
        if self.host.current_list_id is None:
            QMessageBox.warning(self.host, "Error", "No list selected.")
            return
        details = self.host.db_manager.get_silver_bar_list_details(
            self.host.current_list_id
        )
        if not details:
            QMessageBox.warning(
                self.host,
                "Error",
                "Could not retrieve list details for printing.",
            )
            return

        bars_in_list = self.host.db_manager.get_bars_in_list(self.host.current_list_id)
        _LOGGER.info(
            "Printing list %s (ID: %s) with %s bars.",
            details["list_identifier"],
            self.host.current_list_id,
            len(bars_in_list),
        )

        try:
            from .print_manager import PrintManager

            parent_context = self.host.parent()
            current_print_font = (
                getattr(parent_context, "print_font", None) if parent_context else None
            )

            print_manager = PrintManager(
                self.host.db_manager, print_font=current_print_font
            )
            self._start_list_print_preview_build(
                print_manager=print_manager,
                build_preview=lambda: (
                    print_manager.build_silver_bar_list_preview_payload(
                        details,
                        bars_in_list,
                    )
                ),
            )

        except ImportError:
            QMessageBox.critical(self.host, "Error", "Could not import PrintManager.")
        except AttributeError as exc:
            QMessageBox.critical(
                self.host,
                "Error",
                f"Print function not found or incorrect in PrintManager: {exc}",
            )
        except Exception as exc:
            QMessageBox.critical(
                self.host,
                "Print Error",
                f"An unexpected error occurred during printing: {exc}\n{traceback.format_exc()}",
            )

    def _start_list_print_preview_build(self, *, print_manager, build_preview) -> None:
        if self._preview_builder is None:
            self._preview_builder = PreviewBuildController(
                self.host, message="Preparing list print preview..."
            )
        self._preview_builder.start(
            build_preview,
            on_ready=lambda payload: print_manager.show_preview(
                payload, parent_widget=self.host
            ),
            on_error=lambda message: QMessageBox.warning(
                self.host, "Print Error", message
            ),
            empty_message="Failed to generate print preview for the list.",
        )

    def shutdown(self) -> None:
        if self._preview_builder is not None:
            self._preview_builder.shutdown()
            self._preview_builder = None
