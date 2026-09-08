"""Shared styling helpers for the estimate-entry workflow."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from .theme_tokens import apply_theme_tokens

ESTIMATE_ENTRY_STYLESHEET = apply_theme_tokens(
    """
QWidget#EstimateEntryRoot {
    background-color: __PAGE_BG__;
}

QWidget#EstimateHeaderContainer,
QWidget#EstimateCommandBar,
QWidget#PrimaryActionStrip,
QWidget#SecondaryActionStrip,
QWidget#VoucherToolbar,
QWidget#EstimateHeaderActions,
QWidget#LiveRateCard,
QWidget#TotalsSidebar,
QWidget#TotalsContainer {
    background-color: __SURFACE_BG__;
    border: 1px solid __CARD_BORDER__;
    border-radius: __RADIUS_MD__;
}

QWidget#EstimateHeaderActions {
    background-color: transparent;
    border: none;
}

QWidget#EstimateHeaderContainer {
    border-color: __CARD_BORDER_SOFT__;
    border-radius: 0px;
    min-height: 36px;
}

QWidget#VoucherToolbar,
QWidget#PrimaryActionStrip,
QWidget#SecondaryActionStrip {
    border: none;
    background-color: transparent;
}

QWidget#EstimateCommandBar {
    border-color: __CARD_BORDER_SOFT__;
    border-left: none;
    border-right: none;
    border-radius: 0px;
    min-height: 36px;
}

QWidget#VoucherToolbar QLabel#DocumentTitleLabel {
    color: __TEXT_STRONG__;
    font-size: 12pt;
    font-weight: 700;
}

QWidget#VoucherToolbar QLabel#VoucherFieldLabel {
    color: __FIELD_TEXT__;

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
    color: #006d77;
    background-color: #f0f8f8;
    border-color: #aed5d8;
}

QLabel#EstimateModeBadge[modeState="silver_bar"] {
    color: #b45309;
    background-color: #fff7ed;
    border-color: #fdba74;
}

QLabel#EstimateStatusLabel {
    color: __TEXT_MUTED__;
    padding: 1px 0px;

}

QLabel#EstimateStatusLabel[statusLevel="info"] {
    color: #006d77;
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
QWidget#SecondaryActionStrip QPushButton,
QWidget#SecondaryActionStrip QToolButton,
QWidget#LiveRateCard QToolButton,
QPushButton#VoucherLoadButton,
QToolButton#EstimateToolsButton,
QPushButton#EstimateSettingsButton {
    color: __TEXT_STRONG__;
    background-color: __HEADER_BG__;
    border: 1px solid __INPUT_BORDER__;
    border-radius: __RADIUS_SM__;
    padding: 2px 7px;
    min-height: 24px;
    font-weight: 600;
}

QWidget#PrimaryActionStrip QPushButton[iconOnly="true"],
QWidget#SecondaryActionStrip QPushButton[iconOnly="true"],
QWidget#SecondaryActionStrip QToolButton[iconOnly="true"],
QWidget#LiveRateCard QToolButton[iconOnly="true"] {
    min-width: 30px;
    max-width: 30px;
    min-height: 24px;
    max-height: 24px;
    padding: 1px;
}

QWidget#PrimaryActionStrip QPushButton:hover,
QWidget#SecondaryActionStrip QPushButton:hover,
QWidget#SecondaryActionStrip QToolButton:hover,
QWidget#LiveRateCard QToolButton:hover,
QPushButton#VoucherLoadButton:hover,
QToolButton#EstimateToolsButton:hover,
QPushButton#EstimateSettingsButton:hover {
    background-color: #e8eef6;
    border-color: #7c8ea6;
}

QWidget#PrimaryActionStrip QPushButton:pressed,
QWidget#SecondaryActionStrip QPushButton:pressed,
QWidget#SecondaryActionStrip QToolButton:pressed,
QWidget#LiveRateCard QToolButton:pressed,
QPushButton#VoucherLoadButton:pressed,
QToolButton#EstimateToolsButton:pressed,
QPushButton#EstimateSettingsButton:pressed {
    background-color: #dbe4ef;
    border-color: #64748b;
}

QWidget#PrimaryActionStrip QPushButton:disabled,
QWidget#SecondaryActionStrip QPushButton:disabled,
QWidget#SecondaryActionStrip QToolButton:disabled,
QWidget#LiveRateCard QToolButton:disabled,
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
    background-color: #006670;
    border-color: #006670;
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
    color: #006d77;
    background-color: #f0f8f8;
    border-color: #00848e;
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
    background-color: #f0f8f8;
    border-color: #c1dedf;
}

