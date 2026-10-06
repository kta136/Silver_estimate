"""Print a stable list, issue it on success, and start the next list."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer

from silverestimate.domain.silver_bar_workspace import BarListSnapshot
from silverestimate.persistence.repository_results import RepositoryFailureKind

from .preview_build_worker import PreviewBuildController
from .print_preview_output import PrintOutputOutcome

if TYPE_CHECKING:
    from .silver_bar_management import SilverBarDialog


class SilverBarListPrintController:
    def __init__(self, host: SilverBarDialog) -> None:
        self.host = host
        self.printed: BarListSnapshot | None = None
        self._preview_builder: PreviewBuildController | None = None

    def invalidate(self) -> None:
        self.printed = None

    def print_selected_list(self, *, preview: bool = False) -> None:
        h = self.host
        if h.current_list_id is None or h._busy or h._loading_list:
            return
        from .print_manager import PrintManager

        try:
            snapshot = h.db_manager.get_silver_bar_list_snapshot(h.current_list_id)
            if not snapshot.bars:
                h.set_status("Add bars before printing.")
                return
            h.apply_snapshot(snapshot)
            if (
                self.printed
                and self.printed.signature == snapshot.signature
                and not preview
            ):
                self.complete_issue()
                return
            self.invalidate()
            h._busy = True
            h._load_controller.cancel_search()
            h._update_actions()
            manager = PrintManager(h.db_manager)
            self._start_list_print_preview_build(
                print_manager=manager,
                build_preview=lambda: manager.build_silver_bar_list_preview_payload(
                    snapshot.details, snapshot.bars
                ),
                snapshot=snapshot,
                preview=preview,
            )
        except Exception as exc:
            self._print_failed(str(exc))

    def _start_list_print_preview_build(
        self,
        *,
        print_manager,
        build_preview,
        snapshot: BarListSnapshot,
        preview: bool = False,
    ) -> None:
        if self._preview_builder is None:
            self._preview_builder = PreviewBuildController(
                self.host, message="Preparing list for printing…"
            )
        self._preview_builder.start(
            build_preview,
            on_ready=lambda payload: self._preview_ready(
                print_manager, payload, snapshot, preview=preview
            ),
            on_error=self._print_failed,
            empty_message="Could not prepare the list for printing.",
        )

    def _preview_ready(
        self, manager, payload, snapshot: BarListSnapshot, *, preview: bool = False
    ) -> None:
        try:
            outcome = (
                manager.show_preview(payload, parent_widget=self.host)
                if preview
                else manager.quick_print(payload)
            )
        except Exception as exc:
            self._print_failed(str(exc))
            return
        self.host._busy = False
        if isinstance(outcome, PrintOutputOutcome) and outcome.succeeded:
            if snapshot.issued:
                self.host.set_status("Issued list reprinted.")
            else:
                self.printed = snapshot
                self.host._update_actions()
                self.complete_issue()
        else:
            self.host.set_status(
                outcome.message or "No print was submitted. The list is unchanged.",
                error=not outcome.cancelled,
            )
        self.host._update_actions()
        self._restore_focus()
        QTimer.singleShot(0, self._restore_focus)

    def _restore_focus(self) -> None:
        if not self.host._closed and self.host.isVisible() and not self.host._busy:
            self.host.activateWindow()
            self.host.focus_weight()

    def _print_failed(self, message: str) -> None:
        self.host._busy = False
        self.host._update_actions()
        self.host.set_status(f"Printing failed: {message}", error=True)
        self._restore_focus()

    def complete_issue(self) -> None:
        snapshot = self.printed
        h = self.host
        if snapshot is None or not h.editable or h.current_list_id != snapshot.list_id:
            return
        result = h.db_manager.issue_printed_list(snapshot.list_id, snapshot.signature)
        if result.failure:
            if result.failure.kind == RepositoryFailureKind.CONFLICT:
                self.invalidate()
            h.set_status(
                f"Printed, but not issued: {result.failure.message}"
                + (" Alt+I retries without printing again." if self.printed else ""),
                error=True,
            )
            h._update_actions()
            return
        identifier = str(snapshot.details["list_identifier"])
        self.invalidate()
        h.create_new_list()
        h.set_status(f"{identifier} issued. Ready for the next list.")

    def shutdown(self) -> None:
        if self._preview_builder is not None:
            self._preview_builder.shutdown()
