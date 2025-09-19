"""Live rate polling and scheduling services."""
from __future__ import annotations

import logging
import threading
from typing import Callable, Optional, Tuple

from PyQt5.QtCore import QObject, QSettings, QTimer, pyqtSignal

from silverestimate.infrastructure.app_constants import SETTINGS_APP, SETTINGS_ORG
from silverestimate.services.dda_rate_fetcher import (
    fetch_broadcast_rate_exact,
    fetch_silver_agra_local_mohar_rate,
)


class LiveRateService(QObject):
    rate_updated = pyqtSignal(object, object, object)

    def __init__(self, parent: Optional[QObject] = None, logger: Optional[logging.Logger] = None) -> None:
        super().__init__(parent)
        self._logger = logger or logging.getLogger(__name__)
        self._rate_fetch_in_progress = False
        self._timer: Optional[QTimer] = None

    def start(self) -> None:
        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        if not self._timer:
            self._timer = QTimer(self)
            self._timer.setSingleShot(False)
            self._timer.timeout.connect(self.refresh_now)
        interval_sec = int(settings.value("rates/refresh_interval_sec", 60))
        interval_ms = max(5, interval_sec) * 1000
        self._timer.setInterval(interval_ms)
        raw_enabled = settings.value("rates/auto_refresh_enabled", True)
        if isinstance(raw_enabled, bool):
            auto_enabled = raw_enabled
        elif isinstance(raw_enabled, str):
            auto_enabled = raw_enabled.strip().lower() in ("1", "true", "yes", "on")
        else:
            auto_enabled = True
        if auto_enabled:
            if not self._timer.isActive():
                self._timer.start()
                self._logger.info("Live-rate timer started: every %s ms", interval_ms)
        else:
            self.stop()

    def stop(self) -> None:
        if self._timer and self._timer.isActive():
            self._timer.stop()
            self._logger.info("Live-rate timer disabled via settings")

    def refresh_now(self) -> None:
        settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
        if not settings.value("rates/live_enabled", True, type=bool):
            return
        if self._rate_fetch_in_progress:
            return
        self._rate_fetch_in_progress = True
        self._logger.info("Live-rate fetch started")

        def _worker():
            try:
                brate, is_open, _ = fetch_broadcast_rate_exact(timeout=5)
                api_rate = None
                if brate is None:
                    api_rate, _ = fetch_silver_agra_local_mohar_rate(timeout=5)
                self._logger.info(
                    "LiveRate fetch: broadcast=%s, open=%s, api=%s",
                    brate,
                    is_open,
                    api_rate,
                )
            except Exception as exc:
                self._logger.warning("Rate fetch error (broadcast): %s", exc)
                brate, is_open = None, True
                try:
                    api_rate, _ = fetch_silver_agra_local_mohar_rate(timeout=5)
                except Exception as fallback_exc:
                    self._logger.warning("Rate fetch error (API fallback): %s", fallback_exc)
                    api_rate = None
            self.rate_updated.emit(brate, api_rate, is_open)
            self._rate_fetch_in_progress = False

        threading.Thread(target=_worker, daemon=True).start()
