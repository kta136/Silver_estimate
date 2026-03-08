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

QWidget#EstimateHeaderContainer {
    border-color: __CARD_BORDER_SOFT__;
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
    padding: 1px 8px;
    font-weight: 600;
}

QLabel#EstimateModeBadge {
    color: __HEADER_TEXT__;
    background-color: __HEADER_BG__;
    border: 1px solid __INPUT_BORDER__;
    border-radius: 999px;
    padding: 2px 8px;
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
    padding: 1px 0px;
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
    padding: 2px 7px;
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
    padding: 2px 7px;
    min-height: 16px;
    font-weight: 600;
}

QWidget#PrimaryActionStrip QPushButton[iconOnly="true"],
QWidget#SecondaryActionStrip QPushButton[iconOnly="true"],
QWidget#SecondaryActionStrip QToolButton[iconOnly="true"] {
    min-width: 30px;
    max-width: 30px;
    min-height: 24px;
    max-height: 24px;
    padding: 1px;
}

QWidget#PrimaryActionStrip QPushButton:hover,
QWidget#SecondaryActionStrip QPushButton:hover,
QWidget#SecondaryActionStrip QToolButton:hover,
QPushButton#VoucherLoadButton:hover {
    background-color: #e8eef6;
    border-color: #7c8ea6;
}

QWidget#PrimaryActionStrip QPushButton:pressed,
QWidget#SecondaryActionStrip QPushButton:pressed,
QWidget#SecondaryActionStrip QToolButton:pressed,
QPushButton#VoucherLoadButton:pressed {
    background-color: #dbe4ef;
    border-color: #64748b;
}

QWidget#PrimaryActionStrip QPushButton:disabled,
QWidget#SecondaryActionStrip QPushButton:disabled,
QWidget#SecondaryActionStrip QToolButton:disabled,
QPushButton#VoucherLoadButton:disabled {
    color: #94a3b8;
    background-color: __HEADER_BG__;
    border-color: #dbe4ee;
}

QWidget#PrimaryActionStrip QPushButton#SavePrimaryButton {
    color: #ffffff;
    background-color: __PRIMARY_BG__;
    border-color: __PRIMARY_BG__;
}

QWidget#PrimaryActionStrip QPushButton#SavePrimaryButton:hover {
    background-color: __PRIMARY_BG_HOVER__;
    border-color: __PRIMARY_BG_HOVER__;
}

QWidget#PrimaryActionStrip QPushButton#SavePrimaryButton:pressed {
    background-color: #0b5f59;
    border-color: #0b5f59;
}

QPushButton#DeleteRowButton {
    color: #991b1b;
    background-color: #fff7f7;
    border-color: #fecaca;
    font-weight: 600;
}

QPushButton#DeleteRowButton:hover,
QToolButton#DeleteEstimateButton:hover {
    color: #ffffff;
    background-color: #ef4444;
    border-color: #dc2626;
}

QPushButton#DeleteRowButton:pressed,
QToolButton#DeleteEstimateButton:pressed {
    color: #ffffff;
    background-color: #dc2626;
    border-color: #b91c1c;
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
    background-color: #fff7f7;
    border-color: #fecaca;
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
    font-size: 8pt;
}

QWidget#TotalsContainer {
    border-color: #dbe5ef;
}

QTableView#EstimateTableView {
    background-color: __SURFACE_BG__;
    alternate-background-color: #f8fbff;
    gridline-color: #d9e2ec;
    selection-background-color: __SELECTION_BG__;
    selection-color: __TEXT_STRONG__;
    border: 1px solid __CARD_BORDER_SOFT__;
    border-radius: 12px;
}

QTableView#EstimateTableView::item {
    padding: 1px 5px;
}

QTableView#EstimateTableView::item:hover {
    background-color: #f1f5f9;
}

QTableView#EstimateTableView::item:selected,
QTableView#EstimateTableView::item:selected:active,
QTableView#EstimateTableView::item:selected:!active {
    background-color: #dbeafe;
    color: __TEXT_STRONG__;
    border-top: 1px solid #60a5fa;
    border-bottom: 1px solid #60a5fa;
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
    padding: 5px 8px;
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
    background-color: #f7fbff;
    border-color: #93c5fd;
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
    font-size: 10pt;
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

QLabel#MetricValue[sectionKind="final_calc"] {
    color: #0f172a;
    font-weight: 700;
}

QLabel#GrandTotalValue {
    color: #065f46;
    font-weight: 800;
}

QLabel#FinalMetricLabel {
    color: __HEADER_TEXT__;
    font-weight: 700;
}

QLabel#GrandTotalLabel {
    color: #0f172a;
    font-weight: 800;
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
