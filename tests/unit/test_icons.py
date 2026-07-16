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
