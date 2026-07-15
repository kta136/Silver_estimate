"""Independent settings page for the DDA public live-rate transport."""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from silverestimate.infrastructure.settings import SettingsStore


@dataclass(frozen=True)
class LiveRateSettingsState:
    visible: bool = True
    automatic: bool = True


class LiveRatesSettingsPage(QWidget):
    """Own live-rate controls, persistence, and enable-state synchronization."""

    changed = pyqtSignal()

    def __init__(self, settings: SettingsStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        group = QGroupBox("DDA Agra Mohar Live Rate")
        form = QFormLayout(group)
        form.setContentsMargins(16, 16, 16, 16)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        state = self.load_state()
        self.live_enabled_checkbox = QCheckBox("Enable live rate (show in UI)")
        self.live_enabled_checkbox.setChecked(state.visible)
        form.addRow("Live Rate:", self.live_enabled_checkbox)

        self.automatic_checkbox = QCheckBox("Enable automatic SSE updates")
        self.automatic_checkbox.setChecked(state.automatic)
        form.addRow("Automatic:", self.automatic_checkbox)

        hint = QLabel(
            "Uses the public customer finalRate for item ID "
            "cmomws5tw000004i5k5t6yrnw. SSE is primary; anonymous HTTPS polls "
            "every 10 seconds only while disconnected."
        )
        hint.setWordWrap(True)
        layout.addWidget(group)
        layout.addWidget(hint)
        layout.addStretch()

        self.live_enabled_checkbox.toggled.connect(self._sync_enabled)
        self.live_enabled_checkbox.toggled.connect(self.changed.emit)
        self.automatic_checkbox.toggled.connect(self.changed.emit)
        self._sync_enabled(state.visible)

    def load_state(self) -> LiveRateSettingsState:
        return LiveRateSettingsState(
            visible=bool(self._settings.value("rates/live_enabled", True, type=bool)),
            automatic=bool(
                self._settings.value("rates/auto_refresh_enabled", True, type=bool)
            ),
        )

    def state(self) -> LiveRateSettingsState:
        return LiveRateSettingsState(
            visible=self.live_enabled_checkbox.isChecked(),
            automatic=self.automatic_checkbox.isChecked(),
        )

    def save(self) -> LiveRateSettingsState:
        state = self.state()
        self._settings.setValue("rates/live_enabled", state.visible)
        self._settings.setValue("rates/auto_refresh_enabled", state.automatic)
        self._settings.remove("rates/refresh_interval_sec")
        return state

    def _sync_enabled(self, visible: bool) -> None:
        self.automatic_checkbox.setEnabled(visible)


__all__ = ["LiveRateSettingsState", "LiveRatesSettingsPage"]
