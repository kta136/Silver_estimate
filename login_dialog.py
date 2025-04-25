import sys
# import bcrypt # No longer needed
from passlib.context import CryptContext # Import CryptContext
from passlib.exc import UnknownHashError, PasslibSecurityWarning # Import specific exceptions
import warnings # To potentially filter passlib warnings if needed

from PyQt5.QtWidgets import (QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
                             QMessageBox, QApplication, QFormLayout)
from PyQt5.QtCore import Qt, QSettings

# Configure passlib context for Argon2 (recommended)
# Schemes='default' will use the first scheme listed (argon2) for hashing.
# Deprecated='auto' will allow verification of older hashes if needed in the future.
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

# Optional: Filter specific passlib warnings if they become noisy during development/packaging
# warnings.filterwarnings("ignore", category=PasslibSecurityWarning)

class LoginDialog(QDialog):
    """
    Dialog for user authentication (login) and initial password setup.
    """
    def __init__(self, is_setup=False, parent=None):
        super().__init__(parent)
        self.is_setup = is_setup
        self.setWindowTitle("Authentication Required" if not is_setup else "Create Passwords")
        self.setModal(True) # Ensure user interacts with this dialog first

        self._password = ""
        self._backup_password = "" # Only used in setup mode
        self.reset_requested = False # Add flag to track reset request

        self._setup_ui()
        self._connect_signals()

        # Prevent closing via the 'X' button if desired, force use of buttons
        # self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

    def _setup_ui(self):
        """Create the UI elements for the dialog."""
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.password_label = QLabel("Password:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow(self.password_label, self.password_input)

        if self.is_setup:
            # Renamed label to be less descriptive of function
            self.backup_password_label = QLabel("Secondary Password:")
            self.backup_password_input = QLineEdit()
            self.backup_password_input.setEchoMode(QLineEdit.Password)
            form_layout.addRow(self.backup_password_label, self.backup_password_input)

            # Renamed label
            self.confirm_password_label = QLabel("Confirm Secondary Password:")
            self.confirm_password_input = QLineEdit()
            self.confirm_password_input.setEchoMode(QLineEdit.Password)
            form_layout.addRow(self.confirm_password_label, self.confirm_password_input)

            # Removed the informational label explaining the wipe function
            # self.info_label = QLabel(...)
            # layout.addWidget(self.info_label)

        layout.addLayout(form_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("Login" if not self.is_setup else "Create Passwords")
        self.cancel_button = QPushButton("Cancel")

        button_layout.addStretch()
        # Add Reset button only in login mode
        if not self.is_setup:
            self.reset_button = QPushButton("Reset / Wipe All Data")
            self.reset_button.setStyleSheet("color: red;") # Make it stand out
            button_layout.addWidget(self.reset_button)
            button_layout.addSpacing(20) # Add some space

        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        layout.addLayout(button_layout)

        self.setMinimumWidth(400 if not self.is_setup else 350) # Wider if reset button is present

    def _connect_signals(self):
        """Connect UI signals to slots."""
        self.ok_button.clicked.connect(self._handle_ok)
        self.cancel_button.clicked.connect(self.reject)
        # Connect reset button if it exists
        if hasattr(self, 'reset_button'):
            self.reset_button.clicked.connect(self._handle_reset_request)

        # Optionally connect returnPressed for convenience
        self.password_input.returnPressed.connect(self._handle_ok)
        if self.is_setup:
            self.backup_password_input.returnPressed.connect(self._handle_ok)
            self.confirm_password_input.returnPressed.connect(self._handle_ok)


    def _handle_ok(self):
        """Handle the OK/Login/Create button click."""
        # Ensure reset flag is false if OK is clicked
        self.reset_requested = False
        password = self.password_input.text()

        if not password:
            QMessageBox.warning(self, "Input Error", "Password cannot be empty.")
            return

        if self.is_setup:
            backup_password = self.backup_password_input.text()
            confirm_backup = self.confirm_password_input.text()

            if not backup_password:
                QMessageBox.warning(self, "Input Error", "Backup password cannot be empty.")
                return
            if password == backup_password:
                 # Updated error message
                 QMessageBox.warning(self, "Input Error", "Main and Secondary Passwords must be different.")
                 return
            if backup_password != confirm_backup:
                 # Updated error message
                QMessageBox.warning(self, "Input Error", "Secondary passwords do not match.")
                return

            # Store passwords internally for retrieval after accept()
            self._password = password
            self._backup_password = backup_password
            self.accept() # Close dialog successfully

        else: # Login mode
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
            "Confirm Data Wipe",
            "Are you absolutely sure you want to reset?\n\n"
            "This will permanently delete ALL application data (items, estimates, lists, etc.) "
            "and password settings.\n\n"
            "THIS ACTION CANNOT BE UNDONE.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel
        )

        if reply == QMessageBox.Yes:
            self.reset_requested = True
            self.accept() # Close the dialog, main logic will check the flag


    # --- Static methods for hashing and verification ---

    @staticmethod
    def hash_password(password):
        """Hashes a password using the configured passlib context (Argon2)."""
        if not password:
            return None
        try:
            # Passlib handles encoding and salt generation automatically
            hashed = pwd_context.hash(password)
            return hashed
        except Exception as e:
            print(f"Error hashing password: {e}")
            return None

    @staticmethod
    def verify_password(stored_hash, provided_password):
        """Verifies a provided password against a stored hash using passlib."""
        if not stored_hash or not provided_password:
            return False
        try:
            # pwd_context.verify handles identifying the hash type (e.g., argon2, bcrypt)
            # and performs the comparison.
            return pwd_context.verify(provided_password, stored_hash)
        except UnknownHashError:
            print(f"Warning: Unknown hash format encountered: {stored_hash[:10]}...")
            return False
        except ValueError as ve: # Catches potential issues like malformed hash string
             print(f"Warning: Error comparing password hash (invalid format?): {ve}")
             return False
        except Exception as e:
            print(f"Error verifying password: {e}")
            return False


# Example usage (for testing)
if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Simulate first run
    print("Testing Setup Mode:")
    setup_dialog = LoginDialog(is_setup=True)
    if setup_dialog.exec_() == QDialog.Accepted:
        pw = setup_dialog.get_password()
        bpw = setup_dialog.get_backup_password() # Method name kept for internal consistency
        print(f"Setup Accepted! Password: {pw}, Secondary Password: {bpw}") # Updated print statement
        # In real app, hash and save these
        hashed_pw = LoginDialog.hash_password(pw)
        hashed_bpw = LoginDialog.hash_password(bpw)
        print(f"Hashed PW: {hashed_pw}")
        print(f"Hashed BPW: {hashed_bpw}")

        # Simulate storing hashes (using QSettings for example)
        settings = QSettings("YourCompany", "SilverEstimateApp_Test")
        settings.setValue("security/password_hash", hashed_pw)
        settings.setValue("security/backup_hash", hashed_bpw)
        settings.sync()

    else:
        print("Setup Cancelled.")

    print("\nTesting Login Mode:")
    # Simulate subsequent run - load stored hashes
    settings = QSettings("YourCompany", "SilverEstimateApp_Test")
    stored_pw_hash = settings.value("security/password_hash")
    stored_bpw_hash = settings.value("security/backup_hash")

    if stored_pw_hash and stored_bpw_hash:
        login_dialog = LoginDialog(is_setup=False)
        if login_dialog.exec_() == QDialog.Accepted:
            # Check if reset was requested first
            if login_dialog.was_reset_requested():
                print("Result: Reset Requested")
                # In real app, trigger perform_data_wipe() here
            else:
                entered_pw = login_dialog.get_password()
                print(f"Login Accepted! Entered Password: {entered_pw}")

                # Verify against stored hashes
                is_valid_pw = LoginDialog.verify_password(stored_pw_hash, entered_pw)
                is_backup_pw = LoginDialog.verify_password(stored_bpw_hash, entered_pw)

                if is_valid_pw:
                    print("Result: Correct Main Password")
                elif is_backup_pw:
                    # Updated print statement for testing clarity
                    print("Result: Correct Secondary Password (Triggers Wipe)")
                else:
                    print("Result: Incorrect Password")
        else:
            print("Login Cancelled.")
    else:
        print("No stored passwords found for login test.")

    # Clean up test settings
    settings.clear()

    sys.exit(0)