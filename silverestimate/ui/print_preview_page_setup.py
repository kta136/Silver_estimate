"""Printer selection, page setup, and orientation controls for preview."""

from __future__ import annotations

import logging

from PySide6.QtGui import QAction, QPageLayout
from PySide6.QtPrintSupport import QPageSetupDialog, QPrintDialog, QPrinter
from PySide6.QtWidgets import QDialog, QMenu, QSizePolicy

from .icons import get_icon
from .print_preview_dialog import PrintPreviewDialog
from .print_preview_preferences import PrintPreviewPreferences
from .themed_controls import ThemedComboBox

LOGGER = logging.getLogger(__name__)


class PrintPreviewPageSetupController:
    """Own printer/page dialogs and orientation mutation."""

    def __init__(
        self,
        *,
        printer: QPrinter,
        preferences: PrintPreviewPreferences,
    ) -> None:
        self._printer = printer
        self._preferences = preferences

    def add_menu_actions(
        self,
        menu: QMenu,
        preview: PrintPreviewDialog,
    ) -> None:
        select_printer = QAction(
            get_icon("printer_select", widget=preview),
            "Printer Setup",
            preview,
        )
        select_printer.setToolTip("Choose a printer and keep it for this session")
        select_printer.setPriority(QAction.Priority.LowPriority)
        select_printer.triggered.connect(lambda: self.choose_printer(preview))
        menu.addAction(select_printer)

        page_setup = QAction(
            get_icon("page_setup", widget=preview),
            "Page Setup",
            preview,
        )
        page_setup.setToolTip("Choose page size, margins, and paper setup")
        page_setup.setPriority(QAction.Priority.LowPriority)
        page_setup.triggered.connect(lambda: self.open_page_setup(preview))
        menu.addAction(page_setup)

    def build_orientation_combo(
        self,
        preview: PrintPreviewDialog,
    ) -> ThemedComboBox:
        combo = ThemedComboBox(preview)
        combo.setObjectName("PreviewOrientationCombo")
        combo.setMinimumWidth(88)
        combo.setMaximumWidth(94)
        combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        combo.setToolTip("Choose paper orientation for this preview")
        combo.addItem("Portrait", QPageLayout.Orientation.Portrait)
        combo.addItem("Landscape", QPageLayout.Orientation.Landscape)
        current = self._printer.pageLayout().orientation()
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.currentIndexChanged.connect(
            lambda: self.set_orientation(preview, combo.currentData())
        )
        return combo

    def choose_printer(self, preview: PrintPreviewDialog) -> bool:
        dialog = QPrintDialog(self._printer, preview)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        self._preferences.remember_selected_printer(self._printer)
        preview.preview_widget.updatePreview()
        return True

    def open_page_setup(self, preview: PrintPreviewDialog) -> bool:
        dialog = QPageSetupDialog(self._printer, preview)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        preview.preview_widget.updatePreview()
        return True

    def set_orientation(
        self,
        preview: PrintPreviewDialog,
        orientation: QPageLayout.Orientation,
    ) -> bool:
        try:
            self._printer.setPageOrientation(orientation)
        except Exception as exc:
            LOGGER.debug("Failed to set preview orientation: %s", exc)
            return False
        preview.preview_widget.updatePreview()
        return True


__all__ = ["PrintPreviewPageSetupController"]
