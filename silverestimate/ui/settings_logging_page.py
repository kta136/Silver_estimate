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

from .display_formatting import count_label
from .message_dialogs import confirm_destructive
from .themed_controls import ThemedComboBox, ThemedSpinBox

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
                message=(
                    f"Removed {count_label(removed_count, 'old log file')}."
                    if removed_count
                    else "There were no old log files to remove."
                ),
            )
        except Exception as exc:
            LOGGER.error("Manual log cleanup failed: %s", exc, exc_info=True)
            return LogCleanupResult(
                succeeded=False,
                message=f"The old log files could not be removed. Details: {exc}",
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


# The four stored flags as three levels a person can choose between.
LOG_LEVEL_PRESETS: tuple[tuple[str, str, str, dict[str, bool]], ...] = (
    (
        "errors",
        "Errors only",
        "Records problems only. Smallest log files.",
        {
            "debug_mode": False,
            "enable_info": False,
            "enable_critical": True,
            "enable_debug": False,
        },
    ),
    (
        "normal",
        "Normal (recommended)",
        "Records problems and the main actions, such as saves and backups.",
        {
            "debug_mode": False,
            "enable_info": True,
            "enable_critical": True,
            "enable_debug": True,
        },
    ),
    (
        "detailed",
        "Detailed, for troubleshooting",
        "Records every step. Use while chasing a problem; files grow quickly.",
        {
            "debug_mode": True,
            "enable_info": True,
            "enable_critical": True,
            "enable_debug": True,
        },
    ),
)
_CUSTOM_LEVEL = "custom"


def log_level_for(state: LoggingSettingsState) -> str:
    """Return the preset matching ``state``, or ``custom`` when none does."""
    for key, _label, _description, flags in LOG_LEVEL_PRESETS:
        if all(getattr(state, name) == value for name, value in flags.items()):
            return key
    # Without debug mode the debug-detail flag has no effect, so it does not
    # decide the level.
    if not state.debug_mode and state.enable_critical:
        return "normal" if state.enable_info else "errors"
    return _CUSTOM_LEVEL


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
        self._custom_flags: dict[str, bool] = {}
        self._build_ui(controller.load_state())

    def state(self) -> LoggingSettingsState:
        flags = self._flags_for(str(self.level_combo.currentData()))
        return LoggingSettingsState(
            auto_cleanup=self.auto_cleanup_checkbox.isChecked(),
            cleanup_days=self.cleanup_days_spin.value(),
            **flags,
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

    def set_level(self, key: str) -> None:
        """Choose a detail level by its key (``errors``, ``normal``, ``detailed``)."""
        index = self.level_combo.findData(key)
        if index >= 0:
            self.level_combo.setCurrentIndex(index)

    def _flags_for(self, key: str) -> dict[str, bool]:
        for preset, _label, _description, flags in LOG_LEVEL_PRESETS:
            if preset == key:
                return dict(flags)
        return dict(self._custom_flags)

    def _build_ui(self, state: LoggingSettingsState) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("Logging")
        title.setObjectName("SettingsTitleLabel")
        layout.addWidget(title)
        description = QLabel(
            "Logs help find the cause of a problem. Choose how much is recorded "
            "and how long the files are kept."
        )
        description.setWordWrap(True)
        description.setObjectName("SettingsMutedDescription")
        layout.addWidget(description)

        layout.addWidget(self._create_log_levels_group())
        layout.addWidget(self._create_cleanup_group())
        layout.addWidget(self._create_utilities_group())
        layout.addStretch()

        self._load_to_ui(state)
        self.level_combo.currentIndexChanged.connect(self._level_changed)
        self.auto_cleanup_checkbox.toggled.connect(self._emit_changed)
        self.cleanup_days_spin.valueChanged.connect(self._emit_changed)
        self.cleanup_days_spin.valueChanged.connect(self._sync_days_suffix)
        self.auto_cleanup_checkbox.toggled.connect(self.cleanup_days_spin.setEnabled)

    def _create_log_levels_group(self) -> QGroupBox:
        group = QGroupBox("Recording")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        row = QHBoxLayout()
        level_label = QLabel("Detail level:")
        row.addWidget(level_label)
        self.level_combo = ThemedComboBox()
        self.level_combo.setAccessibleName("Log detail level")
        for key, label, _description, _flags in LOG_LEVEL_PRESETS:
            self.level_combo.addItem(label, key)
        self._polish_field(self.level_combo, width=280)
        level_label.setBuddy(self.level_combo)
        row.addWidget(self.level_combo)
        row.addStretch()
        layout.addLayout(row)

        self.level_description = QLabel("")
        self.level_description.setWordWrap(True)
        self.level_description.setObjectName("SettingsMutedDescription")
        layout.addWidget(self.level_description)
        return group

    def _create_cleanup_group(self) -> QGroupBox:
        group = QGroupBox("Retention")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)

        self.auto_cleanup_checkbox = QCheckBox("Delete old logs automatically")
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
            "Older log files are removed at midnight each day while the app is open."
        )
        description.setWordWrap(True)
        description.setObjectName("SettingsMutedDescription")
        layout.addWidget(description)
        return group

    def _create_utilities_group(self) -> QGroupBox:
        group = QGroupBox("Log files")
        layout = QHBoxLayout(group)
        layout.setSpacing(10)

        self.manual_cleanup_button = QPushButton("Delete Old Logs Now...")
        self.manual_cleanup_button.setToolTip(
            "Delete log files older than the number of days above"
        )
        self.manual_cleanup_button.clicked.connect(self._confirm_manual_cleanup)
        layout.addWidget(self.manual_cleanup_button)

        self.open_logs_button = QPushButton("Open Logs Folder")
        self.open_logs_button.setToolTip(
            "Open the folder containing application log files"
        )
        self.open_logs_button.clicked.connect(self._open_logs_folder)
        layout.addWidget(self.open_logs_button)
        layout.addStretch()
        return group

    def _load_to_ui(self, state: LoggingSettingsState) -> None:
        key = log_level_for(state)
        custom_index = self.level_combo.findData(_CUSTOM_LEVEL)
        if key == _CUSTOM_LEVEL:
            # Keep a hand-edited combination until the user picks a level.
            self._custom_flags = {
                "debug_mode": state.debug_mode,
                "enable_info": state.enable_info,
                "enable_critical": state.enable_critical,
                "enable_debug": state.enable_debug,
            }
            if custom_index < 0:
                self.level_combo.addItem("Custom (keep current)", _CUSTOM_LEVEL)
        elif custom_index >= 0:
            self.level_combo.removeItem(custom_index)
        self.set_level(key)
        self._sync_level_description()
        self.auto_cleanup_checkbox.setChecked(state.auto_cleanup)
        self.cleanup_days_spin.setValue(state.cleanup_days)
        self.cleanup_days_spin.setEnabled(state.auto_cleanup)
        self._sync_days_suffix()

    def _level_changed(self, *_args: object) -> None:
        self._sync_level_description()
        self.changed.emit()

    def _sync_level_description(self) -> None:
        key = str(self.level_combo.currentData())
        text = next(
            (
                description
                for preset, _label, description, _flags in LOG_LEVEL_PRESETS
                if preset == key
            ),
            "Keeps the combination already saved for this PC.",
        )
        self.level_description.setText(text)

    def _sync_days_suffix(self, *_args: object) -> None:
        self.cleanup_days_spin.setSuffix(
            " day" if self.cleanup_days_spin.value() == 1 else " days"
        )

    def _confirm_manual_cleanup(self) -> None:
        days = self.cleanup_days_spin.value()
        if not confirm_destructive(
            self,
            title="Delete Old Logs",
            heading=f"Delete log files older than {count_label(days, 'day')}?",
            detail="The files are removed permanently.",
            action_label="Delete Old Logs",
        ):
            return

        self.setCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            result = self._controller.cleanup_logs(days)
        finally:
            self.unsetCursor()
        if result.succeeded:
            QMessageBox.information(
                self,
                "Old Logs Deleted",
                result.message,
            )
        else:
            QMessageBox.critical(
                self,
                "Logs Not Deleted",
                result.message,
            )

    def _open_logs_folder(self) -> None:
        result = self._controller.open_logs_folder()
        if not result.succeeded:
            QMessageBox.critical(
                self,
                "Logs Folder Not Opened",
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
    "LOG_LEVEL_PRESETS",
    "LoggingSettingsActions",
    "LoggingSettingsPage",
    "LoggingSettingsState",
    "SettingsLoggingController",
    "default_logging_settings_actions",
    "log_level_for",
]
