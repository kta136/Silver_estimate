import types

from PyQt5.QtGui import QFont

from silverestimate.infrastructure.settings import get_app_settings
from silverestimate.ui.settings_dialog import SettingsDialog


class _MessageBoxStub:
    critical_calls = []

    @classmethod
    def reset(cls):
        cls.critical_calls = []

    @classmethod
    def critical(cls, *args, **kwargs):
        cls.critical_calls.append((args, kwargs))
        return None


def _make_main_window(estimate_widget):
    return types.SimpleNamespace(
        print_font=QFont("Arial", 10),
        estimate_widget=estimate_widget,
        show_import_dialog=lambda: None,
        delete_all_estimates=lambda: None,
        delete_all_data=lambda: None,
        reconfigure_rate_visibility_from_settings=lambda: True,
        reconfigure_rate_timer_from_settings=lambda: True,
        db=object(),
    )


class _PrinterStub:
    def __init__(self, name):
        self._name = name

    def printerName(self):
        return self._name


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
        dialog.margin_left_spin.setValue(12)
        dialog.margin_top_spin.setValue(3)
        dialog.margin_right_spin.setValue(14)
        dialog.margin_bottom_spin.setValue(4)
        dialog.preview_zoom_spin.setValue(1.75)
        dialog.printer_combo.setCurrentText("Warehouse Printer")
        dialog.page_size_combo.setCurrentText("Legal")
        dialog.orientation_combo.setCurrentText("Landscape")
        dialog.estimate_layout_combo.setCurrentIndex(
            dialog.estimate_layout_combo.findData("thermal")
        )

        assert dialog.apply_settings() is True
        assert settings.value("print/margins") == "12,3,14,4"
        assert settings.value("print/preview_zoom") == 1.75
        assert settings.value("print/default_printer") == "Warehouse Printer"
        assert settings.value("print/page_size") == "Legal"
        assert settings.value("print/orientation") == "Landscape"
        assert settings.value("print/estimate_layout") == "thermal"
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
        assert dialog.margin_left_spin.value() == 10
        assert dialog.margin_top_spin.value() == 2
        assert dialog.margin_right_spin.value() == 10
        assert dialog.margin_bottom_spin.value() == 2
        assert dialog.preview_zoom_spin.value() == 1.25
        assert dialog.page_size_combo.currentText() == "A4"
        assert dialog.orientation_combo.currentText() == "Portrait"
        assert dialog.estimate_layout_combo.currentData() == "old"
        assert dialog.printer_combo.currentText() == "Counter Printer"
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
        dialog.table_font_size_spin.setValue(12)
        dialog.breakdown_font_size_spin.setValue(11)
        dialog.final_calc_font_size_spin.setValue(18)
        dialog.totals_position_combo.setCurrentIndex(
            dialog.totals_position_combo.findData("bottom")
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
        assert dialog.table_font_size_spin.value() == 9
        assert dialog.breakdown_font_size_spin.value() == 9
        assert dialog.final_calc_font_size_spin.value() == 10
        assert dialog.totals_position_combo.currentData() == "right"
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
