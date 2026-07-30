"""Logging and diagnostics settings page."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QCursor, QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from silverestimate.infrastructure import logger as application_logger
from silverestimate.infrastructure.app_constants import LOG_DIR
from silverestimate.infrastructure.settings import (
    SettingsKey,
    SettingsStore,
    as_settings_store,
)

from .themed_controls import ThemedSpinBox

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class LoggingSettingsState:
    """Validated logging preferences."""

    debug_mode: bool = False
    enable_info: bool = True
    enable_critical: bool = True
    enable_debug: bool = True
    auto_cleanup: bool = False
    cleanup_days: int = 1


@dataclass(frozen=True)
class LogCleanupResult:
    """Explicit result returned by manual log cleanup."""

    succeeded: bool
    removed_count: int = 0
    message: str = ""


@dataclass(frozen=True)
class DiagnosticsActionResult:
    """Explicit result for a diagnostics utility action."""

    succeeded: bool
    message: str = ""


@dataclass(frozen=True)
class LoggingSettingsActions:
    """Infrastructure actions used by the logging settings controller."""

    reconfigure: Callable[[], object]
    cleanup: Callable[[int], int]
    open_logs_folder: Callable[[], bool]


def default_logging_settings_actions() -> LoggingSettingsActions:
    """Create production actions while keeping them injectable in tests."""

    return LoggingSettingsActions(
        reconfigure=lambda: application_logger.reconfigure_logging(),
        cleanup=lambda days: application_logger.cleanup_old_logs(
            max_age_days=days,
        ),
        open_logs_folder=_open_logs_folder,
    )


class SettingsLoggingController:
    """Load, validate, persist, and apply logging preferences."""

    def __init__(
        self,
        settings: SettingsStore,
        actions: LoggingSettingsActions,
    ) -> None:
        self._settings = as_settings_store(settings)
        self._actions = actions

    def load_state(self) -> LoggingSettingsState:
        return LoggingSettingsState(
            debug_mode=self._settings.get_bool(
                SettingsKey.LOGGING_DEBUG_MODE,
                False,
            ),
            enable_info=self._settings.get_bool(
                SettingsKey.LOGGING_ENABLE_INFO,
                True,
            ),
            enable_critical=self._settings.get_bool(
                SettingsKey.LOGGING_ENABLE_CRITICAL,
                True,
            ),
            enable_debug=self._settings.get_bool(
                SettingsKey.LOGGING_ENABLE_DEBUG,
                True,
            ),
            auto_cleanup=self._settings.get_bool(
                SettingsKey.LOGGING_AUTO_CLEANUP,
                False,
            ),
            cleanup_days=self._settings.get_int(
                SettingsKey.LOGGING_CLEANUP_DAYS,
                1,
                minimum=1,
                maximum=365,
            ),
        )

    def apply_state(self, state: LoggingSettingsState) -> None:
        self.validate_state(state)
        previous_state = self.load_state()
        self._write_state(state)
        try:
            result = self._actions.reconfigure()
            if result is False:
                raise RuntimeError("Logging runtime rejected the new configuration.")
        except Exception:
            self._write_state(previous_state)
            try:
                self._actions.reconfigure()
            except Exception:
                LOGGER.exception(
                    "Failed to restore the prior logging runtime configuration."
                )
            raise

    def cleanup_logs(self, days: int) -> LogCleanupResult:
        if not 1 <= days <= 365:
            return LogCleanupResult(
                succeeded=False,
                message="Cleanup retention must be between 1 and 365 days.",
            )
        try:
            LOGGER.info(
                "Manual log cleanup initiated for files older than %s days",
                days,
            )
            removed_count = self._actions.cleanup(days)
            LOGGER.info(
                "Manual log cleanup completed: removed %s files",
                removed_count,
            )
            return LogCleanupResult(
                succeeded=True,
                removed_count=removed_count,
                message=f"Successfully removed {removed_count} old log file(s).",
            )
        except Exception as exc:
            LOGGER.error("Manual log cleanup failed: %s", exc, exc_info=True)
            return LogCleanupResult(
                succeeded=False,
                message=f"An error occurred during log cleanup: {exc}",
            )

    def open_logs_folder(self) -> DiagnosticsActionResult:
        try:
            opened = self._actions.open_logs_folder()
        except Exception as exc:
            return DiagnosticsActionResult(
                succeeded=False,
                message=f"Could not open the logs folder: {exc}",
            )
        if not opened:
            return DiagnosticsActionResult(
                succeeded=False,
                message="The operating system could not open the logs folder.",
            )
        return DiagnosticsActionResult(succeeded=True)

    @staticmethod
    def default_state() -> LoggingSettingsState:
        return LoggingSettingsState()

    @staticmethod
    def validate_state(state: LoggingSettingsState) -> None:
        if not 1 <= state.cleanup_days <= 365:
            raise ValueError("Cleanup retention must be between 1 and 365 days.")

    def _write_state(self, state: LoggingSettingsState) -> None:
        self._settings.set(SettingsKey.LOGGING_DEBUG_MODE, state.debug_mode)
        self._settings.set(SettingsKey.LOGGING_ENABLE_INFO, state.enable_info)
        self._settings.set(
            SettingsKey.LOGGING_ENABLE_CRITICAL,
            state.enable_critical,
        )
        self._settings.set(SettingsKey.LOGGING_ENABLE_DEBUG, state.enable_debug)
        self._settings.set(SettingsKey.LOGGING_AUTO_CLEANUP, state.auto_cleanup)
        self._settings.set(SettingsKey.LOGGING_CLEANUP_DAYS, state.cleanup_days)


class LoggingSettingsPage(QWidget):
    """Own logging controls and diagnostics actions."""

    changed = Signal()

    def __init__(
        self,
        controller: SettingsLoggingController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._build_ui(controller.load_state())

    def state(self) -> LoggingSettingsState:
        return LoggingSettingsState(
            debug_mode=self.debug_mode_checkbox.isChecked(),
            enable_info=self.enable_info_checkbox.isChecked(),
            enable_critical=self.enable_critical_checkbox.isChecked(),
            enable_debug=self.enable_debug_checkbox.isChecked(),
            auto_cleanup=self.auto_cleanup_checkbox.isChecked(),
            cleanup_days=self.cleanup_days_spin.value(),
        )

    def apply(self) -> LoggingSettingsState:
        state = self.state()
        self._controller.apply_state(state)
        return state

    def validate(self) -> None:
        self._controller.validate_state(self.state())

    def restore_defaults(self) -> None:
        self._load_to_ui(self._controller.default_state())
        self.changed.emit()

    def _build_ui(self, state: LoggingSettingsState) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        description = QLabel(
            "Configure how the application logs events and manages log files. "
            "Changes take effect when settings are applied."
        )
        description.setWordWrap(True)
        description.setObjectName("SettingsMutedDescription")
        layout.addWidget(description)

        layout.addWidget(self._create_debug_group())
        layout.addWidget(self._create_log_levels_group())
        layout.addWidget(self._create_cleanup_group())
        layout.addWidget(self._create_utilities_group())
        layout.addStretch()

        self._load_to_ui(state)
        for checkbox in (
            self.debug_mode_checkbox,
            self.enable_info_checkbox,
            self.enable_critical_checkbox,
            self.enable_debug_checkbox,
            self.auto_cleanup_checkbox,
        ):
            checkbox.toggled.connect(self._emit_changed)
        self.cleanup_days_spin.valueChanged.connect(self._emit_changed)
        self.auto_cleanup_checkbox.toggled.connect(self.cleanup_days_spin.setEnabled)

    def _create_debug_group(self) -> QGroupBox:
        group = QGroupBox("Debug Settings")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.debug_mode_checkbox = QCheckBox("Enable Debug Mode")
        self.debug_mode_checkbox.setToolTip(
            "Enable detailed debug logging (may affect performance)"
        )
        layout.addWidget(self.debug_mode_checkbox)

        description = QLabel(
            "Debug mode captures detailed information about application operations. "
            "This is useful for troubleshooting but may affect performance."
        )
        description.setWordWrap(True)
        description.setObjectName("SettingsMutedDescription")
        layout.addWidget(description)
        return group

    def _create_log_levels_group(self) -> QGroupBox:
        group = QGroupBox("Log Levels")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.enable_info_checkbox = QCheckBox("Enable Normal Logs (INFO)")
        self.enable_info_checkbox.setToolTip(
            "Log normal application events (INFO level)"
        )
        layout.addWidget(self.enable_info_checkbox)

        self.enable_critical_checkbox = QCheckBox(
            "Enable Critical Logs (ERROR and CRITICAL)"
        )
        self.enable_critical_checkbox.setToolTip("Log errors and critical issues")
        layout.addWidget(self.enable_critical_checkbox)

        self.enable_debug_checkbox = QCheckBox(
            "Enable Debug Logs (when Debug Mode is on)"
        )
        self.enable_debug_checkbox.setToolTip(
            "Log detailed debug information (only when Debug Mode is enabled)"
        )
        layout.addWidget(self.enable_debug_checkbox)

        description = QLabel(
            "You can enable or disable specific log levels. Critical logs are "
            "recommended for troubleshooting."
        )
        description.setWordWrap(True)
        description.setObjectName("SettingsMutedDescription")
        layout.addWidget(description)
        return group

    def _create_cleanup_group(self) -> QGroupBox:
        group = QGroupBox("Automatic Log Cleanup")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.auto_cleanup_checkbox = QCheckBox("Automatically Delete Old Logs")
        self.auto_cleanup_checkbox.setToolTip(
            "Automatically delete log files older than the specified number of days"
        )
        layout.addWidget(self.auto_cleanup_checkbox)

        days_layout = QHBoxLayout()
        days_layout.addWidget(QLabel("Keep logs for:"))
        self.cleanup_days_spin = ThemedSpinBox()
        self.cleanup_days_spin.setRange(1, 365)
        self.cleanup_days_spin.setSuffix(" days")
        self._polish_field(self.cleanup_days_spin, width=150)
        days_layout.addWidget(self.cleanup_days_spin)
        days_layout.addStretch()
        layout.addLayout(days_layout)

        description = QLabel(
            "Automatic cleanup helps manage disk space by removing old log files. "
            "Cleanup occurs at midnight each day."
        )
        description.setWordWrap(True)
        description.setObjectName("SettingsMutedDescription")
        layout.addWidget(description)
        return group

    def _create_utilities_group(self) -> QGroupBox:
        group = QGroupBox("Utilities")
        layout = QHBoxLayout(group)
        layout.setSpacing(10)

        self.manual_cleanup_button = QPushButton("Clean Up Logs Now…")
        self.manual_cleanup_button.setToolTip("Manually delete old log files")
        self.manual_cleanup_button.clicked.connect(self._confirm_manual_cleanup)
        layout.addWidget(self.manual_cleanup_button)

        self.open_logs_button = QPushButton("Open Logs Folder…")
        self.open_logs_button.setToolTip(
            "Open the folder containing application log files"
        )
        self.open_logs_button.clicked.connect(self._open_logs_folder)
        layout.addWidget(self.open_logs_button)
        layout.addStretch()
        return group

    def _load_to_ui(self, state: LoggingSettingsState) -> None:
        self.debug_mode_checkbox.setChecked(state.debug_mode)
        self.enable_info_checkbox.setChecked(state.enable_info)
        self.enable_critical_checkbox.setChecked(state.enable_critical)
        self.enable_debug_checkbox.setChecked(state.enable_debug)
        self.auto_cleanup_checkbox.setChecked(state.auto_cleanup)
        self.cleanup_days_spin.setValue(state.cleanup_days)
        self.cleanup_days_spin.setEnabled(state.auto_cleanup)

    def _confirm_manual_cleanup(self) -> None:
        days = self.cleanup_days_spin.value()
        reply = QMessageBox.question(
            self,
            "Confirm Log Cleanup",
            f"This will permanently delete log files older than {days} day(s)."
            "\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.setCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            result = self._controller.cleanup_logs(days)
        finally:
            self.unsetCursor()
        if result.succeeded:
            QMessageBox.information(
                self,
                "Log Cleanup Complete",
                result.message,
            )
        else:
            QMessageBox.critical(
                self,
                "Log Cleanup Failed",
                result.message,
            )

    def _open_logs_folder(self) -> None:
        result = self._controller.open_logs_folder()
        if not result.succeeded:
            QMessageBox.critical(
                self,
                "Open Logs Folder",
                result.message,
            )

    def _emit_changed(self, *_args: object) -> None:
        self.changed.emit()

    @staticmethod
    def _polish_field(widget: QWidget, *, width: int) -> None:
        widget.setMinimumWidth(min(width, 180))
        widget.setMaximumWidth(width)
        widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )


def _open_logs_folder() -> bool:
    try:
        return QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_DIR)))
    except Exception:
        return QDesktopServices.openUrl(QUrl.fromLocalFile("logs"))


__all__ = [
    "DiagnosticsActionResult",
    "LogCleanupResult",
    "LoggingSettingsActions",
    "LoggingSettingsPage",
    "LoggingSettingsState",
    "SettingsLoggingController",
    "default_logging_settings_actions",
]
