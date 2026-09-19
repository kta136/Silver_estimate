"""Keep compact command rows reachable on smaller desktops."""

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import QFrame, QScrollArea, QSizePolicy, QStyle, QWidget


class ToolbarOverflow(QScrollArea):
    def __init__(self, content, parent=None):
        super().__init__(parent)
        if not isinstance(content, QWidget):
            widget = QWidget()
            widget.setLayout(content)
            content = widget
        self.setWidget(content)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._sync_height)
        content.installEventFilter(self)
        self._sync_height()

    def _sync_height(self):
        content = self.widget()
        overflow = content.minimumSizeHint().width() > self.width()
        extra = (
            self.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
            if overflow
            else 0
        )
        self.setFixedHeight(content.sizeHint().height() + extra)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_height()

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.LayoutRequest, QEvent.Type.FontChange):
            self._resize_timer.start(0)
        return super().eventFilter(watched, event)
