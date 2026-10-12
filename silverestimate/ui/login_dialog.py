from contextlib import suppress

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from silverestimate.infrastructure.app_constants import APP_NAME, APP_VERSION
from silverestimate.infrastructure.paths import get_asset_path
from silverestimate.infrastructure.windows_integration import bring_window_to_front

from .message_dialogs import confirm_by_typing, confirm_destructive
from .shared_screen_theme import build_management_screen_stylesheet

BRAND_PANEL_WIDTH = 200
BRAND_ICON_SIZE = 96
# The setup form holds two columns of fields, so it is wider than sign-in.
SIGN_IN_FORM_WIDTH = 400
SETUP_FORM_WIDTH = 640


class LoginDialog(QDialog):
    """
    Dialog for user authentication (login) and initial password setup.

    A brand strip on the left and the form on the right. Setup puts the main
    and recovery passwords side by side so the whole dialog stays well inside
    a 1366x768 screen, even with Windows scaled to 125%.
    """

    MIN_PASSWORD_LENGTH = 8

    def __init__(self, is_setup=False, parent=None):
        super().__init__(parent)
        self.is_setup = is_setup
        self.setWindowTitle("Sign In" if not is_setup else "Create Passwords")
        self.setModal(True)  # Ensure user interacts with this dialog first
        self.setObjectName("LoginDialog")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setStyleSheet(
            build_management_screen_stylesheet(
                root_selector="QDialog#LoginDialog",
                card_names=["LoginDangerCard"],
                title_label="LoginTitleLabel",
                subtitle_label="LoginSubtitleLabel",
                field_label="LoginFieldLabel",
                primary_button="LoginPrimaryButton",
                secondary_button="LoginSecondaryButton",
                danger_button="LoginDangerButton",
                input_selectors=["QLineEdit"],
                extra_rules="""
                QWidget#LoginForm {
                    background-color: __SURFACE_BG__;
                }
                QFrame#LoginBrandPanel {
                    background-color: qlineargradient(
                        x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #0a4852, stop: 1 #052a31
                    );
                    border: none;
                }
                QFrame#LoginBrandPanel QLabel {
                    color: #ffffff;
                    background: transparent;
                }
                QLabel#LoginBrandName {
                    font-size: 15pt;
                    font-weight: 700;
                }
                QLabel#LoginBrandVersion {
                    font-weight: 600;
                }
                QLabel#LoginTitleLabel {
                    font-size: 16pt;
                }
                QLabel#LoginErrorLabel {
                    color: #b91c1c;
                    font-weight: 600;
                }
                QLabel#LoginProgressLabel[state="pending"] {
                    color: #9a3412;
                }
                QLabel#LoginProgressLabel[state="ready"] {
                    color: #166534;
                    font-weight: 600;
                }
                QLabel#LoginCapsLabel {
                    color: #9a3412;
                    font-weight: 600;
                }
                QLabel#LoginRequirementsLabel {
                    background-color: __HEADER_BG__;
                    border: 1px solid __CARD_BORDER_SOFT__;
                    border-radius: 8px;
                    color: __FIELD_TEXT__;
                    padding: 7px 10px;
                }
                QCheckBox#LoginShowPasswords {
                    color: __FIELD_TEXT__;
                    spacing: 8px;
                }
                QCheckBox#LoginShowPasswords::indicator {
                    width: 14px;
                    height: 14px;
                    border-radius: 4px;
                    border: 1px solid __INPUT_BORDER__;
                    background-color: __SURFACE_BG__;
                }
                QCheckBox#LoginShowPasswords::indicator:checked {
                    background-color: __PRIMARY_BG__;
                    border: 1px solid __PRIMARY_BG__;
                }
                QPushButton#LoginPrimaryButton,
                QPushButton#LoginSecondaryButton,
                QPushButton#LoginDangerButton {
                    min-height: 30px;
                    padding: 6px 12px;
                }
                QPushButton#LoginPrimaryButton {
                    min-width: 112px;
                }
                QPushButton#LoginSecondaryButton {
                    min-width: 84px;
                }
                QPushButton#LoginForgotButton {
                    color: __PRIMARY_BG__;
                    font-weight: 600;
                    text-align: left;
                    border: none;
                    padding: 0;
                    background: transparent;
                }
                QPushButton#LoginForgotButton:hover {
                    color: __PRIMARY_BG__;
                    text-decoration: underline;
                }
                QLabel#LoginDangerTitle {
                    color: #991b1b;
                    font-weight: 700;
                }
                QLabel#LoginDangerBody {
                    color: #7f1d1d;
                }
                QFrame#LoginDangerCard {
                    background-color: __DANGER_BG__;
                    border: 1px solid __DANGER_BORDER__;
                    border-radius: 8px;
                }
                """,
            )
        )

        self._password = str()
        self._backup_password = str()  # Only used in setup mode
        self.reset_requested = False  # Add flag to track reset request
        self._startup_activation_pending = True
        self._form_width = SETUP_FORM_WIDTH if is_setup else SIGN_IN_FORM_WIDTH

        self._setup_ui()
        self._connect_signals()
        self._fit_to_content()

    # -- layout ---------------------------------------------------------

    def _setup_ui(self):
        """Create the UI elements for the dialog."""
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_brand_panel())

        form = QWidget(self)
        form.setObjectName("LoginForm")
        form.setFixedWidth(self._form_width)
        root.addWidget(form)
        form_layout = QVBoxLayout(form)
        self._form_layout = form_layout
        form_layout.setContentsMargins(28, 28, 28, 24)
        form_layout.setSpacing(0)

        title_label = QLabel("Create Passwords" if self.is_setup else "Sign In")
        title_label.setObjectName("LoginTitleLabel")
        form_layout.addWidget(title_label)
        form_layout.addSpacing(3)

        subtitle_label = QLabel(
            "Set a main password and a secondary recovery password."
            if self.is_setup
            else "Enter your password to continue."
        )
        subtitle_label.setObjectName("LoginSubtitleLabel")
        subtitle_label.setWordWrap(True)
        form_layout.addWidget(subtitle_label)
        form_layout.addSpacing(16)

        if self.is_setup:
            self._build_setup_fields(form, form_layout)
        else:
            self._build_sign_in_fields(form_layout)

        self.show_passwords_checkbox = QCheckBox(
            "Show passwords" if self.is_setup else "Show password"
        )
        self.show_passwords_checkbox.setObjectName("LoginShowPasswords")
        visibility_row = QHBoxLayout()
        visibility_row.addWidget(self.show_passwords_checkbox)
        visibility_row.addStretch()
        self.caps_lock_label = QLabel("Caps Lock is on")
        self.caps_lock_label.setObjectName("LoginCapsLabel")
        visibility_row.addWidget(self.caps_lock_label)
        self.caps_lock_label.hide()
        self._caps_timer = QTimer(self)
        self._caps_timer.timeout.connect(self._update_caps_lock)
        self._caps_timer.start(250)
        form_layout.addSpacing(10)
        form_layout.addLayout(visibility_row)
        form_layout.addSpacing(6)

        # One reserved place for what is still missing or wrong. The fields
        # and buttons keep their position whether or not it has text.
        status_host = QWidget(form)
        status_layout = QVBoxLayout(status_host)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(0)
        if self.is_setup:
            self.progress_label = QLabel("")
            self.progress_label.setObjectName("LoginProgressLabel")
            self.progress_label.setWordWrap(True)
            status_layout.addWidget(self.progress_label)
        self.error_label = QLabel("")
        self.error_label.setObjectName("LoginErrorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        status_layout.addWidget(self.error_label)
        status_layout.addStretch(1)
        status_host.setMinimumHeight(
            self.fontMetrics().lineSpacing() * (2 if self.is_setup else 1) + 8
        )
        form_layout.addWidget(status_host)
        form_layout.addSpacing(8)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        self.ok_button = QPushButton(
            "Sign In" if not self.is_setup else "Create Passwords"
        )
        self.ok_button.setObjectName("LoginPrimaryButton")
        self.ok_button.setDefault(True)
        self.ok_button.setAutoDefault(True)
        if self.is_setup:
            self.ok_button.setToolTip(
                "Create passwords and initialize the application\nBoth passwords will be saved securely\nApplication will start after setup"
            )
        else:
            self.ok_button.setToolTip(
                "Login to the application\nKeyboard: Enter\nVerifies password and opens main window"
            )

        self.cancel_button = QPushButton("Exit")
        self.cancel_button.setObjectName("LoginSecondaryButton")
        self.cancel_button.setToolTip(
            "Exit without logging in\nApplication will close\nNo data will be accessed or modified"
        )

        button_layout.addStretch(1)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        form_layout.addLayout(button_layout)

        if not self.is_setup:
            forgot_link = QPushButton("Need help?")
            forgot_link.setObjectName("LoginForgotButton")
            forgot_link.setCursor(Qt.CursorShape.PointingHandCursor)
            forgot_link.setAccessibleName("Show password recovery options")
            forgot_link.setFlat(True)
            button_layout.insertWidget(0, forgot_link)

            self._danger_card = QFrame(form)
            self._danger_card.setObjectName("LoginDangerCard")
            self._danger_card.setVisible(False)
            danger_layout = QVBoxLayout(self._danger_card)
            danger_layout.setContentsMargins(16, 14, 16, 14)
            danger_layout.setSpacing(8)

            danger_title = QLabel("Trouble signing in?")
            danger_title.setObjectName("LoginDangerTitle")
            danger_layout.addWidget(danger_title)

            danger_body = QLabel(
                "Wipes all stored data and passwords. This cannot be undone."
            )
            danger_body.setObjectName("LoginDangerBody")
            danger_body.setWordWrap(True)
            danger_layout.addWidget(danger_body)

            danger_action_layout = QHBoxLayout()
            danger_action_layout.setSpacing(10)
            self.reset_button = QPushButton("Wipe All Data...")
            self.reset_button.setObjectName("LoginDangerButton")
            self.reset_button.setToolTip(
                "Permanently delete all application data and credentials\n"
                "Includes items, estimates, silver bars, and lists\n"
                "Requires typing DELETE to confirm"
            )
            danger_action_layout.addWidget(self.reset_button)
            danger_action_layout.addStretch()
            danger_layout.addLayout(danger_action_layout)
            form_layout.addSpacing(12)
            form_layout.addWidget(self._danger_card)

            forgot_link.clicked.connect(self._toggle_recovery_options)

    def _build_brand_panel(self) -> QFrame:
        panel = QFrame(self)
        panel.setObjectName("LoginBrandPanel")
        panel.setFixedWidth(BRAND_PANEL_WIDTH)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 24, 22, 24)
        layout.setSpacing(0)
        centered = Qt.AlignmentFlag.AlignHCenter
        layout.addStretch(1)

        icon_label = QLabel(panel)
        icon_label.setObjectName("LoginBrandIcon")
        icon_label.setFixedSize(BRAND_ICON_SIZE, BRAND_ICON_SIZE)
        icon_label.setAccessibleName(f"{APP_NAME} logo")
        pixmap = self._brand_pixmap()
        if pixmap is not None:
            icon_label.setPixmap(pixmap)
            icon_label.setScaledContents(True)
        layout.addWidget(icon_label, 0, centered)
        layout.addSpacing(18)

        name_label = QLabel(APP_NAME, panel)
        name_label.setObjectName("LoginBrandName")
        name_label.setWordWrap(True)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)
        layout.addSpacing(4)

        version_label = QLabel(f"Version {APP_VERSION}", panel)
        version_label.setObjectName("LoginBrandVersion")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)
        layout.addStretch(1)
        return panel

    def _brand_pixmap(self) -> QPixmap | None:
        with suppress(Exception):
            path = get_asset_path("assets", "icons", "silverestimate.ico")
            if path.exists():
                pixmap = QIcon(str(path)).pixmap(
                    QSize(BRAND_ICON_SIZE, BRAND_ICON_SIZE)
                )
                if not pixmap.isNull():
                    return pixmap
        return None

    def _password_field(
        self, label: str, placeholder: str, tooltip: str
    ) -> tuple[QLabel, QLineEdit]:
        label_widget = QLabel(label)
        label_widget.setObjectName("LoginFieldLabel")
        field = QLineEdit()
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setClearButtonEnabled(True)
        field.setPlaceholderText(placeholder)
        field.setToolTip(tooltip)
        field.setAccessibleName(label)
        label_widget.setBuddy(field)
        return label_widget, field

    def _build_sign_in_fields(self, form_layout: QVBoxLayout) -> None:
        self.password_label, self.password_input = self._password_field(
            "Password",
            "Enter your main password",
            "Enter your password to access the application\nPress Enter to login\nUse Reset button if password is forgotten",
        )
        form_layout.addWidget(self.password_label)
        form_layout.addSpacing(4)
        form_layout.addWidget(self.password_input)

    def _build_setup_fields(self, form: QWidget, form_layout: QVBoxLayout) -> None:
        """Main password on the left, recovery password on the right."""
        self.password_label, self.password_input = self._password_field(
            "Main Password",
            "Create a main password",
            "Enter your main password for database access\nChoose a strong, memorable password",
        )
        (
            self.confirm_main_password_label,
            self.confirm_main_password_input,
        ) = self._password_field(
            "Confirm Main Password",
            "Re-enter the main password",
            "Re-enter the main password exactly to prevent setup lockout",
        )
        self.backup_password_label, self.backup_password_input = self._password_field(
            "Recovery Password",
            "Create a recovery password",
            "Enter a different recovery password\nMust be different from main password\nUsed for emergency access and data management",
        )
        (
            self.confirm_password_label,
            self.confirm_password_input,
        ) = self._password_field(
            "Confirm Recovery Password",
            "Re-enter the recovery password",
            "Re-enter the recovery password to confirm\nMust match exactly\nEnsures password was typed correctly",
        )

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(4)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.addWidget(self.password_label, 0, 0)
        grid.addWidget(self.password_input, 1, 0)
        grid.addWidget(self.backup_password_label, 0, 1)
        grid.addWidget(self.backup_password_input, 1, 1)
        grid.setRowMinimumHeight(2, 8)
        grid.addWidget(self.confirm_main_password_label, 3, 0)
        grid.addWidget(self.confirm_main_password_input, 4, 0)
        grid.addWidget(self.confirm_password_label, 3, 1)
        grid.addWidget(self.confirm_password_input, 4, 1)
        form_layout.addLayout(grid)
        form_layout.addSpacing(14)

        self.password_requirements_label = QLabel(
            "Use two different passwords of at least 8 characters each. "
            "The main password opens the database; the recovery password "
            "is for emergency access. Store it safely."
        )
        self.password_requirements_label.setObjectName("LoginRequirementsLabel")
        self.password_requirements_label.setWordWrap(True)
        form_layout.addWidget(self.password_requirements_label)

        # Tab walks down each column in the order the passwords are typed.
        previous: QWidget = self.password_input
        for field in (
            self.confirm_main_password_input,
            self.backup_password_input,
            self.confirm_password_input,
        ):
            QWidget.setTabOrder(previous, field)
            previous = field

    def _fit_to_content(self) -> None:
        """Size the dialog to its content, never clipping wrapped text.

        The width is fixed by the design; the height is what the layout needs
        at that width, so a wrapped label always gets all of its lines.
        """
        layout = self.layout()
        if layout is None:
            return
        # Hiding a widget only queues the relayout; measure what is shown now.
        self._form_layout.invalidate()
        layout.invalidate()
        layout.activate()
        width = BRAND_PANEL_WIDTH + self._form_width
        height = (
            layout.totalHeightForWidth(width)
            if layout.hasHeightForWidth()
            else layout.sizeHint().height()
        )
        self.setFixedSize(width, height)

    def _toggle_recovery_options(self) -> None:
        self._danger_card.setVisible(not self._danger_card.isVisible())
        self._fit_to_content()

    def _update_caps_lock(self):
        import sys

        enabled = False
        if sys.platform == "win32":
            import ctypes

            enabled = bool(ctypes.windll.user32.GetKeyState(0x14) & 1)
        self.caps_lock_label.setVisible(enabled)

    def _connect_signals(self):
        """Connect UI signals to slots."""
        self.ok_button.clicked.connect(self._handle_ok)
        self.cancel_button.clicked.connect(self.reject)
        self.show_passwords_checkbox.toggled.connect(self._toggle_password_visibility)
        # Connect reset button if it exists
        if hasattr(self, "reset_button"):
            self.reset_button.clicked.connect(self._handle_reset_request)

        # Optionally connect returnPressed for convenience
        self.password_input.returnPressed.connect(self._handle_ok)
        for field in self._password_inputs():
            field.textChanged.connect(self._on_password_edited)
        self._update_setup_progress()
        if self.is_setup:
            self.confirm_main_password_input.returnPressed.connect(self._handle_ok)
            self.backup_password_input.returnPressed.connect(self._handle_ok)
            self.confirm_password_input.returnPressed.connect(self._handle_ok)

    def showEvent(self, event):
        super().showEvent(event)
        if self._startup_activation_pending:
            self._startup_activation_pending = False
            QTimer.singleShot(0, self._request_startup_foreground)
            QTimer.singleShot(150, self._request_startup_foreground)

    def _request_startup_foreground(self):
        """Raise the startup dialog so it does not open behind other windows."""
        if not self.isVisible():
            return

        self.showNormal()
        self.raise_()
        self.activateWindow()
        QApplication.alert(self, 0)
        self.password_input.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

        with suppress(Exception):
            bring_window_to_front(int(self.winId()))

    def _password_inputs(self) -> list[QLineEdit]:
        fields = [self.password_input]
        if self.is_setup:
            fields.extend(
                [
                    self.confirm_main_password_input,
                    self.backup_password_input,
                    self.confirm_password_input,
                ]
            )
        return fields

    def _toggle_password_visibility(self, checked):
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        for field in self._password_inputs():
            field.setEchoMode(mode)

    def _show_error(self, message: str, field: QLineEdit | None = None) -> None:
        """Say what to fix inside the dialog and put the cursor there."""
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        if self.is_setup:
            # It would only repeat the error in other words.
            self.progress_label.setVisible(False)
        if field is not None:
            field.setFocus()
            field.selectAll()

    def _on_password_edited(self, *_args) -> None:
        self.error_label.clear()
        self.error_label.setVisible(False)
        self._update_setup_progress()

    def _setup_error_field(self, message: str) -> QLineEdit | None:
        if not self.is_setup:
            return self.password_input
        if message.startswith("Main passwords do not match"):
            return self.confirm_main_password_input
        if message.startswith("Recovery passwords do not match"):
            return self.confirm_password_input
        if message.startswith(("Recovery", "Main and Recovery")):
            return self.backup_password_input
        return self.password_input

    def _update_setup_progress(self) -> None:
        """Show what is still missing while the passwords are typed."""
        if not self.is_setup:
            return
        pending = self._setup_validation_error(
            self.password_input.text(),
            self.confirm_main_password_input.text(),
            self.backup_password_input.text(),
            self.confirm_password_input.text(),
        )
        if not any(field.text() for field in self._password_inputs()):
            text, state = "", "idle"
        elif pending:
            text, state = f"Still needed: {pending}", "pending"
        else:
            text, state = "Both passwords are ready.", "ready"
        self.progress_label.setText(text)
        self.progress_label.setVisible(bool(text))
        if self.progress_label.property("state") != state:
            self.progress_label.setProperty("state", state)
            style = self.progress_label.style()
            style.unpolish(self.progress_label)
            style.polish(self.progress_label)

    def _setup_validation_error(
        self,
        password: str,
        confirm_main: str,
        backup_password: str,
        confirm_backup: str,
    ) -> str | None:
        error: str | None = None
        if len(password) < self.MIN_PASSWORD_LENGTH:
            error = (
                f"Main password must contain at least {self.MIN_PASSWORD_LENGTH} "
                "characters."
            )
        elif password != confirm_main:
            error = "Main passwords do not match."
        elif not backup_password:
            error = "Recovery password cannot be empty."
        elif len(backup_password) < self.MIN_PASSWORD_LENGTH:
            error = (
                f"Recovery password must contain at least {self.MIN_PASSWORD_LENGTH} "
                "characters."
            )
        elif password == backup_password:
            error = "Main and Recovery Passwords must be different."
        elif backup_password != confirm_backup:
            error = "Recovery passwords do not match."
        return error

    def _handle_ok(self):
        """Handle the OK/Login/Create button click."""
        # Ensure reset flag is false if OK is clicked
        self.reset_requested = False
        password = self.password_input.text()

        if not password:
            self._show_error(
                "Enter the main password." if self.is_setup else "Enter your password.",
                self.password_input,
            )
            return

        if self.is_setup:
            confirm_main = self.confirm_main_password_input.text()
            backup_password = self.backup_password_input.text()
            confirm_backup = self.confirm_password_input.text()
            validation_error = self._setup_validation_error(
                password,
                confirm_main,
                backup_password,
                confirm_backup,
            )
            if validation_error:
                self._show_error(
                    validation_error, self._setup_error_field(validation_error)
                )
                return

            # Store passwords internally for retrieval after accept()
            self._password = password
            self._backup_password = backup_password
            self.accept()  # Close dialog successfully

        else:  # Login mode
            # Store password for retrieval
            self._password = password
            # Verification happens outside the dialog in main.py's run_authentication
            self.accept()

    def get_password(self):
        """Return the entered main password."""
        return self._password

    def get_backup_password(self):
        """Return the entered secondary password (only valid in setup mode)."""
        if self.is_setup:
            return self._backup_password
        return None

    def was_reset_requested(self):
        """Check if the reset button was clicked and confirmed."""
        return self.reset_requested

    def _handle_reset_request(self):
        """Handle the Reset / Wipe All Data button click."""
        if confirm_destructive(
            self,
            title="Wipe All Data",
            heading="Wipe all data and passwords?",
            detail=(
                "Items, estimates, silver bars, lists and both passwords will "
                "be removed. This cannot be undone."
            ),
            action_label="Wipe All Data",
        ):
            # The button stays off until the word is typed, so there is no
            # wrong answer to explain afterwards.
            if not confirm_by_typing(
                self,
                title="Wipe All Data",
                heading="Type DELETE to wipe all data",
                detail="This is the last step. It cannot be undone.",
                action_label="Wipe All Data",
            ):
                self.reset_requested = False
                return
            self.reset_requested = True
            self.accept()  # Close the dialog, main logic will check the flag
