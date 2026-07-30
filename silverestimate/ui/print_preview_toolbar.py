"""Toolbar construction for the print-preview workspace."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QMenu,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QWidget,
)

from .custom_font_dialog import CustomFontDialog
from .icons import get_icon
from .print_format_spec import ESTIMATE_FORMAT_LABELS
from .print_preview_navigation import PrintPreviewNavigationController
from .print_preview_output import PrintPreviewOutputController
from .print_preview_page_setup import PrintPreviewPageSetupController
from .print_preview_session import PrintPreviewSession
from .theme_tokens import (
    CARD_BORDER,
    CARD_BORDER_SOFT,
    FIELD_TEXT,
    HEADER_BG,
    INPUT_BORDER,
    SELECTION_BG,
    SURFACE_BG,
    TEXT_STRONG,
)
from .themed_controls import ThemedComboBox

TOOLBAR_STYLE = f"""
    QToolBar#PrintPreviewToolbar {{
        background-color: {HEADER_BG};
        border: 1px solid {CARD_BORDER};
        spacing: 4px;
        padding: 4px;
    }}
    QToolBar#PrintPreviewToolbar QToolButton {{
        background-color: {SURFACE_BG};
        border: 1px solid {INPUT_BORDER};
        border-radius: 6px;
        color: {TEXT_STRONG};
        min-height: 30px;
        padding: 4px 6px;
    }}
    QToolBar#PrintPreviewToolbar QToolButton:hover {{
        background-color: {SELECTION_BG};
        border-color: {FIELD_TEXT};
    }}
    QToolBar#PrintPreviewToolbar QToolButton:checked {{
        background-color: {SELECTION_BG};
        border-color: {FIELD_TEXT};
    }}
    QToolBar#PrintPreviewToolbar QToolButton:disabled {{
        background-color: {CARD_BORDER_SOFT};
        border-color: {CARD_BORDER};
        color: {FIELD_TEXT};
    }}
    QToolBar#PrintPreviewToolbar::separator {{
        background-color: {CARD_BORDER_SOFT};
        height: 1px;
        width: 1px;
        margin: 6px;
    }}
    QWidget#PreviewPageNavigator {{
        background-color: {SURFACE_BG};
        border: 1px solid {INPUT_BORDER};
        border-radius: 6px;
    }}
    QWidget#PreviewPageNavigator QLabel {{
        color: {FIELD_TEXT};
    }}
    QComboBox#PreviewOrientationCombo {{
        min-width: 88px;
        max-width: 94px;
        min-height: 28px;
    }}
    QComboBox#PreviewFormatCombo {{
        min-width: 82px;
        max-width: 90px;
        min-height: 28px;
    }}
    QSpinBox#PreviewPageSpin {{
        min-width: 52px;
        max-width: 60px;
        min-height: 28px;
    }}
    """


class PrintPreviewToolbarBuilder:
    """Build preview controls from focused navigation/output collaborators."""

    def __init__(
        self,
        *,
        navigation: PrintPreviewNavigationController,
        page_setup: PrintPreviewPageSetupController,
        output: PrintPreviewOutputController,
        get_print_font: Callable[[], QFont] | None = None,
        persist_print_font: Callable[[QFont], None] | None = None,
    ) -> None:
        self._navigation = navigation
        self._page_setup = page_setup
        self._output = output
        self._get_print_font = get_print_font
        self._persist_print_font = persist_print_font

    def build(
        self,
        session: PrintPreviewSession,
        parent_widget: QWidget | None,
    ) -> None:
        """Populate the custom preview window's toolbar and More menu."""
        preview = session.preview
        preview_widget = session.preview_widget
        toolbar = preview.primary_toolbar
        self._configure_toolbar(toolbar)

        more_menu = QMenu("More preview actions", preview)
        more_menu.setObjectName("PreviewMoreMenu")
        self._page_setup.add_menu_actions(more_menu, preview)

        self._add_output_actions(toolbar, session, parent_widget)
        toolbar.addSeparator()
        toolbar.addWidget(self._page_setup.build_orientation_combo(preview))
        self._add_report_controls(toolbar, session)
        self._add_print_font_action(toolbar, preview)
        toolbar.addSeparator()

        more_menu.addSeparator()
        self._navigation.add_view_mode_actions(
            more_menu,
            preview_widget,
            preview,
        )
        self._navigation.add_zoom_actions(
            toolbar,
            preview,
            preview_widget,
            add_icon_only_action,
        )
        toolbar.addWidget(self._spacer(preview))
        self._navigation.add_page_navigation(
            toolbar,
            more_menu,
            preview,
            preview_widget,
        )
        toolbar.addWidget(self._more_button(preview, more_menu))
        self._add_close_action(more_menu, preview)

    @staticmethod
    def _configure_toolbar(toolbar: QToolBar) -> None:
        toolbar.clear()
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setContentsMargins(4, 4, 4, 4)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        toolbar.setIconSize(QSize(22, 22))
        toolbar.setStyleSheet(TOOLBAR_STYLE)

    def _add_output_actions(
        self,
        toolbar: QToolBar,
        session: PrintPreviewSession,
        parent_widget: QWidget | None,
    ) -> None:
        preview = session.preview
        print_action = QAction(get_icon("print", widget=preview), "Print", preview)
        print_action.setToolTip("Send directly to the selected printer (Ctrl+P)")
        print_action.setShortcut("Ctrl+P")
        print_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        print_action.triggered.connect(
            lambda: self._output.quick_print_current(
                preview,
                session.payload,
                parent_widget,
            )
        )
        add_icon_only_action(toolbar, print_action)

        export_action = QAction(
            get_icon("save_pdf", widget=preview),
            "Export PDF",
            preview,
        )
        export_action.setToolTip("Export the current preview to a PDF file (Ctrl+S)")
        export_action.setShortcut("Ctrl+S")
        export_action.triggered.connect(
            lambda: self._output.export_pdf_via_dialog(
                session.payload,
                parent_widget,
            )
        )
        add_icon_only_action(toolbar, export_action)

    def _add_report_controls(
        self,
        toolbar: QToolBar,
        session: PrintPreviewSession,
    ) -> None:
        payload = session.payload
        if payload.document_kind != "estimate" or not payload.available_formats:
            return

        format_combo = self._build_format_combo(session)
        toolbar.addWidget(format_combo)
        if payload.tunch_visibility_factory is None:
            return

        tunch_checkbox = QCheckBox("Show Tunch", session.preview)
        tunch_checkbox.setObjectName("PreviewTunchCheckbox")
        tunch_checkbox.setChecked(bool(payload.show_tunch))
        tunch_checkbox.setToolTip(
            "Show or hide the optional Tunch column in this estimate"
        )
        tunch_checkbox.toggled.connect(session.switch_tunch_visibility)
        toolbar.addWidget(tunch_checkbox)

    def _build_format_combo(
        self,
        session: PrintPreviewSession,
    ) -> ThemedComboBox:
        payload = session.payload
        combo = ThemedComboBox(session.preview)
        combo.setObjectName("PreviewFormatCombo")
        combo.setMinimumWidth(82)
        combo.setMaximumWidth(90)
        combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        combo.setToolTip("Switch between Classic and Modern estimate formats")
        for format_key in payload.available_formats:
            combo.addItem(
                ESTIMATE_FORMAT_LABELS.get(format_key, format_key.title()),
                format_key,
            )
        index = combo.findData(payload.format_key)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.currentIndexChanged.connect(
            lambda: session.switch_format(combo.currentData())
        )
        return combo

    def _add_print_font_action(
        self,
        toolbar: QToolBar,
        preview,
    ) -> None:
        if self._get_print_font is None or self._persist_print_font is None:
            return
        font_action = QAction(
            get_icon("print_font", widget=preview),
            "Print Font",
            preview,
        )
        font_action.setToolTip(
            "Choose the print font family, size, and weight for this report"
        )
        font_action.triggered.connect(lambda: self.choose_print_font(preview))
        add_icon_only_action(toolbar, font_action)

    def choose_print_font(self, preview) -> bool:
        if self._get_print_font is None or self._persist_print_font is None:
            return False
        dialog = CustomFontDialog(self._get_print_font(), preview)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        self._persist_print_font(dialog.get_selected_font())
        preview.preview_widget.updatePreview()
        return True

    @staticmethod
    def _spacer(preview) -> QWidget:
        spacer = QWidget(preview)
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        return spacer

    @staticmethod
    def _more_button(preview, more_menu: QMenu) -> QToolButton:
        more_button = QToolButton(preview)
        more_button.setObjectName("PreviewMoreButton")
        more_button.setText("More")
        more_button.setIcon(get_icon("more", widget=preview))
        more_button.setToolTip("Printer, page view, navigation, and close actions")
        more_button.setAccessibleName("More preview actions")
        more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more_button.setMenu(more_menu)
        more_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        return more_button

    @staticmethod
    def _add_close_action(more_menu: QMenu, preview) -> None:
        more_menu.addSeparator()
        close_action = QAction(
            get_icon("close", widget=preview),
            "Close",
            preview,
        )
        close_action.setToolTip("Close print preview")
        close_action.triggered.connect(preview.close)
        more_menu.addAction(close_action)


def add_icon_only_action(toolbar: QToolBar, action: QAction) -> None:
    """Add a compact toolbar action while preserving its accessible label."""
    toolbar.addAction(action)
    button = toolbar.widgetForAction(action)
    if isinstance(button, QToolButton):
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setAccessibleName(action.text())


__all__ = ["PrintPreviewToolbarBuilder", "add_icon_only_action"]
