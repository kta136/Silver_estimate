from pathlib import Path

from PySide6.QtCore import QSizeF, Qt
from PySide6.QtGui import QAction, QFont, QKeySequence, QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewWidget
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QMenu,
    QMessageBox,
    QToolBar,
    QToolButton,
    QWidget,
)

from silverestimate.infrastructure.settings import get_app_settings
from silverestimate.ui.estimate_print_document import EstimatePrintDocument
from silverestimate.ui.print_payload_builder import PrintPreviewPayload
from silverestimate.ui.print_preview_controller import PrintPreviewController
from silverestimate.ui.print_preview_dialog import PrintPreviewDialog
from silverestimate.ui.silver_bar_print_document import (
    SilverBarListPrintDocument,
)


class _PreviewWidgetStub:
    def __init__(self):
        self.zoom_modes = []
        self.zoom_factor = None

    def setZoomMode(self, mode):
        self.zoom_modes.append(mode)

    def setZoomFactor(self, zoom_factor):
        self.zoom_factor = zoom_factor


def _estimate_document(
    format_key: str = "modern",
    *,
    show_tunch: bool = False,
) -> EstimatePrintDocument:
    return EstimatePrintDocument.from_mapping(
        {
            "header": {
                "voucher_no": "V-001",
                "date": "2026-07-26",
                "silver_rate": 100,
            },
            "items": [],
        },
        format_key=format_key,
        show_tunch=show_tunch,
    )


def _report_document() -> SilverBarListPrintDocument:
    return SilverBarListPrintDocument.from_rows(
        {"list_identifier": "LIST-001", "list_note": "Preview"},
        [],
    )


def _estimate_payload(format_key: str = "modern") -> PrintPreviewPayload:
    def build(
        selected_format: str,
        show_tunch: bool = False,
    ) -> PrintPreviewPayload:
        return PrintPreviewPayload(
            document=_estimate_document(
                selected_format,
                show_tunch=show_tunch,
            ),
            title="Print Preview",
            document_kind="estimate",
            identifier="V-001",
            suggested_filename="Estimate-V-001.pdf",
            format_key=selected_format,
            available_formats=("classic", "modern"),
            format_factory=lambda next_format: build(next_format, show_tunch),
            show_tunch=show_tunch,
            tunch_visibility_factory=lambda visible: build(selected_format, visible),
        )

    return build(format_key)


def test_custom_preview_dialog_owns_single_toolbar_and_preview_canvas(qtbot):
    preview = PrintPreviewDialog(QPrinter())
    qtbot.addWidget(preview)

    assert preview.objectName() == "PrintPreviewDialog"
    assert preview.isModal()
    assert preview.findChild(QToolBar) is preview.toolbar
    assert len(preview.findChildren(QToolBar)) == 1
    assert preview.findChild(QPrintPreviewWidget) is preview.preview_widget
    assert preview.preview_widget.objectName() == "PrintPreviewCanvas"
    assert preview.layout().count() == 2


