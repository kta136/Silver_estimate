"""Draw the app logo and write ``assets/icons/silverestimate.svg`` and ``.ico``.

A silver bar on a teal tile with the rupee sign engraved in it. The SVG is
the master; the icon holds it rendered at every size Windows asks for. At 32
px and below the engraving and sparkle are left out and the bar is drawn
larger, so it stays a clear shape.

    python scripts/build_app_icon.py
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)

TEAL_TOP = "#14a9b4"
TEAL_BOTTOM = "#00525c"


def svg(detail: bool) -> str:
    """The logo. ``detail`` False is the plain bar used at 32 px and below."""
    # The bar is drawn on a 256 grid, centred. Small sizes scale it up so it
    # fills more of the tile and has no engraving to blur.
    scale = 1.0 if detail else 1.16
    lift = 0 if detail else -4
    engraving = ""
    sparkle = ""
    shadow = ""
    if detail:
        engraving = """
  <g fill="none" stroke-linecap="round" stroke-linejoin="round">
    <g transform="translate(0 2.2)" stroke="#ffffff" stroke-opacity="0.55" stroke-width="8">
      <path d="M113 132 H147 M113 144 H147 M113 132 H131 A11.5 11.5 0 0 1 131 155 H115 L141 176"/>
    </g>
    <g stroke="#0a4f59" stroke-width="8">
      <path d="M113 132 H147 M113 144 H147 M113 132 H131 A11.5 11.5 0 0 1 131 155 H115 L141 176"/>
    </g>
  </g>"""
        sparkle = """
  <path d="M190 56 L194 68 L206 72 L194 76 L190 88 L186 76 L174 72 L186 68 Z"
        fill="#ffffff" fill-opacity="0.95"/>
  <path d="M214 94 L216 100 L222 102 L216 104 L214 110 L212 104 L206 102 L212 100 Z"
        fill="#ffffff" fill-opacity="0.8"/>"""
        shadow = """
  <ellipse cx="128" cy="198" rx="100" ry="10" fill="url(#floor)"/>"""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <defs>
    <linearGradient id="tile" x1="0" y1="0" x2="0.35" y2="1">
      <stop offset="0" stop-color="{TEAL_TOP}"/>
      <stop offset="1" stop-color="{TEAL_BOTTOM}"/>
    </linearGradient>
    <linearGradient id="gloss" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.20"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="top" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="1" stop-color="#d3dbe2"/>
    </linearGradient>
    <linearGradient id="front" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#d4dbe2"/>
      <stop offset="0.55" stop-color="#aab5c0"/>
      <stop offset="1" stop-color="#7d8a98"/>
    </linearGradient>
    <radialGradient id="floor" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#00262b" stop-opacity="0.45"/>
      <stop offset="1" stop-color="#00262b" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect x="8" y="8" width="240" height="240" rx="58" fill="url(#tile)"/>
  <path d="M66 8 H190 A58 58 0 0 1 248 66 V120 Q128 150 8 120 V66 A58 58 0 0 1 66 8 Z"
        fill="url(#gloss)"/>{shadow}
  <g transform="translate(128 {128 + lift}) scale({scale}) translate(-128 -128)">
    <g stroke-linejoin="round" stroke-linecap="round">
      <path d="M44 188 L66 114 H190 L212 188 Z" fill="url(#front)" stroke="#8f9ba8" stroke-width="10"/>
      <path d="M88 64 H168 L190 114 H66 Z" fill="url(#top)" stroke="#e9eef2" stroke-width="10"/>
      <path d="M44 188 L66 114 H190 L212 188 Z" fill="url(#front)"/>
      <path d="M88 64 H168 L190 114 H66 Z" fill="url(#top)"/>
    </g>
    <path d="M70 114 H186" stroke="#8793a0" stroke-opacity="0.55" stroke-width="2" fill="none"/>
    <path d="M62 120.5 H194" stroke="#ffffff" stroke-opacity="0.55" stroke-width="3" fill="none" stroke-linecap="round"/>
    <path d="M98 72 H140 L122 106 H82 Z" fill="#ffffff" fill-opacity="0.5"/>{engraving}
  </g>{sparkle}
</svg>
"""


def render(svg_text: str, size: int) -> QImage:
    renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()
    return image


def png_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


def pack_ico(entries: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(entries))
    offset = 6 + 16 * len(entries)
    directory, blobs = b"", b""
    for size, blob in entries:
        dim = 0 if size >= 256 else size
        directory += struct.pack(
            "<BBBBHHII", dim, dim, 0, 0, 1, 32, len(blob), offset + len(blobs)
        )
        blobs += blob
    return header + directory + blobs


def main(out_dir: Path) -> None:
    app = QGuiApplication(sys.argv)  # noqa: F841 - Qt needs one to render
    detailed, plain = svg(True), svg(False)
    (out_dir / "silverestimate.svg").write_text(detailed, encoding="utf-8")
    entries = [
        (size, png_bytes(render(detailed if size > 32 else plain, size)))
        for size in SIZES
    ]
    (out_dir / "silverestimate.ico").write_bytes(pack_ico(entries))
    print(f"Wrote {out_dir / 'silverestimate.ico'} ({len(entries)} sizes)")


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else root / "assets" / "icons")