QLabel#LiveRateTitle {
    color: __TEXT_MUTED__;
    background-color: transparent;

    font-weight: 600;
}

QLabel#LiveRateValue {
    color: __TEXT_STRONG__;
    background-color: transparent;
    border: none;
    border-radius: 0px;
    padding: 0px;
    font-weight: 800;
}

QLabel#LiveRateMeta,
QLabel#SummaryDragHint {
    color: __TEXT_MUTED__;

}

QWidget#TotalsContainer {
    border-color: #dbe5ef;
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
    background-color: #e0f2f3;
    color: __TEXT_STRONG__;
    border-top: 1px solid __SELECTION_BORDER__;
    border-bottom: 1px solid __SELECTION_BORDER__;
}

QTableView#EstimateTableView QLineEdit {
    color: __TEXT_STRONG__;
    background-color: #f0f8f8;
    border: 1px solid __FOCUS_RING__;
    border-radius: 6px;
    padding: 1px 6px;
    selection-background-color: __FOCUS_RING__;
    selection-color: #ffffff;
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
    border-color: #e0f2f3;
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
    color: #1e3a8a;
}

QLabel#SectionTitle[sectionKind="return"] {
    color: #881337;
}

QLabel#SectionTitle[sectionKind="silver_bar"] {
    color: #14532d;
}

QLabel#SectionTitle[sectionKind="final_calc"] {
    color: #0f172a;

}

QFrame#FinalCalcHeader QLabel#SectionTitle[sectionKind="final_calc"] {
    color: #ffffff;
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

QLabel#SectionDragHandle {
    color: #94a3b8;
    font-size: 12pt;
    font-weight: 700;
    padding-left: 6px;
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
    color: #166534;
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
    color: #ffffff;
}

QLabel#FinalMetricLabel {
    color: __TEXT_STRONG__;
    font-weight: 400;
}

QLabel#GrandTotalLabel {
    color: #0f172a;
    font-weight: 800;
}

QFrame#BottomStatusStrip {
    background-color: __HEADER_BG__;
    border-top: 1px solid __CARD_BORDER__;
    border-left: none;
    border-right: none;
    border-bottom: none;
    color: __TEXT_MUTED__;
}

QLabel#StatusStripText {
    color: __TEXT_MUTED__;

}
"""
)

ESTIMATE_ENTRY_STYLESHEET += apply_theme_tokens("""
QWidget#TotalsSidebar { background: __SURFACE_BG__; border: none; }
QFrame#TotalsCard[sectionKind="totals"] { background: __SURFACE_BG__; border-color: __CARD_BORDER__; }
QFrame#EstimateSidebarActions { background: __SURFACE_BG__; border: 1px solid __CARD_BORDER__; border-radius: 6px; }
QFrame#EstimateSidebarActions QPushButton, QFrame#EstimateSidebarActions QToolButton {
 background: __SURFACE_BG__; border: 1px solid __INPUT_BORDER__; border-radius: 4px; padding: 1px 6px; color: __TEXT_STRONG__;
}
QFrame#EstimateSidebarActions QToolButton#DeleteEstimateButton { color: #df202e; border-color: __DANGER_BORDER__; }
QLabel#MetricLabel[sectionKind="totals"], QLabel#MetricValue[sectionKind="totals"], QLabel#SectionTitle[sectionKind="totals"] { color: __TEXT_STRONG__; }
QTableView#EstimateTableView::item:selected { border: none; background: __SELECTION_BG__; }
QTableView#EstimateTableView QLineEdit { background: white; border: 1px solid __FOCUS_RING__; border-radius: 0; }
QWidget#LiveRateCard { background: white; border-color: __CARD_BORDER__; }
QTableWidget#SummaryTable {
 background: __SURFACE_BG__; color: __TEXT_STRONG__; border: none;
 gridline-color: __CARD_BORDER__; selection-background-color: __SURFACE_BG__;
}
QTableWidget#SummaryTable::item { padding: 0px 5px; }
QTableWidget#SummaryTable QHeaderView::section {
 background: __HEADER_BG__; padding: 1px 5px; font-weight: 600;
 border: none; border-right: 1px solid __CARD_BORDER__; border-bottom: 1px solid __CARD_BORDER__;
}
QTableView#EstimateTableView QHeaderView::section {
    padding: 2px 4px;
    border-right: 1px solid #edf0f3;
}
QWidget#VoucherToolbar QComboBox { padding-top: 1px; padding-bottom: 1px; min-height: 22px; }
""")


def refresh_widget_style(widget: QWidget | None) -> None:
    """Re-polish a widget after changing dynamic properties used by QSS."""
    if widget is None:
        return
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
