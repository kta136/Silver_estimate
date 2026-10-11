"""Shared styling helpers for the estimate-entry workflow."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from .theme_tokens import apply_theme_tokens

ESTIMATE_ENTRY_STYLESHEET = apply_theme_tokens(
    """
QWidget#EstimateEntryRoot {
    background-color: __PAGE_BG__;
}

QWidget#TotalsSidebar {
    background-color: __SURFACE_BG__;
    border: 1px solid __CARD_BORDER__;
    border-radius: __RADIUS_MD__;
}

QWidget#PrimaryActionStrip {
    border: none;
    border-radius: __RADIUS_MD__;
    background-color: transparent;
}

QWidget#VoucherToolbar QLabel#VoucherFieldLabel {
    color: __TEXT_MUTED__;
    font-size: 8pt;
    font-weight: 600;
}

QLabel#UnsavedBadge {
    color: __SUCCESS_TEXT__;
    background-color: __SUCCESS_BG__;
    border: 1px solid __SUCCESS_BORDER__;
    border-radius: 10px;
    padding: 1px 8px;
    font-weight: 600;
}

QLabel#UnsavedBadge[dirty="true"] {
    color: __WARNING_TEXT__;
    background-color: __WARNING_BG__;
    border-color: __WARNING_BORDER__;
}

QLabel#EstimateModeBadge {
    color: __HEADER_TEXT__;
    background-color: __HEADER_BG__;
    border: 1px solid __INPUT_BORDER__;
    border-radius: __RADIUS_SM__;
    padding: 2px 8px;
    font-weight: 600;
}

QLabel#EstimateModeBadge[modeState="return"] {
    color: __INFO_TEXT__;
    background-color: __INFO_BG__;
    border-color: #aed5d8;
}

QLabel#EstimateModeBadge[modeState="silver_bar"] {
    color: #b45309;
    background-color: __WARNING_BG__;
    border-color: __WARNING_BORDER__;
}

QLabel#EstimateStatusLabel {
    color: __TEXT_MUTED__;
    padding: 1px 0px;

}

QLabel#EstimateStatusLabel[statusLevel="info"] {
    color: __INFO_TEXT__;
}

QLabel#EstimateStatusLabel[statusLevel="warning"] {
    color: #b45309;
}

QLabel#EstimateStatusLabel[statusLevel="error"] {
    color: __DANGER_TEXT__;
}

QWidget#EstimateEntryRoot QLineEdit,
QWidget#EstimateEntryRoot QDateEdit,
QWidget#EstimateEntryRoot QDoubleSpinBox {
    background-color: __SURFACE_BG__;
    border: 1px solid __INPUT_BORDER__;
    border-radius: __RADIUS_SM__;
    padding: 2px 7px;
    min-height: 22px;
}

QWidget#EstimateEntryRoot QLineEdit:focus,
QWidget#EstimateEntryRoot QDateEdit:focus,
QWidget#EstimateEntryRoot QDoubleSpinBox:focus {
    border: 1px solid __FOCUS_RING__;
}

QWidget#PrimaryActionStrip QPushButton,
QWidget#LiveRateCard QToolButton,
QPushButton#VoucherLoadButton {
    color: __TEXT_STRONG__;
    background-color: __HEADER_BG__;
    border: 1px solid __INPUT_BORDER__;
    border-radius: __RADIUS_SM__;
    padding: 2px 7px;
    min-height: 24px;
    font-weight: 600;
}

QWidget#LiveRateCard QToolButton {
    min-width: 30px;
    max-width: 30px;
    min-height: 24px;
    max-height: 24px;
    padding: 1px;
}

QWidget#PrimaryActionStrip QPushButton:hover,
QWidget#LiveRateCard QToolButton:hover,
QPushButton#VoucherLoadButton:hover {
    background-color: #e8eef6;
    border-color: #7c8ea6;
}

QWidget#PrimaryActionStrip QPushButton:pressed,
QWidget#LiveRateCard QToolButton:pressed,
QPushButton#VoucherLoadButton:pressed {
    background-color: #dbe4ef;
    border-color: #64748b;
}

QWidget#PrimaryActionStrip QPushButton:disabled,
QWidget#LiveRateCard QToolButton:disabled,
QPushButton#VoucherLoadButton:disabled {
    color: #94a3b8;
    background-color: __HEADER_BG__;
    border-color: #dbe4ee;
}

QWidget#PrimaryActionStrip QPushButton#SavePrimaryButton {
    color: __SURFACE_BG__;
    background-color: __PRIMARY_BG__;
    border-color: __PRIMARY_BG__;
}

