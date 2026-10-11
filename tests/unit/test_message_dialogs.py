"""The confirmations and prompts every screen shares."""

import pytest
from PySide6.QtWidgets import QDialog, QLineEdit, QWidget

from silverestimate.ui import message_dialogs
from silverestimate.ui.message_dialogs import (
    BUTTON_ROLE,
    TextPromptDialog,
    ask,
    ask_save_discard,
    ask_text,
    ask_with_option,
    confirm_by_typing,
    confirm_destructive,
    dialog_stylesheet,
)


def _answer_with(monkeypatch, press, *, tick=None):
    """Press the button named ``press`` and record how each dialog looked."""
    seen = []

    def run(dialog):
        if tick is not None:
            dialog.checkBox().setChecked(tick)
        buttons = {button.text(): button for button in dialog.buttons()}
        seen.append(
            {
                "style": dialog.styleSheet(),
                "roles": {
                    text: button.property(BUTTON_ROLE)
                    for text, button in buttons.items()
                },
                "default": dialog.defaultButton().text(),
                "escape": dialog.escapeButton().text(),
            }
        )
        buttons[press].click()

    monkeypatch.setattr(message_dialogs, "_run_dialog", run)
    return seen


def test_a_confirmation_looks_the_same_whichever_screen_opens_it(qtbot, monkeypatch):
    plain, styled = QWidget(), QWidget()
    # A screen that styles its own buttons must not restyle the dialog.
    styled.setStyleSheet(
        "QPushButton { background: green; } QLabel { font-size: 30pt; }"
    )
    for parent in (plain, styled):
        qtbot.addWidget(parent)
    seen = _answer_with(monkeypatch, "Cancel")

    for parent in (plain, styled):
        assert not confirm_destructive(
            parent,
            title="Delete Item",
            heading="Delete item RING001?",
            action_label="Delete Item",
        )

    assert seen[0] == seen[1]
    assert seen[0]["style"] == dialog_stylesheet()
    # The action is red and Enter never reaches it.
    assert seen[0]["roles"] == {"Delete Item": "danger", "Cancel": "neutral"}
    assert seen[0]["default"] == seen[0]["escape"] == "Cancel"


@pytest.mark.parametrize(
    ("default_to_cancel", "default"), [(False, "Reopen List"), (True, "Cancel")]
)
def test_a_harmless_confirmation_colours_the_action(
    qtbot, monkeypatch, default_to_cancel, default
):
    parent = QWidget()
    qtbot.addWidget(parent)
    seen = _answer_with(monkeypatch, "Reopen List")

    assert ask(
        parent,
        title="Reopen Issued List",
        heading="Reopen the list?",
        action_label="Reopen List",
        default_to_cancel=default_to_cancel,
    )

    assert seen[0]["roles"] == {"Reopen List": "primary", "Cancel": "neutral"}
    assert seen[0]["default"] == default


@pytest.mark.parametrize("choice", ["Save", "Discard", "Cancel"])
def test_unsaved_work_prompt_offers_three_named_choices(qtbot, monkeypatch, choice):
    parent = QWidget()
    qtbot.addWidget(parent)
    seen = _answer_with(monkeypatch, choice)

    answer = ask_save_discard(
        parent, title="Unsaved Estimate", heading="Save this estimate first?"
    )

    assert answer == choice.lower()
    assert seen[0]["roles"] == {
        "Save": "primary",
        "Discard": "danger-outline",
        "Cancel": "neutral",
    }
    # Enter loses nothing: it backs out and keeps the work as it is.
    assert seen[0]["default"] == seen[0]["escape"] == "Cancel"


@pytest.mark.parametrize(
    ("press", "tick", "expected"),
    [
        ("Restore Catalog", True, (True, True)),
        ("Restore Catalog", False, (True, False)),
        ("Cancel", True, (False, False)),
    ],
)
def test_a_ticked_option_counts_only_when_confirmed(
    qtbot, monkeypatch, press, tick, expected
):
    parent = QWidget()
    qtbot.addWidget(parent)
    _answer_with(monkeypatch, press, tick=tick)

    assert (
        ask_with_option(
            parent,
            title="Restore Item Catalog",
            heading="Restore the item catalog from this backup?",
            option_label="Also remove items that are not in the backup",
            action_label="Restore Catalog",
        )
        == expected
    )


def test_typed_confirmation_keeps_its_button_off_until_the_word_is_typed(qtbot):
    dialog = TextPromptDialog(
        None,
        title="Delete All Data",
        heading="Type DELETE to delete all data",
        action_label="Delete All Data",
        destructive=True,
        required_text="DELETE",
    )
    qtbot.addWidget(dialog)

    assert dialog.styleSheet() == dialog_stylesheet()
    assert dialog.action_button.property(BUTTON_ROLE) == "danger"
    assert not dialog.action_button.isEnabled()
    dialog.input.setText("delet")
    assert not dialog.action_button.isEnabled()
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted

    dialog.input.setText(" delete ")
    assert dialog.action_button.isEnabled()
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_a_password_prompt_hides_what_is_typed(qtbot):
    dialog = TextPromptDialog(
        None,
        title="Backup Password",
        heading="Main password of this backup",
        action_label="Check Backup",
        password=True,
    )
    qtbot.addWidget(dialog)

    assert dialog.input.echoMode() == QLineEdit.EchoMode.Password
    # Nothing is required, so the button works at once.
    assert dialog.action_button.isEnabled()


def test_ask_text_returns_what_was_typed_or_none(qtbot, confirmations):
    parent = QWidget()
    qtbot.addWidget(parent)
    confirmations.always_type("Dispatch A")
    assert (
        ask_text(
            parent,
            title="List Note",
            heading="Note for this list",
            action_label="Save Note",
        )
        == "Dispatch A"
    )

    confirmations.always_type(None)
    assert (
        ask_text(
            parent,
            title="List Note",
            heading="Note for this list",
            action_label="Save Note",
        )
        is None
    )
    assert confirmations.prompts == ["List Note: Note for this list"] * 2


@pytest.mark.parametrize(("typed", "confirmed"), [("DELETE", True), ("nope", False)])
def test_mass_deletion_goes_on_only_with_the_word(
    qtbot, confirmations, typed, confirmed
):
    parent = QWidget()
    qtbot.addWidget(parent)
    confirmations.always_type(typed)

    assert (
        confirm_by_typing(
            parent,
            title="Delete All Estimates",
            heading="Type DELETE to delete every estimate",
            action_label="Delete All Estimates",
        )
        is confirmed
    )
