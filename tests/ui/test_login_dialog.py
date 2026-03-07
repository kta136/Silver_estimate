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
        assert dialog.backup_password_label.text() == "Secondary Password:"
        assert dialog.confirm_password_label.text() == "Confirm Secondary Password:"
    finally:
        dialog.deleteLater()
