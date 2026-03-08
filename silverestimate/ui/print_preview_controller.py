"""Preview dialog helpers extracted from PrintManager."""

from __future__ import annotations

import logging
import os
from typing import Callable

from PyQt5.QtCore import QEvent, QObject, QSize, Qt
from PyQt5.QtPrintSupport import (
    QPageSetupDialog,
    QPrintDialog,
    QPrinter,
    QPrintPreviewDialog,
    QPrintPreviewWidget,
)
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSizePolicy,
    QSpinBox,
    QToolBar,
    QWidget,
)

from silverestimate.infrastructure.settings import get_app_settings
from silverestimate.ui.icons import get_icon
from silverestimate.ui.print_payload_builder import PrintPreviewPayload

LOGGER = logging.getLogger(__name__)

_LAYOUT_LABELS = {
    "old": "Classic",
    "new": "Modern",
    "thermal": "Thermal",
}


class _PreviewWheelZoomFilter(QObject):
    """Translate Ctrl+wheel into preview zoom actions."""

    def __init__(
        self,
        *,
        zoom_in: Callable[[], None],
        zoom_out: Callable[[], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._zoom_in = zoom_in
        self._zoom_out = zoom_out

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API
        if event.type() != QEvent.Wheel:
            return super().eventFilter(watched, event)
        if not bool(event.modifiers() & Qt.ControlModifier):
            return super().eventFilter(watched, event)

        delta = 0
        try:
            delta = int(event.angleDelta().y())
        except Exception:
            delta = 0
        if delta > 0:
            self._zoom_in()
        elif delta < 0:
            self._zoom_out()
        else:
            return super().eventFilter(watched, event)
        return True


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
        payload: PrintPreviewPayload,
        *,
        parent_widget=None,
    ) -> None:
        """Open QPrintPreviewDialog with custom toolbar actions and persistent zoom."""
        preview = QPrintPreviewDialog(self._printer, parent_widget)
        state = {"payload": payload}
        preview.setWindowTitle(payload.title)
        preview.paintRequested.connect(
            lambda printer: self._render_document(
                printer,
                state["payload"].html_content,
                state["payload"].table_mode,
            )
        )

        preview_widget = preview.findChild(QPrintPreviewWidget)
        self._apply_initial_zoom(preview_widget)
        self._install_ctrl_wheel_zoom(preview, preview_widget)

        try:
            self._augment_preview_toolbar(
                preview,
                preview_widget,
                state,
                parent_widget,
            )
        except Exception as exc:
            LOGGER.warning("Could not augment preview toolbar: %s", exc, exc_info=True)

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
        preview: QPrintPreviewDialog,
        preview_widget: QPrintPreviewWidget | None,
        state: dict[str, PrintPreviewPayload],
        parent_widget,
    ) -> None:
        """Add useful actions to the existing QPrintPreviewDialog toolbar."""
        toolbars = preview.findChildren(QToolBar)
        toolbar = toolbars[0] if toolbars else None
        if not toolbar:
            return

        toolbar.clear()
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        toolbar.setIconSize(QSize(24, 24))
        toolbar.setStyleSheet(
            """
            QToolButton {
                min-width: 40px;
                min-height: 40px;
                padding: 6px;
            }
            """
        )

        payload = state["payload"]

        act_qprint = QAction(get_icon("print", widget=preview), "Quick Print", preview)
        act_qprint.setToolTip("Send directly to the selected printer (Ctrl+Shift+P)")
        act_qprint.setShortcut("Ctrl+Shift+P")
        act_qprint.triggered.connect(
            lambda: self._quick_print_current(
                preview,
                state["payload"],
                parent_widget,
            )
        )
        toolbar.addAction(act_qprint)

        act_pdf = QAction(get_icon("save_pdf", widget=preview), "Save PDF", preview)
        act_pdf.setToolTip("Export the current preview to a PDF file (Ctrl+S)")
        act_pdf.setShortcut("Ctrl+S")
        act_pdf.triggered.connect(
            lambda: self._export_pdf_via_dialog(state["payload"], parent_widget)
        )
        toolbar.addAction(act_pdf)

        act_sel_prn = QAction(
            get_icon("printer_select", widget=preview),
            "Printer",
            preview,
        )
        act_sel_prn.setToolTip("Choose a printer and keep it for this session")
        act_sel_prn.triggered.connect(lambda: self._choose_printer(preview))
        toolbar.addAction(act_sel_prn)

        act_page = QAction(get_icon("page_setup", widget=preview), "Page Setup", preview)
        act_page.setToolTip("Choose page size, margins, and paper setup")
        act_page.triggered.connect(lambda: self._page_setup_and_refresh(preview))
        toolbar.addAction(act_page)

        orientation_combo = self._build_orientation_combo(preview)
        toolbar.addWidget(orientation_combo)

        if payload.document_kind == "estimate" and payload.available_layouts:
            layout_combo = self._build_layout_combo(preview, payload)
            layout_combo.currentIndexChanged.connect(
                lambda: self._switch_layout(
                    preview,
                    layout_combo.currentData(),
                    state,
                )
            )
            toolbar.addWidget(layout_combo)

        toolbar.addSeparator()

        if preview_widget:
            self._add_view_mode_actions(toolbar, preview_widget, preview)
            toolbar.addSeparator()

            act_fitw = QAction(
                get_icon("fit_width", widget=preview),
                "Fit Width",
                preview,
            )
            act_fitw.setShortcut("Ctrl+W")
            act_fitw.triggered.connect(lambda: self._fit_width(preview_widget))
            toolbar.addAction(act_fitw)

            act_fitp = QAction(
                get_icon("fit_page", widget=preview),
                "Fit Page",
                preview,
            )
            act_fitp.setShortcut("Ctrl+F")
            act_fitp.triggered.connect(lambda: self._fit_page(preview_widget))
            toolbar.addAction(act_fitp)

            act_zo = QAction(
                get_icon("zoom_out", widget=preview),
                "Zoom Out",
                preview,
            )
            act_zo.setShortcut("Ctrl+-")
            act_zo.triggered.connect(lambda: self._zoom_out(preview_widget))
            toolbar.addAction(act_zo)

            act_zi = QAction(
                get_icon("zoom_in", widget=preview),
                "Zoom In",
                preview,
            )
            act_zi.setShortcut("Ctrl++")
            act_zi.triggered.connect(lambda: self._zoom_in(preview_widget))
            toolbar.addAction(act_zi)

        spacer = QWidget(preview)
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        if preview_widget:
            act_first = QAction(
                get_icon("page_first", widget=preview),
                "First",
                preview,
            )
            act_first.setToolTip("Go to first page (Home)")
            act_first.setShortcut("Home")
            act_first.triggered.connect(lambda: preview_widget.setCurrentPage(1))
            toolbar.addAction(act_first)

            act_prev = QAction(
                get_icon("page_previous", widget=preview),
                "Prev",
                preview,
            )
            act_prev.setToolTip("Go to previous page (PgUp)")
            act_prev.setShortcut("PgUp")
            act_prev.triggered.connect(
                lambda: preview_widget.setCurrentPage(
                    max(1, preview_widget.currentPage() - 1)
                )
            )
            toolbar.addAction(act_prev)

            page_spin, total_label = self._build_page_navigation_widget(
                preview,
                preview_widget,
            )
            toolbar.addWidget(page_spin.parentWidget())

            act_next = QAction(
                get_icon("page_next", widget=preview),
                "Next",
                preview,
            )
            act_next.setToolTip("Go to next page (PgDown)")
            act_next.setShortcut("PgDown")
            act_next.triggered.connect(lambda: self._go_next_page(preview_widget))
            toolbar.addAction(act_next)

            act_last = QAction(
                get_icon("page_last", widget=preview),
                "Last",
                preview,
            )
            act_last.setToolTip("Go to last page (End)")
            act_last.setShortcut("End")
            act_last.triggered.connect(lambda: self._go_last_page(preview_widget))
            toolbar.addAction(act_last)

            def update_page_info() -> None:
                try:
                    page_count = max(1, int(preview_widget.pageCount()))
                except Exception:
                    page_count = 1
                try:
                    current_page = int(preview_widget.currentPage())
                except Exception:
                    current_page = 1
                current_page = min(max(1, current_page), page_count)
                page_spin.blockSignals(True)
                page_spin.setMaximum(page_count)
                page_spin.setValue(current_page)
                page_spin.blockSignals(False)
                total_label.setText(f"/ {page_count}")

            try:
                preview_widget.previewChanged.connect(update_page_info)
            except Exception as exc:
                LOGGER.debug("Failed to hook previewChanged signal: %s", exc)
            update_page_info()

    def _add_view_mode_actions(
        self,
        toolbar: QToolBar,
        preview_widget: QPrintPreviewWidget,
        preview: QPrintPreviewDialog,
    ) -> None:
        group = QActionGroup(preview)
        group.setExclusive(True)

        view_actions: list[tuple[QAction, QPrintPreviewWidget.ViewMode]] = []
        for icon_name, text, mode in (
            (
                "view_single_page",
                "Single Page",
                QPrintPreviewWidget.SinglePageView,
            ),
            (
                "view_facing_pages",
                "Facing Pages",
                QPrintPreviewWidget.FacingPagesView,
            ),
            (
                "view_overview",
                "All Pages",
                QPrintPreviewWidget.AllPagesView,
            ),
        ):
            action = QAction(get_icon(icon_name, widget=preview), text, preview)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked=False, view_mode=mode: self._set_view_mode(
                    preview_widget,
                    view_mode,
                )
            )
            group.addAction(action)
            toolbar.addAction(action)
            view_actions.append((action, mode))

        def sync_view_actions() -> None:
            try:
                current_mode = preview_widget.viewMode()
            except Exception:
                current_mode = QPrintPreviewWidget.SinglePageView
            for action, mode in view_actions:
                action.blockSignals(True)
                action.setChecked(mode == current_mode)
                action.blockSignals(False)

        sync_view_actions()
        try:
            preview_widget.previewChanged.connect(sync_view_actions)
        except Exception as exc:
            LOGGER.debug("Failed to sync preview view mode actions: %s", exc)

    def _build_orientation_combo(self, preview: QPrintPreviewDialog) -> QComboBox:
        combo = QComboBox(preview)
        combo.setObjectName("PreviewOrientationCombo")
        combo.setToolTip("Choose paper orientation for this preview")
        combo.addItem("Portrait", QPrinter.Portrait)
        combo.addItem("Landscape", QPrinter.Landscape)
        current = self._printer.orientation()
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.currentIndexChanged.connect(
            lambda: self._set_orientation_and_refresh(preview, combo.currentData())
        )
        return combo

    def _build_layout_combo(
        self,
        preview: QPrintPreviewDialog,
        payload: PrintPreviewPayload,
    ) -> QComboBox:
        combo = QComboBox(preview)
        combo.setObjectName("PreviewLayoutCombo")
        combo.setToolTip("Switch the estimate print layout without leaving preview")
        for layout_mode in payload.available_layouts:
            combo.addItem(_LAYOUT_LABELS.get(layout_mode, layout_mode.title()), layout_mode)
        index = combo.findData(payload.layout_mode)
        combo.setCurrentIndex(index if index >= 0 else 0)
        return combo

    def _build_page_navigation_widget(
        self,
        preview: QPrintPreviewDialog,
        preview_widget: QPrintPreviewWidget,
    ) -> tuple[QSpinBox, QLabel]:
        container = QWidget(preview)
        container.setObjectName("PreviewPageNavigator")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(4)

        label = QLabel("Page", container)
        spin = QSpinBox(container)
        spin.setRange(1, 1)
        spin.setMinimumWidth(72)
        spin.setAlignment(Qt.AlignRight)
        spin.setToolTip("Jump directly to a page number")
        total_label = QLabel("/ 1", container)

        spin.valueChanged.connect(lambda value: preview_widget.setCurrentPage(value))

        layout.addWidget(label)
        layout.addWidget(spin)
        layout.addWidget(total_label)
        return spin, total_label

    def _install_ctrl_wheel_zoom(
        self,
        preview: QPrintPreviewDialog,
        preview_widget: QPrintPreviewWidget | None,
    ) -> None:
        if not preview_widget:
            return
        filter_obj = _PreviewWheelZoomFilter(
            zoom_in=lambda: self._zoom_in(preview_widget),
            zoom_out=lambda: self._zoom_out(preview_widget),
            parent=preview,
        )
        preview_widget.installEventFilter(filter_obj)
        viewport = getattr(preview_widget, "viewport", lambda: None)()
        if viewport is not None:
            viewport.installEventFilter(filter_obj)
        preview._wheel_zoom_filter = filter_obj  # type: ignore[attr-defined]

    def _switch_layout(
        self,
        preview: QPrintPreviewDialog,
        layout_mode,
        state: dict[str, PrintPreviewPayload],
    ) -> None:
        payload = state["payload"]
        if not layout_mode or payload.layout_factory is None:
            return
        next_payload = payload.layout_factory(str(layout_mode))
        if next_payload is None:
            return
        state["payload"] = next_payload
        preview.setWindowTitle(next_payload.title)
        preview_widget = preview.findChild(QPrintPreviewWidget)
        if preview_widget:
            preview_widget.updatePreview()
        else:
            preview.repaint()

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

    def _set_view_mode(
        self,
        preview_widget: QPrintPreviewWidget,
        view_mode: QPrintPreviewWidget.ViewMode,
    ) -> None:
        try:
            preview_widget.setViewMode(view_mode)
        except Exception as exc:
            LOGGER.debug("Failed to set preview view mode: %s", exc)

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

    def _choose_printer(self, preview: QPrintPreviewDialog) -> None:
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

    def _export_pdf_via_dialog(
        self,
        payload: PrintPreviewPayload,
        parent_widget,
    ) -> None:
        """Prompt for a PDF path and export current content as PDF."""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(
            parent_widget,
            "Save as PDF",
            self._default_pdf_path(payload.suggested_filename),
            "PDF Files (*.pdf)",
            options=options,
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".pdf"):
            file_path = f"{file_path}.pdf"
        try:
            pdf_printer = QPrinter(QPrinter.HighResolution)
            pdf_printer.setOutputFormat(QPrinter.PdfFormat)
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
            self._render_document(
                pdf_printer,
                payload.html_content,
                payload.table_mode,
            )
            settings.setValue("print/last_export_dir", os.path.dirname(file_path))
            QMessageBox.information(
                parent_widget,
                "Saved",
                f"PDF saved to:\n{file_path}",
            )
        except Exception as exc:
            LOGGER.warning(
                "Failed to export PDF '%s': %s",
                file_path,
                exc,
                exc_info=True,
            )
            QMessageBox.critical(
                parent_widget,
                "Export Failed",
                self._friendly_export_error_message(file_path, exc),
            )

    def _default_pdf_path(self, suggested_filename: str) -> str:
        settings = get_app_settings()
        last_export_dir = settings.value("print/last_export_dir", "", type=str) or ""
        if last_export_dir and os.path.isdir(last_export_dir):
            return os.path.join(last_export_dir, suggested_filename)
        return suggested_filename

    @staticmethod
    def _friendly_export_error_message(file_path: str, exc: Exception) -> str:
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
        return f"Could not save the PDF to:\n{file_path}\n\n{hint}"

    def _page_setup_and_refresh(self, preview: QPrintPreviewDialog) -> None:
        """Open page setup dialog and refresh preview if accepted."""
        dialog = QPageSetupDialog(self._printer, preview)
        if dialog.exec_() == QDialog.Accepted:
            preview_widget = preview.findChild(QPrintPreviewWidget)
            if preview_widget:
                preview_widget.updatePreview()
            else:
                preview.repaint()

    def _set_orientation_and_refresh(
        self,
        preview: QPrintPreviewDialog,
        orientation: QPrinter.Orientation,
    ) -> None:
        try:
            self._printer.setOrientation(orientation)
        except Exception as exc:
            LOGGER.debug("Failed to set preview orientation: %s", exc)
            return
        preview_widget = preview.findChild(QPrintPreviewWidget)
        if preview_widget:
            preview_widget.updatePreview()
        else:
            preview.repaint()

    def _quick_print_current(
        self,
        preview: QPrintPreviewDialog,
        payload: PrintPreviewPayload,
        parent_widget,
    ) -> None:
        """Send the document directly to the currently configured/default printer."""
        try:
            self._render_document(
                self._printer,
                payload.html_content,
                payload.table_mode,
            )
            QMessageBox.information(
                parent_widget or preview,
                "Printing",
                "Document sent to printer.",
            )
        except Exception as exc:
            LOGGER.warning("Quick print failed: %s", exc, exc_info=True)
            QMessageBox.critical(
                parent_widget or preview,
                "Print Failed",
                self._friendly_print_error_message(exc),
            )

    @staticmethod
    def _friendly_print_error_message(exc: Exception) -> str:
        lower = str(exc or "").strip().lower()
        hint = "Check that the selected printer is available, then try again."
        if any(token in lower for token in ("not found", "invalid printer")):
            hint = "The selected printer is not available. Choose another printer."
        elif any(token in lower for token in ("offline", "unreachable")):
            hint = "The selected printer appears to be offline or unreachable."
        return "Could not send the document to the printer.\n\n" + hint
