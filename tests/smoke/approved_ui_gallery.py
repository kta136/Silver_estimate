"""Opt-in deterministic captures of the approved presentation states."""

import json
import os
from dataclasses import replace

from PySide6.QtCore import QDate, QSize, Qt, QTimer
from PySide6.QtGui import QFont, QPageLayout, QPainter, QPixmap
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

from silverestimate.domain.estimate_models import EstimateLineCategory
from silverestimate.persistence.draft_repository import DraftRecord
from silverestimate.ui.estimate_draft_recovery import choose_recovery
from silverestimate.ui.estimate_print_document import EstimatePrintDocument
from silverestimate.ui.estimate_print_renderer import EstimatePrintRenderer
from silverestimate.ui.login_dialog import LoginDialog
from silverestimate.ui.print_manager import PrintManager
from tests.factories import multi_section_print_estimate


def capture_approved_gallery(
    *,
    capture,
    window,
    history,
    settings,
    inventory,
    silver_history,
    font_dialog,
    item_selection,
    optimal,
    qtbot,
):
    output = capture.output_dir / "approved-gallery"
    output.mkdir(parents=True, exist_ok=True)
    width, height = map(
        int, os.environ.get("SILVER_UI_CAPTURE_SIZE", "1366x768").split("x")
    )
    manifest = []

    def save(widget, name, *, full=False):
        if full:
            widget.resize(width, height)
        widget.show()
        QApplication.processEvents()
        qtbot.wait(35)
        if full:
            assert widget.width() <= width and widget.height() <= height, (
                name,
                widget.size(),
            )
        pixmap = widget.grab()
        assert pixmap.save(str(output / (name + ".png")))
        manifest.append(
            dict(
                screen=name,
                width=widget.width(),
                height=widget.height(),
                device_pixel_ratio=pixmap.devicePixelRatio(),
            )
        )

    entry = window.estimate_widget
    window.show_estimate()
    window.resize(width, height)
    row = entry.item_table.get_all_rows()[0]
    entry.item_table.set_all_rows(
        [
            replace(
                row,
                row_index=i,
                line_key=f"gallery-{i}",
                name="Silver Ring",
                pieces=1,
                category=EstimateLineCategory.RETURN
                if i in (5, 12)
                else EstimateLineCategory.SILVER_BAR
                if i in (7, 13)
                else EstimateLineCategory.REGULAR,
            )
            for i in range(28)
        ]
    )
    entry.date_edit.setDate(QDate(2026, 9, 6))
    entry.silver_rate_spin.setValue(75000)
    entry.live_rate_value_label.setText("₹75,000.00")
    entry.live_rate_meta_label.setText("Updated 10:30 AM")
    entry.note_edit.setText("Sample customer")
    entry.totals_controller.calculate_totals()
    entry.item_table.setCurrentCell(2, 2)
    save(entry, "estimate-entry")
    for label in (entry.grand_total_label, entry.net_fine_label, entry.net_wage_label):
        assert label.mapTo(entry, label.rect().topRight()).x() < entry.width()
        assert label.fontMetrics().horizontalAdvance(label.text()) <= label.width()

    window.show_item_master()
    catalog = window.item_master_widget
    catalog.items_table.selectRow(0)
    save(catalog, "item-master")
    history.estimates_table.selectRow(0)
    save(history, "estimate-history", full=True)
    inventory.available_bars_table.selectRow(0)
    save(inventory, "silver-bar-management", full=True)
    for index, name in enumerate(
        (
            "settings",
            "settings-live-rates",
            "settings-printing",
            "settings-data-backups",
            "settings-security",
            "settings-logging",
        )
    ):
        settings.sidebar.setCurrentRow(index)
        settings.resize(width, height)
        if index == 2:
            settings.print_page._refresh_preview()
        save(settings, name, full=True)
    silver_history.tab_widget.setCurrentIndex(0)
    silver_history.bars_table.selectRow(0)
    save(silver_history, "silver-history-all", full=True)
    silver_history.tab_widget.setCurrentIndex(1)
    silver_history.lists_table.selectRow(0)
    save(silver_history, "silver-history-issued", full=True)
    save(font_dialog, "font-dialog")
    save(item_selection, "item-selection")
    optimal.resize(600, min(640, height - 40))
    save(optimal, "optimal-list")
    login = LoginDialog(is_setup=False, parent=window)
    qtbot.addWidget(login)
    login.password_input.setText("ExamplePassword")
    save(login, "login")
    login.close()

    def capture_modal(name):
        def finish(attempt=0):
            modal = QApplication.activeModalWidget()
            if modal is None and attempt < 100:
                QTimer.singleShot(20, lambda: finish(attempt + 1))
                return
            assert modal is not None, name
            try:
                save(modal, name, full=name == "print-preview-controls")
                for button in modal.findChildren(QPushButton):
                    if button.isVisible():
                        text_width = button.fontMetrics().horizontalAdvance(
                            button.text().replace("&&", "&")
                        )
                        assert text_width <= button.width() - 10, (
                            name,
                            button.text(),
                            button.width(),
                        )
                if name == "delete-confirmation":
                    assert modal.defaultButton() is modal.button(
                        QMessageBox.StandardButton.Cancel
                    )
            finally:
                if isinstance(modal, QMessageBox):
                    modal.button(QMessageBox.StandardButton.Cancel).click()
                else:
                    modal.reject()

        QTimer.singleShot(40, finish)

    capture_modal("last-balance")
    entry.workflow_controller.show_last_balance_dialog()
    capture_modal("draft-recovery")
    assert (
        choose_recovery(window, DraftRecord("gallery", "100", "{}", "2026-09-06 10:30"))
        == "cancel"
    )
    import silverestimate.ui.estimate_history as history_module

    previous = history_module.QMessageBox
    history_module.QMessageBox = QMessageBox
    try:
        capture_modal("delete-confirmation")
        history.delete_selected_estimate()
    finally:
        history_module.QMessageBox = previous

    sample = multi_section_print_estimate()
    sample["header"].update(voucher_no="100", date="2026-09-06", silver_rate=75000)
    for rate, name in (
        (75000, "print-summary-with-rate"),
        (0, "print-summary-without-rate"),
    ):
        sample["header"]["silver_rate"] = rate
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        printer.setOutputFileName(str(output / (name + ".pdf")))
        document = EstimatePrintDocument.from_mapping(sample, format_key="modern")
        EstimatePrintRenderer().paint(
            printer, document, print_font=QFont("Segoe UI", 8)
        )
        del printer
        pdf = QPdfDocument()
        pdf.load(str(output / (name + ".pdf")))
        assert pdf.pageCount() == 1
        size = (
            pdf.pagePointSize(0)
            .toSize()
            .scaled(QSize(1700, 1700), Qt.AspectRatioMode.KeepAspectRatio)
        )
        rendered = pdf.render(0, size)
        sheet = QPixmap(size)
        sheet.fill(Qt.GlobalColor.white)
        painter = QPainter(sheet)
        painter.drawImage(0, 0, rendered)
        painter.end()
        sheet.save(str(output / (name + ".png")))
        pdf.close()
        del pdf
        manifest.append(dict(screen=name, rate=rate))
    manager = PrintManager(window.db, print_font=QFont("Segoe UI", 8))
    manager._set_estimate_format("modern")
    payload = manager.build_estimate_preview_payload("100", estimate_data=sample)
    capture_modal("print-preview-controls")
    manager.show_preview(payload, parent_widget=window)
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
