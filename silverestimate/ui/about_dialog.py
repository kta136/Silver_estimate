"""The About window: name, version, licence and a link to the source."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from silverestimate.infrastructure.app_constants import APP_NAME, APP_VERSION
from silverestimate.infrastructure.paths import get_asset_path

from .message_dialogs import ROLE_PRIMARY, dialog_stylesheet, set_button_role

PROJECT_URL = "https://github.com/kta136/Silver_estimate"

_STYLE = """
QDialog#AboutDialog { background-color: #f7f8fa; }
QLabel#AboutName { font-size: 14pt; font-weight: 700; }
QLabel#AboutVersion, QLabel#AboutNotice { color: #475569; }
QLabel#AboutLink a { color: #006d77; }
"""


class AboutDialog(QDialog):
    """Say what the app is, under which licence, and where its source lives."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AboutDialog")
        self.setWindowTitle(f"About {APP_NAME}")
        self.setModal(True)
        self.setStyleSheet(dialog_stylesheet() + _STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 22, 24, 18)
        outer.setSpacing(16)

        top = QHBoxLayout()
        top.setSpacing(16)
        icon_path = get_asset_path("assets", "icons", "silverestimate.png")
        if icon_path.exists():
            icon = QLabel(self)
            icon.setPixmap(QIcon(str(icon_path)).pixmap(56, 56))
            icon.setFixedSize(56, 56)
            top.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(4)
        self.name_label = self._label(APP_NAME, "AboutName")
        self.version_label = self._label(f"Version {APP_VERSION}", "AboutVersion")
        text.addWidget(self.name_label)
        text.addWidget(self.version_label)
        text.addSpacing(8)
        text.addWidget(
            self._label(
                "Estimates, the item catalog and silver bar lists for a silver shop.",
                wrap=True,
            )
        )
        text.addSpacing(8)
        text.addWidget(
            self._label(
                "© 2023–2026 Silver Estimation App. Free software under "
                "the GNU General Public License v3.0 only, with no warranty.",
                "AboutNotice",
                wrap=True,
            )
        )
        text.addWidget(
            self._label(
                "Built with Qt (PySide6, LGPL) and other open-source components. "
                "LICENSE and THIRD_PARTY_NOTICES.md are supplied with the app.",
                "AboutNotice",
                wrap=True,
            )
        )
        text.addSpacing(8)
        # One unbroken, clickable line: an address split across two lines can
        # be neither read nor copied reliably.
        self.link_label = self._label(
            f'Source code: <a href="{PROJECT_URL}">{PROJECT_URL}</a>', "AboutLink"
        )
        self.link_label.setTextFormat(Qt.TextFormat.RichText)
        self.link_label.setOpenExternalLinks(True)
        self.link_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        text.addWidget(self.link_label)
        top.addLayout(text, 1)
        outer.addLayout(top)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.close_button = QPushButton("Close", self)
        set_button_role(self.close_button, ROLE_PRIMARY)
        self.close_button.setDefault(True)
        self.close_button.clicked.connect(self.accept)
        buttons.addWidget(self.close_button)
        outer.addLayout(buttons)

        self.setMinimumWidth(520)

    def _label(self, text: str, name: str = "", *, wrap: bool = False) -> QLabel:
        label = QLabel(text, self)
        if name:
            label.setObjectName(name)
        label.setWordWrap(wrap)
        return label

    def text(self) -> str:
        """Everything the window says, for tests and screen readers."""
        return "\n".join(
            label.text() for label in self.findChildren(QLabel) if label.text()
        )


__all__ = ["PROJECT_URL", "AboutDialog"]
