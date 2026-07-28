"""Responsive print-preview workspace around Qt's embeddable preview widget."""

from __future__ import annotations

from PySide6.QtGui import QBrush, QColor
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewWidget
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .theme_tokens import CARD_BORDER, PAGE_BG


class PrintPreviewDialog(QDialog):
    """Own a single preview toolbar and the document canvas."""

    def __init__(
        self,
        printer: QPrinter,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PrintPreviewDialog")
        self.setModal(True)
        self.setSizeGripEnabled(True)
        self.setMinimumSize(760, 540)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.primary_toolbar = QToolBar(self)
        self.primary_toolbar.setObjectName("PrintPreviewToolbar")
        self.toolbar = self.primary_toolbar
        layout.addWidget(self.primary_toolbar)

        self.preview_widget = QPrintPreviewWidget(printer, self)
        self.preview_widget.setObjectName("PrintPreviewCanvas")
        graphics_view = self.preview_widget.findChild(QGraphicsView)
        if graphics_view is not None:
            graphics_view.setBackgroundBrush(QBrush(QColor("#e5e7eb")))
        layout.addWidget(self.preview_widget, 1)

        self.setStyleSheet(f"""
            QDialog#PrintPreviewDialog {{
                background-color: {PAGE_BG};
            }}
            QPrintPreviewWidget#PrintPreviewCanvas {{
                background-color: #e5e7eb;
                border-top: 1px solid {CARD_BORDER};
            }}
            """)


__all__ = ["PrintPreviewDialog"]
