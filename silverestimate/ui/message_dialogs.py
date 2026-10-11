"""Confirmation dialogs, prompts and error wording shared by every screen.

A confirmation names what its button does ("Delete Item", not "Yes"), a
destructive one defaults to Cancel, and an unexpected error is described in
plain words with the technical reason kept as a detail line.

Every dialog here carries its own stylesheet. A dialog otherwise inherits the
stylesheet of the screen that opened it, and the same question would look
different from the estimate screen, Settings and the silver bar window. The
rule the buttons follow: the one that does the thing is coloured (teal, or red
when it destroys something), the one that backs out is plain, and the keyboard
default, shown by the focus ring, is whichever is safest.
"""

from __future__ import annotations

from html import escape
from typing import Literal, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .confirmation_layout import polish_confirmation
from .theme_tokens import apply_theme_tokens

# Dynamic property the stylesheet reads to colour a button.
BUTTON_ROLE = "dialogRole"
ROLE_PRIMARY = "primary"
ROLE_DANGER = "danger"
ROLE_DANGER_OUTLINE = "danger-outline"
ROLE_NEUTRAL = "neutral"

SaveChoice = Literal["save", "discard", "cancel"]

_STYLE = """
QMessageBox, QDialog#TextPromptDialog {
    background-color: __PAGE_BG__;
}
QLabel {
    background: transparent;
    color: __TEXT_STRONG__;
    font-size: %(body)spt;
    font-weight: 400;
}
QLabel#qt_msgbox_label, QLabel#TextPromptHeading {
    font-size: %(heading)spt;
    font-weight: 700;
}
QLabel#TextPromptDetail {
    color: __FIELD_TEXT__;
}
QCheckBox {
    color: __TEXT_STRONG__;
    font-size: %(body)spt;
    spacing: 8px;
}
QLineEdit {
    background-color: __SURFACE_BG__;
    border: 1px solid __INPUT_BORDER__;
    border-radius: 5px;
    color: __TEXT_STRONG__;
    font-size: %(body)spt;
    min-height: 22px;
    padding: 5px 8px;
    selection-background-color: __SELECTION_BG__;
    selection-color: __TEXT_STRONG__;
}
QLineEdit:focus {
    border: 1px solid __FOCUS_RING__;
}
QPushButton {
    background-color: __SURFACE_BG__;
    border: 1px solid __INPUT_BORDER__;
    border-radius: 5px;
    color: __TEXT_STRONG__;
    font-size: %(body)spt;
    font-weight: 600;
    min-height: 18px;
    padding: 8px 16px;
}
QPushButton:hover {
    background-color: __HEADER_BG__;
    border-color: __HEADER_TEXT__;
}
QPushButton:focus {
    border: 2px solid __FOCUS_RING__;
    padding: 7px 15px;
}
QPushButton[dialogRole="primary"] {
    background-color: __PRIMARY_BG__;
    border-color: __PRIMARY_BG__;
    color: #ffffff;
}
QPushButton[dialogRole="primary"]:hover {
    background-color: __PRIMARY_BG_HOVER__;
    border-color: __PRIMARY_BG_HOVER__;
}
QPushButton[dialogRole="primary"]:focus {
    border: 2px solid __PRIMARY_BG_PRESSED__;
}
QPushButton[dialogRole="danger"] {
    background-color: #c72735;
    border-color: #c72735;
    color: #ffffff;
}
QPushButton[dialogRole="danger"]:hover {
    background-color: #a91e2c;
    border-color: #a91e2c;
}
QPushButton[dialogRole="danger"]:focus {
    border: 2px solid #7f1420;
}
QPushButton[dialogRole="danger-outline"] {
    border-color: #dc2638;
    color: #b91c1c;
}
QPushButton[dialogRole="danger-outline"]:hover {
    background-color: __DANGER_BG__;
    border-color: #b91c1c;
}
QPushButton:disabled {
    background-color: __CARD_BORDER_SOFT__;
    border-color: __CARD_BORDER__;
    color: #8a94a3;
}
"""


def dialog_stylesheet() -> str:
    """Return the look every dialog in this module shares.

    Sizes follow the interface font chosen in Settings rather than a fixed
    point size.
    """
    app = QApplication.instance()
    size = cast(QApplication, app).font().pointSizeF() if app is not None else 0.0
    if size <= 0:
        size = 9.0
    return apply_theme_tokens(
        _STYLE % {"body": f"{size:g}", "heading": f"{size + 1.5:g}"}
    )


def set_button_role(button: QPushButton, role: str) -> None:
    button.setProperty(BUTTON_ROLE, role)


def style_message_box(dialog: QMessageBox) -> None:
    """Give a message box the shared look and font-aware button widths."""
    dialog.setStyleSheet(dialog_stylesheet())
    polish_confirmation(dialog)


def _run_dialog(dialog: QMessageBox) -> None:
    """Show ``dialog`` modally. Tests replace this to answer without a window."""
    dialog.exec()


