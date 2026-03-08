from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget

from silverestimate.ui import icons


class _QtAwesomeStub:
    def __init__(self):
        self.calls = []

    def icon(self, name, **kwargs):
        self.calls.append((name, kwargs))
        return QIcon()


def test_get_icon_uses_mdi6_mapping(qtbot, monkeypatch):
    widget = QWidget()
    qtbot.addWidget(widget)
    stub = _QtAwesomeStub()
    monkeypatch.setattr(icons, "_qtawesome", stub)

    icons.get_icon("search", widget=widget, color="#ffffff")

    assert stub.calls == [
        (
            "mdi6.magnify",
            {
                "color": "#ffffff",
                "color_active": "#ffffff",
                "color_disabled": "#94a3b8",
            },
        )
    ]


def test_get_icon_supports_extended_action_mappings(qtbot, monkeypatch):
    widget = QWidget()
    qtbot.addWidget(widget)
    stub = _QtAwesomeStub()
    monkeypatch.setattr(icons, "_qtawesome", stub)

    icons.get_icon("estimate_entry", widget=widget)
    icons.get_icon("delete_row", widget=widget)
    icons.get_icon("reset_layout", widget=widget)
    icons.get_icon("print_estimate", widget=widget)
    icons.get_icon("silver_bars", widget=widget)
    icons.get_icon("bar_mode", widget=widget)
    icons.get_icon("view_single_page", widget=widget)
    icons.get_icon("view_facing_pages", widget=widget)
    icons.get_icon("view_overview", widget=widget)
    icons.get_icon("exit", widget=widget)
    icons.get_icon("close", widget=widget)

    assert [call[0] for call in stub.calls] == [
        "mdi6.calculator-variant-outline",
        "mdi6.table-row-remove",
        "mdi6.table-column-width",
        "mdi6.printer-outline",
        "mdi6.gold",
        "mdi6.weight",
        "mdi6.file-outline",
        "mdi6.book-open-page-variant-outline",
        "mdi6.view-grid-outline",
        "mdi6.logout-variant",
        "mdi6.close",
    ]


def test_get_icon_uses_standard_icon_fallback_without_qtawesome(qtbot, monkeypatch):
    widget = QWidget()
    qtbot.addWidget(widget)
    monkeypatch.setattr(icons, "_qtawesome", None)

    icon = icons.get_icon("print", widget=widget)

    assert not icon.isNull()
