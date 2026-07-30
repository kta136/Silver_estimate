import types

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QTableWidget

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


def _make_main_window(estimate_widget, *, db=None):
    return types.SimpleNamespace(
        print_font=QFont("Arial", 10),
        estimate_widget=estimate_widget,
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


def test_settings_dialog_uses_visible_arrow_controls(qt_app, settings_stub):
    del qt_app, settings_stub
    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
        apply_totals_position=lambda value: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    try:
        assert isinstance(dialog.appearance_page.table_font_size_spin, ThemedSpinBox)
        assert isinstance(dialog.print_page.preview_zoom_spin, ThemedDoubleSpinBox)
        assert isinstance(dialog.appearance_page.totals_position_combo, ThemedComboBox)
        assert isinstance(dialog.print_page.printer_combo, ThemedComboBox)
        assert isinstance(dialog.print_page.estimate_format_combo, ThemedComboBox)
        assert (
            dialog.sidebar.horizontalScrollBarPolicy()
            == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        assert dialog.minimumHeight() <= 540
        assert dialog.sidebar.width() >= 200
        assert dialog.page_scroll.widgetResizable() is True
        assert (
            dialog.page_scroll.horizontalScrollBarPolicy()
            == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        assert dialog.appearance_page.print_font_button.minimumWidth() >= 180
        assert dialog.appearance_page.table_font_size_spin.maximumWidth() <= 180
        preview_table = dialog.findChild(QTableWidget, "SettingsPreviewTable")
        assert preview_table is not None
        assert preview_table.item(0, 2).textAlignment() == (
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
    finally:
        dialog.deleteLater()


def test_settings_accept_does_not_close_when_apply_fails(
    qt_app, monkeypatch, settings_stub
):
    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
        apply_totals_position=lambda value: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    try:
        monkeypatch.setattr(dialog, "apply_settings", lambda: False)
        dialog.accept()
        assert dialog.result() == 0
    finally:
        dialog.deleteLater()


def test_settings_apply_persists_print_preferences(qt_app, monkeypatch, settings_stub):
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
    try:
        dialog.print_page.margin_left_spin.setValue(12)
        dialog.print_page.margin_top_spin.setValue(3)
        dialog.print_page.margin_right_spin.setValue(14)
        dialog.print_page.margin_bottom_spin.setValue(4)
        dialog.print_page.preview_zoom_spin.setValue(1.75)
        dialog.print_page.printer_combo.setCurrentText("Warehouse Printer")
        dialog.print_page.page_size_combo.setCurrentText("Legal")
        dialog.print_page.orientation_combo.setCurrentText("Landscape")
        dialog.print_page.estimate_format_combo.setCurrentIndex(
            dialog.print_page.estimate_format_combo.findData("classic")
        )

        assert dialog.apply_settings() is True
        assert settings.value("print/margins") == "12,3,14,4"
        assert settings.value("print/preview_zoom") == 1.75
        assert settings.value("print/default_printer") == "Warehouse Printer"
        assert settings.value("print/page_size") == "Legal"
        assert settings.value("print/orientation") == "Landscape"
        assert settings.value("print/estimate_layout") == "classic"
    finally:
        dialog.deleteLater()


def test_settings_dialog_uses_defaults_for_invalid_print_settings(
    qt_app, monkeypatch, settings_stub
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
    try:
        assert dialog.print_page.margin_left_spin.value() == 10
        assert dialog.print_page.margin_top_spin.value() == 2
        assert dialog.print_page.margin_right_spin.value() == 10
        assert dialog.print_page.margin_bottom_spin.value() == 2
        assert dialog.print_page.preview_zoom_spin.value() == 1.25
        assert dialog.print_page.page_size_combo.currentText() == "A4"
        assert dialog.print_page.orientation_combo.currentText() == "Landscape"
        assert settings.value("print/estimate_layout") == "modern"
        assert dialog.print_page.estimate_format_combo.currentData() == "modern"
        assert dialog.print_page.printer_combo.currentData() == ""
    finally:
        dialog.deleteLater()


def test_settings_dialog_preserves_portrait_orientation(
    qt_app, monkeypatch, settings_stub
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
    try:
        assert dialog.print_page.orientation_combo.currentText() == "Portrait"
    finally:
        dialog.deleteLater()


def test_settings_apply_persists_ui_preferences(qt_app, monkeypatch, settings_stub):
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


def test_settings_apply_persists_logging_preferences(
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


def test_settings_apply_can_clear_default_printer(qt_app, monkeypatch, settings_stub):
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
    try:
        dialog.print_page.printer_combo.setCurrentIndex(
            dialog.print_page.printer_combo.findData("")
        )

        assert dialog.apply_settings() is True
        assert settings.value("print/default_printer") is None
    finally:
        dialog.deleteLater()


def test_settings_dialog_uses_defaults_for_invalid_ui_preferences(
    qt_app, monkeypatch, settings_stub
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
    try:
        assert dialog.appearance_page.table_font_size_spin.value() == 9
        assert dialog.appearance_page.breakdown_font_size_spin.value() == 9
        assert dialog.appearance_page.final_calc_font_size_spin.value() == 10
        assert dialog.appearance_page.totals_position_combo.currentData() == "right"
    finally:
        dialog.deleteLater()


def test_settings_apply_calls_public_estimate_widget_methods(
    qt_app, monkeypatch, settings_stub
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
    qt_app,
    monkeypatch,
    settings_stub,
):
    del qt_app
    _MessageBoxStub.reset()
    credential_store.set_password_hash("main", "old-main-hash")
    credential_store.set_password_hash("backup", "old-backup-hash")
    changed_passwords = []

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
