"""Controller coordinating the verified DDA rate stream with the main UI."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace

from PyQt6.QtCore import QDateTime, QLocale, QObject, QTimer

from silverestimate.infrastructure.settings import SettingsReader, get_app_settings
from silverestimate.services.dda_rate_fetcher import DdaRateSnapshot
from silverestimate.services.live_rate_service import LiveRateService

LiveRateWidgetGetter = Callable[[], object | None]
StatusCallback = Callable[[str, int, str], None]


class LiveRateController(QObject):
    """Own live-rate presentation state without duplicating network transports."""

    def __init__(
        self,
        *,
        parent: QObject,
        widget_getter: LiveRateWidgetGetter,
        status_callback: StatusCallback | None,
        logger: logging.Logger | None = None,
        service_factory: Callable[..., LiveRateService] = LiveRateService,
        settings_provider: Callable[[], SettingsReader] = get_app_settings,
        single_shot: Callable[[int, Callable[[], None]], None] = QTimer.singleShot,
    ) -> None:
        super().__init__(parent)
        self._parent = parent
        self._widget_getter = widget_getter
        self._status_callback = status_callback or (lambda *_: None)
        self._logger = logger or logging.getLogger(__name__)
        self._service_factory = service_factory
        self._settings_provider = settings_provider
        self._single_shot = single_shot
        self._service: LiveRateService | None = None
        self._last_snapshot: DdaRateSnapshot | None = None
        self._last_refresh_at: QDateTime | None = None
        self._last_source: str | None = None
        self._last_error: str | None = None
        self._connection_state = "idle"
        self._manual_refresh = False
        self._ui_enabled = True

    def initialize(self, *, initial_refresh_delay_ms: int = 500) -> None:
        show_ui = self.apply_visibility_settings()
        self.apply_timer_settings(force_show_ui=show_ui)
        if show_ui:
            self._single_shot(initial_refresh_delay_ms, self.refresh_now)

    def shutdown(self) -> None:
        if self._service is None:
            return
        try:
            self._service.stop()
        except Exception as exc:
            self._logger.debug("Failed to stop live-rate service: %s", exc)
        finally:
            self._service = None

    def apply_visibility_settings(self) -> bool:
        show_ui, _, _ = self._read_settings()
        self._ui_enabled = show_ui
        widget = self._widget_getter()
        if not widget:
            return show_ui
        components = (
            getattr(widget, "live_rate_value_label", None),
            getattr(widget, "live_rate_meta_label", None),
            getattr(widget, "refresh_rate_button", None),
        )
        for component in components:
            if component is None:
                continue
            try:
                component.setVisible(show_ui)
            except Exception as exc:
                self._logger.debug(
                    "Failed to update live-rate component visibility: %s", exc
                )
        label = getattr(widget, "live_rate_value_label", None)
        meta = getattr(widget, "live_rate_meta_label", None)
        if label is not None:
            try:
                if not show_ui:
                    label.setText("-")
                elif label.text() in {"", "-"}:
                    label.setText("Loading…")
            except Exception as exc:
                self._logger.debug("Failed to update live-rate label: %s", exc)
        if meta is not None:
            try:
                if not show_ui:
                    meta.setText("--:--")
                elif self._last_snapshot is None:
                    meta.setText("Not updated")
            except Exception as exc:
                self._logger.debug("Failed to update live-rate metadata: %s", exc)
        return show_ui

    def apply_timer_settings(self, *, force_show_ui: bool | None = None) -> None:
        show_ui, auto_refresh, _ = self._read_settings()
        if force_show_ui is not None:
            show_ui = force_show_ui
        service = self._ensure_service() if (show_ui or auto_refresh) else self._service
        if service is None:
            return
        try:
            service.stop()
        except Exception as exc:
            self._logger.debug("Failed to stop live-rate service: %s", exc)
        if auto_refresh and show_ui:
            try:
                service.start()
            except Exception as exc:
                self._logger.warning(
                    "Unable to start DDA live-rate stream: %s", exc, exc_info=True
                )
        else:
            self._logger.info(
                "DDA live rate disabled (ui=%s, automatic=%s)",
                show_ui,
                auto_refresh,
            )

    def refresh_now(self) -> None:
        if not self._ui_enabled:
            return
        self._manual_refresh = True
        service = self._ensure_service()
        if service is not None:
            try:
                service.refresh_now()
                self._status_callback("Refreshing live rate.", 1500, "info")
                return
            except Exception as exc:
                self._logger.warning(
                    "DDA live-rate refresh failed: %s", exc, exc_info=True
                )
        self._fallback_refresh()

    def _ensure_service(self) -> LiveRateService | None:
        if self._service is not None:
            return self._service
        try:
            service = self._service_factory(parent=self._parent, logger=self._logger)
            service.rate_updated.connect(self._handle_rate_updated)
            service.feed_status_updated.connect(self._handle_feed_status)
            service.connection_state_changed.connect(self._handle_connection_state)
            service.stream_error.connect(self._handle_stream_error)
            self._service = service
            return service
        except Exception as exc:
            self._logger.warning("DDA live-rate service unavailable: %s", exc)
            self._service = None
            return None

    def _fallback_refresh(self) -> None:
        widget = self._widget_getter()
        if widget and hasattr(widget, "refresh_silver_rate"):
            try:
                widget.refresh_silver_rate()
            except Exception as exc:
                self._logger.warning("Manual live-rate refresh failed: %s", exc)
                self._status_callback("Live rate refresh failed", 3000, "warning")
            finally:
                self._manual_refresh = False
            return
        self._manual_refresh = False
        self._status_callback("Live rate refresh unavailable", 3000, "warning")

    def _handle_rate_updated(self, snapshot: object) -> None:
        if not isinstance(snapshot, DdaRateSnapshot):
            self._handle_stream_error("DDA worker emitted an invalid snapshot.")
            return
        self._single_shot(0, lambda: self._update_display(snapshot))

    def _handle_feed_status(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        market_state = payload.get("marketState")
        if isinstance(market_state, dict) and self._last_snapshot is not None:
            snapshot = replace(self._last_snapshot, market_state=dict(market_state))
            self._single_shot(0, lambda: self._update_display(snapshot))

    def _handle_connection_state(self, state: str) -> None:
        self._connection_state = str(state)
        if self._last_snapshot is not None:
            snapshot = self._last_snapshot
            self._single_shot(0, lambda: self._update_display(snapshot))

    def _handle_stream_error(self, message: str) -> None:
        self._last_error = str(message)
        self._logger.warning("DDA live-rate stream: %s", message)
        if self._last_snapshot is None and self._manual_refresh:
            widget = self._widget_getter()
            label = getattr(widget, "live_rate_value_label", None) if widget else None
            meta = getattr(widget, "live_rate_meta_label", None) if widget else None
            if label is not None:
                label.setText("Unavailable")
            if meta is not None:
                meta.setText("Retry")
            self._status_callback("Live rate unavailable", 3000, "warning")
            self._manual_refresh = False

    def _update_display(self, snapshot: DdaRateSnapshot) -> None:
        widget = self._widget_getter()
        label = getattr(widget, "live_rate_value_label", None) if widget else None
        if label is None:
            self._manual_refresh = False
            return
        try:
            gram_rate = snapshot.final_rate / 1000.0
            display_value = QLocale.system().toCurrencyString(gram_rate)
        except Exception:
            display_value = f"₹ {snapshot.final_rate / 1000.0:.2f}"
        label.setText(f"{display_value} /g")

        source = {
            "https": "DDA HTTPS",
            "sse": "DDA SSE",
            "cache": "Cached DDA",
        }[snapshot.transport]
        stale = self._connection_state in {
            "disconnected",
            "offline-stale",
            "reconnecting",
        }
        server_local = snapshot.server_time.astimezone()
        received_local = snapshot.received_at.astimezone()
        market_label = "Market status unavailable"
        if snapshot.market_state:
            market_label = str(
                snapshot.market_state.get("label")
                or snapshot.market_state.get("code")
                or market_label
            )
        tooltip_rows = [
            f"Source: {source}",
            f"Item ID: {snapshot.item_id}",
            f"Customer finalRate: {snapshot.final_rate:g} {snapshot.unit}",
            f"Sequence: {snapshot.sequence}",
            f"Server time: {server_local:%Y-%m-%d %H:%M:%S %Z}",
            f"Received: {received_local:%Y-%m-%d %H:%M:%S %Z}",
            f"Market: {market_label}",
            f"Connection: {self._connection_state}",
        ]
        if stale:
            tooltip_rows.append("Offline/stale: retaining the last verified rate")
        if self._last_error:
            tooltip_rows.append(f"Last transport error: {self._last_error}")
        label.setToolTip("\n".join(tooltip_rows))

        meta_text = f"{server_local:%H:%M}{'*' if stale else ''}"
        meta = getattr(widget, "live_rate_meta_label", None) if widget else None
        if meta is not None:
            meta.setText(meta_text)
            meta.setToolTip(
                "Last verified DDA server time"
                + (" — offline/stale" if stale else " — live")
            )
        self._last_snapshot = snapshot
        self._last_refresh_at = QDateTime.currentDateTime()
        self._last_source = source
        self._last_error = None if not stale else self._last_error
        if self._manual_refresh:
            self._status_callback("Live rate updated", 2000, "info")
        self._manual_refresh = False

    def _read_settings(self) -> tuple[bool, bool, int]:
        try:
            settings = self._settings_provider()
            show_ui = self._coerce_bool(
                settings.value("rates/live_enabled", True), True
            )
            automatic = self._coerce_bool(
                settings.value("rates/auto_refresh_enabled", True), True
            )
            return show_ui, automatic, 10
        except Exception as exc:
            self._logger.debug("Using default DDA live-rate settings: %s", exc)
            return True, True, 10

    @staticmethod
    def _coerce_bool(value: object, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, str):
            normalized = value.strip().lower()
            return (
                default
                if not normalized
                else normalized
                in {
                    "1",
                    "true",
                    "yes",
                    "on",
                    "enabled",
                }
            )
        if isinstance(value, int | float):
            return value != 0
        return default


__all__ = ["LiveRateController"]
