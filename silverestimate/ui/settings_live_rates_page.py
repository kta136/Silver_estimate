"""Independent settings page for the DDA public live-rate transport."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from silverestimate.infrastructure.settings import (
    SettingsKey,
    SettingsStore,
    as_settings_store,
)


@dataclass(frozen=True)
class LiveRateSettingsState:
    visible: bool = True
    automatic: bool = True


class LiveRatesSettingsPage(QWidget):
    """Own live-rate controls, persistence, and enable-state synchronization."""

    changed = Signal()

    def __init__(self, settings: SettingsStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = as_settings_store(settings)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        title = QLabel("Live Rates")
        title.setObjectName("SettingsTitleLabel")
        layout.addWidget(title)
        group = QGroupBox("Current Live Rates")
        form = QFormLayout(group)
        form.setContentsMargins(16, 16, 16, 16)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.rate_value = QLabel("Not updated")
        self.rate_status = QLabel("Waiting for connection")
        form.addRow("Provider", QLabel("DDA Agra Mohar"))
        form.addRow("Live silver rate", self.rate_value)
        form.addRow("Status", self.rate_status)
        state = self.load_state()
        self.live_enabled_checkbox = QCheckBox("Show live rate in estimate entry")
        self.live_enabled_checkbox.setChecked(state.visible)
        form.addRow("Live Rate:", self.live_enabled_checkbox)

        self.automatic_checkbox = QCheckBox("Update automatically")
        self.automatic_checkbox.setChecked(state.automatic)
        form.addRow("Automatic:", self.automatic_checkbox)

        hint = QLabel(
            "Uses the public customer finalRate for item ID "
            "cmomws5tw000004i5k5t6yrnw. SSE is primary; anonymous HTTPS polls "
            "every 10 seconds only while disconnected."
        )
        hint.setWordWrap(True)
        layout.addWidget(group)
        technical = QPushButton("Technical details")
        technical.setCheckable(True)
        technical.toggled.connect(hint.setVisible)
        hint.hide()
        layout.addWidget(technical)
        layout.addWidget(hint)
        layout.addStretch()

        self.live_enabled_checkbox.toggled.connect(self._sync_enabled)
        self.live_enabled_checkbox.toggled.connect(self.changed.emit)
        self.automatic_checkbox.toggled.connect(self.changed.emit)
        self._sync_enabled(state.visible)

    def set_rate_status(self, value: str, status: str) -> None:
        self.rate_value.setText(value)
        self.rate_status.setText(status)

    def load_state(self) -> LiveRateSettingsState:
        return LiveRateSettingsState(
            visible=self._settings.get_bool(SettingsKey.RATES_LIVE_ENABLED, True),
            automatic=self._settings.get_bool(
                SettingsKey.RATES_AUTO_REFRESH_ENABLED,
                True,
            ),
        )

    def state(self) -> LiveRateSettingsState:
        return LiveRateSettingsState(
            visible=self.live_enabled_checkbox.isChecked(),
            automatic=self.automatic_checkbox.isChecked(),
        )

    def restore_defaults(self) -> None:
        self.live_enabled_checkbox.setChecked(True)
        self.automatic_checkbox.setChecked(True)

    def save(self) -> LiveRateSettingsState:
        state = self.state()
        self._settings.set(SettingsKey.RATES_LIVE_ENABLED, state.visible)
        self._settings.set(SettingsKey.RATES_AUTO_REFRESH_ENABLED, state.automatic)
        return state

    def _sync_enabled(self, visible: bool) -> None:
        self.automatic_checkbox.setEnabled(visible)


__all__ = ["LiveRateSettingsState", "LiveRatesSettingsPage"]
