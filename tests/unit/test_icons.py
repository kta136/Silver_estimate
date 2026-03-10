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


def test_get_icon_uses_fallbacks_for_common_actions_without_qtawesome(
    qtbot, monkeypatch
):
    widget = QWidget()
    qtbot.addWidget(widget)
    monkeypatch.setattr(icons, "_qtawesome", None)

    for name in (
        "new",
        "delete_row",
        "delete_estimate",
        "exit",
        "silver_bars",
        "settings",
        "history",
        "return_mode",
        "bar_mode",
        "view_single_page",
        "view_facing_pages",
        "view_overview",
    ):
        assert not icons.get_icon(name, widget=widget).isNull(), name


def test_resolve_qtawesome_fonts_dir_prefers_bundled_assets(monkeypatch, tmp_path):
    bundled_fonts_dir = tmp_path / "qtawesome" / "fonts"
    bundled_fonts_dir.mkdir(parents=True)

    monkeypatch.setattr(icons, "get_asset_path", lambda *parts: tmp_path.joinpath(*parts))

    resolved = icons._resolve_qtawesome_fonts_dir()

    assert resolved == bundled_fonts_dir