QWidget#PrimaryActionStrip QPushButton#SavePrimaryButton:hover {
    background-color: __PRIMARY_BG_HOVER__;
    border-color: __PRIMARY_BG_HOVER__;
}

QWidget#PrimaryActionStrip QPushButton#SavePrimaryButton:pressed {
    background-color: __PRIMARY_BG_PRESSED__;
    border-color: __PRIMARY_BG_PRESSED__;
}

QPushButton#DeleteRowButton {
    color: #991b1b;
    background-color: #fff7f7;
    border-color: #fecaca;
    font-weight: 600;
}

QPushButton#DeleteRowButton:hover,
QToolButton#DeleteEstimateButton:hover {
    color: __SURFACE_BG__;
    background-color: #ef4444;
    border-color: #dc2626;
}

QPushButton#DeleteRowButton:pressed,
QToolButton#DeleteEstimateButton:pressed {
    color: __SURFACE_BG__;
    background-color: #dc2626;
    border-color: __DANGER_TEXT__;
}

QToolButton#DeleteEstimateButton {
    color: __DANGER_TEXT__;
    background-color: #fff7f7;
    border-color: #fecaca;
}

QLabel#LiveRateValue {
    color: __TEXT_STRONG__;
    background-color: transparent;
    border: none;
    border-radius: 0px;
    padding: 0px;
    font-weight: 800;
}

QLabel#LiveRateMeta {
    color: __TEXT_MUTED__;

}

QTableView#EstimateTableView {
    background-color: __SURFACE_BG__;
    alternate-background-color: #f8fbff;
    gridline-color: #e8edf1;
    selection-background-color: __SELECTION_BG__;
    selection-color: __TEXT_STRONG__;
    border: 1px solid __CARD_BORDER_SOFT__;
    border-radius: 0px;
}

QTableView#EstimateTableView::item {
    padding: 1px 4px;
}

QTableView#EstimateTableView::item:hover {
    background-color: #f1f5f9;
}

QTableView#EstimateTableView::item:selected,
QTableView#EstimateTableView::item:selected:active,
QTableView#EstimateTableView::item:selected:!active {
    background-color: __SELECTION_BG__;
    color: __TEXT_STRONG__;
    border-top: 1px solid __SELECTION_BORDER__;
    border-bottom: 1px solid __SELECTION_BORDER__;
}

QTableView#EstimateTableView QLineEdit {
    color: __TEXT_STRONG__;
    background-color: __INFO_BG__;
    border: 1px solid __FOCUS_RING__;
    border-radius: 6px;
    padding: 1px 6px;
    selection-background-color: __FOCUS_RING__;
    selection-color: __SURFACE_BG__;
}

QHeaderView::section {
    background-color: __HEADER_BG__;
    color: __TEXT_STRONG__;
    border: none;
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #e2e8f0;
    padding: 5px 8px;
    font-weight: 700;
}

QTableCornerButton::section {
    background-color: __HEADER_BG__;
    border: none;
}

QWidget#TotalsSidebar {
    background-color: #f8fbff;
    border-color: __SELECTION_BG__;
    border-radius: __RADIUS_MD__;
}

QFrame#TotalsCard,
QFrame#FinalCalcCard {
    background-color: __SURFACE_BG__;
    border: 1px solid #e2e8f0;
    border-radius: __RADIUS_MD__;
}

QFrame#FinalCalcCard {
    background-color: __SURFACE_BG__;
    border-color: __PRIMARY_BG__;
}

QFrame#FinalCalcHeader {
    background-color: __PRIMARY_BG__;
    border-radius: __RADIUS_MD__;
}

QFrame#TotalsCard[sectionKind="totals"] {
    background-color: #f7fbff;
    border-color: #aed5d8;
}

QFrame#TotalsCard[sectionKind="return"] {
    background-color: __DANGER_BG__;
    border-color: #fecdd3;
}

QFrame#TotalsCard[sectionKind="silver_bar"] {
    background-color: #f0fdf4;
    border-color: __SUCCESS_BORDER__;
}

QListWidget#SummarySectionsList {
    background: transparent;
    border: none;
    outline: none;
}

QListWidget#SummarySectionsList::item {
    background: transparent;
    border: none;
    padding: 0px;
    margin: 0px;
}

QListWidget#SummarySectionsList::item:selected {
    background: transparent;
    border: none;
}

QLabel#SectionTitle {
    color: __TEXT_STRONG__;
    font-weight: 700;
}