def test_preview_toolbar_uses_single_custom_icon_set(qtbot):
    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: None,
        get_print_font=lambda: QFont("Arial", 8),
        persist_print_font=lambda _font: None,
    )
    payload = _estimate_payload()
    preview = PrintPreviewDialog(controller._printer)
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
    assert toolbar.objectName() == "PrintPreviewToolbar"
    assert not toolbar.isMovable()
    assert not toolbar.isFloatable()
    assert toolbar.iconSize().width() == 22
    assert preview.findChild(QWidget, "PreviewPageNavigator") is not None
    format_combo = preview.findChild(QComboBox, "PreviewFormatCombo")
    assert format_combo is not None
    assert [format_combo.itemText(index) for index in range(format_combo.count())] == [
        "Classic",
        "Modern",
    ]
    assert format_combo.currentData() == "modern"
    tunch_checkbox = preview.findChild(QCheckBox, "PreviewTunchCheckbox")
    assert tunch_checkbox is not None
    assert tunch_checkbox.isChecked() is False

    print_action = next(
        action for action in toolbar.actions() if action.text() == "Print"
    )
    assert (
        print_action.shortcut().matches(QKeySequence("Ctrl+P"))
        == QKeySequence.SequenceMatch.ExactMatch
    )
    assert print_action.shortcutContext() == Qt.ShortcutContext.WindowShortcut

    action_texts = [action.text() for action in toolbar.actions() if action.text()]

    assert "Quick Print" not in action_texts
    assert "Save PDF" not in action_texts
    assert "Printer" not in action_texts
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

    expected_toolbar_actions = [
        "Print",
        "Export PDF",
        "Print Font",
        "Fit Width",
        "Fit Page",
        "Zoom Out",
        "Zoom In",
    ]
    assert action_texts == expected_toolbar_actions

    for action_text in expected_toolbar_actions:
        action = next(
            action for action in toolbar.actions() if action.text() == action_text
        )
        button = toolbar.widgetForAction(action)
        assert isinstance(button, QToolButton)
        assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
        assert button.accessibleName() == action_text

    more_button = toolbar.findChild(QToolButton, "PreviewMoreButton")
    assert more_button is not None
    assert more_button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert more_button.accessibleName() == "More preview actions"
    more_action = next(
        action
        for action in toolbar.actions()
        if toolbar.widgetForAction(action) is more_button
    )
    page_navigator = preview.findChild(QWidget, "PreviewPageNavigator")
    page_action = next(
        action
        for action in toolbar.actions()
        if toolbar.widgetForAction(action) is page_navigator
    )
    fit_width_action = next(
        action for action in toolbar.actions() if action.text() == "Fit Width"
    )
    fit_page_action = next(
        action for action in toolbar.actions() if action.text() == "Fit Page"
    )
    print_action = next(
        action for action in toolbar.actions() if action.text() == "Print"
    )
    export_action = next(
        action for action in toolbar.actions() if action.text() == "Export PDF"
    )
    font_action = next(
        action for action in toolbar.actions() if action.text() == "Print Font"
    )
    orientation_combo = preview.findChild(QComboBox, "PreviewOrientationCombo")
    orientation_action = next(
        action
        for action in toolbar.actions()
        if toolbar.widgetForAction(action) is orientation_combo
    )
    format_action = next(
        action
        for action in toolbar.actions()
        if toolbar.widgetForAction(action) is format_combo
    )
    tunch_action = next(
        action
        for action in toolbar.actions()
        if toolbar.widgetForAction(action) is tunch_checkbox
    )
    ordered_actions = toolbar.actions()
    assert ordered_actions.index(print_action) < ordered_actions.index(export_action)
    assert ordered_actions.index(export_action) < ordered_actions.index(
        orientation_action
    )
    assert ordered_actions.index(orientation_action) < ordered_actions.index(
        format_action
    )
    assert ordered_actions.index(format_action) < ordered_actions.index(tunch_action)
    assert ordered_actions.index(tunch_action) < ordered_actions.index(font_action)
    assert ordered_actions.index(font_action) < ordered_actions.index(fit_width_action)
    assert toolbar.actions().index(more_action) > toolbar.actions().index(
        fit_width_action
    )
    assert toolbar.actions().index(fit_page_action) < toolbar.actions().index(
        page_action
    )
    assert toolbar.actions().index(page_action) < toolbar.actions().index(more_action)
    assert toolbar.actions()[-1] is more_action
    assert fit_width_action.priority() == QAction.Priority.NormalPriority
    assert fit_page_action.priority() == QAction.Priority.NormalPriority
    more_menu = more_button.menu()
    assert isinstance(more_menu, QMenu)
    menu_action_texts = [
        action.text() for action in more_menu.actions() if action.text()
    ]
    expected_menu_actions = [
        "Printer Setup",
        "Page Setup",
        "Single Page",
        "Facing Pages",
        "All Pages",
        "First",
        "Prev",
        "Next",
        "Last",
        "Close",
    ]
    assert menu_action_texts == expected_menu_actions

    for action in [*toolbar.actions(), *more_menu.actions()]:
        if action.text() in set(expected_toolbar_actions + expected_menu_actions):
            assert not action.icon().isNull()


def test_silver_bar_preview_exposes_print_font_without_format_controls(qtbot):
    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: None,
        get_print_font=lambda: QFont("Arial", 8),
        persist_print_font=lambda _font: None,
    )
    payload = PrintPreviewPayload(
        document=_report_document(),
        title="Print Preview - List LIST-001",
        document_kind="silver_bar_list",
        identifier="LIST-001",
        suggested_filename="Silver-Bar-List-LIST-001.pdf",
    )
    preview = PrintPreviewDialog(controller._printer)
    qtbot.addWidget(preview)

    controller._augment_preview_toolbar(
        preview,
        preview.findChild(QPrintPreviewWidget),
        {"payload": payload},
        None,
    )

    toolbar = preview.findChild(QToolBar)
    assert toolbar is not None
    action_texts = [action.text() for action in toolbar.actions() if action.text()]
    assert "Print Font" in action_texts
    assert preview.findChild(QComboBox, "PreviewFormatCombo") is None
    assert preview.findChild(QCheckBox, "PreviewTunchCheckbox") is None


