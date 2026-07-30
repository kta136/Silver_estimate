"""Qt lifecycle wrapper for the DDA HTTPS/SSE live-rate worker."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal

from silverestimate.infrastructure.settings import (
    SettingsKey,
    SettingsReader,
    as_settings_reader,
    get_app_settings,
)
from silverestimate.services.dda_rate_stream import DdaRateStreamWorker


class LiveRateService(QObject):
    """Own exactly one cooperative DDA stream worker and its Qt thread."""

    rate_updated = Signal(object)
    feed_status_updated = Signal(object)
    connection_state_changed = Signal(str)
    stream_error = Signal(str)

    def __init__(
        self,
        parent: QObject | None = None,
        logger: logging.Logger | None = None,
        settings_provider: Callable[[], SettingsReader] = get_app_settings,
        worker_factory: Callable[..., DdaRateStreamWorker] = DdaRateStreamWorker,
        thread_factory: Callable[..., QThread] = QThread,
    ) -> None:
        super().__init__(parent)
        self._logger = logger or logging.getLogger(__name__)
        self._settings_provider = settings_provider
        self._worker_factory = worker_factory
        self._thread_factory = thread_factory
        self._worker: DdaRateStreamWorker | None = None
        self._thread: QThread | None = None

    def start(self) -> None:
        settings = as_settings_reader(self._settings_provider())
        if not settings.get_bool(SettingsKey.RATES_LIVE_ENABLED, True):
            return
        if self._thread is not None and self._thread.isRunning():
            return

        worker = self._worker_factory(logger=self._logger)
        thread = self._thread_factory(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.rate_received.connect(self.rate_updated.emit)
        worker.feed_status_received.connect(self.feed_status_updated.emit)
        worker.connection_state_changed.connect(self.connection_state_changed.emit)
        worker.stream_error.connect(self.stream_error.emit)
        self._worker = worker
        self._thread = thread
        thread.start()

    def stop(self) -> None:
        worker = self._worker
        thread = self._thread
        if worker is not None:
            worker.stop()
        if thread is not None:
            thread.quit()
            if thread.isRunning() and not thread.wait(6000):
                self._logger.warning("DDA SSE worker did not stop within 6 seconds.")
        if worker is not None:
            for signal in (
                worker.rate_received,
                worker.feed_status_received,
                worker.connection_state_changed,
                worker.stream_error,
            ):
                with contextlib.suppress(TypeError):
                    signal.disconnect()
        self._worker = None
        self._thread = None

    def refresh_now(self) -> None:
        settings = as_settings_reader(self._settings_provider())
        if not settings.get_bool(SettingsKey.RATES_LIVE_ENABLED, True):
            return
        was_running = self._thread is not None and self._thread.isRunning()
        self.start()
        if was_running and self._worker is not None:
            self._worker.request_refresh()


__all__ = ["LiveRateService"]