QLabel#SectionTitle[sectionKind="totals"] {
    color: #1e3a8a;
}

QLabel#SectionTitle[sectionKind="return"] {
    color: #881337;
}

QLabel#SectionTitle[sectionKind="silver_bar"] {
    color: #14532d;
}

QLabel#SectionTitle[sectionKind="final_calc"] {
    color: __TEXT_STRONG__;

}

QFrame#FinalCalcHeader QLabel#SectionTitle[sectionKind="final_calc"] {
    color: __SURFACE_BG__;
}

QLabel#MetricLabel {
    color: __TEXT_STRONG__;
    font-weight: 400;
}

QLabel#MetricLabel[sectionKind="totals"] {
    color: #1e3a8a;
}

QLabel#MetricLabel[sectionKind="return"] {
    color: #881337;
}

QLabel#MetricLabel[sectionKind="silver_bar"] {
    color: #14532d;
}

QLabel#MetricValue {
    color: __TEXT_STRONG__;
    font-weight: 400;
}

QLabel#MetricValue[sectionKind="totals"] {
    color: #1e3a8a;
}

QLabel#MetricValue[sectionKind="return"] {
    color: #991b1b;
}

QLabel#MetricValue[sectionKind="silver_bar"] {
    color: __SUCCESS_TEXT__;
}

QLabel#MetricValue[sectionKind="final_calc"] {
    color: __TEXT_STRONG__;
    font-weight: 400;
}

QLabel#GrandTotalValue {
    color: #064e3b;
    font-weight: 800;
}

QFrame#FinalCalcHeader QLabel#GrandTotalValue {
    color: __SURFACE_BG__;
}

QLabel#FinalMetricLabel {
    color: __TEXT_STRONG__;
    font-weight: 400;
}

