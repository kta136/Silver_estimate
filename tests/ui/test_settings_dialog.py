import types

from PyQt5.QtGui import QFont

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


def test_settings_accept_does_not_close_when_apply_fails(
    qt_app, monkeypatch, settings_stub
):
    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: True,
        apply_breakdown_font_size=lambda size: True,
        apply_final_calc_font_size=lambda size: True,
    )
    dialog = SettingsDialog(main_window_ref=_make_main_window(estimate_widget))
    try:
        monkeypatch.setattr(dialog, "apply_settings", lambda: False)
        dialog.accept()
        assert dialog.result() == 0
    finally:
        dialog.deleteLater()


def test_settings_apply_calls_public_estimate_widget_methods(
    qt_app, monkeypatch, settings_stub
):
    _MessageBoxStub.reset()
    calls = {"table": 0, "breakdown": 0, "final": 0}

    estimate_widget = types.SimpleNamespace(
        apply_table_font_size=lambda size: calls.__setitem__(
            "table", calls["table"] + 1
        )
        or True,
        apply_breakdown_font_size=lambda size: calls.__setitem__(
            "breakdown", calls["breakdown"] + 1
        )
        or True,
        apply_final_calc_font_size=lambda size: calls.__setitem__(
            "final", calls["final"] + 1
        )
        or True,
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
        assert not _MessageBoxStub.critical_calls
    finally:
        dialog.deleteLater()
