#!/usr/bin/env python
import logging
import logging.handlers
import os
from datetime import datetime, timedelta
from pathlib import Path
from PyQt5.QtCore import QtMsgType
import PyQt5.QtCore as QtCore

from silverestimate.infrastructure.settings import get_app_settings

# Global variable to store the cleanup scheduler instance
_cleanup_scheduler = None

def setup_logging(app_name="silver_app", log_dir="logs", debug_mode=False,
                  enable_info=True, enable_error=True, enable_debug=True):
    """
    Configure the logging system for the Silver Estimation App.
    
    Args:
        app_name (str): Base name for log files
        log_dir (str): Directory to store log files
        debug_mode (bool): Whether to enable debug logging
        enable_info (bool): Whether to enable INFO level logs
        enable_error (bool): Whether to enable ERROR and CRITICAL level logs
        enable_debug (bool): Whether to enable DEBUG level logs (only when debug_mode is True)
    
    Returns:
        logging.Logger: Configured root logger
    """
    # Create log directory if it doesn't exist
    log_path = Path(log_dir)
    archived_path = log_path / "archived"
    log_path.mkdir(exist_ok=True)
    archived_path.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Common log format
    log_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(module)s:%(lineno)d] [%(funcName)s] %(message)s'
    )
    
    # Main log file (INFO and above) - only if enabled
    if enable_info:
        main_handler = logging.handlers.RotatingFileHandler(
            log_path / f"{app_name}.log",
            maxBytes=5*1024*1024,  # 5MB
            backupCount=10,
            encoding='utf-8'
        )
        main_handler.setLevel(logging.INFO)
        main_handler.setFormatter(log_format)
        root_logger.addHandler(main_handler)
    
    # Error log file (ERROR and CRITICAL only) - only if enabled
    if enable_error:
        error_handler = logging.handlers.RotatingFileHandler(
            log_path / f"{app_name}_error.log",
            maxBytes=5*1024*1024,  # 5MB
            backupCount=10,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(log_format)
        root_logger.addHandler(error_handler)
    
    # Debug log file (all levels, only when debug_mode is True and enabled)
    if debug_mode and enable_debug:
        debug_handler = logging.handlers.RotatingFileHandler(
            log_path / f"{app_name}_debug.log",
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
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
    logger = logging.getLogger('qt')
    
    # Reduce noise for benign, frequent Qt messages
    msg_lower = (message or "").lower()
    if "edit: editing failed" in msg_lower:
        # Happens when an edit is requested on a non-editable item
        logging.getLogger('qt').debug(message)
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

class LoggingStatusBar:
    """Status bar that logs messages in addition to displaying them."""
    
    def __init__(self, status_bar, logger=None):
        self.status_bar = status_bar
        self.logger = logger or logging.getLogger()
    
    def show_message(self, message, timeout=0):
        """Show message in status bar and log at DEBUG level to reduce noise."""
        self.logger.debug(f"Status: {message}")
        self.status_bar.showMessage(message, timeout)

class DatabaseOperation:
    """Context manager for database operations with proper logging and error handling."""
    
    def __init__(self, db_manager, operation_name, logger=None):
        self.db_manager = db_manager
        self.operation_name = operation_name
        self.logger = logger or logging.getLogger()
        self.success = False
    
    def __enter__(self):
        self.logger.debug(f"Starting database operation: {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.logger.debug(f"Completed database operation: {self.operation_name}")
            self.success = True
            return True
        
        import sqlite3
        if issubclass(exc_type, sqlite3.Error):
            self.logger.error(f"Database error during {self.operation_name}: {str(exc_val)}", exc_info=True)
        elif issubclass(exc_type, ValueError):
            self.logger.warning(f"Value error during {self.operation_name}: {str(exc_val)}", exc_info=True)
        else:
            self.logger.error(f"Unexpected error during {self.operation_name}: {str(exc_val)}", exc_info=True)
        
        # Don't suppress the exception
        return False

def sanitize_for_logging(data, sensitive_keys=None):
    """
    Sanitize potentially sensitive data for logging.
    
    Args:
        data: Dictionary containing data to sanitize
        sensitive_keys: List of keys to mask
        
    Returns:
        Dict: Sanitized copy of the data
    """
    if sensitive_keys is None:
        sensitive_keys = ['password', 'key', 'salt', 'hash', 'token', 'secret']
    
    if not isinstance(data, dict):
        return data
    
    result = {}
    for key, value in data.items():
        if any(s_key in key.lower() for s_key in sensitive_keys):
            result[key] = '********'
        elif isinstance(value, dict):
            result[key] = sanitize_for_logging(value, sensitive_keys)
        else:
            result[key] = value
    
    return result

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
    logger.debug(f"Starting log cleanup for files older than {max_age_days} days in {log_dir}")
    
    # Validate parameters
    if max_age_days < 1:
        logger.warning(f"Invalid max_age_days value ({max_age_days}), using default of 1 day")
        max_age_days = 1
    
    log_path = Path(log_dir)
    if not log_path.exists():
        logger.warning(f"Log directory {log_dir} does not exist, nothing to clean up")
        return 0
        
    cutoff = datetime.now() - timedelta(days=max_age_days)
    removed_count = 0
    
    # Process all log files in the main directory
    for file_path in log_path.glob("*.log*"):
        if file_path.is_file():
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
                        logger.warning(f"Failed to remove old archived log file {file_path}: {e}")
    
    logger.info(f"Log cleanup completed: removed {removed_count} files older than {max_age_days} days")
    return removed_count


class LogCleanupScheduler:
    """Scheduler for automatic log cleanup."""
    
    def __init__(self, log_dir="logs", cleanup_days=1):
        """
        Initialize the log cleanup scheduler.
        
        Args:
            log_dir (str): Directory containing log files
            cleanup_days (int): Maximum age of log files in days
        """
        self.log_dir = log_dir
        self.cleanup_days = max(1, min(cleanup_days, 365))  # Ensure valid range
        self.timer = None
        self.midnight_timer = None
        self.logger = logging.getLogger(__name__)
        self.is_running = False
    
    def start(self):
        """Start the scheduled cleanup."""
        if self.is_running:
            self.stop()
            
        # Calculate time until midnight
        now = datetime.now()
        midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        seconds_until_midnight = (midnight - now).total_seconds()
        
        # Create a QTimer that fires at midnight
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._run_cleanup)
        self.timer.setSingleShot(False)
        self.timer.start(24 * 60 * 60 * 1000)  # 24 hours in milliseconds
        
        # Also run an initial cleanup after a short delay
        self.midnight_timer = QtCore.QTimer()
        self.midnight_timer.timeout.connect(self._run_cleanup)
        self.midnight_timer.setSingleShot(True)
        self.midnight_timer.start(int(seconds_until_midnight * 1000))
        
        self.is_running = True
        next_cleanup_time = midnight.strftime("%Y-%m-%d %H:%M:%S")
        self.logger.info(f"Log cleanup scheduler started. Next cleanup at {next_cleanup_time} (in {seconds_until_midnight/3600:.1f} hours)")
    
    def stop(self):
        """Stop the scheduled cleanup."""
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
        
        if self.midnight_timer is not None:
            self.midnight_timer.stop()
            self.midnight_timer = None
            
        self.is_running = False
        self.logger.info("Log cleanup scheduler stopped")
    
    def update_settings(self, log_dir=None, cleanup_days=None):
        """
        Update scheduler settings without restarting.
        
        Args:
            log_dir (str, optional): New log directory path
            cleanup_days (int, optional): New cleanup days value
        """
        restart_needed = False
        
        if log_dir is not None and log_dir != self.log_dir:
            self.log_dir = log_dir
            restart_needed = True
            
        if cleanup_days is not None and cleanup_days != self.cleanup_days:
            self.cleanup_days = max(1, min(cleanup_days, 365))  # Ensure valid range
            restart_needed = True
            
        if restart_needed and self.is_running:
            self.logger.debug("Restarting scheduler with new settings")
            self.stop()
            self.start()
    
    def _run_cleanup(self):
        """Run the cleanup operation."""
        try:
            self.logger.debug(f"Running scheduled cleanup for logs older than {self.cleanup_days} days")
            removed_count = cleanup_old_logs(self.log_dir, self.cleanup_days)
            self.logger.info(f"Automatic log cleanup completed. Removed {removed_count} old log files")
            
            # Calculate next run time for logging
            next_cleanup = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            self.logger.debug(f"Next scheduled cleanup: {next_cleanup.strftime('%Y-%m-%d %H:%M:%S')}")
            
        except Exception as e:
            self.logger.error(f"Error during automatic log cleanup: {e}", exc_info=True)


def get_log_config():
    """
    Get logging configuration from environment variables or settings.
    
    Returns:
        dict: Dictionary containing all logging configuration settings
    """
    settings = get_app_settings()
    
    # Environment variables take precedence
    debug_mode = os.environ.get('SILVER_APP_DEBUG', '').lower() in ('true', '1', 'yes')
    if 'SILVER_APP_DEBUG' not in os.environ:
        debug_mode = settings.value("logging/debug_mode", False, type=bool)
    
    log_dir = os.environ.get('SILVER_APP_LOG_DIR', 'logs')
    
    # Get log level enable/disable settings
    enable_info = settings.value("logging/enable_info", True, type=bool)
    # Backward-compat: accept either enable_error or enable_critical; default True
    enable_error = settings.value("logging/enable_error", None, type=bool)
    if enable_error is None:
        enable_error = settings.value("logging/enable_critical", True, type=bool)
    enable_debug = settings.value("logging/enable_debug", True, type=bool)
    
    # Get auto-cleanup settings
    auto_cleanup = settings.value("logging/auto_cleanup", False, type=bool)
    cleanup_days = settings.value("logging/cleanup_days", 1, type=int)
    
    # Ensure cleanup_days is within reasonable range
    if cleanup_days < 1:
        cleanup_days = 1
    elif cleanup_days > 365:
        cleanup_days = 365
    
    return {
        'debug_mode': debug_mode,
        'log_dir': log_dir,
        'enable_info': enable_info,
        'enable_error': enable_error,
        'enable_debug': enable_debug,
        'auto_cleanup': auto_cleanup,
        'cleanup_days': cleanup_days
    }


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
        debug_mode=config['debug_mode'],
        log_dir=config['log_dir'],
        enable_info=config['enable_info'],
        enable_error=config['enable_error'],
        enable_debug=config['enable_debug']
    )
    
    # Configure cleanup scheduler if enabled
    global _cleanup_scheduler
    
    if config['auto_cleanup']:
        if _cleanup_scheduler is None:
            # Create new scheduler if it doesn't exist
            _cleanup_scheduler = LogCleanupScheduler(
                log_dir=config['log_dir'],
                cleanup_days=config['cleanup_days']
            )
            _cleanup_scheduler.start()
        else:
            # Update existing scheduler with new settings
            _cleanup_scheduler.update_settings(
                log_dir=config['log_dir'],
                cleanup_days=config['cleanup_days']
            )
    else:
        # Stop and remove scheduler if auto-cleanup is disabled
        if _cleanup_scheduler is not None:
            _cleanup_scheduler.stop()
            _cleanup_scheduler = None
    
    # Log the reconfiguration
    root_logger.info("Logging system reconfigured with new settings")
    root_logger.debug(f"New logging configuration: {config}")
        
    return root_logger
