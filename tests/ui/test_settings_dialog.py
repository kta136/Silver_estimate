import types

import pytest
from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QBoxLayout,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QTableWidget,
)

from silverestimate.infrastructure.settings import SettingsKey, get_app_settings
from silverestimate.security import credential_store
from silverestimate.ui.application_theme import apply_light_application_theme
from silverestimate.ui.settings_dialog import SettingsDialog
from silverestimate.ui.themed_controls import (
    ThemedComboBox,
    ThemedDoubleSpinBox,
    ThemedSpinBox,
)
from tests.smoke.test_full_startup_smoke import _configure_smoke_font


class _MessageBoxStub:
    critical_calls = []
    information_calls = []
    warning_calls = []

    @classmethod
    def reset(cls):
        cls.critical_calls = []
        cls.information_calls = []
        cls.warning_calls = []

    @classmethod
    def critical(cls, *args, **kwargs):
        cls.critical_calls.append((args, kwargs))
        return None

    @classmethod
    def information(cls, *args, **kwargs):
        cls.information_calls.append((args, kwargs))
        return None

    @classmethod
    def warning(cls, *args, **kwargs):
        cls.warning_calls.append((args, kwargs))
        return None


def _make_main_window(estimate_layout, *, db=None):
    return types.SimpleNamespace(
        print_font=QFont("Arial", 10),
        estimate_widget=types.SimpleNamespace(layout_controller=estimate_layout),
        show_catalog_restore_dialog=lambda: None,
        show_catalog_backup_dialog=lambda: None,
        delete_all_estimates=lambda: None,
        delete_vouchers_by_range=lambda: None,
        delete_all_data=lambda: None,
        reconfigure_rate_visibility_from_settings=lambda: True,
        reconfigure_rate_timer_from_settings=lambda: True,
        db=db or object(),
    )


class _PrinterStub:
    def __init__(self, name):
        self._name = name

    def printerName(self):
        return self._name