def _run_prompt(dialog: TextPromptDialog) -> bool:
    """Show a text prompt modally; True when its action button was used.

    Tests replace this to type an answer without a window.
    """
    return dialog.exec() == QDialog.DialogCode.Accepted


def _message_box(
    parent: QWidget | None,
    title: str,
    heading: str,
    detail: str,
    icon: QMessageBox.Icon | None = None,
) -> QMessageBox:
    dialog = QMessageBox(parent)
    dialog.setWindowTitle(title)
    dialog.setText(f"<b>{escape(heading)}</b>")
    if detail:
        dialog.setInformativeText(detail)
    if icon is not None:
        dialog.setIcon(icon)
    return dialog


def _confirm(  # noqa: PLR0913 - one keyword per visible part of the dialog
    dialog: QMessageBox,
    *,
    action_label: str,
    cancel_label: str,
    destructive: bool,
    default_to_cancel: bool,
) -> bool:
    dialog.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
    )
    action = cast(QPushButton, dialog.button(QMessageBox.StandardButton.Yes))
    cancel = cast(QPushButton, dialog.button(QMessageBox.StandardButton.Cancel))
    action.setText(action_label)
    cancel.setText(cancel_label)
    set_button_role(action, ROLE_DANGER if destructive else ROLE_PRIMARY)
    set_button_role(cancel, ROLE_NEUTRAL)
    # A destructive action must be chosen, never reached by pressing Enter.
    dialog.setDefaultButton(cancel if destructive or default_to_cancel else action)
    dialog.setEscapeButton(cancel)
    style_message_box(dialog)
    try:
        _run_dialog(dialog)
        return dialog.clickedButton() is action
    finally:
        dialog.deleteLater()


def ask(  # noqa: PLR0913 - one keyword per visible part of the dialog
    parent: QWidget | None,
    *,
    title: str,
    heading: str,
    detail: str = "",
    action_label: str,
    cancel_label: str = "Cancel",
    destructive: bool = False,
    default_to_cancel: bool = False,
    icon: QMessageBox.Icon | None = None,
) -> bool:
    """Ask the user to confirm ``action_label``; return True when they do."""
    return _confirm(
        _message_box(parent, title, heading, detail, icon),
        action_label=action_label,
        cancel_label=cancel_label,
        destructive=destructive,
        default_to_cancel=default_to_cancel,
    )


def confirm_destructive(  # noqa: PLR0913 - mirrors ``ask``
    parent: QWidget | None,
    *,
    title: str,
    heading: str,
    detail: str = "",
    action_label: str,
    cancel_label: str = "Cancel",
) -> bool:
    """Confirm a deletion or other change that cannot be undone."""
    return ask(
        parent,
        title=title,
        heading=heading,
        detail=detail,
        action_label=action_label,
        cancel_label=cancel_label,
        destructive=True,
    )


def ask_with_option(  # noqa: PLR0913 - one keyword per visible part of the dialog
    parent: QWidget | None,
    *,
    title: str,
    heading: str,
    detail: str = "",
    option_label: str,
    action_label: str,
    cancel_label: str = "Cancel",
    default_to_cancel: bool = True,
) -> tuple[bool, bool]:
    """Confirm ``action_label`` with one tick box.

    Returns whether the user confirmed and whether the box was ticked.
    """
    dialog = _message_box(parent, title, heading, detail)
    option = QCheckBox(option_label, dialog)
    dialog.setCheckBox(option)
    confirmed = _confirm(
        dialog,
        action_label=action_label,
        cancel_label=cancel_label,
        destructive=False,
        default_to_cancel=default_to_cancel,
    )
    return confirmed, confirmed and option.isChecked()


def ask_save_discard(  # noqa: PLR0913 - one keyword per visible part of the dialog
    parent: QWidget | None,
    *,
    title: str,
    heading: str,
    detail: str = "",
    save_label: str = "Save",
    discard_label: str = "Discard",
    cancel_label: str = "Cancel",
) -> SaveChoice:
    """Ask what to do with unsaved work before moving on.

    Enter goes to Cancel: it loses nothing and leaves the work as it is.
    """
    dialog = _message_box(parent, title, heading, detail)
    dialog.setStandardButtons(
        QMessageBox.StandardButton.Save
        | QMessageBox.StandardButton.Discard
        | QMessageBox.StandardButton.Cancel
    )
    save = cast(QPushButton, dialog.button(QMessageBox.StandardButton.Save))
    discard = cast(QPushButton, dialog.button(QMessageBox.StandardButton.Discard))
    cancel = cast(QPushButton, dialog.button(QMessageBox.StandardButton.Cancel))
    save.setText(save_label)
    discard.setText(discard_label)
    cancel.setText(cancel_label)
    set_button_role(save, ROLE_PRIMARY)
    set_button_role(discard, ROLE_DANGER_OUTLINE)
    set_button_role(cancel, ROLE_NEUTRAL)
    dialog.setDefaultButton(cancel)
    dialog.setEscapeButton(cancel)
    style_message_box(dialog)
    try:
        _run_dialog(dialog)
        clicked = dialog.clickedButton()
        return (
            "save" if clicked is save else "discard" if clicked is discard else "cancel"
        )
    finally:
        dialog.deleteLater()


