"""Check compiled Qt typography with synthetic widgets and no user settings."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMenuBar,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from silverestimate.ui.appearance import apply_interface_appearance, set_table_font
from silverestimate.ui.application_theme import (
    LIGHT_APPLICATION_STYLESHEET,
    apply_application_font,
)
from silverestimate.ui.estimate_entry_components.totals_panel import TotalsPanel
from silverestimate.ui.estimate_entry_theme import ESTIMATE_ENTRY_STYLESHEET


def verify_artifact_ui_fonts(app: QApplication) -> dict[str, int]:
    app.setStyle("Fusion")
    app.setStyleSheet(LIGHT_APPLICATION_STYLESHEET)
    apply_application_font(app, QFont("Segoe UI", 14))
    window = QWidget()
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    window.setObjectName("EstimateEntryRoot")
    window.setStyleSheet(ESTIMATE_ENTRY_STYLESHEET)
    layout = QVBoxLayout(window)
    menu = QMenuBar(window)
    menu.addMenu("File")
    layout.addWidget(menu)
    button = QPushButton("Save")
    button.setObjectName("SavePrimaryButton")
    layout.addWidget(button)
    content = QHBoxLayout()
    layout.addLayout(content)
    table = QTableWidget(1, 2)
    table.setHorizontalHeaderLabels(["Gross (g)", "Lbr Amt"])
    table.setProperty("denseTable", True)
    set_table_font(table, QFont("Segoe UI", 14))
    content.addWidget(table)
    totals = TotalsPanel(layout_mode="sidebar")
    content.addWidget(totals)
    totals.set_breakdown_font_size(9)
    totals.set_final_calc_font_size(12)
    window.resize(1100, 700)
    window.show()
    try:
        app.processEvents()
        totals.set_breakdown_font_size(11)
        totals.set_final_calc_font_size(16)
        apply_interface_appearance("Segoe UI", 11, "compact", True)
        app.processEvents()
        fonts = {
            "button": button.font().pointSize(),
            "menu": menu.font().pointSize(),
            "table": table.font().pointSize(),
            "header": table.horizontalHeader().font().pointSize(),
            "totals_header": totals.category_table.horizontalHeader()
            .font()
            .pointSize(),
            "totals": totals.net_fine_label.font().pointSize(),
            "final_amount": totals.grand_total_label.font().pointSize(),
        }
        expected = dict.fromkeys(fonts, 11)
        expected["totals"] = 16
        expected["final_amount"] = 16
        if fonts != expected or window.grab().isNull():
            raise RuntimeError(f"Frozen interface typography check failed: {fonts}")
        return fonts
    finally:
        window.close()
        window.deleteLater()
        app.processEvents()
