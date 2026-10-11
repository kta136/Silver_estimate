#!/usr/bin/env python
import logging
import logging.handlers
import os
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QtMsgType

from silverestimate.infrastructure.paths import get_runtime_root
from silverestimate.infrastructure.settings import SettingsKey, get_app_settings

# Daily files kept per log when automatic deletion is off, so logs stay bounded.
DEFAULT_BACKUP_DAYS = 30


def _read_error_logging_enabled(settings):
    return settings.get_bool(
        SettingsKey.LOGGING_ENABLE_CRITICAL,
        True,
    )


def setup_logging(
    app_name="silver_app",
    log_dir="logs",
    debug_mode=False,
    enable_info=True,
    enable_error=True,
    enable_debug=True,
    backup_days=DEFAULT_BACKUP_DAYS,
):
    """
    Configure the logging system for the Silver Estimation App.

    Args:
        app_name (str): Base name for log files
        log_dir (str): Directory to store log files
        debug_mode (bool): Whether to enable debug logging
        enable_info (bool): Whether to enable INFO level logs
        enable_error (bool): Whether to enable ERROR and CRITICAL level logs
        enable_debug (bool): Whether to enable DEBUG level logs (only when debug_mode is True)
        backup_days (int): Daily log files kept after each midnight rollover

    Returns:
        logging.Logger: Configured root logger
    """
    # Create log directory if it doesn't exist
    log_path = Path(log_dir)
    archived_path = log_path / "archived"
    log_path.mkdir(parents=True, exist_ok=True)
    archived_path.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)

    # Clear any existing handlers, releasing their files so they can roll over
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()

    # Common log format
    log_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(module)s:%(lineno)d] [%(funcName)s] %(message)s"
    )

    # Main log file (INFO and above) - only if enabled
    if enable_info:
        main_handler = logging.handlers.TimedRotatingFileHandler(
            log_path / f"{app_name}.log",
            when="midnight",
            backupCount=backup_days,
            encoding="utf-8",
        )
        main_handler.setLevel(logging.INFO)
        main_handler.setFormatter(log_format)
        root_logger.addHandler(main_handler)

    # Error log file (ERROR and CRITICAL only) - only if enabled
    if enable_error:
        error_handler = logging.handlers.TimedRotatingFileHandler(
            log_path / f"{app_name}_error.log",
            when="midnight",
            backupCount=backup_days,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(log_format)
        root_logger.addHandler(error_handler)

    # Debug log file (all levels, only when debug_mode is True and enabled)
    if debug_mode and enable_debug:
        debug_handler = logging.handlers.TimedRotatingFileHandler(
            log_path / f"{app_name}_debug.log",
            when="midnight",
            backupCount=backup_days,
            encoding="utf-8",
        )
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(log_format)
        root_logger.addHandler(debug_handler)

    # Console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.WARNING)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)

    # Log startup information
    root_logger.info(f"Logging initialized at {datetime.now().isoformat()}")
    if debug_mode:
        root_logger.info("Debug logging enabled")

    return root_logger


def qt_message_handler(mode, context, message):
    """
    Handle Qt debug/warning/critical messages and redirect to Python logging.

    Args:
        mode: QtMsgType enum value
        context: QMessageLogContext object
        message: The message text
    """
    logger = logging.getLogger("qt")

    # Reduce noise for benign, frequent Qt messages
    msg_lower = (message or "").lower()
    if "edit: editing failed" in msg_lower:
        # Happens when an edit is requested on a non-editable item
        logging.getLogger("qt").debug(message)
        return

    if mode == QtMsgType.QtDebugMsg:
        logger.debug(message)
    elif mode == QtMsgType.QtInfoMsg:
        logger.info(message)
    elif mode == QtMsgType.QtWarningMsg:
        logger.warning(message)
    elif mode == QtMsgType.QtCriticalMsg:
        logger.error(message)
    elif mode == QtMsgType.QtFatalMsg:
        logger.critical(message)


def cleanup_old_logs(log_dir="logs", max_age_days=1):
    """
    Remove log files older than max_age_days.

    Args:
        log_dir (str): Directory containing log files
        max_age_days (int): Maximum age of log files in days

    Returns:
        int: Number of files removed
    """
    logger = logging.getLogger(__name__)
    logger.debug(
        f"Starting log cleanup for files older than {max_age_days} days in {log_dir}"
    )

    # Validate parameters
    if max_age_days < 1:
        logger.warning(
            f"Invalid max_age_days value ({max_age_days}), using default of 1 day"
        )
        max_age_days = 1

    log_path = Path(log_dir)
    if not log_path.exists():
        logger.warning(f"Log directory {log_dir} does not exist, nothing to clean up")
        return 0

    cutoff = datetime.now() - timedelta(days=max_age_days)
    removed_count = 0
    # Windows cannot delete a file the running handlers still hold open.
    active_files = {
        Path(handler.baseFilename).resolve()
        for handler in logging.getLogger().handlers
        if isinstance(handler, logging.FileHandler)
    }

    # Process all log files in the main directory
    for file_path in log_path.glob("*.log*"):
        if file_path.is_file() and file_path.resolve() not in active_files:
            file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
            if file_time < cutoff:
                try:
                    file_path.unlink()
                    removed_count += 1
                    logger.debug(f"Removed old log file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove old log file {file_path}: {e}")

    # Process all log files in the archived directory
    archived_path = log_path / "archived"
    if archived_path.exists():
        for file_path in archived_path.glob("*.log*"):
            if file_path.is_file():
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_time < cutoff:
                    try:
                        file_path.unlink()
                        removed_count += 1
                        logger.debug(f"Removed old archived log file: {file_path}")
                    except Exception as e:
                        logger.warning(
                            f"Failed to remove old archived log file {file_path}: {e}"
                        )

    logger.info(
        f"Log cleanup completed: removed {removed_count} files older than {max_age_days} days"
    )
    return removed_count


def get_log_config():
    """
    Get logging configuration from environment variables or settings.

    Returns:
        dict: Dictionary containing all logging configuration settings
    """
    settings = get_app_settings()

    # Environment variables take precedence
    debug_mode = os.environ.get("SILVER_APP_DEBUG", "").lower() in ("true", "1", "yes")
    if "SILVER_APP_DEBUG" not in os.environ:
        debug_mode = settings.get_bool(
            SettingsKey.LOGGING_DEBUG_MODE,
            False,
        )

    log_dir = os.environ.get("SILVER_APP_LOG_DIR") or str(get_runtime_root() / "logs")

    enable_info = settings.get_bool(
        SettingsKey.LOGGING_ENABLE_INFO,
        True,
    )
    enable_error = _read_error_logging_enabled(settings)
    enable_debug = settings.get_bool(
        SettingsKey.LOGGING_ENABLE_DEBUG,
        True,
    )

    # Get auto-cleanup settings
    auto_cleanup = settings.get_bool(
        SettingsKey.LOGGING_AUTO_CLEANUP,
        False,
    )
    cleanup_days = settings.get_int(
        SettingsKey.LOGGING_CLEANUP_DAYS,
        1,
        minimum=1,
        maximum=365,
    )

    return {
        "debug_mode": debug_mode,
        "log_dir": log_dir,
        "enable_info": enable_info,
        "enable_error": enable_error,
        "enable_debug": enable_debug,
        "auto_cleanup": auto_cleanup,
        "cleanup_days": cleanup_days,
    }


def backup_days_for(config):
    """Return how many daily log files the handlers keep for ``config``."""
    if config.get("auto_cleanup"):
        return config["cleanup_days"]
    return DEFAULT_BACKUP_DAYS


def reconfigure_logging():
    """
    Reconfigure the logging system based on current settings.
    Call this when settings are changed.

    Returns:
        logging.Logger: Configured root logger
    """
    config = get_log_config()

    # Re-initialize logging with new settings
    root_logger = setup_logging(
        debug_mode=config["debug_mode"],
        log_dir=config["log_dir"],
        enable_info=config["enable_info"],
        enable_error=config["enable_error"],
        enable_debug=config["enable_debug"],
        backup_days=backup_days_for(config),
    )

    # Log the reconfiguration
    root_logger.info("Logging system reconfigured with new settings")
    root_logger.debug(f"New logging configuration: {config}")

    return root_logger