def test_ctrl_p_prints_active_preview_instead_of_main_window(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    main_print_calls = []
    main_print_action = QAction("Main Print", parent)
    main_print_action.setShortcut("Ctrl+P")
    main_print_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
    main_print_action.triggered.connect(lambda: main_print_calls.append(True))
    parent.addAction(main_print_action)

    preview_print_calls = []
    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: None,
    )
    controller._quick_print_current = lambda *args: preview_print_calls.append(args)
    preview = PrintPreviewDialog(controller._printer, parent)
    qtbot.addWidget(preview)
    preview_widget = preview.findChild(QPrintPreviewWidget)
    controller._augment_preview_toolbar(
        preview,
        preview_widget,
        {"payload": _estimate_payload()},
        parent,
    )

    parent.show()
    preview.show()
    preview.raise_()
    preview.activateWindow()
    preview_widget.setFocus()
    qtbot.waitUntil(preview.isActiveWindow)
    QTest.keyClick(
        preview_widget,
        Qt.Key.Key_P,
        Qt.KeyboardModifier.ControlModifier,
    )
    qtbot.waitUntil(lambda: len(preview_print_calls) == 1)

    assert len(preview_print_calls) == 1
    assert main_print_calls == []


def test_page_keys_trigger_preview_navigation_with_document_focus(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: None,
    )
    preview = PrintPreviewDialog(controller._printer, parent)
    qtbot.addWidget(preview)
    preview_widget = preview.findChild(QPrintPreviewWidget)
    controller._augment_preview_toolbar(
        preview,
        preview_widget,
        {"payload": _estimate_payload()},
        parent,
    )
    page_actions = {
        action.shortcut().toString(): action
        for action in preview.actions()
        if not action.shortcut().isEmpty()
    }
    assert {"PgUp", "PgDown"} <= page_actions.keys()
    assert all(
        page_actions[key].shortcutContext() == Qt.ShortcutContext.WindowShortcut
        for key in ("PgUp", "PgDown")
    )
    triggered = []
    page_actions["PgUp"].triggered.connect(lambda: triggered.append("up"))
    page_actions["PgDown"].triggered.connect(lambda: triggered.append("down"))

    parent.show()
    preview.show()
    preview.raise_()
    preview.activateWindow()
    preview_widget.setFocus()
    qtbot.waitUntil(preview.isActiveWindow)

    QTest.keyClick(preview_widget, Qt.Key.Key_PageDown)
    QTest.keyClick(preview_widget, Qt.Key.Key_PageUp)
    qtbot.waitUntil(lambda: len(triggered) == 2)

    assert triggered == ["down", "up"]


def test_preview_print_font_dialog_persists_selection_and_refreshes(
    monkeypatch,
) -> None:
    initial_font = QFont("Arial", 8)
    selected_font = QFont("Arial", 12)
    selected_font.setPointSizeF(12.0)
    selected_font.setBold(True)
    persisted_fonts = []

    class _PreviewWidget:
        def __init__(self) -> None:
            self.update_calls = 0

        def updatePreview(self) -> None:
            self.update_calls += 1

    class _Preview:
        def __init__(self) -> None:
            self.preview_widget = _PreviewWidget()
            self.repaint_calls = 0

        def repaint(self) -> None:
            self.repaint_calls += 1

    class _FontDialog:
        def __init__(self, font, parent) -> None:
            assert font.family() == initial_font.family()
            assert parent is preview

        def exec(self):
            return QDialog.DialogCode.Accepted

        def get_selected_font(self):
            return selected_font

    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: None,
        get_print_font=lambda: initial_font,
        persist_print_font=persisted_fonts.append,
    )
    preview = _Preview()
    monkeypatch.setattr(
        "silverestimate.ui.print_preview_controller.CustomFontDialog",
        _FontDialog,
    )

    controller._choose_print_font(preview)

    assert persisted_fonts == [selected_font]
    assert preview.preview_widget.update_calls == 1
    assert preview.repaint_calls == 0


