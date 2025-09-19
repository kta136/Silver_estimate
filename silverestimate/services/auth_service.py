"""Authentication and data-wipe services for SilverEstimate."""
from __future__ import annotations

import logging
import os
from typing import Optional

from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QMessageBox, QDialog

from app_constants import SETTINGS_APP, SETTINGS_ORG, DB_PATH
from login_dialog import LoginDialog


def run_authentication(logger: Optional[logging.Logger] = None) -> Optional[str]:
    """Handle authentication flow using the LoginDialog."""
    logger = logger or logging.getLogger(__name__)
    logger.info("Starting authentication process")

    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    password_hash = settings.value("security/password_hash")
    backup_hash = settings.value("security/backup_hash")

    if password_hash and backup_hash:
        logger.debug("Found existing password hashes, showing login dialog")
        login_dialog = LoginDialog(is_setup=False)
        result = login_dialog.exec_()

        if result == QDialog.Accepted:
            if login_dialog.was_reset_requested():
                logger.warning("Data wipe requested via reset button")
                return "wipe"

            entered_password = login_dialog.get_password()
            if LoginDialog.verify_password(password_hash, entered_password):
                logger.info("Authentication successful")
                return entered_password
            if LoginDialog.verify_password(backup_hash, entered_password):
                logger.warning("Secondary password used - triggering data wipe")
                return "wipe"
            logger.warning("Authentication failed: incorrect password")
            QMessageBox.warning(None, "Login Failed", "Incorrect password.")
            return None
        logger.info("Login cancelled by user")
        return None

    logger.info("Password hashes not found in settings. Starting first-time setup.")
    setup_dialog = LoginDialog(is_setup=True)
    result = setup_dialog.exec_()
    if result == QDialog.Accepted:
        logger.info("First-time setup completed")
        password = setup_dialog.get_password()
        backup_password = setup_dialog.get_backup_password()
        hashed_password = LoginDialog.hash_password(password)
        hashed_backup = LoginDialog.hash_password(backup_password)
        if not hashed_password or not hashed_backup:
            logger.error("Failed to hash passwords during setup")
            QMessageBox.critical(None, "Setup Error", "Failed to hash passwords.")
            return None
        settings.setValue("security/password_hash", hashed_password)
        settings.setValue("security/backup_hash", hashed_backup)
        settings.sync()
        logger.info("Passwords created and stored successfully")
        QMessageBox.information(None, "Setup Complete", "Passwords created successfully.")
        return password
    logger.info("Setup cancelled by user")
    return None


def perform_data_wipe(
    db_path: str = DB_PATH, logger: Optional[logging.Logger] = None
) -> bool:
    """Delete encrypted DB and clear credentials from settings."""
    logger = logger or logging.getLogger(__name__)
    logger.warning("Initiating data wipe for encrypted database: %s", db_path)
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
            logger.info("Successfully deleted encrypted database file: %s", db_path)
        else:
            logger.warning("Encrypted database file not found (already deleted?): %s", db_path)

        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        temp_path = settings.value("security/last_temp_db_path")
        if isinstance(temp_path, str) and temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.info("Removed temporary plaintext DB: %s", temp_path)
            except OSError as exc:
                logger.warning("Could not remove temporary plaintext DB: %s", exc)

        for key in (
            "security/password_hash",
            "security/backup_hash",
            "security/db_salt",
            "security/last_temp_db_path",
        ):
            settings.remove(key)
        settings.sync()
        logger.info("Cleared password hashes and database salt from application settings.")
        return True
    except Exception as exc:
        error_message = f"A critical error occurred during data wipe: {exc}"
        logger.critical(error_message, exc_info=True)
        QMessageBox.critical(None, "Data Wipe Error", error_message)
        return False
