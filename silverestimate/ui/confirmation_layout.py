"""Font-aware sizing for compact confirmation messages."""

from PySide6.QtWidgets import QLabel, QMessageBox


def polish_confirmation(dialog: QMessageBox) -> None:
    dialog.ensurePolished()
    for button in dialog.buttons():
        button.ensurePolished()
        caption = button.text().replace("&&", "&")
        width = button.fontMetrics().horizontalAdvance(caption) + 40
        style = button.styleSheet()
        if style and "{" not in style:
            style = "QPushButton { " + style + " }"
        button.setStyleSheet(style + f"\nQPushButton {{ min-width: {width}px; }}")
    body = dialog.findChild(QLabel, "qt_msgbox_informativelabel")
    if body is not None:
        body.setMinimumWidth(380)
    heading = dialog.findChild(QLabel, "qt_msgbox_label")
    if heading is not None:
        font = heading.font()
        font.setPointSize(max(14, font.pointSize()))
        font.setBold(True)
        heading.setFont(font)
    dialog.layout().setContentsMargins(24, 20, 24, 20)
