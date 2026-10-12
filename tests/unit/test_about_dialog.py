"""The About window."""

from PySide6.QtWidgets import QLabel

from silverestimate.infrastructure.app_constants import APP_NAME, APP_VERSION
from silverestimate.ui.about_dialog import AboutDialog


def test_about_gives_the_version_and_licence_briefly(qtbot):
    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    text = dialog.text()
    assert dialog.windowTitle() == f"About {APP_NAME}"
    assert f"Version {APP_VERSION}" in text
    assert "GNU General Public License v3.0" in text
    assert "no warranty" in text
    assert "THIRD_PARTY_NOTICES.md" in text
    # The data is called the item catalog everywhere in the app.
    assert "item catalog" in text and "catalogue" not in text
    # A name, a line on what it is, and two short licence notices.
    assert len(text) < 400
    assert dialog.close_button.isDefault()


def test_about_has_no_web_link(qtbot):
    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    assert not hasattr(dialog, "link_label")
    assert "github" not in dialog.text().lower()
    assert "http" not in dialog.text().lower()
    assert not any(
        label.openExternalLinks() or "href" in label.text()
        for label in dialog.findChildren(QLabel)
    )
