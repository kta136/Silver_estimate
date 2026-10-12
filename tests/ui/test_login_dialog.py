import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QLineEdit

from silverestimate.infrastructure.app_constants import APP_NAME, APP_VERSION
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


def test_setup_dialog_omits_reset_action_and_keeps_secondary_fields(qtbot):
    dialog = LoginDialog(is_setup=True)
    qtbot.addWidget(dialog)
    try:
        assert dialog.ok_button.text() == "Create Passwords"
        assert dialog.cancel_button.text() == "Exit"
        assert not hasattr(dialog, "reset_button")
        # One explanation covers both rules; it is not said twice.
        assert not hasattr(dialog, "password_help_label")
        requirements = dialog.password_requirements_label.text()
        assert "two different passwords" in requirements
        assert "at least 8 characters" in requirements
        assert dialog.password_label.text() == "Main Password"
        assert dialog.confirm_main_password_label.text() == "Confirm Main Password"
        assert dialog.confirm_main_password_input.isClearButtonEnabled() is True
        assert dialog.backup_password_label.text() == "Recovery Password"
        assert dialog.confirm_password_label.text() == "Confirm Recovery Password"
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
    dialog.show()
    boxes = []
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.warning",
        lambda *args: boxes.append(args),
    )
    try:
        dialog.password_input.setText("main-password")
        dialog.confirm_main_password_input.setText("different-password")
        dialog.backup_password_input.setText("recovery-password")
        dialog.confirm_password_input.setText("recovery-password")
        # While typing, the dialog says what is still missing.
        assert dialog.progress_label.text() == (
            "Still needed: Main passwords do not match."
        )

        dialog._handle_ok()

        # The mistake is explained in the dialog, on the field to fix.
        assert boxes == []
        assert dialog.error_label.isVisible()
        assert dialog.error_label.text() == "Main passwords do not match."
        # Once, not twice: the progress line steps aside for the error.
        assert not dialog.progress_label.isVisible()
        assert dialog.focusWidget() is dialog.confirm_main_password_input
        assert dialog.result() == 0

        dialog.confirm_main_password_input.setText("main-password")
        assert not dialog.error_label.isVisible()
        assert dialog.progress_label.isVisible()
        assert dialog.progress_label.text() == "Both passwords are ready."
    finally:
        dialog.deleteLater()


def test_messages_do_not_move_the_fields_or_buttons(qtbot):
    for is_setup in (True, False):
        dialog = LoginDialog(is_setup=is_setup)
        qtbot.addWidget(dialog)
        dialog.show()
        qtbot.wait(20)
        before = (dialog.password_input.geometry(), dialog.ok_button.geometry())

        dialog._handle_ok()
        qtbot.wait(20)

        assert dialog.error_label.isVisible()
        assert (
            dialog.password_input.geometry(),
            dialog.ok_button.geometry(),
        ) == before


def test_wiping_needs_the_word_typed(qtbot, confirmations):
    dialog = LoginDialog(is_setup=False)
    qtbot.addWidget(dialog)
    confirmations.answer("Wipe All Data")

    # Anything but the word leaves the action switched off.
    confirmations.type_text("delet")
    dialog._handle_reset_request()
    assert not dialog.was_reset_requested()

    confirmations.always_type("delete")
    dialog._handle_reset_request()
    assert dialog.was_reset_requested()
    assert confirmations.prompts[-1].startswith("Wipe All Data")


def test_sign_in_explains_an_empty_password_in_place(qtbot):
    dialog = LoginDialog(is_setup=False)
    qtbot.addWidget(dialog)
    dialog.show()
    try:
        assert dialog.cancel_button.text() == "Exit"
        dialog._handle_ok()
        assert dialog.error_label.text() == "Enter your password."
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


# The smallest screen the dialogs are meant for: 1366x768 with Windows scaled to
# 125% leaves 1093x582 logical pixels, less a title bar.
_SMALLEST_SCREEN = (1093, 582 - 40)


@pytest.mark.parametrize("is_setup", [True, False])
def test_dialog_fits_the_smallest_supported_screen(qtbot, is_setup):
    dialog = LoginDialog(is_setup=is_setup)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.wait(20)

    assert dialog.width() <= _SMALLEST_SCREEN[0]
    assert dialog.height() <= _SMALLEST_SCREEN[1]


@pytest.mark.parametrize("is_setup", [True, False])
def test_wrapped_text_is_never_clipped(qtbot, is_setup):
    dialog = LoginDialog(is_setup=is_setup)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.wait(20)

    for label in dialog.findChildren(QLabel):
        if label.wordWrap() and label.isVisible():
            assert label.height() >= label.heightForWidth(label.width()), label.text()


def test_setup_puts_main_and_recovery_passwords_side_by_side(qtbot):
    dialog = LoginDialog(is_setup=True)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.wait(20)

    main, recovery = dialog.password_input, dialog.backup_password_input
    confirm_main, confirm_recovery = (
        dialog.confirm_main_password_input,
        dialog.confirm_password_input,
    )
    assert main.y() == recovery.y()
    assert confirm_main.y() == confirm_recovery.y()
    assert main.x() < recovery.x()
    assert main.geometry().right() < recovery.geometry().left()
    assert main.y() < confirm_main.y()
    # Tab walks down the main column, then down the recovery column.
    assert [field.accessibleName() for field in dialog._password_inputs()] == [
        "Main Password",
        "Confirm Main Password",
        "Recovery Password",
        "Confirm Recovery Password",
    ]


def test_brand_panel_names_the_app(qtbot):
    dialog = LoginDialog(is_setup=False)
    qtbot.addWidget(dialog)
    brand = dialog.findChild(QFrame, "LoginBrandPanel")
    assert brand is not None
    texts = [label.text() for label in brand.findChildren(QLabel)]
    assert APP_NAME in texts
    assert f"Version {APP_VERSION}" in texts
    # Name, version and logo only: no claims about the data.
    assert not any("encrypt" in text.lower() for text in texts)
    logo = brand.findChild(QLabel, "LoginBrandIcon")
    assert logo is not None
    assert not logo.pixmap().isNull()


def test_recovery_options_open_in_place_and_grow_the_dialog(qtbot):
    dialog = LoginDialog(is_setup=False)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.wait(20)
    closed_height = dialog.height()
    assert not dialog.reset_button.isVisible()

    dialog._toggle_recovery_options()
    qtbot.wait(20)

    assert dialog.reset_button.isVisible()
    assert dialog.height() > closed_height
    assert dialog.height() <= _SMALLEST_SCREEN[1]
    assert dialog.reset_button.geometry().bottom() < dialog.height()

    dialog._toggle_recovery_options()
    qtbot.wait(20)
    assert dialog.height() == closed_height


@pytest.mark.parametrize("is_setup", [False, True])
def test_no_text_or_tooltip_makes_claims_about_encryption(qtbot, is_setup):
    dialog = LoginDialog(is_setup=is_setup)
    qtbot.addWidget(dialog)
    try:
        texts = [label.text() for label in dialog.findChildren(QLabel)]
        for widget in dialog.findChildren(QLineEdit):
            texts += [widget.toolTip(), widget.placeholderText()]
        assert not any("encrypt" in text.lower() for text in texts)
    finally:
        dialog.deleteLater()
