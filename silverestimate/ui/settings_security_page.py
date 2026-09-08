"""Security settings page."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from silverestimate.persistence.database_protocols import MainCommandsDatabase
from silverestimate.services.password_change_service import (
    PasswordChangeRequest,
    PasswordChangeResult,
    PasswordChangeService,
    PasswordChangeStatus,
    PasswordField,
    default_password_change_actions,
)
from silverestimate.ui.database_maintenance import run_database_maintenance


class SettingsSecurityController:
    """Expose the password-change service to the security page."""

    def __init__(
        self, database_provider: Callable[[], MainCommandsDatabase | None]
    ) -> None:
        self._database_provider = database_provider

    def change_passwords(
        self,
        request: PasswordChangeRequest,
        parent: QWidget | None = None,
    ) -> PasswordChangeResult:
        database = self._database_provider()
        if database is None:
            return PasswordChangeResult(
                PasswordChangeStatus.FAILED,
                "Encrypted database connection is unavailable",
            )
        try:
            return run_database_maintenance(
                database,
                lambda worker: PasswordChangeService(
                    default_password_change_actions(lambda: worker)
                ).change_passwords(request),
                "Changing Passwords",
                parent,
            )
        except Exception as exc:
            return PasswordChangeResult(PasswordChangeStatus.FAILED, str(exc))


class SecuritySettingsPage(QWidget):
    """Own password inputs and render typed password-change outcomes."""

    def __init__(
        self,
        controller: SettingsSecurityController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._maintenance_active = False
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
        if self._maintenance_active:
            return PasswordChangeResult(
                PasswordChangeStatus.FAILED, "A password change is already running."
            )
        request = self.state()
        self._maintenance_active = True
        self.change_password_button.setEnabled(False)
        try:
            result = self._controller.change_passwords(request, self)
        finally:
            self._maintenance_active = False
            self.change_password_button.setEnabled(True)
        self._apply_result(result)
        return result

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        self.current_password_input = self._password_input(
            "Enter your current main password"
        )
        self.new_password_input = self._password_input("Enter new main password")
        self.confirm_new_password_input = self._password_input(
            "Confirm new main password"
        )
        self.new_secondary_password_input = self._password_input(
            "Enter new recovery password"
        )
        self.confirm_new_secondary_password_input = self._password_input(
            "Confirm new recovery password"
        )
        self.change_password_button = QPushButton("Change Passwords")
        self.change_password_button.clicked.connect(self.change_passwords)
        self.show_passwords_checkbox = QCheckBox("Show passwords")
        self.show_passwords_checkbox.toggled.connect(self._toggle_password_visibility)

        title = QLabel("Security")
        title.setObjectName("SettingsTitleLabel")
        main_layout.addWidget(title)
        main_layout.addWidget(QLabel("Current password"))
        main_layout.addWidget(self.current_password_input)
        columns = QHBoxLayout()
        for label, fields in (
            (
                "Main password",
                (self.new_password_input, self.confirm_new_password_input),
            ),
            (
                "Recovery password",
                (
                    self.new_secondary_password_input,
                    self.confirm_new_secondary_password_input,
                ),
            ),
        ):
            group = QGroupBox(label)
            column = QVBoxLayout(group)
            for caption, field in zip(
                ("New password", "Confirm password"), fields, strict=True
            ):
                column.addWidget(QLabel(caption))
                column.addWidget(field)
            columns.addWidget(group)
        main_layout.addLayout(columns)
        main_layout.addWidget(self.show_passwords_checkbox)
        main_layout.addWidget(
            QLabel(
                "Use at least 8 characters. Main and recovery passwords must differ."
            )
        )
        note = QLabel(
            "Changes take effect when you choose Change passwords, independently of Apply."
        )
        note.setWordWrap(True)
        main_layout.addWidget(note)
        actions = QHBoxLayout()
        actions.addStretch()
        self.change_password_button.setObjectName("SettingsPrimaryButton")
        self.change_password_button.setStyleSheet("QPushButton { color: white; }")
        actions.addWidget(self.change_password_button)
        clear = QPushButton("Clear fields")
        clear.clicked.connect(self._clear_fields)
        actions.addWidget(clear)
        main_layout.addLayout(actions)
        main_layout.addStretch()

    def _clear_fields(self):
        for field in self._password_fields().values():
            field.clear()

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
