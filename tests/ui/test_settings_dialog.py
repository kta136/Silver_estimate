import types

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTableWidget

from silverestimate.infrastructure.settings import get_app_settings
from silverestimate.security import credential_store
from silverestimate.ui.settings_dialog import SettingsDialog
from silverestimate.ui.themed_controls import (
    ThemedComboBox,
    ThemedDoubleSpinBox,
    ThemedSpinBox,
)


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
        apply_totals_position=lambda value: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        assert isinstance(dialog.appearance_page.table_font_size_spin, ThemedSpinBox)
        assert isinstance(dialog.print_page.preview_zoom_spin, ThemedDoubleSpinBox)
        assert isinstance(dialog.appearance_page.totals_position_combo, ThemedComboBox)
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
        apply_totals_position=lambda value: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        monkeypatch.setattr(dialog, "apply_settings", lambda: False)
        dialog.accept()
        assert dialog.result() == 0
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
        apply_totals_position=lambda value: True,
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
        assert settings.value("print/estimate_layout") == "modern"
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
    settings.setValue("print/estimate_layout", "future")
    settings.setValue("print/default_printer", "Missing Printer")

    monkeypatch.setattr(
        "silverestimate.ui.settings_print_controller.QPrinterInfo.availablePrinters",
        lambda: [_PrinterStub("Counter Printer")],
    )

    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
        apply_totals_position=lambda value: True,
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
        assert settings.value("print/estimate_layout") == "modern"
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
        apply_totals_position=lambda value: True,
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
    monkeypatch.setattr(
        "silverestimate.ui.settings_print_controller.QPrinterInfo.availablePrinters",
        lambda: [],
    )
    monkeypatch.setattr(
        "silverestimate.infrastructure.logger.reconfigure_logging", lambda: None
    )

    applied = {}
    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: applied.setdefault("table", size) or True,
        apply_breakdown_font_size=lambda size: (
            applied.setdefault("breakdown", size) or True
        ),
        apply_final_calc_font_size=lambda size: (
            applied.setdefault("final", size) or True
        ),
        apply_totals_position=lambda value: (
            applied.setdefault("position", value) or True
        ),
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        dialog.appearance_page.table_font_size_spin.setValue(12)
        dialog.appearance_page.breakdown_font_size_spin.setValue(11)
        dialog.appearance_page.final_calc_font_size_spin.setValue(18)
        dialog.appearance_page.totals_position_combo.setCurrentIndex(
            dialog.appearance_page.totals_position_combo.findData("bottom")
        )

        assert dialog.apply_settings() is True
        assert settings.value("ui/table_font_size") == 12
        assert settings.value("ui/breakdown_font_size") == 11
        assert settings.value("ui/final_calc_font_size") == 18
        assert settings.value("ui/estimate_totals_position") == "bottom"
        assert applied == {
            "table": 12,
            "breakdown": 11,
            "final": 18,
            "position": "bottom",
        }
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
    page.totals_position_combo.setCurrentIndex(
        page.totals_position_combo.findData("bottom")
    )
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
    assert settings.value("ui/estimate_totals_position") == "bottom"
    assert estimate.item_table.font().pointSize() == 13
    assert not estimate.item_table.alternatingRowColors()
    assert estimate._breakdown_font_size == 12
    assert estimate._final_calc_font_size == 18
    assert estimate._totals_position == "bottom"

    reopened = SettingsDialog(main_window_ref=main_window)
    qtbot.addWidget(reopened)
    assert reopened.appearance_page.table_font_size_spin.value() == 13
    reopened.appearance_page.table_font_size_spin.setValue(15)
    reopened.buttonBox.button(QDialogButtonBox.StandardButton.Cancel).click()
    assert settings.value("ui/table_font_size") == 13
    assert estimate.item_table.font().pointSize() == 13
    reloaded_estimate = make_estimate_widget(fake_db)
    assert reloaded_estimate.item_table.font().pointSize() == 13
    assert reloaded_estimate._totals_position == "bottom"


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
    for size, totals_size, final_size, position in (
        (12, 10, 16, "right"),
        (14, 11, 18, "left"),
        (11, 12, 20, "bottom"),
    ):
        page.table_font_size_spin.setValue(size)
        page.breakdown_font_size_spin.setValue(totals_size)
        page.final_calc_font_size_spin.setValue(final_size)
        page.totals_position_combo.setCurrentIndex(
            page.totals_position_combo.findData(position)
        )
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
        apply_totals_position=lambda value: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        page = dialog.logging_page
        page.debug_mode_checkbox.setChecked(True)
        page.enable_info_checkbox.setChecked(False)
        page.enable_critical_checkbox.setChecked(True)
        page.enable_debug_checkbox.setChecked(True)
        page.auto_cleanup_checkbox.setChecked(True)
        page.cleanup_days_spin.setValue(30)

        assert dialog.apply_settings() is True
        assert settings.value("logging/debug_mode") is True
        assert settings.value("logging/enable_info") is False
        assert settings.value("logging/enable_critical") is True
        assert settings.value("logging/enable_debug") is True
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
        apply_totals_position=lambda value: True,
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
    settings.setValue("ui/estimate_totals_position", "sideways")

    monkeypatch.setattr(
        "silverestimate.ui.settings_print_controller.QPrinterInfo.availablePrinters",
        lambda: [],
    )

    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
        apply_totals_position=lambda value: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        assert dialog.appearance_page.table_font_size_spin.value() == 11
        assert dialog.appearance_page.breakdown_font_size_spin.value() == 11
        assert dialog.appearance_page.final_calc_font_size_spin.value() == 16
        assert dialog.appearance_page.totals_position_combo.currentData() == "right"
    finally:
        dialog.deleteLater()


def test_settings_apply_calls_estimate_layout_controller(
    qtbot, qt_app, monkeypatch, settings_stub
):
    _MessageBoxStub.reset()
    calls = {"table": 0, "breakdown": 0, "final": 0, "position": 0}

    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: (
            calls.__setitem__("table", calls["table"] + 1) or True
        ),
        apply_breakdown_font_size=lambda size: (
            calls.__setitem__("breakdown", calls["breakdown"] + 1) or True
        ),
        apply_final_calc_font_size=lambda size: (
            calls.__setitem__("final", calls["final"] + 1) or True
        ),
        apply_totals_position=lambda value: (
            calls.__setitem__("position", calls["position"] + 1) or True
        ),
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    qtbot.addWidget(dialog)
    try:
        monkeypatch.setattr(
            "silverestimate.ui.settings_dialog.QMessageBox", _MessageBoxStub
        )
        assert dialog.apply_settings() is True
        assert calls["table"] == 1
        assert calls["breakdown"] == 1
        assert calls["final"] == 1
        assert calls["position"] == 1
        assert not _MessageBoxStub.critical_calls
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
        apply_totals_position=lambda value: True,
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
