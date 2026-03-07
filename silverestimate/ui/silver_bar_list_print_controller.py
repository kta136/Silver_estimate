"""Print-preview workflow for silver-bar lists."""

from __future__ import annotations

import logging
import traceback
from typing import TYPE_CHECKING

from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QMessageBox, QProgressDialog

from ._host_proxy import HostProxy

_LOGGER = logging.getLogger(__name__)


class SilverBarListPrintController(HostProxy):
    """Handle list preview preparation and cleanup for silver-bar management."""

    if TYPE_CHECKING:
        _active_print_preview_workers: dict[QThread, object]
        _print_preview_request_id: int

    def print_selected_list(self):
        if self.current_list_id is None:
            QMessageBox.warning(self.host, "Error", "No list selected.")
            return
        details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
        if not details:
            QMessageBox.warning(
                self.host,
                "Error",
                "Could not retrieve list details for printing.",
            )
            return

        bars_in_list = self.db_manager.get_bars_in_list(self.current_list_id)
        _LOGGER.info(
            "Printing list %s (ID: %s) with %s bars.",
            details["list_identifier"],
            self.current_list_id,
            len(bars_in_list),
        )

        try:
            from .print_manager import PrintManager, PrintPreviewBuildWorker

            parent_context = self.host.parent()
            current_print_font = (
                getattr(parent_context, "print_font", None) if parent_context else None
            )

            print_manager = PrintManager(self.db_manager, print_font=current_print_font)
            self._start_list_print_preview_build(
                print_manager=print_manager,
                build_preview=lambda: (
                    print_manager.build_silver_bar_list_preview_payload(
                        details,
                        bars_in_list,
                    )
                ),
                worker_cls=PrintPreviewBuildWorker,
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

    def _next_print_preview_request_id(self) -> int:
        next_id = int(getattr(self, "_print_preview_request_id", 0)) + 1
        self._print_preview_request_id = next_id
        return next_id

    def _start_list_print_preview_build(
        self,
        *,
        print_manager,
        build_preview,
        worker_cls,
    ) -> None:
        request_id = self._next_print_preview_request_id()
        progress = QProgressDialog(
            "Preparing list print preview...",
            "",
            0,
            0,
            self.host,
        )
        progress.setCancelButton(None)
        progress.setWindowTitle("Print Preview")
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()

        worker = worker_cls(request_id, build_preview)
        thread = QThread(self.host)
        worker.moveToThread(thread)

        active_workers = getattr(self, "_active_print_preview_workers", None)
        if active_workers is None:
            self._active_print_preview_workers = {}
            active_workers = self._active_print_preview_workers
        active_workers[thread] = worker

        thread.started.connect(worker.run)
        worker.preview_ready.connect(
            lambda rid, payload: self._on_list_print_preview_ready(
                rid,
                payload,
                thread=thread,
                worker=worker,
                print_manager=print_manager,
                progress=progress,
            )
        )
        worker.preview_error.connect(
            lambda rid, message: self._on_list_print_preview_error(
                rid,
                message,
                thread=thread,
                worker=worker,
                progress=progress,
            )
        )
        worker.finished.connect(
            lambda rid: self._finish_list_print_preview_build(
                rid,
                thread=thread,
                worker=worker,
                progress=progress,
            )
        )
        thread.start()

    def _on_list_print_preview_ready(
        self,
        request_id,
        payload,
        *,
        thread,
        worker,
        print_manager,
        progress,
    ) -> None:
        del thread, worker
        if request_id != getattr(self, "_print_preview_request_id", 0):
            return
        try:
            progress.close()
        except Exception as exc:
            _LOGGER.debug("Failed to close list print preview progress: %s", exc)
        if payload is None:
            QMessageBox.warning(
                self.host,
                "Print Error",
                "Failed to generate print preview for the list.",
            )
            return
        print_manager.show_preview(payload, parent_widget=self.host)

    def _on_list_print_preview_error(
        self,
        request_id,
        message,
        *,
        thread,
        worker,
        progress,
    ) -> None:
        del thread, worker
        if request_id != getattr(self, "_print_preview_request_id", 0):
            return
        try:
            progress.close()
        except Exception as exc:
            _LOGGER.debug(
                "Failed to close list print preview progress after error: %s",
                exc,
            )
        QMessageBox.warning(self.host, "Print Error", message)

    def _finish_list_print_preview_build(
        self,
        request_id,
        *,
        thread,
        worker,
        progress,
    ) -> None:
        del request_id
        try:
            progress.close()
            progress.deleteLater()
        except Exception as exc:
            _LOGGER.debug(
                "Failed to dispose list print preview progress dialog: %s",
                exc,
            )
        active_workers = getattr(self, "_active_print_preview_workers", {})
        active_workers.pop(thread, None)
        try:
            thread.quit()
            thread.wait(1000)
        except Exception as exc:
            self.logger.debug("Failed to stop list preview worker thread: %s", exc)
        try:
            worker.deleteLater()
            thread.deleteLater()
        except Exception as exc:
            self.logger.debug("Failed to delete list preview worker: %s", exc)