"""
)

ESTIMATE_ENTRY_STYLESHEET += apply_theme_tokens("""
/* Native adaptation of the selected 12ui estimate workstation design. */
QWidget#EstimateEntryRoot { background: #f6f7f5; color: #173744; }
QWidget#TotalsSidebar { background: #f6f7f5; border: 1px solid #d5dfe0; border-radius: 6px; }
QFrame#TotalsCard[sectionKind="totals"] { background: __SURFACE_BG__; border-color: #d5dfe0; }
QFrame#EstimateSidebarActions { background: transparent; border: none; }
QFrame#EstimateSidebarActions QPushButton, QFrame#EstimateSidebarActions QToolButton {
 background: __SURFACE_BG__; border: 1px solid __INPUT_BORDER__; border-radius: 5px; padding: 3px 8px; color: #173744; text-align: center;
}
QFrame#EstimateSidebarActions QPushButton:hover, QFrame#EstimateSidebarActions QToolButton:hover {
 background: #eaf4f2; border-color: #81b9b5;
}
/* Both delete buttons share the look of every other delete button. */
QFrame#EstimateSidebarActions QPushButton#DeleteRowButton,
QFrame#EstimateSidebarActions QToolButton#DeleteEstimateButton {
 color: __DANGER_TEXT__; background: __DANGER_BG__; border-color: __DANGER_BORDER__;
}
QFrame#EstimateSidebarActions QPushButton#DeleteRowButton:hover,
QFrame#EstimateSidebarActions QToolButton#DeleteEstimateButton:hover {
 color: __DANGER_TEXT__; background: #ffe4e6; border-color: #fb7185;
}
QFrame#EstimateSidebarActions QPushButton#DeleteRowButton:pressed,
QFrame#EstimateSidebarActions QToolButton#DeleteEstimateButton:pressed {
 color: __SURFACE_BG__; background: #dc2626; border-color: __DANGER_TEXT__;
}
/* A button that cannot be used right now must look switched off. */
QFrame#EstimateSidebarActions QPushButton:disabled,
QFrame#EstimateSidebarActions QToolButton:disabled,
QFrame#EstimateSidebarActions QPushButton#DeleteRowButton:disabled,
QFrame#EstimateSidebarActions QToolButton#DeleteEstimateButton:disabled {
 color: __DISABLED_TEXT__; background: __DISABLED_BG__; border-color: __DISABLED_BORDER__;
}
QLabel#MetricLabel[sectionKind="totals"], QLabel#MetricValue[sectionKind="totals"], QLabel#SectionTitle[sectionKind="totals"] { color: __TEXT_STRONG__; }
QTableView#EstimateTableView {
 background: __SURFACE_BG__; alternate-background-color: #fafcfb; border: 1px solid #d5dfe0;
 border-radius: 4px; gridline-color: #e2e9e8; color: #173744;
}
QTableView#EstimateTableView::item:selected { border: none; background: #dff1ed; color: #123d43; }
QTableView#EstimateTableView QLineEdit { background: white; border: 1px solid __FOCUS_RING__; border-radius: 0; }
QFrame#FinalCalcCard { background: white; border: 1px solid #bddbd8; border-radius: 6px; }
QFrame#FinalCalcHeader { background: #007f83; border-radius: 5px; }
QLabel#UnsavedBadge { background: #e7f5ec; color: #147548; border: none; padding: 5px 8px; }
QLabel#UnsavedBadge[dirty="true"] { background: #fff4d9; color: #94631b; }
QTableWidget#SummaryTable {
 background: __SURFACE_BG__; color: #173744; border: none;
 gridline-color: #e0e7e5; selection-background-color: __SURFACE_BG__;
}
QTableWidget#SummaryTable::item { padding: 0px 5px; }
QTableWidget#SummaryTable QHeaderView::section {
 background: __HEADER_BG__; padding: 1px 5px; font-weight: 600;
 border: none; border-right: 1px solid __CARD_BORDER__; border-bottom: 1px solid __CARD_BORDER__;
}
QTableView#EstimateTableView QHeaderView::section {
    background: #f4f7f5; color: #173744; padding: 4px;
    border-right: 1px solid #e2e9e8; border-bottom: 1px solid #d5dfe0;
}
QWidget#VoucherToolbar QComboBox { padding-top: 3px; padding-bottom: 3px; min-height: 24px; }
QWidget#VoucherToolbar QLineEdit, QWidget#VoucherToolbar QDateEdit,
QWidget#VoucherToolbar QDoubleSpinBox {
 background: __SURFACE_BG__; border-color: __INPUT_BORDER__; border-radius: 4px; padding: 3px 6px; min-height: 24px;
}
QWidget#PrimaryActionStrip QPushButton, QPushButton#VoucherLoadButton {
 background: __SURFACE_BG__; color: #173744; border-color: __INPUT_BORDER__; padding: 4px 8px; min-height: 26px;
}
QWidget#PrimaryActionStrip QPushButton#SavePrimaryButton {
 background: #007f83; border-color: #007f83; color: __SURFACE_BG__;
}
QWidget#PrimaryActionStrip QPushButton#SavePrimaryButton:hover { background: #00696c; }
QWidget#VoucherToolbar {
 background: __SURFACE_BG__; border: 1px solid #d5dfe0; border-radius: 6px;
}
QWidget#EntryModeSelector {
 background: __SURFACE_BG__; border: 1px solid __INPUT_BORDER__; border-radius: 5px;
}
QPushButton#EntryModeButton {
 background: transparent; border: none; border-radius: 3px; color: #173744;
 font-weight: 600; padding: 3px 8px; min-height: 20px;
}
QPushButton#EntryModeButton:hover { background: #eaf4f2; }
QPushButton#EntryModeButton:checked { background: __PRIMARY_BG__; color: __SURFACE_BG__; }
QWidget#EstimateCommandStrip { background: transparent; border: none; }
QWidget#EstimateCommandStrip QWidget#PrimaryActionStrip QPushButton {
 min-height: 18px; padding: 1px 9px;
}
QWidget#EstimateCommandStrip QLabel#UnsavedBadge { padding: 2px 8px; border-radius: 9px; }
QLabel#SidebarStatusText { color: __TEXT_MUTED__; font-size: 9pt; padding-top: 4px; }
QLabel#MetricLabel[categoryKind="return"], QLabel#MetricValue[categoryKind="return"] {
 background: __INFO_BG__; color: __INFO_TEXT__;
}
QLabel#MetricLabel[categoryKind="silver_bar"], QLabel#MetricValue[categoryKind="silver_bar"] {
 background: __WARNING_BG__; color: __WARNING_TEXT__;
}
QWidget#LiveRateCard {
 background: transparent; border: none; border-radius: 0px; padding: 0px;
}
QWidget#LiveRateCard QLabel#LiveRateMeta { color: __TEXT_MUTED__; font-size: 8pt; }
QWidget#LiveRateCard QLabel#VoucherFieldLabel {
 color: __TEXT_MUTED__; font-size: 8pt; font-weight: 600;
}
""")


def refresh_widget_style(widget: QWidget | None) -> None:
    """Re-polish a widget after changing dynamic properties used by QSS."""
    if widget is None:
        return
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
