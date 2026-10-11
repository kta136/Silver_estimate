"""Qt lifecycle wrapper for the DDA HTTPS/SSE live-rate stream."""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from silverestimate.infrastructure.settings import (
    SettingsKey,
    SettingsReader,
    as_settings_reader,
    get_app_settings,
)
from silverestimate.services.dda_rate_stream import DdaRateStream


class LiveRateService(QObject):
    """Own exactly one DDA rate stream on the caller's thread."""

    rate_updated = Signal(object)
    feed_status_updated = Signal(object)
    connection_state_changed = Signal(str)
    stream_error = Signal(str)

    def __init__(
        self,
        parent: QObject | None = None,
        logger: logging.Logger | None = None,
        settings_provider: Callable[[], SettingsReader] = get_app_settings,
        stream_factory: Callable[..., DdaRateStream] = DdaRateStream,
    ) -> None:
        super().__init__(parent)
        self._logger = logger or logging.getLogger(__name__)
        self._settings_provider = settings_provider
        self._stream_factory = stream_factory
        self._stream: DdaRateStream | None = None

    def start(self) -> None:
        settings = as_settings_reader(self._settings_provider())
        if not settings.get_bool(SettingsKey.RATES_LIVE_ENABLED, True):
            return
        if self._stream is not None:
            return

        stream = self._stream_factory(logger=self._logger, parent=self)
        stream.rate_received.connect(self.rate_updated.emit)
        stream.feed_status_received.connect(self.feed_status_updated.emit)
        stream.connection_state_changed.connect(self.connection_state_changed.emit)
        stream.stream_error.connect(self.stream_error.emit)
        self._stream = stream
        stream.start()

    def stop(self) -> None:
        stream, self._stream = self._stream, None
        if stream is None:
            return
        stream.stop()
        for signal in (
            stream.rate_received,
            stream.feed_status_received,
            stream.connection_state_changed,
            stream.stream_error,
        ):
            with contextlib.suppress(TypeError, RuntimeError):
                signal.disconnect()
        stream.deleteLater()

    def refresh_now(self) -> None:
        settings = as_settings_reader(self._settings_provider())
        if not settings.get_bool(SettingsKey.RATES_LIVE_ENABLED, True):
            return
        stream = self._stream
        if stream is None:
            self.start()
        else:
            stream.request_refresh()


__all__ = ["LiveRateService"]