def test_preview_uses_fit_width_when_zoom_is_not_saved(qt_app, settings_stub):
    del qt_app, settings_stub
    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: None,
    )
    preview_widget = _PreviewWidgetStub()

    controller._apply_initial_zoom(preview_widget)

    assert preview_widget.zoom_modes == [QPrintPreviewWidget.ZoomMode.FitToWidth]
    assert preview_widget.zoom_factor is None


def test_preview_uses_saved_custom_zoom_when_available(qt_app, settings_stub):
    del qt_app, settings_stub
    get_app_settings().setValue("print/preview_zoom", 1.75)
    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: None,
    )
    preview_widget = _PreviewWidgetStub()

    controller._apply_initial_zoom(preview_widget)

    assert preview_widget.zoom_modes == [QPrintPreviewWidget.ZoomMode.CustomZoom]
    assert preview_widget.zoom_factor == 1.75


def test_focus_preview_activates_dialog_and_document_view():
    class _FocusStub:
        def __init__(self):
            self.focus_reasons = []

        def setFocus(self, reason):
            self.focus_reasons.append(reason)

    class _PreviewStub(_FocusStub):
        def __init__(self):
            super().__init__()
            self.raise_calls = 0
            self.activate_calls = 0

        def raise_(self):
            self.raise_calls += 1

        def activateWindow(self):
            self.activate_calls += 1

    preview = _PreviewStub()
    preview_widget = _FocusStub()

    PrintPreviewController._focus_preview(preview, preview_widget)

    assert preview.raise_calls == 1
    assert preview.activate_calls == 1
    assert preview_widget.focus_reasons == [Qt.FocusReason.ActiveWindowFocusReason]


def test_preview_defaults_persist_updated_print_preferences(
    qt_app, monkeypatch, settings_stub
):
    del qt_app, settings_stub
    persisted_formats = []
    persisted_tunch = []
    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: None,
        persist_estimate_format=persisted_formats.append,
        persist_tunch_visibility=persisted_tunch.append,
    )
    monkeypatch.setattr(controller._printer, "printerName", lambda: "Warehouse Printer")
    controller._printer.setPageOrientation(QPageLayout.Orientation.Portrait)
    controller._printer.setPageSize(QPageSize(QPageSize.PageSizeId.Legal))
    # Read the actual margins the printer reports (null printer enforces its own minimums)
    actual_margins = controller._printer.pageLayout().margins(
        QPageLayout.Unit.Millimeter
    )
    expected_margins_str = ",".join(
        str(max(0, int(round(v))))
        for v in (
            actual_margins.left(),
            actual_margins.top(),
            actual_margins.right(),
            actual_margins.bottom(),
        )
    )
    payload = _estimate_payload("classic")

    controller._save_preview_defaults(payload)

    settings = get_app_settings()
    assert settings.value("print/default_printer") == "Warehouse Printer"
    assert settings.value("print/orientation") == "Portrait"
    assert settings.value("print/page_size") == "Legal"
    assert settings.value("print/page_size_name") == "Legal"
    assert settings.value("print/page_width_mm") == 215.9
    assert settings.value("print/page_height_mm") == 355.6
    assert settings.value("print/margins") == expected_margins_str
    assert settings.value("print/estimate_layout") == "classic"
    assert settings.value("print/show_tunch", type=bool) is False
    assert persisted_formats == ["classic"]
    assert persisted_tunch == [False]


def test_preview_format_switch_rebuilds_current_estimate_payload(qtbot) -> None:
    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: None,
    )
    preview = PrintPreviewDialog(controller._printer)
    qtbot.addWidget(preview)
    state = {"payload": _estimate_payload("modern")}

    controller._switch_format(preview, "classic", state)

    assert state["payload"].format_key == "classic"
    assert state["payload"].document.format_key == "classic"


def test_preview_tunch_toggle_refreshes_and_survives_format_switch(qtbot) -> None:
    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: None,
    )
    preview = PrintPreviewDialog(controller._printer)
    qtbot.addWidget(preview)
    state = {"payload": _estimate_payload("modern")}

    controller._switch_tunch_visibility(preview, True, state)

    assert state["payload"].show_tunch is True
    controller._switch_format(preview, "classic", state)
    assert state["payload"].format_key == "classic"
    assert state["payload"].show_tunch is True


