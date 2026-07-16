from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit

from silverestimate.ui import login_dialog as login_dialog_module
from silverestimate.ui.login_dialog import LoginDialog


def test_login_dialog_separates_reset_action_from_primary_actions(qtbot):
    dialog = LoginDialog(is_setup=False)
    qtbot.addWidget(dialog)
    try:
        assert dialog.ok_button.text() == "Sign In"
        assert dialog.ok_button.objectName() == "LoginPrimaryButton"
        assert dialog.cancel_button.objectName() == "LoginSecondaryButton"
        assert dialog.password_input.isClearButtonEnabled() is True
        assert dialog.width() >= dialog.minimumWidth()
        assert "QMenu::item:selected" in dialog.styleSheet()
        assert "QToolTip" in dialog.styleSheet()
        assert hasattr(dialog, "reset_button")
        assert dialog.reset_button.objectName() == "LoginDangerButton"
    finally:
        dialog.deleteLater()


def test_login_dialog_warms_password_context_on_idle(qtbot, monkeypatch):
    dialog = LoginDialog(is_setup=False)
    qtbot.addWidget(dialog)
    calls = []
    monkeypatch.setattr(
        login_dialog_module, "_get_pwd_context", lambda: calls.append("warm")
    )

    dialog.schedule_password_context_warmup()

    qtbot.waitUntil(lambda: calls == ["warm"])


def test_setup_dialog_omits_reset_action_and_keeps_secondary_fields(qtbot):
    dialog = LoginDialog(is_setup=True)
    qtbot.addWidget(dialog)
    try:
        assert dialog.ok_button.text() == "Create Passwords"
        assert not hasattr(dialog, "reset_button")
        assert dialog.password_help_label.objectName() == "LoginHelpLabel"
        assert "two different passwords" in dialog.password_help_label.text()
        assert dialog.confirm_main_password_label.text() == "Confirm Main Password:"
        assert dialog.confirm_main_password_input.isClearButtonEnabled() is True
        assert "at least 8 characters" in dialog.password_requirements_label.text()
        assert dialog.backup_password_label.text() == "Recovery Password:"
        assert dialog.confirm_password_label.text() == "Confirm Recovery Password:"
        assert dialog.backup_password_input.isClearButtonEnabled() is True
        assert dialog.confirm_password_input.isClearButtonEnabled() is True
    finally:
        dialog.deleteLater()


def test_login_dialog_show_passwords_toggle_updates_echo_modes(qtbot):
    dialog = LoginDialog(is_setup=True)
    qtbot.addWidget(dialog)
    try:
        assert dialog.password_input.echoMode() == QLineEdit.EchoMode.Password
        assert (
            dialog.confirm_main_password_input.echoMode() == QLineEdit.EchoMode.Password
        )
        assert dialog.backup_password_input.echoMode() == QLineEdit.EchoMode.Password
        assert dialog.confirm_password_input.echoMode() == QLineEdit.EchoMode.Password

        dialog.show_passwords_checkbox.setChecked(True)

        assert dialog.password_input.echoMode() == QLineEdit.EchoMode.Normal
        assert (
            dialog.confirm_main_password_input.echoMode() == QLineEdit.EchoMode.Normal
        )
        assert dialog.backup_password_input.echoMode() == QLineEdit.EchoMode.Normal
        assert dialog.confirm_password_input.echoMode() == QLineEdit.EchoMode.Normal
    finally:
        dialog.deleteLater()


def test_setup_dialog_requires_main_password_confirmation(qtbot, monkeypatch):
    dialog = LoginDialog(is_setup=True)
    qtbot.addWidget(dialog)
    warnings = []
    monkeypatch.setattr(
        "silverestimate.ui.login_dialog.QMessageBox.warning",
        lambda *args: warnings.append(args),
    )
    try:
        dialog.password_input.setText("main-password")
        dialog.confirm_main_password_input.setText("different-password")
        dialog.backup_password_input.setText("recovery-password")
        dialog.confirm_password_input.setText("recovery-password")

        dialog._handle_ok()

        assert warnings
        assert "Main passwords do not match" in warnings[-1][2]
        assert dialog.result() == 0
    finally:
        dialog.deleteLater()


def test_login_dialog_foreground_request_raises_and_focuses(qtbot, monkeypatch):
    dialog = LoginDialog(is_setup=False)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(dialog.isVisible)

    calls = []

    monkeypatch.setattr(LoginDialog, "showNormal", lambda self: calls.append("show"))
    monkeypatch.setattr(LoginDialog, "raise_", lambda self: calls.append("raise"))
    monkeypatch.setattr(
        LoginDialog, "activateWindow", lambda self: calls.append("activate")
    )
    monkeypatch.setattr(LoginDialog, "winId", lambda self: 123)
    monkeypatch.setattr(
        "silverestimate.ui.login_dialog.QApplication.alert",
        lambda widget, msec=0: calls.append(("alert", widget is dialog, msec)),
    )
    monkeypatch.setattr(
        dialog.password_input,
        "setFocus",
        lambda reason=Qt.FocusReason.OtherFocusReason: calls.append(("focus", reason)),
    )
    monkeypatch.setattr(
        "silverestimate.ui.login_dialog.bring_window_to_front",
        lambda hwnd: calls.append(("native-front", hwnd)),
    )

    dialog._request_startup_foreground()

    assert "show" in calls
    assert "raise" in calls
    assert "activate" in calls
    assert ("alert", True, 0) in calls
    assert ("focus", Qt.FocusReason.ActiveWindowFocusReason) in calls
    assert ("native-front", 123) in calls
