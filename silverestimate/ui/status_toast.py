"""A brief status message shown over the bottom of a window.

Screens report what just happened ("Estimate 12 saved", "Row 3 deleted") without
a message box. The toast floats above the content, so it takes no room from the
tables, lets clicks through, and clears itself.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget

from .theme_tokens import apply_theme_tokens

_BOTTOM_MARGIN = 18
_SIDE_MARGIN = 24
# The stylesheet's left and right padding, plus a little slack for bold text.
_HORIZONTAL_PADDING = 2 * 14 + 8

_STYLE = apply_theme_tokens(
    """
QLabel#StatusToast {
    background-color: __TEXT_STRONG__;
    border-radius: 6px;
    color: __SURFACE_BG__;
    font-weight: 600;
    padding: 8px 14px;
}
QLabel#StatusToast[statusLevel="warning"] { background-color: __WARNING_TEXT__; }
QLabel#StatusToast[statusLevel="error"] { background-color: #991b1b; }
"""
)


class StatusToast(QLabel):
    """Show one transient message at the bottom centre of ``host``."""

    def __init__(self, host: QWidget) -> None:
        super().__init__(host)
        self._host = host
        self.setObjectName("StatusToast")
        self.setAccessibleName("Status message")
        self.setStyleSheet(_STYLE)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        # Never in the way of the table or buttons underneath.
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.clear_message)
        host.installEventFilter(self)
        self.hide()

    def show_message(
        self, message: str, timeout: int = 3000, level: str = "info"
    ) -> None:
        """Display ``message`` for ``timeout`` ms; an empty message clears it."""
        text = str(message or "").strip()
        self._timer.stop()
        if not text:
            self.clear_message()
            return
        normalized = (level or "info").lower()
        if self.property("statusLevel") != normalized:
            self.setProperty("statusLevel", normalized)
            style = self.style()
            style.unpolish(self)
            style.polish(self)
        self.setText(text)
        # Until the first show the theme's font and padding are not applied,
        # and a toast measured without them is too short for its own text.
        self.ensurePolished()
        self._place()
        self.show()
        self.raise_()
        if isinstance(timeout, int) and timeout > 0:
            self._timer.start(timeout)

    def clear_message(self) -> None:
        self._timer.stop()
        self.clear()
        self.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            watched is self._host
            and event.type() == QEvent.Type.Resize
            and self.isVisible()
        ):
            self._place()
        return super().eventFilter(watched, event)

    def _place(self) -> None:
        available = max(120, self._host.width() - 2 * _SIDE_MARGIN)
        self.setMaximumWidth(available)
        # One line when the window has room for it; a wrapping label would
        # otherwise ask for a narrow column and break short messages in two.
        one_line = (
            self.fontMetrics().horizontalAdvance(self.text()) + _HORIZONTAL_PADDING
        )
        width = min(one_line, available)
        height = self.heightForWidth(width) if self.hasHeightForWidth() else -1
        if height <= 0:
            height = self.sizeHint().height()
        self.setGeometry(
            max(_SIDE_MARGIN, (self._host.width() - width) // 2),
            max(0, self._host.height() - height - _BOTTOM_MARGIN),
            width,
            height,
        )


__all__ = ["StatusToast"]
