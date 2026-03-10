from PyQt5.QtCore import QSizeF
from PyQt5.QtGui import QPageSize
from PyQt5.QtPrintSupport import QPrinter, QPrintPreviewDialog, QPrintPreviewWidget
from PyQt5.QtWidgets import QMessageBox, QToolBar

from silverestimate.infrastructure.settings import get_app_settings
from silverestimate.ui.print_payload_builder import PrintPreviewPayload
from silverestimate.ui.print_preview_controller import PrintPreviewController


def test_preview_toolbar_uses_single_custom_icon_set(qtbot):
    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: None,
    )
    payload = PrintPreviewPayload(
        html_content="<html><body><p>Preview</p></body></html>",
        title="Print Preview",
        document_kind="estimate",
        identifier="V-001",
        suggested_filename="Estimate-V-001.pdf",
        layout_mode="new",
        available_layouts=("old", "new", "thermal"),
    )
    preview = QPrintPreviewDialog(controller._printer)
    qtbot.addWidget(preview)
    preview_widget = preview.findChild(QPrintPreviewWidget)

    controller._augment_preview_toolbar(
        preview,
        preview_widget,
        {"payload": payload},
        None,
    )

    toolbar = preview.findChild(QToolBar)
    assert toolbar is not None

    action_texts = [action.text() for action in toolbar.actions() if action.text()]

    assert "Print" not in action_texts
    assert "Page setup" not in action_texts
    assert "Fit width" not in action_texts
    assert "Fit page" not in action_texts
    assert "Zoom out" not in action_texts
    assert "Zoom in" not in action_texts
    assert "First page" not in action_texts
    assert "Previous page" not in action_texts
    assert "Next page" not in action_texts
    assert "Last page" not in action_texts
    assert "Show single page" not in action_texts
    assert "Show facing pages" not in action_texts
    assert "Show overview of all pages" not in action_texts

    expected_action_order = [
        "Quick Print",
        "Save PDF",
        "Printer",
        "Page Setup",
        "Single Page",
        "Facing Pages",
        "All Pages",
        "Fit Width",
        "Fit Page",
        "Zoom Out",
        "Zoom In",
        "First",
        "Prev",
        "Next",
        "Last",
    ]
    assert action_texts == expected_action_order

    for action in toolbar.actions():
        if action.text() in set(expected_action_order):
            assert not action.icon().isNull()


def test_preview_defaults_persist_updated_print_preferences(
    qt_app, monkeypatch, settings_stub
):
    del qt_app, settings_stub
    saved_layouts = []
    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: None,
        persist_estimate_layout=saved_layouts.append,
    )
    monkeypatch.setattr(controller._printer, "printerName", lambda: "Warehouse Printer")
    controller._printer.setOrientation(QPrinter.Portrait)
    controller._printer.setPageSize(QPageSize(QPageSize.Legal))
    controller._printer.setPageMargins(12, 3, 14, 4, QPrinter.Millimeter)
    payload = PrintPreviewPayload(
        html_content="<html><body><p>Preview</p></body></html>",
        title="Print Preview",
        document_kind="estimate",
        identifier="V-002",
        suggested_filename="Estimate-V-002.pdf",
        layout_mode="thermal",
        available_layouts=("old", "new", "thermal"),
    )

    controller._save_preview_defaults(payload)

    settings = get_app_settings()
    assert settings.value("print/default_printer") == "Warehouse Printer"
    assert settings.value("print/orientation") == "Portrait"
    assert settings.value("print/orientation_explicit") is True
    assert settings.value("print/page_size") == "Legal"
    assert settings.value("print/page_size_name") == "Legal"
    assert settings.value("print/page_width_mm") == 215.9
    assert settings.value("print/page_height_mm") == 355.6
    assert settings.value("print/margins") == "12,3,14,4"
    assert settings.value("print/estimate_layout") == "thermal"
    assert saved_layouts == ["thermal"]


def test_preview_defaults_store_custom_page_size_dimensions(qt_app, settings_stub):
    del qt_app, settings_stub
    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: None,
    )
    custom_page = QPageSize(QSizeF(120.0, 190.0), QPageSize.Millimeter, "Counter Slip")
    controller._printer.setPageSize(custom_page)
    payload = PrintPreviewPayload(
        html_content="<html><body><p>Preview</p></body></html>",
        title="Print Preview",
        document_kind="silver_bar_list",
        identifier="LIST-001",
        suggested_filename="List.pdf",
    )

    controller._save_preview_defaults(payload)

    settings = get_app_settings()
    assert settings.value("print/page_size") == "Counter Slip"
    assert settings.value("print/page_size_name") == "Counter Slip"
    assert settings.value("print/page_width_mm") == 120.0
    assert settings.value("print/page_height_mm") == 190.0


def test_quick_print_closes_preview_without_success_popup(monkeypatch):
    render_calls = []
    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: render_calls.append(args),
    )
    payload = PrintPreviewPayload(
        html_content="<html><body><p>Preview</p></body></html>",
        title="Print Preview",
        document_kind="estimate",
        identifier="V-003",
        suggested_filename="Estimate-V-003.pdf",
    )

    class _PreviewStub:
        def __init__(self):
            self.accept_calls = 0

        def accept(self):
            self.accept_calls += 1

    preview = _PreviewStub()

    def _unexpected_information(*args, **kwargs):
        raise AssertionError("Success popup should not be shown after quick print")

    monkeypatch.setattr(QMessageBox, "information", _unexpected_information)

    controller._quick_print_current(preview, payload, parent_widget=None)

    assert len(render_calls) == 1
    assert preview.accept_calls == 1


def test_quick_print_failure_keeps_preview_open_and_shows_error(monkeypatch):
    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    payload = PrintPreviewPayload(
        html_content="<html><body><p>Preview</p></body></html>",
        title="Print Preview",
        document_kind="estimate",
        identifier="V-004",
        suggested_filename="Estimate-V-004.pdf",
    )

    class _PreviewStub:
        def __init__(self):
            self.accept_calls = 0

        def accept(self):
            self.accept_calls += 1

    preview = _PreviewStub()
    critical_calls = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda *args: critical_calls.append(args),
    )

    controller._quick_print_current(preview, payload, parent_widget=None)

    assert preview.accept_calls == 0
    assert len(critical_calls) == 1