def test_settings_dialog_uses_visible_arrow_controls(qtbot, qt_app, settings_stub):
    del qt_app, settings_stub
    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        assert isinstance(dialog.appearance_page.table_font_size_spin, ThemedSpinBox)
        assert isinstance(dialog.print_page.preview_zoom_spin, ThemedDoubleSpinBox)
        assert isinstance(dialog.appearance_page.density_combo, ThemedComboBox)
        # The totals panel has one place, beside the table; nothing to choose.
        assert not hasattr(dialog.appearance_page, "totals_position_combo")
        assert isinstance(dialog.print_page.printer_combo, ThemedComboBox)
        assert not hasattr(dialog.print_page, "estimate_format_combo")
        assert [
            dialog.print_page.page_size_combo.itemText(index)
            for index in range(dialog.print_page.page_size_combo.count())
        ] == ["A4", "A5", "Letter", "Legal"]
        assert (
            dialog.sidebar.horizontalScrollBarPolicy()
            == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        assert dialog.minimumHeight() <= 540
        assert dialog.sidebar.width() >= 200
        assert dialog.page_scroll.widgetResizable() is True
        assert (
            dialog.page_scroll.horizontalScrollBarPolicy()
            == Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        assert dialog.appearance_page.print_font_button.minimumWidth() >= 130
        assert dialog.appearance_page.table_font_size_spin.maximumWidth() <= 180
        preview_table = dialog.findChild(QTableWidget, "SettingsPreviewTable")
        assert preview_table is not None
        assert preview_table.item(0, 2).textAlignment() == (
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
    finally:
        dialog.deleteLater()


def test_settings_accept_does_not_close_when_apply_fails(
    qtbot, qt_app, monkeypatch, settings_stub
):
    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        monkeypatch.setattr(dialog, "apply_settings", lambda: False)
        dialog.accept()
        assert dialog.result() == 0
    finally:
        dialog.deleteLater()


def test_settings_dialog_stops_rate_poll_when_closed(qtbot, qt_app, settings_stub):
    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        assert dialog._rate_display_timer.isActive()
        dialog.reject()
        assert not dialog._rate_display_timer.isActive()
    finally:
        dialog.deleteLater()


def test_settings_apply_persists_print_preferences(
    qtbot, qt_app, monkeypatch, settings_stub
):
    del qt_app, settings_stub
    settings = get_app_settings()
    monkeypatch.setattr(
        "silverestimate.ui.settings_print_controller.QPrinterInfo.availablePrinters",
        lambda: [_PrinterStub("Warehouse Printer"), _PrinterStub("Counter Printer")],
    )
    monkeypatch.setattr(
        "silverestimate.infrastructure.logger.reconfigure_logging", lambda: None
    )

    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        dialog.print_page.margin_left_spin.setValue(12)
        dialog.print_page.margin_top_spin.setValue(3)
        dialog.print_page.margin_right_spin.setValue(14)
        dialog.print_page.margin_bottom_spin.setValue(4)
        dialog.print_page.preview_zoom_spin.setValue(1.75)
        dialog.print_page.printer_combo.setCurrentText("Warehouse Printer")
        dialog.print_page.page_size_combo.setCurrentText("Legal")
        dialog.print_page.orientation_combo.setCurrentText("Landscape")

        assert dialog.apply_settings() is True
        assert settings.value("print/margins") == "12,3,14,4"
        assert settings.value("print/preview_zoom") == 1.75
        assert settings.value("print/default_printer") == "Warehouse Printer"
        assert settings.value("print/page_size") == "Legal"
        assert settings.value("print/orientation") == "Landscape"
    finally:
        dialog.deleteLater()


def test_settings_dialog_uses_defaults_for_invalid_print_settings(
    qtbot, qt_app, monkeypatch, settings_stub
):
    del qt_app, settings_stub
    settings = get_app_settings()
    settings.setValue("print/margins", "broken")
    settings.setValue("print/preview_zoom", "not-a-number")
    settings.setValue("print/page_size", "Tabloid")
    settings.setValue("print/orientation", "Sideways")
    settings.setValue("print/default_printer", "Missing Printer")

    monkeypatch.setattr(
        "silverestimate.ui.settings_print_controller.QPrinterInfo.availablePrinters",
        lambda: [_PrinterStub("Counter Printer")],
    )

    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        assert dialog.print_page.margin_left_spin.value() == 10
        assert dialog.print_page.margin_top_spin.value() == 2
        assert dialog.print_page.margin_right_spin.value() == 10
        assert dialog.print_page.margin_bottom_spin.value() == 2
        assert dialog.print_page.preview_zoom_spin.value() == 1.25
        assert dialog.print_page.page_size_combo.currentText() == "A4"
        assert dialog.print_page.orientation_combo.currentText() == "Landscape"
        assert dialog.print_page.printer_combo.currentData() == ""
    finally:
        dialog.deleteLater()


def test_settings_dialog_preserves_portrait_orientation(
    qtbot, qt_app, monkeypatch, settings_stub
):
    del qt_app, settings_stub
    settings = get_app_settings()
    settings.setValue("print/orientation", "Portrait")

    monkeypatch.setattr(
        "silverestimate.ui.settings_print_controller.QPrinterInfo.availablePrinters",
        lambda: [],
    )

    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        assert dialog.print_page.orientation_combo.currentText() == "Portrait"
    finally:
        dialog.deleteLater()


def test_settings_apply_persists_ui_preferences(
    qtbot, qt_app, monkeypatch, settings_stub
):
    del qt_app, settings_stub
    settings = get_app_settings()
    _MessageBoxStub.reset()
    monkeypatch.setattr(
        "silverestimate.ui.settings_print_controller.QPrinterInfo.availablePrinters",
        lambda: [],
    )

    applied = []
    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: applied.append(("table", size)) or True,
        apply_breakdown_font_size=lambda size: (
            applied.append(("breakdown", size)) or True
        ),
        apply_final_calc_font_size=lambda size: applied.append(("final", size)) or True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        monkeypatch.setattr(
            "silverestimate.ui.settings_dialog.QMessageBox", _MessageBoxStub
        )
        dialog.appearance_page.table_font_size_spin.setValue(12)
        dialog.appearance_page.breakdown_font_size_spin.setValue(11)
        dialog.appearance_page.final_calc_font_size_spin.setValue(18)

        assert dialog.apply_settings() is True
        assert settings.value("ui/table_font_size") == 12
        assert settings.value("ui/breakdown_font_size") == 11
        assert settings.value("ui/final_calc_font_size") == 18
        assert not settings.contains("ui/estimate_totals_position")
        # Each size reaches the estimate screen once, with the value chosen.
        assert sorted(applied) == [("breakdown", 11), ("final", 18), ("table", 12)]
        assert not _MessageBoxStub.critical_calls
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize(
    "save_button",
    [QDialogButtonBox.StandardButton.Apply, QDialogButtonBox.StandardButton.Ok],
    ids=["apply", "save-and-close"],
)
def test_settings_save_appearance_on_real_estimate_screen(
    qtbot,
    qt_application_state,
    monkeypatch,
    make_estimate_widget,
    fake_db,
    save_button,
):
    _MessageBoxStub.reset()
    monkeypatch.setattr(
        "silverestimate.ui.settings_dialog.QMessageBox", _MessageBoxStub
    )
    monkeypatch.setattr(
        "silverestimate.ui.settings_print_controller.QPrinterInfo.availablePrinters",
        lambda: [],
    )
    monkeypatch.setattr(
        "silverestimate.infrastructure.logger.reconfigure_logging", lambda: None
    )
    estimate = make_estimate_widget(fake_db)
    main_window = _make_main_window(estimate.layout_controller)
    main_window.estimate_widget = estimate
    dialog = SettingsDialog(main_window_ref=main_window)
    qtbot.addWidget(dialog)
    page = dialog.appearance_page
    page.table_font_size_spin.setValue(13)
    page.breakdown_font_size_spin.setValue(12)
    page.final_calc_font_size_spin.setValue(18)
    page.density_combo.setCurrentIndex(page.density_combo.findData("comfortable"))
    page.alternating_checkbox.setChecked(False)

    dialog.buttonBox.button(save_button).click()

    assert not _MessageBoxStub.critical_calls
    assert dialog.settings_feedback_label.text() == "Settings applied and saved."
    if save_button == QDialogButtonBox.StandardButton.Ok:
        assert dialog.result() == QDialog.DialogCode.Accepted
    settings = get_app_settings()
    assert settings.value("ui/table_font_size") == 13
    assert settings.value("ui/breakdown_font_size") == 12
    assert settings.value("ui/final_calc_font_size") == 18
    assert estimate.item_table.font().pointSize() == 13
    assert not estimate.item_table.alternatingRowColors()
    assert estimate.totals_panel.total_fine_label.font().pointSize() == 12
    assert estimate.totals_panel.grand_total_label.font().pointSize() == 18

    reopened = SettingsDialog(main_window_ref=main_window)
    qtbot.addWidget(reopened)
    assert reopened.appearance_page.table_font_size_spin.value() == 13
    reopened.appearance_page.table_font_size_spin.setValue(15)
    reopened.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).click()
    assert settings.value("ui/table_font_size") == 13
    assert estimate.item_table.font().pointSize() == 13
    reloaded_estimate = make_estimate_widget(fake_db)
    assert reloaded_estimate.item_table.font().pointSize() == 13
    reloaded_panel = reloaded_estimate.totals_panel
    assert reloaded_panel.total_fine_label.font().pointSize() == 12
    assert reloaded_panel.grand_total_label.font().pointSize() == 18


def test_apply_stays_visible_and_reenables_after_repeated_text_changes(
    qtbot, qt_application_state, monkeypatch, make_estimate_widget, fake_db
):
    from silverestimate.ui.application_theme import apply_light_application_theme

    apply_light_application_theme(qt_application_state)
    _MessageBoxStub.reset()
    monkeypatch.setattr(
        "silverestimate.ui.settings_dialog.QMessageBox", _MessageBoxStub
    )
    monkeypatch.setattr(
        "silverestimate.ui.settings_print_controller.QPrinterInfo.availablePrinters",
        lambda: [],
    )
    monkeypatch.setattr(
        "silverestimate.infrastructure.logger.reconfigure_logging", lambda: None
    )
    estimate = make_estimate_widget(fake_db)
    main_window = _make_main_window(estimate.layout_controller)
    main_window.estimate_widget = estimate
    dialog = SettingsDialog(main_window_ref=main_window)
    qtbot.addWidget(dialog)
    dialog.show()
    apply_button = dialog.buttonBox.button(QDialogButtonBox.StandardButton.Apply)
    page = dialog.appearance_page
    for size, totals_size, final_size in (
        (12, 10, 16),
        (14, 11, 18),
        (11, 12, 20),
    ):
        page.table_font_size_spin.setValue(size)
        page.breakdown_font_size_spin.setValue(totals_size)
        page.final_calc_font_size_spin.setValue(final_size)
        qt_application_state.processEvents()
        assert apply_button.isVisible()
        assert apply_button.isEnabled()
        qtbot.mouseClick(apply_button, Qt.MouseButton.LeftButton)
        qt_application_state.processEvents()
        assert not _MessageBoxStub.critical_calls
        assert get_app_settings().get_int("ui/table_font_size") == size
        assert estimate.totals_panel.total_fine_label.font().pointSize() == totals_size
        assert estimate.totals_panel.net_fine_label.font().pointSize() == final_size
        assert estimate.totals_panel.net_wage_label.font().pointSize() == final_size
        assert estimate.totals_panel.grand_total_label.font().pointSize() == final_size
        assert apply_button.isVisible()
        assert not apply_button.isEnabled()


def test_settings_apply_persists_logging_preferences(
    qtbot,
    qt_app,
    monkeypatch,
    settings_stub,
):
    del qt_app, settings_stub
    settings = get_app_settings()
    reconfigure_calls = []
    monkeypatch.setattr(
        "silverestimate.ui.settings_print_controller.QPrinterInfo.availablePrinters",
        lambda: [],
    )
    monkeypatch.setattr(
        "silverestimate.infrastructure.logger.reconfigure_logging",
        lambda: reconfigure_calls.append(True),
    )
    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        page = dialog.logging_page
        assert page.level_combo.currentData() == "normal"
        page.set_level("detailed")
        page.auto_cleanup_checkbox.setChecked(True)
        page.cleanup_days_spin.setValue(30)
        assert page.cleanup_days_spin.suffix() == " days"

        assert dialog.apply_settings() is True
        assert settings.value("logging/level") == "detailed"
        assert settings.value("logging/auto_cleanup") is True
        assert settings.value("logging/cleanup_days") == 30
        assert reconfigure_calls == [True]
    finally:
        dialog.deleteLater()


def test_settings_apply_can_clear_default_printer(
    qtbot, qt_app, monkeypatch, settings_stub
):
    del qt_app, settings_stub
    settings = get_app_settings()
    settings.setValue("print/default_printer", "Warehouse Printer")
    monkeypatch.setattr(
        "silverestimate.ui.settings_print_controller.QPrinterInfo.availablePrinters",
        lambda: [_PrinterStub("Warehouse Printer")],
    )
    monkeypatch.setattr(
        "silverestimate.infrastructure.logger.reconfigure_logging", lambda: None
    )

    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        dialog.print_page.printer_combo.setCurrentIndex(
            dialog.print_page.printer_combo.findData("")
        )

        assert dialog.apply_settings() is True
        assert settings.value("print/default_printer") is None
    finally:
        dialog.deleteLater()


def test_settings_dialog_uses_defaults_for_invalid_ui_preferences(
    qtbot, qt_app, monkeypatch, settings_stub
):
    del qt_app, settings_stub
    settings = get_app_settings()
    settings.setValue("ui/table_font_size", "invalid")
    settings.setValue("ui/breakdown_font_size", None)
    settings.setValue("ui/final_calc_font_size", "huge")

    monkeypatch.setattr(
        "silverestimate.ui.settings_print_controller.QPrinterInfo.availablePrinters",
        lambda: [],
    )

    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        assert dialog.appearance_page.table_font_size_spin.value() == 11
        assert dialog.appearance_page.breakdown_font_size_spin.value() == 11
        assert dialog.appearance_page.final_calc_font_size_spin.value() == 16
    finally:
        dialog.deleteLater()


def test_password_change_uses_auth_service_and_preserves_keyring_names(
    qtbot,
    qt_app,
    monkeypatch,
    settings_stub,
):
    del qt_app
    _MessageBoxStub.reset()
    credential_store.set_password_hash("main", "old-main-hash")
    credential_store.set_password_hash("backup", "old-backup-hash")
    changed_passwords = []
    monkeypatch.setattr(
        "silverestimate.ui.settings_security_page.run_database_maintenance",
        lambda database, operation, title, parent: operation(database),
    )

    class _DatabaseStub:
        @staticmethod
        def change_passwords(password):
            changed_passwords.append(password)
            return types.SimpleNamespace(
                status=types.SimpleNamespace(name="SUCCESS"),
                message="Password updated.",
            )

    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
    )
    dialog = SettingsDialog(
        main_window_ref=_make_main_window(estimate_widget, db=_DatabaseStub())
    )
    qtbot.addWidget(dialog)
    monkeypatch.setattr(
        "silverestimate.ui.settings_security_page.QMessageBox",
        _MessageBoxStub,
    )
    monkeypatch.setattr(
        "silverestimate.services.auth_service.verify_password",
        lambda stored, provided, logger=None: (
            stored == "old-main-hash" and provided == "current-password"
        ),
    )
    monkeypatch.setattr(
        "silverestimate.services.auth_service.hash_password",
        lambda password, logger=None: f"argon2-{password}",
    )
    try:
        page = dialog.security_page
        page.current_password_input.setText("current-password")
        page.new_password_input.setText("new-main-password")
        page.confirm_new_password_input.setText("new-main-password")
        page.new_secondary_password_input.setText("new-recovery-password")
        page.confirm_new_secondary_password_input.setText("new-recovery-password")

        result = page.change_passwords()

        assert result.succeeded
        assert changed_passwords == ["new-main-password"]
        assert credential_store.get_password_hash("main") == (
            "argon2-new-main-password"
        )
        assert credential_store.get_password_hash("backup") == (
            "argon2-new-recovery-password"
        )
        for kind in (
            "pending_main",
            "pending_backup",
            "recovery_main",
            "recovery_backup",
        ):
            assert credential_store.get_password_hash(kind) is None
        assert _MessageBoxStub.information_calls
        assert not _MessageBoxStub.critical_calls
        assert not _MessageBoxStub.warning_calls
    finally:
        dialog.deleteLater()


def test_each_settings_page_needs_only_its_own_width(qtbot, qt_app, settings_stub):
    del qt_app, settings_stub
    from PySide6.QtWidgets import QSizePolicy

    from silverestimate.ui.settings_dialog import PREFERRED_HEIGHT, PREFERRED_WIDTH

    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        # Not nearly the whole screen for a few fields.
        assert dialog.width() <= PREFERRED_WIDTH
        assert dialog.height() <= PREFERRED_HEIGHT
        for index in range(dialog.pages.count()):
            dialog.sidebar.setCurrentRow(index)
            current = dialog.pages.currentWidget()
            for other in range(dialog.pages.count()):
                page = dialog.pages.widget(other)
                expected = (
                    QSizePolicy.Policy.Preferred
                    if page is current
                    else QSizePolicy.Policy.Ignored
                )
                assert page.sizePolicy().horizontalPolicy() == expected
            # A wide page elsewhere no longer forces this one to scroll sideways.
            assert (
                dialog.pages.minimumSizeHint().width()
                == current.minimumSizeHint().width()
            )
    finally:
        dialog.deleteLater()


def test_default_zoom_is_entered_as_a_percentage(qtbot, qt_app, settings_stub):
    del qt_app, settings_stub
    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        spin = dialog.print_page.preview_zoom_spin
        spin.setValue(1.25)
        # Shown the way the print preview shows it; stored as a factor.
        assert spin.text() == "125 %"
        assert spin.value() == 1.25
        assert spin.valueFromText("80 %") == 0.8
        # The row is headed "Margins (mm)"; the boxes hold the number alone.
        assert dialog.print_page.margin_left_spin.suffix() == ""
    finally:
        dialog.deleteLater()


def _settings_dialog_as_opened_on_1366x768(
    qtbot, qt_application_state, size=(1180, 688)
):
    """The dialog at its real size there: 1180x688, in the app's own font."""
    _configure_smoke_font(qt_application_state)
    apply_light_application_theme(qt_application_state)
    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    dialog.resize(*size)
    dialog.show()
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def test_every_page_fits_without_a_scrollbar_at_the_size_it_opens_on_1366x768(
    qtbot, qt_application_state, settings_stub
):
    # Printing and Data & Backups used to scroll, which put "Delete All Data"
    # and the print sample below the fold.
    del settings_stub
    dialog = _settings_dialog_as_opened_on_1366x768(qtbot, qt_application_state)
    try:
        for index in range(dialog.sidebar.count()):
            dialog.sidebar.setCurrentRow(index)
            qtbot.wait(60)
            page = dialog.pages.currentWidget()
            viewport_height = dialog.page_scroll.viewport().height()
            assert not dialog.page_scroll.verticalScrollBar().isVisible(), index
            assert page.minimumSizeHint().height() <= viewport_height, index
            assert page.height() <= viewport_height, index
    finally:
        dialog.deleteLater()


def test_print_margin_boxes_stay_clear_of_the_page_sketch(
    qtbot, qt_application_state, settings_stub
):
    del settings_stub
    dialog = _settings_dialog_as_opened_on_1366x768(qtbot, qt_application_state)
    try:
        dialog.sidebar.setCurrentRow(2)
        qtbot.wait(80)
        page = dialog.print_page
        sketch = next(
            frame
            for frame in page.findChildren(QFrame)
            if frame.size() == QSize(84, 72)
        )
        sketch_rect = QRect(sketch.mapTo(page, QPoint(0, 0)), sketch.size())
        spins = (
            page.margin_top_spin,
            page.margin_left_spin,
            page.margin_right_spin,
            page.margin_bottom_spin,
        )
        for spin in spins:
            spin_rect = QRect(spin.mapTo(page, QPoint(0, 0)), spin.size())
            assert not sketch_rect.intersects(spin_rect), spin
        # Top above the sketch, Bottom below it, Left and Right either side.
        assert page.margin_top_spin.geometry().bottom() < sketch.geometry().top() + 40
        top = page.margin_top_spin.mapTo(page, QPoint(0, 0)).y()
        bottom = page.margin_bottom_spin.mapTo(page, QPoint(0, 0)).y()
        assert top < sketch_rect.top() < sketch_rect.bottom() < bottom + 1
        assert page.margin_left_spin.mapTo(page, QPoint(0, 0)).x() < sketch_rect.left()
        assert (
            page.margin_right_spin.mapTo(page, QPoint(0, 0)).x() > sketch_rect.right()
        )
    finally:
        dialog.deleteLater()


def test_appearance_preview_shows_every_column_at_the_real_dialog_width(
    qtbot, qt_application_state, settings_stub
):
    del settings_stub
    dialog = _settings_dialog_as_opened_on_1366x768(qtbot, qt_application_state)
    try:
        page = dialog.appearance_page
        table = page.preview_table
        qtbot.wait(80)

        assert not table.horizontalScrollBar().isVisible()
        header = table.horizontalHeader()
        for column in range(table.columnCount()):
            title = table.horizontalHeaderItem(column).text()
            assert header.sectionSize(column) >= (
                header.fontMetrics().horizontalAdvance(title)
            ), title
        # Beside the table at this width there is no room: the sample totals
        # sit under it, as one row.
        assert page.preview_content.direction() == QBoxLayout.Direction.TopToBottom
        assert "Grand Total" in page.preview_total.text()
    finally:
        dialog.deleteLater()


@pytest.mark.parametrize("size", [(1180, 688), (1180, 648)])
def test_a_page_is_never_cut_off_without_a_scrollbar(
    qtbot, qt_application_state, settings_stub, size
):
    # 1180x648 is the size on a 1600x900 screen at 125% (1280x688 usable). The
    # scrollbar used to be decided by the page's minimum size hint, while the
    # scroll area enforced the taller height-for-width, so the bottom 10 px of
    # every page were trimmed with no way to reach them.
    del settings_stub
    dialog = _settings_dialog_as_opened_on_1366x768(qtbot, qt_application_state, size)
    try:
        for index in range(dialog.sidebar.count()):
            dialog.sidebar.setCurrentRow(index)
            qtbot.wait(60)
            viewport = dialog.page_scroll.viewport()
            bar = dialog.page_scroll.verticalScrollBar()
            assert bar.isVisible() or dialog.pages.height() <= viewport.height(), index
            # With room for it, no page needs one.
            assert not bar.isVisible(), index
    finally:
        dialog.deleteLater()


def test_no_window_height_cuts_a_page_without_a_scrollbar(
    qtbot, qt_application_state, settings_stub
):
    # Between the height a page can squeeze into and the height the scroll area
    # really asks for (the tallest page's height at this width) the page used
    # to be trimmed with no scrollbar. Every height from 600 to 700 must give
    # either the whole page or a scrollbar.
    del settings_stub
    dialog = _settings_dialog_as_opened_on_1366x768(
        qtbot, qt_application_state, (1180, 700)
    )
    try:
        dialog.sidebar.setCurrentRow(3)
        bar = dialog.page_scroll.verticalScrollBar()
        scrollbar_seen = False
        for height in range(600, 701, 4):
            dialog.resize(1180, height)
            qtbot.wait(40)
            viewport = dialog.page_scroll.viewport()
            assert bar.isVisible() or dialog.pages.height() <= viewport.height(), height
            scrollbar_seen = scrollbar_seen or bar.isVisible()
        # The shortest windows do need one.
        assert scrollbar_seen
    finally:
        dialog.deleteLater()


def test_preview_changes_are_staged_and_footer_buttons_work(
    qtbot, settings_stub, monkeypatch
):
    estimate = types.SimpleNamespace(
        apply_table_font_size=lambda _: True,
        apply_breakdown_font_size=lambda _: True,
        apply_final_calc_font_size=lambda _: True,
    )
    dialog = SettingsDialog(_make_main_window(estimate))
    qtbot.addWidget(dialog)
    dialog.resize(1366, 768)
    dialog.show()
    settings = get_app_settings()
    before = settings.get_int(SettingsKey.UI_TABLE_FONT_SIZE, 11)
    page = dialog.appearance_page
    page.table_font_size_spin.setValue(13)
    page.density_combo.setCurrentIndex(1)
    page.alternating_checkbox.setChecked(False)
    assert page.preview_table.font().pointSize() == 13
    assert not page.preview_table.alternatingRowColors()
    assert settings.get_int(SettingsKey.UI_TABLE_FONT_SIZE, 11) == before
    calls = []
    monkeypatch.setattr(dialog, "apply_settings", lambda: calls.append("saved") or True)
    save = dialog.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
    cancel = dialog.buttonBox.button(QDialogButtonBox.StandardButton.Cancel)
    apply = dialog.buttonBox.button(QDialogButtonBox.StandardButton.Apply)
    # Qt owns button placement so theme/font refreshes keep the footer visible.
    for button in (cancel, apply, save):
        assert dialog.buttonBox.isAncestorOf(button)
        assert button.isVisible()
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    assert calls == ["saved"]
    assert dialog.result() == dialog.DialogCode.Accepted
