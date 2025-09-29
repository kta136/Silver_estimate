"""Controller coordinating live-rate service with the main window UI."""
from __future__ import annotations

import logging
from typing import Callable, Optional, Tuple

from PyQt5.QtCore import QObject, QLocale, QTimer

from silverestimate.infrastructure.settings import get_app_settings
from silverestimate.services.live_rate_service import LiveRateService


LiveRateWidgetGetter = Callable[[], Optional[object]]
StatusCallback = Callable[[str, int, str], None]


class LiveRateController(QObject):
    """Keep live-rate related concerns out of :class:`MainWindow`."""

    def __init__(
        self,
        *,
        parent: QObject,
        widget_getter: LiveRateWidgetGetter,
        status_callback: Optional[StatusCallback],
        logger: Optional[logging.Logger] = None,
        service_factory: Callable[..., LiveRateService] = LiveRateService,
        settings_provider: Callable[[], object] = get_app_settings,
    ) -> None:
        super().__init__(parent)
        self._parent = parent
        self._widget_getter = widget_getter
        self._status_callback = status_callback or (lambda *_: None)
        self._logger = logger or logging.getLogger(__name__)
        self._service_factory = service_factory
        self._settings_provider = settings_provider
        self._service: Optional[LiveRateService] = None
        self._manual_refresh = False
        self._ui_enabled = True

    # --- Lifecycle -----------------------------------------------------

    def initialize(self, *, initial_refresh_delay_ms: int = 500) -> None:
        """Instantiate the service, apply settings, and optionally refresh."""
        show_ui = self.apply_visibility_settings()
        self.apply_timer_settings(force_show_ui=show_ui)
        if show_ui:
            QTimer.singleShot(initial_refresh_delay_ms, self.refresh_now)

    def shutdown(self) -> None:
        """Stop timers before the main window closes."""
        if self._service:
            try:
                self._service.stop()
            except Exception:
                pass

    # --- Public API used by settings dialog ----------------------------

    def apply_visibility_settings(self) -> bool:
        """Re-read visibility settings and toggle rate UI components."""
        show_ui, _, _ = self._read_settings()
        self._ui_enabled = show_ui
        widget = self._widget_getter()
        if not widget:
            return show_ui
        components = (
            getattr(widget, "live_rate_label", None),
            getattr(widget, "live_rate_value_label", None),
            getattr(widget, "refresh_rate_button", None),
        )
        for component in components:
            if component is not None:
                try:
                    component.setVisible(show_ui)
                except Exception:
                    pass
        label = getattr(widget, "live_rate_value_label", None)
        if label is not None:
            try:
                if not show_ui:
                    label.setText("-")
                elif label.text() in ("", "-"):
                    label.setText(".")
            except Exception:
                pass
        return show_ui

    def apply_timer_settings(self, *, force_show_ui: Optional[bool] = None) -> None:
        """Restart the periodic refresh timer based on settings."""
        show_ui, auto_refresh, _ = self._read_settings()
        if force_show_ui is not None:
            show_ui = force_show_ui
        service = self._ensure_service() if (show_ui or auto_refresh) else self._service
        if not service:
            return
        try:
            service.stop()
        except Exception:
            pass
        if auto_refresh and show_ui:
            try:
                service.start()
            except Exception as exc:
                self._logger.warning("Unable to start live-rate timer: %s", exc, exc_info=True)
        else:
            self._logger.info("Live rate auto-refresh disabled (ui=%s, auto=%s)", show_ui, auto_refresh)

    def refresh_now(self) -> None:
        """Trigger an immediate live-rate fetch."""
        if not self._ui_enabled:
            return
        self._manual_refresh = True
        service = self._ensure_service()
        if service:
            try:
                service.refresh_now()
                self._status_callback("Refreshing live rate.", 1500, "info")
                return
            except Exception as exc:
                self._logger.warning("Live rate service refresh failed: %s", exc, exc_info=True)
        self._fallback_refresh()

    # --- Internal helpers ---------------------------------------------

    def _ensure_service(self) -> Optional[LiveRateService]:
        if self._service:
            return self._service
        try:
            service = self._service_factory(parent=self._parent, logger=self._logger)
            service.rate_updated.connect(self._handle_rate_updated)
            self._service = service
            return service
        except Exception as exc:
            self._logger.warning("Live rate service unavailable: %s", exc, exc_info=True)
            self._service = None
            return None

    def _fallback_refresh(self) -> None:
        widget = self._widget_getter()
        if widget and hasattr(widget, "refresh_silver_rate"):
            try:
                widget.refresh_silver_rate()
            except Exception as exc:
                self._logger.warning("Manual live rate refresh failed: %s", exc, exc_info=True)
                self._status_callback("Live rate refresh failed", 3000, "warning")
            finally:
                self._manual_refresh = False
        else:
            self._manual_refresh = False
            self._status_callback("Live rate refresh unavailable", 3000, "warning")

    def _handle_rate_updated(self, broadcast_rate, api_rate, market_open) -> None:
        best_rate = broadcast_rate if broadcast_rate not in (None, "") else api_rate
        QTimer.singleShot(0, lambda: self._update_display(best_rate, broadcast_rate, api_rate, market_open))

    def _update_display(self, effective_rate, broadcast_rate, api_rate, market_open) -> None:
        widget = self._widget_getter()
        label = getattr(widget, "live_rate_value_label", None) if widget else None
        if label is None:
            self._manual_refresh = False
            return
        tooltip_parts = []
        if broadcast_rate not in (None, ""):
            tooltip_parts.append(f"Broadcast: {broadcast_rate}")
        if api_rate not in (None, ""):
            tooltip_parts.append(f"API: {api_rate}")
        tooltip_parts.append("Market open" if market_open else "Market closed")
        tooltip_text = "\n".join(tooltip_parts)
        try:
            if effective_rate in (None, ""):
                label.setText("N/A /g")
                label.setToolTip(tooltip_text)
                if self._manual_refresh:
                    self._status_callback("Live rate unavailable", 3000, "warning")
                self._manual_refresh = False
                return
            gram_rate = float(effective_rate) / 1000.0
        except Exception:
            label.setText("N/A /g")
            label.setToolTip(tooltip_text)
            if self._manual_refresh:
                self._status_callback("Live rate unavailable", 3000, "warning")
            self._manual_refresh = False
            return
        try:
            display_value = QLocale.system().toCurrencyString(gram_rate)
        except Exception:
            display_value = f"? {gram_rate:.2f}" if isinstance(gram_rate, float) else str(gram_rate)
        label.setText(f"{display_value} /g")
        label.setToolTip(tooltip_text)
        if self._manual_refresh:
            self._status_callback("Live rate updated", 2000, "info")
        self._manual_refresh = False

    def _read_settings(self) -> Tuple[bool, bool, int]:
        try:
            settings = self._settings_provider()
        except Exception as exc:
            self._logger.debug("Falling back to default live-rate settings: %s", exc, exc_info=True)
            return True, True, 60
        try:
            ui_raw = settings.value("rates/live_enabled", True)
            auto_raw = settings.value("rates/auto_refresh_enabled", True)
            interval_raw = settings.value("rates/refresh_interval_sec", 60)
        except Exception as exc:
            self._logger.debug("Could not read live-rate settings: %s", exc, exc_info=True)
            return True, True, 60
        show_ui = self._coerce_bool(ui_raw, True)
        auto_refresh = self._coerce_bool(auto_raw, True)
        try:
            interval = int(interval_raw)
        except Exception:
            interval = 60
        interval = max(5, interval)
        return show_ui, auto_refresh, interval

    @staticmethod
    def _coerce_bool(value, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, str):
            norm = value.strip().lower()
            if not norm:
                return default
            return norm in {"1", "true", "yes", "on", "enabled"}
        if isinstance(value, (int, float)):
            return value != 0
        return default

    # --- Compatibility helpers ----------------------------------------

    @property
    def service(self) -> Optional[LiveRateService]:
        """Expose the underlying service for compatibility with legacy code."""
        return self._service

