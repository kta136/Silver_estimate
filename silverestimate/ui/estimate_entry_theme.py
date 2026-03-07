"""Shared styling helpers for the estimate-entry workflow."""

from __future__ import annotations

from PyQt5.QtWidgets import QWidget

from .theme_tokens import apply_theme_tokens

ESTIMATE_ENTRY_STYLESHEET = apply_theme_tokens(
    """
QWidget#EstimateEntryRoot {
    background-color: __PAGE_BG__;
}

QWidget#EstimateHeaderContainer,
QWidget#PrimaryActionStrip,
QWidget#SecondaryActionStrip,
QWidget#VoucherToolbar,
QWidget#EstimateHeaderActions,
QWidget#LiveRateCard,
QWidget#TotalsSidebar,
QWidget#TotalsContainer {
    background-color: __SURFACE_BG__;
    border: 1px solid __CARD_BORDER__;
    border-radius: 12px;
}

QWidget#EstimateHeaderActions {
    background-color: transparent;
    border: none;
}

QWidget#VoucherToolbar,
QWidget#PrimaryActionStrip,
QWidget#SecondaryActionStrip {
    border-color: __CARD_BORDER_SOFT__;
}

QWidget#VoucherToolbar QLabel#DocumentTitleLabel {
    color: __TEXT_STRONG__;
    font-size: 12pt;
    font-weight: 700;
}

QWidget#VoucherToolbar QLabel#VoucherFieldLabel {
    color: __FIELD_TEXT__;
    font-size: 8.5pt;
    font-weight: 600;
}

QLabel#UnsavedBadge {
    color: #9a3412;
    background-color: #fff7ed;
    border: 1px solid #fdba74;
    border-radius: 999px;
    padding: 2px 8px;
    font-weight: 600;
}

QLabel#EstimateModeBadge {
    color: __HEADER_TEXT__;
    background-color: __HEADER_BG__;
    border: 1px solid __INPUT_BORDER__;
    border-radius: 999px;
    padding: 4px 10px;
    font-weight: 600;
}

QLabel#EstimateModeBadge[modeState="return"] {
    color: #1d4ed8;
    background-color: #eff6ff;
    border-color: #93c5fd;
}

QLabel#EstimateModeBadge[modeState="silver_bar"] {
    color: #b45309;
    background-color: #fff7ed;
    border-color: #fdba74;
}

QLabel#EstimateStatusLabel {
    color: __TEXT_MUTED__;
    padding: 2px 0px;
    font-size: 8.5pt;
}

QLabel#EstimateStatusLabel[statusLevel="info"] {
    color: #1d4ed8;
}

QLabel#EstimateStatusLabel[statusLevel="warning"] {
    color: #b45309;
}

QLabel#EstimateStatusLabel[statusLevel="error"] {
    color: #b91c1c;
}

QWidget#EstimateEntryRoot QLineEdit,
QWidget#EstimateEntryRoot QDateEdit,
QWidget#EstimateEntryRoot QDoubleSpinBox {
    background-color: __SURFACE_BG__;
    border: 1px solid __INPUT_BORDER__;
    border-radius: 8px;
    padding: 3px 7px;
    min-height: 14px;
}

QWidget#EstimateEntryRoot QLineEdit:focus,
QWidget#EstimateEntryRoot QDateEdit:focus,
QWidget#EstimateEntryRoot QDoubleSpinBox:focus {
    border: 2px solid __FOCUS_RING__;
}

QWidget#PrimaryActionStrip QPushButton,
QWidget#SecondaryActionStrip QPushButton,
QWidget#SecondaryActionStrip QToolButton,
QPushButton#VoucherLoadButton {
    color: __TEXT_STRONG__;
    background-color: __HEADER_BG__;
    border: 1px solid __INPUT_BORDER__;
    border-radius: 8px;
    padding: 3px 8px;
    min-height: 18px;
    font-weight: 600;
}

QWidget#PrimaryActionStrip QPushButton:hover,
QWidget#SecondaryActionStrip QPushButton:hover,
QWidget#SecondaryActionStrip QToolButton:hover,
QPushButton#VoucherLoadButton:hover {
    background-color: #eef2f7;
    border-color: #94a3b8;
}

QWidget#PrimaryActionStrip QPushButton:disabled,
QWidget#SecondaryActionStrip QPushButton:disabled,
QWidget#SecondaryActionStrip QToolButton:disabled,
QPushButton#VoucherLoadButton:disabled {
    color: #94a3b8;
    background-color: __HEADER_BG__;
    border-color: #dbe4ee;
}

QPushButton#SavePrimaryButton {
    color: #ffffff;
    background-color: __PRIMARY_BG__;
    border-color: __PRIMARY_BG__;
}

QPushButton#SavePrimaryButton:hover {
    background-color: __PRIMARY_BG_HOVER__;
    border-color: __PRIMARY_BG_HOVER__;
}

QPushButton#ReturnModeButton[modeState="return"],
QPushButton#SilverBarModeButton[modeState="silver_bar"] {
    border-width: 2px;
}

QPushButton#ReturnModeButton[modeState="return"] {
    color: #1d4ed8;
    background-color: #eff6ff;
    border-color: #60a5fa;
}

QPushButton#SilverBarModeButton[modeState="silver_bar"] {
    color: #b45309;
    background-color: #fff7ed;
    border-color: #fb923c;
}

QToolButton#DeleteEstimateButton {
    color: #b91c1c;
    background-color: __DANGER_BG__;
    border-color: __DANGER_BORDER__;
}

QToolButton#DeleteEstimateButton:hover {
    background-color: #ffe4e6;
    border-color: #fb7185;
}

QWidget#LiveRateCard {
    background-color: #eff6ff;
    border-color: #bfdbfe;
}

QLabel#LiveRateValue {
    color: __TEXT_STRONG__;
    background-color: __SURFACE_BG__;
    border: 1px solid #93c5fd;
    border-radius: 10px;
    padding: 3px 8px;
    font-size: 10pt;
    font-weight: 700;
}

QLabel#LiveRateMeta,
QLabel#SummaryDragHint {
    color: __TEXT_MUTED__;
    font-size: 8.5pt;
}

QWidget#TotalsContainer {
    border-color: #dbe5ef;
}

QTableView#EstimateTableView {
    background-color: __SURFACE_BG__;
    gridline-color: #d9e2ec;
    selection-background-color: __SELECTION_BG__;
    selection-color: __TEXT_STRONG__;
    border: 1px solid __CARD_BORDER_SOFT__;
    border-radius: 12px;
}

QTableView#EstimateTableView::item {
    padding: 2px 5px;
}

QTableView#EstimateTableView::item:hover {
    background-color: __HEADER_BG__;
}

QTableView#EstimateTableView::item:selected:active {
    background-color: __SELECTION_BG__;
    color: __TEXT_STRONG__;
    border: 1px solid __FOCUS_RING__;
}

QTableView#EstimateTableView QLineEdit {
    color: __TEXT_STRONG__;
    background-color: #eff6ff;
    border: 2px solid __FOCUS_RING__;
    border-radius: 6px;
    padding: 1px 6px;
    selection-background-color: __FOCUS_RING__;
    selection-color: #ffffff;
}

QTableView#EstimateTableView:focus {
    border: 2px solid __FOCUS_RING__;
}

QHeaderView::section {
    background-color: __HEADER_BG__;
    color: __HEADER_TEXT__;
    border: none;
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #e2e8f0;
    padding: 6px 8px;
    font-weight: 700;
}

QTableCornerButton::section {
    background-color: __HEADER_BG__;
    border: none;
}

QWidget#TotalsSidebar {
    background-color: #f8fbff;
    border-color: #dbeafe;
}

QFrame#TotalsCard,
QFrame#FinalCalcCard {
    background-color: __SURFACE_BG__;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}

QFrame#TotalsCard[sectionKind="totals"],
QFrame#FinalCalcCard {
    background-color: #eff6ff;
    border-color: #bfdbfe;
}

QFrame#TotalsCard[sectionKind="return"] {
    background-color: #fff1f2;
    border-color: #fecdd3;
}

QFrame#TotalsCard[sectionKind="silver_bar"] {
    background-color: #f0fdf4;
    border-color: #bbf7d0;
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
    color: #1d4ed8;
}

QLabel#SectionTitle[sectionKind="return"] {
    color: #991b1b;
}

QLabel#SectionTitle[sectionKind="silver_bar"] {
    color: #166534;
}

QLabel#SectionTitle[sectionKind="final_calc"] {
    color: #0f172a;
}

QLabel#MetricLabel {
    color: __FIELD_TEXT__;
}

QLabel#MetricLabel[sectionKind="totals"] {
    color: #1e3a8a;
}

QLabel#MetricLabel[sectionKind="return"] {
    color: #9f1239;
}

QLabel#MetricLabel[sectionKind="silver_bar"] {
    color: #166534;
}

QLabel#SectionDragHandle {
    color: #94a3b8;
    font-size: 12pt;
    font-weight: 700;
    padding-left: 6px;
}

QLabel#MetricValue {
    color: __TEXT_STRONG__;
    font-weight: 600;
}

QLabel#MetricValue[sectionKind="totals"] {
    color: #1e40af;
}

QLabel#MetricValue[sectionKind="return"] {
    color: #b91c1c;
}

QLabel#MetricValue[sectionKind="silver_bar"] {
    color: #15803d;
}

QLabel#GrandTotalValue {
    color: #065f46;
    font-weight: 800;
}

QLabel#FinalMetricLabel {
    color: __HEADER_TEXT__;
    font-weight: 700;
}
"""
)


def refresh_widget_style(widget: QWidget | None) -> None:
    """Re-polish a widget after changing dynamic properties used by QSS."""
    if widget is None:
        return
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
