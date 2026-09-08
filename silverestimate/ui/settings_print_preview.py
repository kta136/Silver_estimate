"""Render the actual estimate painter using staged printing preferences."""

from dataclasses import replace
from tempfile import TemporaryDirectory

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QPainter, QPixmap
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QLabel, QSizePolicy

from .estimate_print_document import EstimatePrintDocument
from .estimate_print_renderer import EstimatePrintRenderer
from .print_page_settings import PrintPageSettings, apply_print_page_settings_to_printer


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
        document = replace(document, format_key=state.estimate_format)
        page = PrintPageSettings(
            margins=state.margins,
            page_size=state.page_size,
            orientation=state.orientation,
            page_width_mm=state.page_width_mm,
            page_height_mm=state.page_height_mm,
            page_size_name=state.page_size_name,
        )
        try:
            with TemporaryDirectory(prefix="silverestimate-preview-") as directory:
                path = directory + "/sample.pdf"
                printer = QPrinter(QPrinter.PrinterMode.HighResolution)
                printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
                printer.setOutputFileName(path)
                apply_print_page_settings_to_printer(
                    printer, page, include_default_printer=False
                )
                EstimatePrintRenderer().paint(printer, document, print_font=font)
                del printer
                pdf = QPdfDocument()
                try:
                    pdf.load(path)
                    size = pdf.pagePointSize(0).toSize()
                    rendered = pdf.render(
                        0,
                        size.scaled(
                            QSize(1200, 1200), Qt.AspectRatioMode.KeepAspectRatio
                        ),
                    )
                    self._image = QPixmap(rendered.size())
                    self._image.fill(Qt.GlobalColor.white)
                    painter = QPainter(self._image)
                    painter.drawImage(0, 0, rendered)
                    painter.end()
                finally:
                    pdf.close()
                    del pdf
            self._fit()
        except (RuntimeError, ValueError) as exc:
            self.setText(str(exc))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        if not self._image.isNull():
            self.setPixmap(
                self._image.scaled(
                    self.size() - QSize(28, 28),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
