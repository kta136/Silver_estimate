from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QWidget

from silverestimate.ui import icons


def test_get_icon_supports_all_semantic_mappings(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)

    for name in icons._ICON_SPECS:
        assert not icons.get_icon(name, widget=widget).isNull(), name


def test_get_icon_caches_rendered_native_icon(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    icons.clear_icon_cache()

    first = icons.get_icon("search", widget=widget, color="#ffffff")
    second = icons.get_icon("search", widget=widget, color="#ffffff")

    assert isinstance(first, QIcon)
    assert first.cacheKey() == second.cacheKey()
    assert len(icons._ICON_CACHE) == 1


def test_get_icon_applies_requested_color(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)
    icons.clear_icon_cache()

    image = (
        icons.get_icon("print", widget=widget, color="#ff0000")
        .pixmap(QSize(24, 24))
        .toImage()
    )
    opaque_colors = {
        image.pixelColor(x, y).name()
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y).alpha() > 0
    }

    assert opaque_colors == {"#ff0000"}


def test_icons_keep_transparent_backgrounds_in_disabled_state(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)

    for name in icons._ICON_SPECS:
        image = (
            icons.get_icon(name, widget=widget)
            .pixmap(QSize(24, 24), QIcon.Mode.Disabled)
            .toImage()
        )
        opaque_pixels = sum(
            image.pixelColor(x, y).alpha() > 0
            for x in range(image.width())
            for y in range(image.height())
        )
        coverage = opaque_pixels / (image.width() * image.height())

        assert 0.02 < coverage < 0.55, name


def test_problematic_menu_icons_have_distinct_silhouettes(qtbot):
    widget = QWidget()
    qtbot.addWidget(widget)

    silhouettes = []
    for name in ("tools", "history", "settings", "new"):
        image = icons.get_icon(name, widget=widget).pixmap(QSize(24, 24)).toImage()
        silhouettes.append(
            frozenset(
                (x, y)
                for x in range(image.width())
                for y in range(image.height())
                if image.pixelColor(x, y).alpha() > 0
            )
        )

    assert len(set(silhouettes)) == len(silhouettes)
