"""Typed PDF export and physical-print execution for previews."""

from __future__ import annotations

import logging
import os
import tempfile
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from .print_page_settings import (
    copy_printer_page_layout,
    validate_quick_print_printer,
)
from .print_payload_builder import PrintDocument, PrintPreviewPayload
from .print_preview_preferences import PrintPreviewPreferences

LOGGER = logging.getLogger(__name__)


class PrintOutputStatus(str, Enum):
    """Stable output states shared by UI and tests."""

    SUCCESS = "success"
    CANCELLED = "cancelled"
    VALIDATION_FAILED = "validation_failed"
    FAILED = "failed"


@dataclass(frozen=True)
class PrintOutputOutcome:
    """Explicit result from PDF export or physical print execution."""

    status: PrintOutputStatus
    message: str = ""
    output_path: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status is PrintOutputStatus.SUCCESS

    @property
    def cancelled(self) -> bool:
        return self.status is PrintOutputStatus.CANCELLED


class PrintOutputService:
    """Execute print outputs without owning dialogs or preview widgets."""

    def __init__(
        self,
        *,
        printer: QPrinter,
        render_document: Callable[[QPrinter, PrintDocument], None],
        printer_validator: Callable[[QPrinter], tuple[bool, str]] | None = None,
    ) -> None:
        self._printer = printer
        self._render_document = render_document
        self._printer_validator = printer_validator or (
            lambda current_printer: validate_quick_print_printer(current_printer)
        )

    def export_pdf(
        self,
        payload: PrintPreviewPayload,
        file_path: str,
    ) -> PrintOutputOutcome:
        """Atomically render a payload to a selected PDF path."""
        normalized_path = str(file_path or "").strip()
        if not normalized_path:
            return PrintOutputOutcome(PrintOutputStatus.CANCELLED)
        if not normalized_path.lower().endswith(".pdf"):
            normalized_path = f"{normalized_path}.pdf"

        target_path = os.path.abspath(normalized_path)
        target_dir = os.path.dirname(target_path) or os.getcwd()
        temp_path = ""
        try:
            fd, temp_path = tempfile.mkstemp(
                prefix=".silverestimate-",
                suffix=".pdf",
                dir=target_dir,
            )
            os.close(fd)
            pdf_printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            pdf_printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            pdf_printer.setOutputFileName(temp_path)
            copy_printer_page_layout(self._printer, pdf_printer)
            self._render_document(pdf_printer, payload.document)
            if not os.path.exists(temp_path) or os.path.getsize(temp_path) <= 0:
                raise RuntimeError("PDF export produced an empty file.")
            os.replace(temp_path, target_path)
            temp_path = ""
            return PrintOutputOutcome(
                PrintOutputStatus.SUCCESS,
                message=f"PDF saved to:\n{target_path}",
                output_path=target_path,
            )
        except Exception as exc:
            LOGGER.warning(
                "Failed to export PDF '%s': %s",
                target_path,
                exc,
                exc_info=True,
            )
            return PrintOutputOutcome(
                PrintOutputStatus.FAILED,
                message=friendly_export_error_message(target_path, exc),
                output_path=target_path,
            )
        finally:
            if temp_path:
                try:
                    os.remove(temp_path)
                except OSError:
                    LOGGER.debug("Failed to remove temporary PDF %s", temp_path)

    def quick_print(self, payload: PrintPreviewPayload) -> PrintOutputOutcome:
        """Send the current immutable payload to the configured printer."""
        try:
            valid_printer, validation_message = self._printer_validator(self._printer)
            if not valid_printer:
                return PrintOutputOutcome(
                    PrintOutputStatus.VALIDATION_FAILED,
                    message=validation_message,
                )
            self._render_document(self._printer, payload.document)
            return PrintOutputOutcome(PrintOutputStatus.SUCCESS)
        except Exception as exc:
            LOGGER.warning("Quick print failed: %s", exc, exc_info=True)
            return PrintOutputOutcome(
                PrintOutputStatus.FAILED,
                message=friendly_print_error_message(exc),
            )


class PrintPreviewOutputController:
    """Own output prompts and translate typed outcomes into preview feedback."""

    def __init__(
        self,
        *,
        service: PrintOutputService,
        preferences: PrintPreviewPreferences,
    ) -> None:
        self._service = service
        self._preferences = preferences

    def export_pdf_via_dialog(
        self,
        payload: PrintPreviewPayload,
        parent_widget: QWidget | None,
    ) -> PrintOutputOutcome:
        file_path, _ = QFileDialog.getSaveFileName(
            parent_widget,
            "Save as PDF",
            self._preferences.default_pdf_path(payload.suggested_filename),
            "PDF Files (*.pdf)",
        )
        outcome = self._service.export_pdf(payload, file_path)
        if outcome.cancelled:
            return outcome
        if outcome.succeeded:
            target_dir = os.path.dirname(outcome.output_path) or os.getcwd()
            self._preferences.remember_export_directory(target_dir)
            QMessageBox.information(
                parent_widget,
                "Saved",
                outcome.message,
            )
            return outcome
        QMessageBox.critical(
            parent_widget,
            "Export Failed",
            outcome.message,
        )
        return outcome

    def quick_print_current(
        self,
        preview,
        payload: PrintPreviewPayload,
        parent_widget: QWidget | None,
    ) -> PrintOutputOutcome:
        outcome = self._service.quick_print(payload)
        if outcome.succeeded:
            try:
                preview.accept()
            except Exception as exc:
                LOGGER.debug("Failed to close preview after printing: %s", exc)
            return outcome
        QMessageBox.critical(
            parent_widget or preview,
            "Print Failed",
            outcome.message,
        )
        return outcome


def friendly_export_error_message(file_path: str, exc: Exception) -> str:
    lower = str(exc or "").strip().lower()
    hint = "Choose a different location and try again."
    if isinstance(exc, PermissionError) or any(
        token in lower for token in ("permission", "access is denied", "denied")
    ):
        hint = (
            "The file may be open in another program, or you may not have "
            "permission to save in that folder."
        )
    elif any(token in lower for token in ("in use", "used by another process")):
        hint = "Close the file in any other program and try again."
    elif any(token in lower for token in ("no such file", "cannot find")):
        hint = "The target folder may no longer exist."
    elif "empty file" in lower:
        hint = "The PDF renderer did not produce output. Try printing again."
    return f"Could not save the PDF to:\n{file_path}\n\n{hint}"


def friendly_print_error_message(exc: Exception) -> str:
    lower = str(exc or "").strip().lower()
    hint = "Check that the selected printer is available, then try again."
    if any(token in lower for token in ("not found", "invalid printer")):
        hint = "The selected printer is not available. Choose another printer."
    elif any(token in lower for token in ("offline", "unreachable")):
        hint = "The selected printer appears to be offline or unreachable."
    return "Could not send the document to the printer.\n\n" + hint


__all__ = [
    "PrintOutputOutcome",
    "PrintOutputService",
    "PrintOutputStatus",
    "PrintPreviewOutputController",
    "friendly_export_error_message",
    "friendly_print_error_message",
]
