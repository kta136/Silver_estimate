"""The app icon is a real multi-size icon, so every Windows surface can use it."""

import struct
from pathlib import Path

import pytest
from PySide6.QtGui import QIcon

from silverestimate.infrastructure.paths import get_asset_path

EXPECTED_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]


@pytest.fixture
def icon_path() -> Path:
    return get_asset_path("assets", "icons", "silverestimate.ico")


def test_icon_holds_every_size_windows_asks_for(icon_path):
    data = icon_path.read_bytes()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    assert (reserved, kind) == (0, 1)

    sizes = []
    for index in range(count):
        width, height, _, _, _, bits, length, offset = struct.unpack(
            "<BBBBHHII", data[6 + 16 * index : 22 + 16 * index]
        )
        sizes.append(width or 256)
        assert (width or 256) == (height or 256)
        assert bits == 32
        assert data[offset : offset + 8] == b"\x89PNG\r\n\x1a\n"
        assert offset + length <= len(data)
    assert sizes == EXPECTED_SIZES


def test_qt_reads_every_size_of_the_icon(qt_app, icon_path):
    icon = QIcon(str(icon_path))

    assert not icon.isNull()
    assert sorted(size.width() for size in icon.availableSizes()) == EXPECTED_SIZES
    for size in (16, 32, 64, 256):
        assert not icon.pixmap(size, size).isNull()


def test_the_vector_master_is_kept_beside_the_icon(icon_path):
    master = icon_path.with_suffix(".svg")

    assert master.is_file()
    assert master.read_text(encoding="utf-8").lstrip().startswith("<svg")
