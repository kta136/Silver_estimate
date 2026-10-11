"""The About window."""

from silverestimate.infrastructure.app_constants import APP_NAME, APP_VERSION
from silverestimate.ui.about_dialog import PROJECT_URL, AboutDialog


def test_about_gives_the_version_licence_and_a_link_that_can_be_clicked(qtbot):
    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    text = dialog.text()
    assert dialog.windowTitle() == f"About {APP_NAME}"
    assert f"Version {APP_VERSION}" in text
    assert "GNU General Public License v3.0" in text
    assert "THIRD_PARTY_NOTICES.md" in text
    # The data is called the item catalog everywhere in the app.
    assert "item catalog" in text and "catalogue" not in text

    link = dialog.link_label
    assert f'href="{PROJECT_URL}"' in link.text()
    assert link.openExternalLinks()
    # One unbroken line: an address split in two can be neither read nor copied.
    assert not link.wordWrap()
    assert dialog.close_button.isDefault()
