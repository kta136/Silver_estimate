from PyQt5.QtPrintSupport import QPrinter, QPrintPreviewDialog, QPrintPreviewWidget
from PyQt5.QtWidgets import QToolBar

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
