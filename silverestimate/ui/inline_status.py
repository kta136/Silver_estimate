"""Inline status message helper for UI widgets."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from PyQt5 import sip
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QLabel


class InlineStatusController:
    """Manage transient inline status messages on a QLabel."""

    def __init__(
        self,
        *,
        parent,
        label_getter: Callable[[], Optional[QLabel]],
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._label_getter = label_getter
        self._logger = logger or logging.getLogger(__name__)
        self._timer = QTimer(parent)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.clear)

    @staticmethod
    def _qt_object_available(obj: Any) -> bool:
        try:
            return not sip.isdeleted(obj)
        except TypeError:
            return obj is not None
        except RuntimeError:
            return False

    def show(self, message: str, *, timeout: int = 3000, level: str = "info") -> None:
        label = self._label_getter()
        if label is None:
            self._logger.info("Status: %s", message)
            return

        color = {
            "info": "#2b6cb0",
            "warning": "#8a6d3b",
            "error": "#a61b1b",
        }.get((level or "info").lower(), "#2b6cb0")

        try:
            label.setStyleSheet(f"color: {color}; padding-left: 8px;")
            label.setText(message or "")
        except Exception:
            self._logger.debug("Could not update inline status label", exc_info=True)

        if not self._qt_object_available(self._timer):
            return

        try:
            self._timer.stop()
            if isinstance(timeout, int) and timeout > 0:
                self._timer.start(timeout)
        except RuntimeError:
            return

    def clear(self) -> None:
        if not self._qt_object_available(self._timer):
            return
        try:
            self._timer.stop()
        except RuntimeError:
            return
        label = self._label_getter()
        if label is None:
            return
        try:
            label.setText("")
        except Exception:
            self._logger.debug("Could not clear inline status label", exc_info=True)