def test_preview_defaults_store_custom_page_size_dimensions(qt_app, settings_stub):
    del qt_app, settings_stub
    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: None,
    )
    custom_page = QPageSize(
        QSizeF(120.0, 190.0), QPageSize.Unit.Millimeter, "Counter Slip"
    )
    controller._printer.setPageSize(custom_page)
    payload = PrintPreviewPayload(
        document=_report_document(),
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
        document=_estimate_document(),
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
    monkeypatch.setattr(
        "silverestimate.ui.print_preview_controller.validate_quick_print_printer",
        lambda printer: (True, ""),
    )

    controller._quick_print_current(preview, payload, parent_widget=None)

    assert len(render_calls) == 1
    assert preview.accept_calls == 1


def test_quick_print_failure_keeps_preview_open_and_shows_error(monkeypatch):
    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    payload = PrintPreviewPayload(
        document=_estimate_document(),
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
    monkeypatch.setattr(
        "silverestimate.ui.print_preview_controller.validate_quick_print_printer",
        lambda printer: (True, ""),
    )

    controller._quick_print_current(preview, payload, parent_widget=None)

    assert preview.accept_calls == 0
    assert len(critical_calls) == 1


def test_quick_print_blocks_missing_printer_before_render(monkeypatch):
    render_calls = []
    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=lambda *args: render_calls.append(args),
    )
    payload = PrintPreviewPayload(
        document=_estimate_document(),
        title="Print Preview",
        document_kind="estimate",
        identifier="V-005",
        suggested_filename="Estimate-V-005.pdf",
    )

    class _PreviewStub:
        def __init__(self):
            self.accept_calls = 0

        def accept(self):
            self.accept_calls += 1

    preview = _PreviewStub()
    critical_calls = []
    monkeypatch.setattr(
        "silverestimate.ui.print_preview_controller.validate_quick_print_printer",
        lambda printer: (False, "The selected printer is no longer available."),
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda *args: critical_calls.append(args),
    )

    controller._quick_print_current(preview, payload, parent_widget=None)

    assert render_calls == []
    assert preview.accept_calls == 0
    assert len(critical_calls) == 1
    assert "no longer available" in critical_calls[0][2]


def test_export_pdf_writes_temp_then_replaces_target(
    qt_app, settings_stub, tmp_path, monkeypatch
):
    del qt_app, settings_stub
    target = tmp_path / "estimate.pdf"
    target.write_bytes(b"old-pdf")
    render_targets = []

    def _render_pdf(printer, document):
        del document
        output_path = Path(printer.outputFileName())
        render_targets.append(output_path)
        output_path.write_bytes(b"%PDF-1.4\nok\n")

    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=_render_pdf,
    )
    payload = PrintPreviewPayload(
        document=_estimate_document(),
        title="Print Preview",
        document_kind="estimate",
        identifier="V-006",
        suggested_filename="Estimate-V-006.pdf",
    )
    info_calls = []
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(target), "PDF Files (*.pdf)"),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args: info_calls.append(args),
    )

    controller._export_pdf_via_dialog(payload, parent_widget=None)

    assert target.read_bytes() == b"%PDF-1.4\nok\n"
    assert render_targets
    assert render_targets[0] != target
    assert not list(tmp_path.glob(".silverestimate-*.pdf"))
    assert len(info_calls) == 1


def test_export_pdf_empty_temp_keeps_existing_file(
    qt_app, settings_stub, tmp_path, monkeypatch
):
    del qt_app, settings_stub
    target = tmp_path / "estimate.pdf"
    target.write_bytes(b"old-pdf")

    def _render_empty_pdf(printer, document):
        del document
        Path(printer.outputFileName()).write_bytes(b"")

    controller = PrintPreviewController(
        printer=QPrinter(),
        render_document=_render_empty_pdf,
    )
    payload = PrintPreviewPayload(
        document=_estimate_document(),
        title="Print Preview",
        document_kind="estimate",
        identifier="V-007",
        suggested_filename="Estimate-V-007.pdf",
    )
    critical_calls = []
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(target), "PDF Files (*.pdf)"),
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda *args: critical_calls.append(args),
    )

    controller._export_pdf_via_dialog(payload, parent_widget=None)

    assert target.read_bytes() == b"old-pdf"
    assert not list(tmp_path.glob(".silverestimate-*.pdf"))
    assert len(critical_calls) == 1
