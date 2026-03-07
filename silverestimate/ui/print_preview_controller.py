"""Preview dialog helpers extracted from PrintManager."""

from __future__ import annotations

import logging
from typing import Callable

from PyQt5.QtPrintSupport import (
    QPageSetupDialog,
    QPrintDialog,
    QPrinter,
    QPrintPreviewDialog,
    QPrintPreviewWidget,
)
from PyQt5.QtWidgets import (
    QAction,
    QDialog,
    QFileDialog,
    QLabel,
    QMessageBox,
    QToolBar,
    QWidgetAction,
)

from silverestimate.infrastructure.settings import get_app_settings

LOGGER = logging.getLogger(__name__)


class PrintPreviewController:
    """Own the preview dialog and related export/print actions."""

    def __init__(
        self,
        *,
        printer: QPrinter,
        render_document: Callable[[QPrinter, str, bool], None],
    ) -> None:
        self._printer = printer
        self._render_document = render_document

    def open_preview(
        self,
        html_content: str,
        parent_widget,
        title: str,
        *,
        table_mode: bool = False,
    ) -> None:
        """Open QPrintPreviewDialog with custom toolbar actions and persistent zoom."""
        preview = QPrintPreviewDialog(self._printer, parent_widget)
        preview.setWindowTitle(title)
        preview.paintRequested.connect(
            lambda printer: self._render_document(
                printer,
                html_content,
                table_mode,
            )
        )

        preview_widget = preview.findChild(QPrintPreviewWidget)
        self._apply_initial_zoom(preview_widget)

        try:
            self._augment_preview_toolbar(
                preview,
                preview_widget,
                html_content,
                table_mode,
                parent_widget,
            )
        except Exception as exc:
            LOGGER.warning("Could not augment preview toolbar: %s", exc)

        preview.showMaximized()
        preview.exec_()
        self._save_preview_zoom(preview_widget)

    def _apply_initial_zoom(self, preview_widget: QPrintPreviewWidget | None) -> None:
        if not preview_widget:
            LOGGER.warning("Could not find QPrintPreviewWidget to set zoom.")
            return
        try:
            settings = get_app_settings()
            default_zoom = 1.25
            zoom_factor = settings.value(
                "print/preview_zoom",
                defaultValue=default_zoom,
                type=float,
            )
            zoom_factor = max(0.1, min(zoom_factor, 5.0))
            LOGGER.debug("Applying zoom factor: %s", zoom_factor)
            try:
                preview_widget.setZoomMode(QPrintPreviewWidget.CustomZoom)
            except Exception as exc:
                LOGGER.debug(
                    "Failed to switch preview widget to custom zoom: %s",
                    exc,
                )
            preview_widget.setZoomFactor(zoom_factor)
        except Exception as exc:
            LOGGER.warning("Error setting initial zoom: %s", exc)

    def _save_preview_zoom(self, preview_widget: QPrintPreviewWidget | None) -> None:
        if not preview_widget:
            return
        try:
            zoom_factor = float(preview_widget.zoomFactor())
            settings = get_app_settings()
            settings.setValue("print/preview_zoom", zoom_factor)
            LOGGER.debug("Saved preview zoom: %s", zoom_factor)
        except Exception as exc:
            LOGGER.warning("Could not save preview zoom: %s", exc)

    def _augment_preview_toolbar(
        self,
        preview,
        preview_widget,
        html_content,
        table_mode,
        parent_widget,
    ) -> None:
        """Add useful actions to the existing QPrintPreviewDialog toolbar."""
        toolbars = preview.findChildren(QToolBar)
        toolbar = toolbars[0] if toolbars else None
        if not toolbar:
            return

        def sep():
            toolbar.addSeparator()

        act_pdf = QAction("Save PDF", preview)
        act_pdf.setToolTip("Export to PDF file (Ctrl+S)")
        act_pdf.setShortcut("Ctrl+S")
        act_pdf.triggered.connect(
            lambda: self._export_pdf_via_dialog(
                html_content,
                table_mode,
                parent_widget,
            )
        )
        toolbar.addAction(act_pdf)

        act_page = QAction("Page Setup", preview)
        act_page.setToolTip("Choose page size, margins, orientation")
        act_page.triggered.connect(lambda: self._page_setup_and_refresh(preview))
        toolbar.addAction(act_page)

        sep()

        if preview_widget:
            act_zi = QAction("Zoom +", preview)
            act_zi.setShortcut("+")
            act_zi.triggered.connect(lambda: self._zoom_in(preview_widget))
            toolbar.addAction(act_zi)

            act_zo = QAction("Zoom -", preview)
            act_zo.setShortcut("-")
            act_zo.triggered.connect(lambda: self._zoom_out(preview_widget))
            toolbar.addAction(act_zo)

            act_fitw = QAction("Fit Width", preview)
            act_fitw.setShortcut("Ctrl+W")
            act_fitw.triggered.connect(lambda: self._fit_width(preview_widget))
            toolbar.addAction(act_fitw)

            act_fitp = QAction("Fit Page", preview)
            act_fitp.setShortcut("Ctrl+F")
            act_fitp.triggered.connect(lambda: self._fit_page(preview_widget))
            toolbar.addAction(act_fitp)

        sep()

        act_orient = QAction("Toggle Portrait/Landscape", preview)
        act_orient.setToolTip("Switch orientation and refresh preview")
        act_orient.triggered.connect(
            lambda: self._toggle_orientation_and_refresh(preview)
        )
        toolbar.addAction(act_orient)

        sep()

        if preview_widget:
            act_first = QAction("First", preview)
            act_first.setToolTip("Go to first page (Home)")
            act_first.setShortcut("Home")
            act_first.triggered.connect(lambda: preview_widget.setCurrentPage(1))
            toolbar.addAction(act_first)

            act_prev = QAction("Prev", preview)
            act_prev.setShortcut("PgUp")
            act_prev.triggered.connect(
                lambda: preview_widget.setCurrentPage(
                    max(1, preview_widget.currentPage() - 1)
                )
            )
            toolbar.addAction(act_prev)

            act_next = QAction("Next", preview)
            act_next.setShortcut("PgDown")
            act_next.triggered.connect(lambda: self._go_next_page(preview_widget))
            toolbar.addAction(act_next)

            act_last = QAction("Last", preview)
            act_last.setToolTip("Go to last page (End)")
            act_last.setShortcut("End")
            act_last.triggered.connect(lambda: self._go_last_page(preview_widget))
            toolbar.addAction(act_last)

            page_info = QLabel("")
            page_info_action = QWidgetAction(preview)
            page_info_action.setDefaultWidget(page_info)
            toolbar.addAction(page_info_action)

            def update_page_info():
                try:
                    page_info.setText(
                        f"  Page {preview_widget.currentPage()} / {preview_widget.pageCount()}  "
                    )
                except Exception as exc:
                    LOGGER.debug("Failed to update preview page info: %s", exc)

            try:
                preview_widget.previewChanged.connect(update_page_info)
            except Exception as exc:
                LOGGER.debug("Failed to hook previewChanged signal: %s", exc)
            update_page_info()

        sep()

        act_qprint = QAction("Quick Print", preview)
        act_qprint.setToolTip("Send directly to current/default printer (Ctrl+Shift+P)")
        act_qprint.setShortcut("Ctrl+Shift+P")
        act_qprint.triggered.connect(
            lambda: self._quick_print_current(
                preview,
                html_content,
                table_mode,
                parent_widget,
            )
        )
        toolbar.addAction(act_qprint)

        act_sel_prn = QAction("Select Printer", preview)
        act_sel_prn.setToolTip("Choose a printer and keep it for this session")
        act_sel_prn.triggered.connect(lambda: self._choose_printer(preview))
        toolbar.addAction(act_sel_prn)

    def _zoom_in(self, preview_widget: QPrintPreviewWidget) -> None:
        try:
            preview_widget.setZoomMode(QPrintPreviewWidget.CustomZoom)
        except Exception as exc:
            LOGGER.debug("Failed to switch preview widget to custom zoom: %s", exc)
        try:
            zoom_factor = float(preview_widget.zoomFactor())
        except Exception:
            zoom_factor = 1.0
        preview_widget.setZoomFactor(min(5.0, zoom_factor * 1.10))

    def _zoom_out(self, preview_widget: QPrintPreviewWidget) -> None:
        try:
            preview_widget.setZoomMode(QPrintPreviewWidget.CustomZoom)
        except Exception as exc:
            LOGGER.debug("Failed to switch preview widget to custom zoom: %s", exc)
        try:
            zoom_factor = float(preview_widget.zoomFactor())
        except Exception:
            zoom_factor = 1.0
        preview_widget.setZoomFactor(max(0.1, zoom_factor / 1.10))

    def _fit_width(self, preview_widget: QPrintPreviewWidget) -> None:
        try:
            preview_widget.fitToWidth()
        except Exception as exc:
            LOGGER.debug("Failed to fit preview to width: %s", exc)

    def _fit_page(self, preview_widget: QPrintPreviewWidget) -> None:
        try:
            preview_widget.fitInView()
        except Exception as exc:
            LOGGER.debug("Failed to fit preview to page: %s", exc)

    def _go_next_page(self, preview_widget: QPrintPreviewWidget) -> None:
        try:
            page_count = preview_widget.pageCount()
        except Exception:
            page_count = preview_widget.currentPage() + 1
        preview_widget.setCurrentPage(min(page_count, preview_widget.currentPage() + 1))

    def _go_last_page(self, preview_widget: QPrintPreviewWidget) -> None:
        try:
            preview_widget.setCurrentPage(preview_widget.pageCount())
        except Exception as exc:
            LOGGER.debug("Failed to navigate preview to last page: %s", exc)

    def _choose_printer(self, preview) -> None:
        dialog = QPrintDialog(self._printer, preview)
        if dialog.exec_() != QDialog.Accepted:
            return
        try:
            settings = get_app_settings()
            settings.setValue("print/default_printer", self._printer.printerName())
        except Exception as exc:
            LOGGER.debug("Failed to persist selected printer name: %s", exc)
        preview_widget = preview.findChild(QPrintPreviewWidget)
        if preview_widget:
            preview_widget.updatePreview()

    def _export_pdf_via_dialog(self, html_content, table_mode, parent_widget) -> None:
        """Prompt for a PDF path and export current content as PDF."""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            parent_widget,
            "Save as PDF",
            "estimate.pdf",
            "PDF Files (*.pdf)",
            options=options,
        )
        if not file_path:
            return
        try:
            pdf_printer = QPrinter(QPrinter.HighResolution)
            pdf_printer.setOutputFormat(QPrinter.PdfFormat)
            if not file_path.lower().endswith(".pdf"):
                file_path = f"{file_path}.pdf"
            pdf_printer.setOutputFileName(file_path)
            pdf_printer.setPageSize(self._printer.pageSize())
            pdf_printer.setOrientation(self._printer.orientation())
            settings = get_app_settings()
            margins_str = settings.value(
                "print/margins",
                defaultValue="10,5,10,5",
                type=str,
            )
            try:
                margins = [int(m.strip()) for m in margins_str.split(",")]
                if len(margins) != 4:
                    margins = [10, 5, 10, 5]
            except Exception:
                margins = [10, 5, 10, 5]
            pdf_printer.setPageMargins(
                margins[0],
                margins[1],
                margins[2],
                margins[3],
                QPrinter.Millimeter,
            )
            self._render_document(pdf_printer, html_content, table_mode)
            QMessageBox.information(
                parent_widget,
                "Saved",
                f"PDF saved to:\n{file_path}",
            )
        except Exception as exc:
            QMessageBox.critical(
                parent_widget,
                "Export Failed",
                f"Could not export PDF:\n{str(exc)}",
            )

    def _page_setup_and_refresh(self, preview) -> None:
        """Open page setup dialog and refresh preview if accepted."""
        dialog = QPageSetupDialog(self._printer, preview)
        if dialog.exec_() == QDialog.Accepted:
            preview_widget = preview.findChild(QPrintPreviewWidget)
            if preview_widget:
                preview_widget.updatePreview()
            else:
                preview.repaint()

    def _toggle_orientation_and_refresh(self, preview) -> None:
        """Toggle between portrait and landscape and refresh preview."""
        current = self._printer.orientation()
        self._printer.setOrientation(
            QPrinter.Landscape if current == QPrinter.Portrait else QPrinter.Portrait
        )
        preview_widget = preview.findChild(QPrintPreviewWidget)
        if preview_widget:
            preview_widget.updatePreview()
        else:
            preview.repaint()

    def _quick_print_current(
        self,
        preview,
        html_content,
        table_mode,
        parent_widget,
    ) -> None:
        """Send the document directly to the currently configured/default printer."""
        try:
            self._render_document(self._printer, html_content, table_mode)
            QMessageBox.information(
                parent_widget or preview,
                "Printing",
                "Document sent to printer.",
            )
        except Exception as exc:
            QMessageBox.critical(
                parent_widget or preview,
                "Print Failed",
                f"Could not print document:\n{str(exc)}",
            )
