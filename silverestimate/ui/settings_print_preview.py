"""Render the actual estimate painter using staged printing preferences."""

from PySide6.QtCore import QMarginsF, QSize, Qt
from PySide6.QtGui import QFont, QPageLayout, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy

from .estimate_print_document import EstimatePrintDocument
from .estimate_print_renderer import EstimatePrintRenderer
from .print_page_settings import PrintPageSettings, qt_orientation

ZOOM_FACTOR = 2


class SettingsPrintPreview(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 280)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "background: #eef0f2; border: 1px solid #d9dde2; padding: 12px;"
        )
        self._image = QPixmap()
        # A whole page is too small to read at this size, so a click enlarges
        # the top of the page and another click shows the whole page again.
        self._zoomed = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sync_tooltip()

    def render_preferences(self, state, font: QFont) -> None:
        document = EstimatePrintDocument.from_mapping(
            {
                "header": {
                    "voucher_no": "100",
                    "date": "2026-09-06",
                    "silver_rate": 75000,
                    "note": "Sample estimate",
                },
                "items": [
                    dict(
                        item_code="RING001",
                        item_name="Silver Ring",
                        gross=10,
                        poly=0.5,
                        net_wt=9.5,
                        purity=91.6,
                        wage_rate=250,
                        pieces=1,
                        fine=8.702,
                        wage=2375,
                    )
                    for _ in range(6)
                ],
            }
        )
        page = PrintPageSettings(
            margins=state.margins,
            page_size=state.page_size,
            orientation=state.orientation,
            page_width_mm=state.page_width_mm,
            page_height_mm=state.page_height_mm,
            page_size_name=state.page_size_name,
        )
        page_layout = QPageLayout(
            page.to_qpage_size(),
            qt_orientation(page.orientation),
            QMarginsF(*[float(value) for value in page.margins]),
            QPageLayout.Unit.Millimeter,
        )
        try:
            self._image = QPixmap.fromImage(
                EstimatePrintRenderer().paint_first_page_image(
                    document, page_layout, print_font=font
                )
            )
            self._fit()
        except (RuntimeError, ValueError) as exc:
            self.setText(str(exc))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()

    def set_zoomed(self, zoomed: bool) -> None:
        self._zoomed = bool(zoomed)
        self._sync_tooltip()
        self._fit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self._image.isNull():
            self.set_zoomed(not self._zoomed)
            event.accept()
            return
        super().mousePressEvent(event)

    def _sync_tooltip(self) -> None:
        self.setToolTip(
            "Click to show the whole page"
            if self._zoomed
            else "Click to enlarge the top of the page"
        )

    def _fit(self) -> None:
        if self._image.isNull():
            return
        area = self.size() - QSize(28, 28)
        if not self._zoomed:
            self.setPixmap(
                self._image.scaled(
                    area,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            return
        # Twice the fitted width, cropped to the area from the page's top left.
        enlarged = self._image.scaledToWidth(
            max(1, area.width() * ZOOM_FACTOR),
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(
            enlarged.copy(
                0,
                0,
                min(enlarged.width(), max(1, area.width())),
                min(enlarged.height(), max(1, area.height())),
            )
        )
