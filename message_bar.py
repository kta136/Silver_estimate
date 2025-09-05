#!/usr/bin/env python
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QFrame
from PyQt5.QtCore import Qt, QTimer


class MessageBar(QFrame):
    """A simple top-of-window message bar with auto-hide.

    Use show_message(text, timeout_ms=3000, level='info') to display messages.
    Levels: 'info', 'warning', 'error' (affects styling only).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setObjectName("MessageBar")

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(10, 6, 10, 6)
        self._layout.setSpacing(8)

        self._label = QLabel("")
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(22, 22)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.clicked.connect(self.hide)
        self._close_btn.setToolTip("Dismiss message")

        self._layout.addWidget(self._label, 1)
        self._layout.addWidget(self._close_btn, 0, Qt.AlignRight)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        # Start hidden
        self.hide()

        # Basic stylesheet; can be overridden by app theme
        self._styles = {
            'info':    "background:#e6f4ff; color:#084b83; border:1px solid #b6e0fe; border-radius:4px;",
            'warning': "background:#fff7e6; color:#8a6d3b; border:1px solid #ffe0a3; border-radius:4px;",
            'error':   "background:#fdecea; color:#a61b1b; border:1px solid #f5c2c0; border-radius:4px;",
        }

    def show_message(self, text: str, timeout_ms: int = 3000, level: str = 'info'):
        level = (level or 'info').lower()
        if level not in self._styles:
            level = 'info'
        self.setStyleSheet(self._styles[level])
        self._label.setText(text or "")
        self.show()

        self._timer.stop()
        if isinstance(timeout_ms, int) and timeout_ms > 0:
            self._timer.start(timeout_ms)

