from PyQt5.QtCore import Qt

from silverestimate.ui.login_dialog import LoginDialog


def test_login_dialog_separates_reset_action_from_primary_actions(qtbot):
    dialog = LoginDialog(is_setup=False)
    qtbot.addWidget(dialog)
    try:
        assert dialog.ok_button.text() == "Login"
        assert dialog.ok_button.objectName() == "LoginPrimaryButton"
        assert dialog.cancel_button.objectName() == "LoginSecondaryButton"
        assert hasattr(dialog, "reset_button")
        assert dialog.reset_button.objectName() == "LoginDangerButton"
    finally:
        dialog.deleteLater()


def test_setup_dialog_omits_reset_action_and_keeps_secondary_fields(qtbot):
    dialog = LoginDialog(is_setup=True)
    qtbot.addWidget(dialog)
    try:
        assert dialog.ok_button.text() == "Create Passwords"
        assert not hasattr(dialog, "reset_button")
        assert dialog.backup_password_label.text() == "Recovery Password:"
        assert dialog.confirm_password_label.text() == "Confirm Recovery Password:"
    finally:
        dialog.deleteLater()


def test_login_dialog_show_passwords_toggle_updates_echo_modes(qtbot):
    dialog = LoginDialog(is_setup=True)
    qtbot.addWidget(dialog)
    try:
        assert dialog.password_input.echoMode() == dialog.password_input.Password
        assert (
            dialog.backup_password_input.echoMode()
            == dialog.backup_password_input.Password
        )
        assert (
            dialog.confirm_password_input.echoMode()
            == dialog.confirm_password_input.Password
        )

        dialog.show_passwords_checkbox.setChecked(True)

        assert dialog.password_input.echoMode() == dialog.password_input.Normal
        assert dialog.backup_password_input.echoMode() == dialog.password_input.Normal
        assert dialog.confirm_password_input.echoMode() == dialog.password_input.Normal
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
        lambda reason=Qt.OtherFocusReason: calls.append(("focus", reason)),
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
    assert ("focus", Qt.ActiveWindowFocusReason) in calls
    assert ("native-front", 123) in calls
