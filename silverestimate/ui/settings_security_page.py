"""Security settings page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from silverestimate.services.password_change_service import (
    PasswordChangeRequest,
    PasswordChangeResult,
    PasswordChangeService,
    PasswordChangeStatus,
    PasswordField,
)


class SettingsSecurityController:
    """Expose the password-change service to the security page."""

    def __init__(self, password_change_service: PasswordChangeService) -> None:
        self._password_change_service = password_change_service

    def change_passwords(
        self,
        request: PasswordChangeRequest,
    ) -> PasswordChangeResult:
        return self._password_change_service.change_passwords(request)


class SecuritySettingsPage(QWidget):
    """Own password inputs and render typed password-change outcomes."""

    def __init__(
        self,
        controller: SettingsSecurityController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._build_ui()

    def state(self) -> PasswordChangeRequest:
        return PasswordChangeRequest(
            current_password=self.current_password_input.text(),
            new_main_password=self.new_password_input.text(),
            confirm_main_password=self.confirm_new_password_input.text(),
            new_recovery_password=self.new_secondary_password_input.text(),
            confirm_recovery_password=self.confirm_new_secondary_password_input.text(),
        )

    def change_passwords(self) -> PasswordChangeResult:
        result = self._controller.change_passwords(self.state())
        self._apply_result(result)
        return result

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        password_group = QGroupBox("Change Passwords")
        form = QFormLayout(password_group)
        self._configure_form(form)

        self.current_password_input = self._password_input(
            "Enter your current main password"
        )
        form.addRow("Current Password:", self.current_password_input)

        self.new_password_input = self._password_input("Enter new main password")
        form.addRow("New Main Password:", self.new_password_input)

        self.confirm_new_password_input = self._password_input(
            "Confirm new main password"
        )
        form.addRow("Confirm New Main:", self.confirm_new_password_input)

        form.addRow(QLabel("-" * 40))

        self.new_secondary_password_input = self._password_input(
            "Enter new recovery password"
        )
        form.addRow(
            "New Recovery Password:",
            self.new_secondary_password_input,
        )

        self.confirm_new_secondary_password_input = self._password_input(
            "Confirm new recovery password"
        )
        form.addRow(
            "Confirm New Recovery:",
            self.confirm_new_secondary_password_input,
        )

        self.change_password_button = QPushButton("Change Passwords")
        self.change_password_button.clicked.connect(self.change_passwords)
        form.addRow("", self.change_password_button)

        self.show_passwords_checkbox = QCheckBox("Show passwords")
        self.show_passwords_checkbox.toggled.connect(self._toggle_password_visibility)
        form.addRow("", self.show_passwords_checkbox)

        main_layout.addWidget(password_group)
        main_layout.addStretch()

    def _apply_result(self, result: PasswordChangeResult) -> None:
        fields = self._password_fields()
        for field_name in result.clear_fields:
            fields[field_name].clear()
        if result.focus_field is not None:
            fields[result.focus_field].setFocus()

        if result.status is PasswordChangeStatus.SUCCESS:
            QMessageBox.information(self, "Password Updated", result.message)
        elif result.status is PasswordChangeStatus.ROLLED_BACK:
            QMessageBox.warning(self, "Password Change Rolled Back", result.message)
        elif result.status is PasswordChangeStatus.VALIDATION_FAILED:
            QMessageBox.warning(self, "Password Change Failed", result.message)
        else:
            QMessageBox.critical(self, "Password Change Error", result.message)

    def _password_fields(self) -> dict[PasswordField, QLineEdit]:
        return {
            "current_password": self.current_password_input,
            "new_main_password": self.new_password_input,
            "confirm_main_password": self.confirm_new_password_input,
            "new_recovery_password": self.new_secondary_password_input,
            "confirm_recovery_password": self.confirm_new_secondary_password_input,
        }

    def _toggle_password_visibility(self, checked: bool) -> None:
        echo_mode = (
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        for field in self._password_fields().values():
            field.setEchoMode(echo_mode)

    @staticmethod
    def _password_input(placeholder: str) -> QLineEdit:
        field = QLineEdit()
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setPlaceholderText(placeholder)
        return field

    @staticmethod
    def _configure_form(form: QFormLayout) -> None:
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)


__all__ = [
    "SecuritySettingsPage",
    "SettingsSecurityController",
]
