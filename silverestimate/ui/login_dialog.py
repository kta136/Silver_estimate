import logging
from contextlib import suppress

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from silverestimate.infrastructure.windows_integration import bring_window_to_front

from .shared_screen_theme import build_management_screen_stylesheet
from .window_sizing import resize_to_available_screen

_pwd_context = None


def _get_pwd_context():
    global _pwd_context
    if _pwd_context is None:
        from passlib.context import CryptContext

        _pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
    return _pwd_context


def warm_password_context() -> None:
    """Load the verifier while the authentication dialog is idle."""

    try:
        _get_pwd_context()
    except Exception:
        logging.getLogger(__name__).debug(
            "Password verifier warm-up failed", exc_info=True
        )


# Optional: Filter specific passlib warnings if they become noisy during development/packaging


class LoginDialog(QDialog):
    """
    Dialog for user authentication (login) and initial password setup.
    """

    MIN_PASSWORD_LENGTH = 8

    def __init__(self, is_setup=False, parent=None):
        super().__init__(parent)
        self.is_setup = is_setup
        self.setWindowTitle("Sign In" if not is_setup else "Create Passwords")
        self.setModal(True)  # Ensure user interacts with this dialog first
        self.setObjectName("LoginDialog")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setMinimumWidth(420 if not self.is_setup else 440)
        self.setStyleSheet(
            build_management_screen_stylesheet(
                root_selector="QDialog#LoginDialog",
                card_names=["LoginPanelFrame", "LoginDangerCard"],
                title_label="LoginTitleLabel",
                subtitle_label="LoginSubtitleLabel",
                field_label="LoginFieldLabel",
                primary_button="LoginPrimaryButton",
                secondary_button="LoginSecondaryButton",
                danger_button="LoginDangerButton",
                input_selectors=["QLineEdit"],
                extra_rules="""
                QFrame#LoginPanelFrame {
                    background-color: __SURFACE_BG__;
                    border: 1px solid __CARD_BORDER__;
                    border-radius: 18px;
                }
                QLabel#LoginSubtitleLabel {
                    font-size: 9pt;
                }
                QLabel#LoginHelpLabel {
                    color: __TEXT_MUTED__;
                    font-size: 9pt;
                }
                QLabel#LoginRequirementsLabel {
                    background-color: __HEADER_BG__;
                    border: 1px solid __CARD_BORDER_SOFT__;
                    border-radius: 8px;
                    color: __FIELD_TEXT__;
                    font-size: 9pt;
                    padding: 7px 9px;
                }
                QCheckBox#LoginShowPasswords {
                    color: __FIELD_TEXT__;
                    font-size: 8.6pt;
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
                    font-size: 9pt;
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
                    font-size: 8.9pt;
                    font-weight: 700;
                }
                QLabel#LoginDangerBody {
                    color: #7f1d1d;
                    font-size: 8.3pt;
                }
                QFrame#LoginDangerCard {
                    background-color: __DANGER_BG__;
                    border: 1px solid __DANGER_BORDER__;
                    border-radius: 12px;
                }
                """,
            )
        )

        self._password = str()
        self._backup_password = str()  # Only used in setup mode
        self.reset_requested = False  # Add flag to track reset request
        self._startup_activation_pending = True

        self._setup_ui()
        resize_to_available_screen(
            self,
            preferred_width=500 if self.is_setup else 460,
            preferred_height=self.sizeHint().height() + 36,
        )
        self._connect_signals()

        # Prevent closing via the 'X' button if desired, force use of buttons

    def schedule_password_context_warmup(self) -> None:
        """Warm Passlib on the next event-loop turn, after the dialog appears."""

        QTimer.singleShot(0, warm_password_context)

    def _setup_ui(self):
        """Create the UI elements for the dialog."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(0)

        panel = QFrame(self)
        panel.setObjectName("LoginPanelFrame")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 20, 20, 20)
        panel_layout.setSpacing(12)
        layout.addWidget(panel)

        title_label = QLabel("Create Passwords" if self.is_setup else "Sign In")
        title_label.setObjectName("LoginTitleLabel")
        panel_layout.addWidget(title_label)

        subtitle_label = QLabel(
            "Set a main password and a secondary recovery password."
            if self.is_setup
            else "Enter your password to continue."
        )
        subtitle_label.setObjectName("LoginSubtitleLabel")
        subtitle_label.setWordWrap(True)
        panel_layout.addWidget(subtitle_label)

        self.password_label = QLabel("Password:")
        self.password_label.setObjectName("LoginFieldLabel")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setClearButtonEnabled(True)
        self.password_input.setPlaceholderText(
            "Enter your main password"
            if not self.is_setup
            else "Create a strong main password"
        )
        if self.is_setup:
            self.password_input.setToolTip(
                "Enter your main password for database access\nThis password encrypts your data\nChoose a strong, memorable password"
            )
        else:
            self.password_input.setToolTip(
                "Enter your password to access the application\nPress Enter to login\nUse Reset button if password is forgotten"
            )
        panel_layout.addWidget(self.password_label)
        panel_layout.addWidget(self.password_input)

        if self.is_setup:
            self.confirm_main_password_label = QLabel("Confirm Main Password:")
            self.confirm_main_password_label.setObjectName("LoginFieldLabel")
            self.confirm_main_password_input = QLineEdit()
            self.confirm_main_password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.confirm_main_password_input.setClearButtonEnabled(True)
            self.confirm_main_password_input.setPlaceholderText(
                "Re-enter the main password"
            )
            self.confirm_main_password_input.setToolTip(
                "Re-enter the main password exactly to prevent setup lockout"
            )
            panel_layout.addWidget(self.confirm_main_password_label)
            panel_layout.addWidget(self.confirm_main_password_input)

            self.password_requirements_label = QLabel(
                "Use at least 8 characters for each password. Keep the two "
                "passwords different and store the recovery password safely."
            )
            self.password_requirements_label.setObjectName("LoginRequirementsLabel")
            self.password_requirements_label.setWordWrap(True)
            panel_layout.addWidget(self.password_requirements_label)

            self.password_help_label = QLabel(
                "Use two different passwords. The main password opens the database; "
                "the recovery password is for emergency access."
            )
            self.password_help_label.setObjectName("LoginHelpLabel")
            self.password_help_label.setWordWrap(True)
            panel_layout.addWidget(self.password_help_label)

            self.backup_password_label = QLabel("Recovery Password:")
            self.backup_password_label.setObjectName("LoginFieldLabel")
            self.backup_password_input = QLineEdit()
            self.backup_password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.backup_password_input.setClearButtonEnabled(True)
            self.backup_password_input.setPlaceholderText("Create a recovery password")
            self.backup_password_input.setToolTip(
                "Enter a different recovery password\nMust be different from main password\nUsed for emergency access and data management"
            )
            panel_layout.addWidget(self.backup_password_label)
            panel_layout.addWidget(self.backup_password_input)

            self.confirm_password_label = QLabel("Confirm Recovery Password:")
            self.confirm_password_label.setObjectName("LoginFieldLabel")
            self.confirm_password_input = QLineEdit()
            self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.confirm_password_input.setClearButtonEnabled(True)
            self.confirm_password_input.setPlaceholderText(
                "Re-enter the recovery password"
            )
            self.confirm_password_input.setToolTip(
                "Re-enter the recovery password to confirm\nMust match exactly\nEnsures password was typed correctly"
            )
            panel_layout.addWidget(self.confirm_password_label)
            panel_layout.addWidget(self.confirm_password_input)

        self.show_passwords_checkbox = QCheckBox(
            "Show passwords" if self.is_setup else "Show password"
        )
        self.show_passwords_checkbox.setObjectName("LoginShowPasswords")
        panel_layout.addWidget(self.show_passwords_checkbox)

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

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("LoginSecondaryButton")
        self.cancel_button.setToolTip(
            "Exit without logging in\nApplication will close\nNo data will be accessed or modified"
        )

        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        panel_layout.addLayout(button_layout)

        if not self.is_setup:
            forgot_link = QPushButton("Forgot password?")
            forgot_link.setObjectName("LoginForgotButton")
            forgot_link.setCursor(Qt.CursorShape.PointingHandCursor)
            forgot_link.setAccessibleName("Show password recovery options")
            forgot_link.setFlat(True)
            panel_layout.addWidget(forgot_link)

            danger_card = QFrame(panel)
            danger_card.setObjectName("LoginDangerCard")
            danger_card.setVisible(False)
            danger_layout = QVBoxLayout(danger_card)
            danger_layout.setContentsMargins(18, 16, 18, 16)
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
            panel_layout.addWidget(danger_card)

            forgot_link.clicked.connect(
                lambda: danger_card.setVisible(not danger_card.isVisible())
            )

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

    def _toggle_password_visibility(self, checked):
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        fields = [self.password_input]
        if self.is_setup:
            fields.extend(
                [
                    self.confirm_main_password_input,
                    self.backup_password_input,
                    self.confirm_password_input,
                ]
            )
        for field in fields:
            field.setEchoMode(mode)

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
            QMessageBox.warning(self, "Input Error", "Password cannot be empty.")
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
                QMessageBox.warning(self, "Input Error", validation_error)
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
        reply = QMessageBox.warning(
            self,
            "Confirm Full Data Wipe",
            "This will permanently delete ALL application data and credentials.\n"
            "Items, estimates, silver bars, lists, and passwords will be removed.\n\n"
            "THIS ACTION CANNOT BE UNDONE.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Yes:
            typed, ok = QInputDialog.getText(
                self,
                "Type DELETE to Confirm",
                "Type DELETE to perform an irreversible full data wipe:",
            )
            if not ok or typed.strip().upper() != "DELETE":
                QMessageBox.information(
                    self,
                    "Wipe Cancelled",
                    "Confirmation text did not match. No data was deleted.",
                )
                self.reset_requested = False
                return
            self.reset_requested = True
            self.accept()  # Close the dialog, main logic will check the flag

    # --- Static methods for hashing and verification ---

    @staticmethod
    def hash_password(password):
        """Hashes a password using the configured passlib context (Argon2)."""
        if not password:
            return None
        try:
            # Passlib handles encoding and salt generation automatically
            hashed = _get_pwd_context().hash(password)
            return hashed
        except Exception:
            logging.getLogger(__name__).error("Error hashing password:", exc_info=True)
            return None

    @staticmethod
    def verify_password(stored_hash, provided_password):
        """Verifies a provided password against a stored hash using passlib."""
        if not stored_hash or not provided_password:
            return False
        try:
            # pwd_context.verify handles hash validation and comparison.
            return _get_pwd_context().verify(provided_password, stored_hash)
        except ValueError:  # Catches potential issues like malformed hash string
            logging.getLogger(__name__).warning(
                "Error comparing password hash (invalid format?)", exc_info=True
            )
            return False
        except Exception as exc:
            try:
                from passlib.exc import UnknownHashError

                is_unknown = isinstance(exc, UnknownHashError)
            except Exception:
                is_unknown = False
            if is_unknown:
                logging.getLogger(__name__).warning(
                    f"Unknown hash format encountered: {stored_hash[:10]}..."
                )
                return False
            logging.getLogger(__name__).error(
                "Error verifying password:", exc_info=True
            )
            return False