class TextPromptDialog(QDialog):
    """Ask for one line of text, in the same style as the confirmations."""

    def __init__(  # noqa: PLR0913 - one keyword per visible part of the dialog
        self,
        parent: QWidget | None,
        *,
        title: str,
        heading: str,
        detail: str = "",
        text: str = "",
        placeholder: str = "",
        action_label: str,
        cancel_label: str = "Cancel",
        destructive: bool = False,
        required_text: str | None = None,
        password: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("TextPromptDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self._required_text = (required_text or "").strip().upper()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        heading_label = QLabel(heading, self)
        heading_label.setObjectName("TextPromptHeading")
        heading_label.setWordWrap(True)
        layout.addWidget(heading_label)

        if detail:
            detail_label = QLabel(detail, self)
            detail_label.setObjectName("TextPromptDetail")
            detail_label.setWordWrap(True)
            layout.addWidget(detail_label)

        self.input = QLineEdit(self)
        self.input.setObjectName("TextPromptInput")
        self.input.setAccessibleName(heading)
        self.input.setPlaceholderText(placeholder)
        if password:
            self.input.setEchoMode(QLineEdit.EchoMode.Password)
        self.input.setText(text)
        self.input.selectAll()
        layout.addWidget(self.input)
        layout.addSpacing(6)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)
        self.action_button = QPushButton(action_label, self)
        set_button_role(
            self.action_button, ROLE_DANGER if destructive else ROLE_PRIMARY
        )
        self.cancel_button = QPushButton(cancel_label, self)
        set_button_role(self.cancel_button, ROLE_NEUTRAL)
        buttons.addWidget(self.action_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

        # Enter in the field uses the action button once it is allowed.
        self.action_button.setDefault(True)
        self.cancel_button.setAutoDefault(False)
        self.action_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.input.textChanged.connect(self._sync_action)
        self._sync_action()

        self.setStyleSheet(dialog_stylesheet())
        self.setMinimumWidth(420)
        self.input.setFocus(Qt.FocusReason.OtherFocusReason)

    def _sync_action(self) -> None:
        self.action_button.setEnabled(self.is_acceptable())

    def is_acceptable(self) -> bool:
        """False while a required word has not been typed."""
        if not self._required_text:
            return True
        return self.input.text().strip().upper() == self._required_text

    def value(self) -> str:
        return self.input.text()

    def accept(self) -> None:
        if self.is_acceptable():
            super().accept()


def ask_text(  # noqa: PLR0913 - one keyword per visible part of the dialog
    parent: QWidget | None,
    *,
    title: str,
    heading: str,
    detail: str = "",
    text: str = "",
    placeholder: str = "",
    action_label: str,
    cancel_label: str = "Cancel",
    destructive: bool = False,
    required_text: str | None = None,
    password: bool = False,
) -> str | None:
    """Ask for one line of text; None when the user backs out.

    With ``required_text`` the action button stays off until that word is
    typed, which is how a mass deletion is confirmed a second time.
    """
    dialog = TextPromptDialog(
        parent,
        title=title,
        heading=heading,
        detail=detail,
        text=text,
        placeholder=placeholder,
        action_label=action_label,
        cancel_label=cancel_label,
        destructive=destructive,
        required_text=required_text,
        password=password,
    )
    try:
        if _run_prompt(dialog) and dialog.is_acceptable():
            return dialog.value()
        return None
    finally:
        dialog.deleteLater()


def confirm_by_typing(  # noqa: PLR0913 - mirrors ``ask_text``
    parent: QWidget | None,
    *,
    title: str,
    heading: str,
    detail: str = "",
    action_label: str,
    word: str = "DELETE",
) -> bool:
    """Second step of a mass deletion: the user types ``word`` to go on."""
    return (
        ask_text(
            parent,
            title=title,
            heading=heading,
            detail=detail,
            placeholder=word,
            action_label=action_label,
            destructive=True,
            required_text=word,
        )
        is not None
    )


def with_details(summary: str, error: object) -> str:
    """Return ``summary`` followed by the technical reason, when there is one."""
    reason = str(error or "").strip()
    if not reason or reason in summary:
        return summary
    return f"{summary}\n\nDetails: {reason}"


__all__ = [
    "ROLE_DANGER",
    "ROLE_DANGER_OUTLINE",
    "ROLE_NEUTRAL",
    "ROLE_PRIMARY",
    "SaveChoice",
    "TextPromptDialog",
    "ask",
    "ask_save_discard",
    "ask_text",
    "ask_with_option",
    "confirm_by_typing",
    "confirm_destructive",
    "dialog_stylesheet",
    "set_button_role",
    "style_message_box",
    "with_details",
]
