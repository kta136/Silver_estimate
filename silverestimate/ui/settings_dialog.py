#!/usr/bin/env python
import logging  # Ensure logging is available for getLogger calls

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from silverestimate.infrastructure.settings import SettingsKey, get_app_settings
from silverestimate.services.password_change_service import (
    PasswordChangeService,
    default_password_change_actions,
)
from silverestimate.services.settings_service import FontSettings

from .icons import get_icon
from .settings_appearance_page import (
    AppearanceSettingsActions,
    AppearanceSettingsPage,
    SettingsAppearanceController,
    TotalsPosition,
)
from .settings_data_page import (
    DataManagementActions,
    DataManagementPage,
    SettingsDataController,
)
from .settings_live_rates_page import LiveRatesSettingsPage
from .settings_logging_page import (
    LoggingSettingsPage,
    SettingsLoggingController,
    default_logging_settings_actions,
)
from .settings_print_controller import SettingsPrintController
from .settings_print_page import PrintSettingsPage
from .settings_security_page import (
    SecuritySettingsPage,
    SettingsSecurityController,
)
from .shared_screen_theme import build_management_screen_stylesheet
from .theme_tokens import (
    CARD_BORDER,
    CARD_BORDER_SOFT,
    DANGER_BG,
    DANGER_BORDER,
    FIELD_TEXT,
    HEADER_BG,
    HEADER_TEXT,
    INPUT_BORDER,
    SELECTION_BG,
    SURFACE_BG,
    TEXT_MUTED,
    TEXT_STRONG,
)


def _coerce_int_setting(value: object, default: int) -> int:
    if isinstance(value, (int, float, str, bytes, bytearray)):
        try:
            return int(value)
        except TypeError, ValueError:
            pass
    return default


class SettingsDialog(QDialog):
    """Centralized dialog for application settings."""

    # Signal to indicate settings that require application restart or redraw
    settings_applied = Signal()

    def __init__(self, main_window_ref, parent=None):
        super().__init__(parent)
        self.main_window = main_window_ref  # Store reference to main window
        self.setWindowTitle("Application Settings")
        self.setMinimumSize(900, 540)
        self.setObjectName("SettingsDialog")
        self.setStyleSheet(
            build_management_screen_stylesheet(
                root_selector="QDialog#SettingsDialog",
                card_names=[
                    "SettingsHeaderCard",
                    "SettingsPageCard",
                    "SettingsPreviewCard",
                ],
                title_label="SettingsTitleLabel",
                subtitle_label="SettingsSubtitleLabel",
                primary_button="SettingsPrimaryButton",
                danger_button="SettingsDangerButton",
                input_selectors=[
                    "QLineEdit",
                    "QComboBox",
                    "QSpinBox",
                    "QDoubleSpinBox",
                    "QListWidget",
                    "QListView",
                ],
                extra_rules=f"""
                QFrame#SettingsPageCard QWidget {{
                    color: {TEXT_STRONG};
                }}
                QFrame#SettingsPageCard {{
                    background-color: {SURFACE_BG};
                }}
                QScrollArea#SettingsPageScroll {{
                    background-color: {SURFACE_BG};
                    border: none;
                }}
                QScrollArea#SettingsPageScroll > QWidget > QWidget {{
                    background-color: {SURFACE_BG};
                }}
                QListWidget#SettingsSidebar {{
                    background-color: {SURFACE_BG};
                    border: 1px solid {CARD_BORDER};
                    border-radius: 12px;
                    outline: none;
                    padding: 8px;
                }}
                QListWidget#SettingsSidebar::item {{
                    border-radius: 8px;
                    color: {HEADER_TEXT};
                    margin: 2px 0;
                    padding: 8px 10px;
                }}
                QListWidget#SettingsSidebar::item:selected,
                QListWidget#SettingsSidebar::item:selected:!active {{
                    background-color: {SELECTION_BG};
                    color: {TEXT_STRONG};
                    font-weight: 700;
                }}
                QListWidget#SettingsSidebar::item:hover:!selected {{
                    background-color: {HEADER_BG};
                    color: {TEXT_STRONG};
                }}
                QLabel {{
                    color: {FIELD_TEXT};
                }}
                QLabel#SettingsWarningLabel {{
                    background-color: {DANGER_BG};
                    border: 1px solid {DANGER_BORDER};
                    border-radius: 8px;
                    color: #991b1b;
                    font-weight: 600;
                    padding: 8px 10px;
                }}
                QLabel#SettingsMutedDescription {{
                    color: {TEXT_MUTED};
                    font-size: 9pt;
                }}
                QLabel#SettingsValueLabel {{
                    color: {TEXT_STRONG};
                    font-weight: 600;
                }}
                QPushButton {{
                    background-color: {HEADER_BG};
                    border: 1px solid {INPUT_BORDER};
                    border-radius: 8px;
                    color: {TEXT_STRONG};
                    font-weight: 600;
                    min-height: 24px;
                    padding: 5px 10px;
                }}
                QPushButton:hover {{
                    background-color: {SELECTION_BG};
                    border-color: {HEADER_TEXT};
                }}
                QPushButton:disabled {{
                    background-color: {CARD_BORDER_SOFT};
                    border-color: {CARD_BORDER};
                    color: {TEXT_MUTED};
                }}
                QPushButton#SettingsDangerButton {{
                    background-color: {DANGER_BG};
                    border-color: {DANGER_BORDER};
                    color: #991b1b;
                }}
                QPushButton#SettingsDangerButton:hover {{
                    background-color: #ffe4e6;
                    border-color: #fb7185;
                }}
                QDialogButtonBox {{
                    padding-top: 4px;
                }}
                QFrame#SettingsPreviewCard {{
                    margin-top: 6px;
                }}
                QTableWidget#SettingsPreviewTable {{
                    border-radius: 8px;
                    gridline-color: {CARD_BORDER_SOFT};
                    selection-background-color: {SELECTION_BG};
                }}
                QLabel#SettingsPreviewTitle {{
                    color: {TEXT_STRONG};
                    font-size: 10.5pt;
                    font-weight: 700;
                }}
                QLabel#SettingsGrandTotalPreview {{
                    background-color: {SURFACE_BG};
                    border: 1px solid {CARD_BORDER};
                    border-radius: 8px;
                    color: {TEXT_STRONG};
                    font-weight: 700;
                    padding: 8px 10px;
                }}
                QLabel#SettingsFeedbackLabel {{
                    border-radius: 6px;
                    color: {TEXT_STRONG};
                    font-weight: 600;
                    padding: 6px 10px;
                }}
                QLabel#SettingsFeedbackLabel[state="dirty"] {{
                    background-color: #fff7ed;
                    border: 1px solid #fdba74;
                    color: #9a3412;
                }}
                QLabel#SettingsFeedbackLabel[state="saved"] {{
                    background-color: #ecfdf5;
                    border: 1px solid #bbf7d0;
                    color: #166534;
                }}
                """,
            )
        )

        # Load current settings
        self.settings = get_app_settings()
        self._print_settings_controller = SettingsPrintController(self.settings)
        self._appearance_settings_controller = SettingsAppearanceController(
            self.settings,
            self._appearance_settings_actions(),
        )
        self._logging_settings_controller = SettingsLoggingController(
            self.settings,
            default_logging_settings_actions(),
        )
        self._data_settings_controller = SettingsDataController(
            database_provider=lambda: getattr(self.main_window, "db", None),
            actions=DataManagementActions(
                delete_all_estimates=self.main_window.delete_all_estimates,
                delete_all_data=self.main_window.delete_all_data,
                restore_item_catalog=self.main_window.show_catalog_restore_dialog,
                create_item_catalog_backup=self.main_window.show_catalog_backup_dialog,
            ),
        )
        self._security_settings_controller = SettingsSecurityController(
            PasswordChangeService(
                default_password_change_actions(
                    lambda: getattr(self.main_window, "db", None)
                )
            )
        )

        # Sidebar + pages (cleaner than rotated west tabs)
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("SettingsSidebar")
        self.sidebar.setViewMode(QListView.ViewMode.ListMode)
        self.sidebar.setIconSize(QSize(20, 20))
        self.sidebar.setSpacing(4)
        self.sidebar.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.sidebar.setFixedWidth(205)

        self.pages = QStackedWidget()
        self.pages.setObjectName("SettingsPages")

        # Build pages list
        page_defs = [
            (
                "User Interface",
                get_icon("user_interface", widget=self),
                self._create_ui_tab(),
            ),
            (
                "Live Rates",
                get_icon("live_rates", widget=self),
                self._create_live_rates_tab(),
            ),
            (
                "Printing",
                get_icon("printing", widget=self),
                self._create_print_tab(),
            ),
            (
                "Data Management",
                get_icon("data_management", widget=self),
                self._create_data_tab(),
            ),
            (
                "Security",
                get_icon("security", widget=self),
                self._create_security_tab(),
            ),
            (
                "Logging",
                get_icon("logging", widget=self),
                self._create_logging_tab(),
            ),
        ]
        for title, icon, widget in page_defs:
            self.sidebar.addItem(QListWidgetItem(icon, title))
            self.pages.addWidget(widget)

        # Remember last page
        try:
            last_idx = _coerce_int_setting(
                self.settings.get_int(SettingsKey.UI_SETTINGS_LAST_TAB, 0),
                0,
            )
        except Exception:
            last_idx = 0
        last_idx = max(0, min(last_idx, len(page_defs) - 1))
        self.sidebar.setCurrentRow(last_idx)
        self.pages.setCurrentIndex(last_idx)
        self.sidebar.currentRowChanged.connect(self._set_current_settings_page)

        # Buttons
        # Add Help button later if needed
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )  # Store as self.buttonBox
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self.apply_settings
        )
        # Disable Apply until change
        self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setEnabled(False)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setObjectName(
            "SettingsPrimaryButton"
        )
        self.buttonBox.button(QDialogButtonBox.StandardButton.Ok).setObjectName(
            "SettingsPrimaryButton"
        )

        # Add Restore Defaults button
        restore_btn = QPushButton("Restore Defaults…")
        restore_btn.setObjectName("SettingsDangerButton")
        restore_btn.setToolTip(
            "Reset all settings to default values\nWill not affect saved estimates or data\nChanges take effect immediately"
        )
        self.buttonBox.addButton(restore_btn, QDialogButtonBox.ButtonRole.ResetRole)
        restore_btn.clicked.connect(self._restore_defaults)

        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_card = QFrame(self)
        header_card.setObjectName("SettingsHeaderCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(12, 12, 12, 12)
        header_layout.setSpacing(2)

        title_label = QLabel("Application Settings")
        title_label.setObjectName("SettingsTitleLabel")
        header_layout.addWidget(title_label)

        subtitle_label = QLabel(
            "Manage interface behavior, printing, data tools, security, and logging."
        )
        subtitle_label.setObjectName("SettingsSubtitleLabel")
        header_layout.addWidget(subtitle_label)
        layout.addWidget(header_card)

        # content row: sidebar + pages
        content = QHBoxLayout()
        content.setSpacing(10)
        content.addWidget(self.sidebar)

        page_card = QFrame(self)
        page_card.setObjectName("SettingsPageCard")
        page_card_layout = QVBoxLayout(page_card)
        page_card_layout.setContentsMargins(12, 12, 12, 12)
        page_card_layout.setSpacing(0)

        self.page_scroll = QScrollArea(page_card)
        self.page_scroll.setObjectName("SettingsPageScroll")
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.page_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.page_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.page_scroll.setWidget(self.pages)
        page_card_layout.addWidget(self.page_scroll)
        content.addWidget(page_card, 1)

        layout.addLayout(content)
        self.settings_feedback_label = QLabel("")
        self.settings_feedback_label.setObjectName("SettingsFeedbackLabel")
        self.settings_feedback_label.setVisible(False)
        layout.addWidget(self.settings_feedback_label)
        layout.addWidget(self.buttonBox)  # Use self.buttonBox here
        self.setLayout(layout)
        self._resize_to_available_screen()
        self._sync_page_scrollbar()

        # If changes fired during construction, reflect pending dirty state
        if getattr(self, "_dirty", False):
            self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setEnabled(
                True
            )

    # --- Tab Creation Methods ---

    def _set_current_settings_page(self, index: int) -> None:
        if 0 <= index < self.pages.count():
            self.pages.setCurrentIndex(index)
            self.settings.set(SettingsKey.UI_SETTINGS_LAST_TAB, index)
        QTimer.singleShot(0, self._sync_page_scrollbar)

    def _sync_page_scrollbar(self) -> None:
        if not hasattr(self, "pages") or not hasattr(self, "page_scroll"):
            return
        try:
            current = self.pages.currentWidget()
            viewport_height = self.page_scroll.viewport().height()
            needs_scrollbar = (
                current is not None
                and viewport_height > 0
                and current.sizeHint().height() > viewport_height
            )
            self.page_scroll.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
                if needs_scrollbar
                else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
        except RuntimeError:
            return

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._sync_page_scrollbar)

    def _create_ui_tab(self):
        """Create the independently owned appearance settings page."""
        self.appearance_page = AppearanceSettingsPage(
            self._appearance_settings_controller,
            self,
        )
        self.appearance_page.changed.connect(self._mark_dirty)
        return self.appearance_page

    def _create_live_rates_tab(self):
        """Create the independently owned DDA live-rate page."""
        page = LiveRatesSettingsPage(self.settings, self)
        page.changed.connect(self._mark_dirty)
        self._live_rates_page = page
        return page

    def _create_print_tab(self):
        """Create the independently owned printing page."""
        self.print_page = PrintSettingsPage(
            self._print_settings_controller,
            self,
        )
        self.print_page.changed.connect(self._mark_dirty)
        return self.print_page

    def _create_data_tab(self):
        """Create the independently owned data-management page."""
        self.data_page = DataManagementPage(
            self._data_settings_controller,
            self,
        )
        return self.data_page

    def _create_logging_tab(self):
        """Create the independently owned logging and diagnostics page."""
        self.logging_page = LoggingSettingsPage(
            self._logging_settings_controller,
            self,
        )
        self.logging_page.changed.connect(self._mark_dirty)
        return self.logging_page

    def _create_security_tab(self):
        """Create the independently owned security page."""
        self.security_page = SecuritySettingsPage(
            self._security_settings_controller,
            self,
        )
        return self.security_page

    # --- Helper Methods ---

    def _appearance_settings_actions(self) -> AppearanceSettingsActions:
        return AppearanceSettingsActions(
            apply_print_font=self._apply_print_font,
            apply_table_font_size=lambda value: self._apply_estimate_widget_value(
                "apply_table_font_size",
                value,
                "table font size",
            ),
            apply_breakdown_font_size=lambda value: self._apply_estimate_widget_value(
                "apply_breakdown_font_size",
                value,
                "breakdown font size",
            ),
            apply_final_calc_font_size=lambda value: self._apply_estimate_widget_value(
                "apply_final_calc_font_size",
                value,
                "final calculation font size",
            ),
            apply_totals_position=lambda value: self._apply_estimate_widget_value(
                "apply_totals_position",
                value,
                "totals panel position",
            ),
        )

    def _apply_print_font(self, font: FontSettings) -> None:
        self.main_window.print_font = font.to_qfont()

    def _apply_estimate_widget_value(
        self,
        method_name: str,
        value: int | TotalsPosition,
        label: str,
    ) -> object:
        widget = getattr(self.main_window, "estimate_widget", None)
        if widget is None:
            return None
        method = getattr(widget, method_name, None)
        if not callable(method):
            raise RuntimeError(
                f"Estimate view does not support '{method_name}' for {label}."
            )
        result = method(value)
        if result is False:
            raise RuntimeError(f"Estimate view rejected {label} value {value}.")
        return result

    def _resize_to_available_screen(self) -> None:
        """Keep the settings dialog usable at larger Windows scale factors."""
        screen = self.screen()
        available = screen.availableGeometry()
        target_width = min(900, max(self.minimumWidth(), available.width() - 80))
        target_height = min(760, max(self.minimumHeight(), available.height() - 80))
        self.resize(target_width, target_height)

    # --- Apply/Save/Accept/Reject ---

    def apply_settings(self):
        """Save currently selected settings and apply immediate changes."""
        logger = logging.getLogger(__name__)
        logger.debug("Applying settings...")

        try:
            self.appearance_page.validate()
            self.print_page.validate()
            self.logging_page.validate()

            appearance_state = self.appearance_page.apply()
            logger.debug("Applied appearance settings: %s", appearance_state)

            print_state = self.print_page.apply()
            logger.debug(
                "Saved print settings: margins=%s zoom=%s printer=%s page_size=%s orientation=%s",
                self._print_settings_controller.serialize_margins(print_state.margins),
                print_state.preview_zoom,
                print_state.default_printer,
                print_state.page_size,
                print_state.orientation,
            )

            # Live Rates settings
            self._live_rates_page.save()
            if hasattr(self.main_window, "reconfigure_rate_visibility_from_settings"):
                self.main_window.reconfigure_rate_visibility_from_settings()
            if hasattr(self.main_window, "reconfigure_rate_timer_from_settings"):
                self.main_window.reconfigure_rate_timer_from_settings()

            logging_state = self.logging_page.apply()
            logger.info("Applied logging settings: %s", logging_state)
            self.settings.sync()
            self.settings_applied.emit()
            logger.info("Settings applied and saved.")

            self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setEnabled(
                False
            )
            self._dirty = False
            self.settings_feedback_label.setText("Settings applied and saved.")
            self.settings_feedback_label.setProperty("state", "saved")
            self.settings_feedback_label.setVisible(True)
            self.settings_feedback_label.style().unpolish(self.settings_feedback_label)
            self.settings_feedback_label.style().polish(self.settings_feedback_label)
            return True
        except Exception as e:
            QMessageBox.critical(
                self, "Error Applying Settings", f"Could not apply settings: {e}"
            )
            logger.error("Error applying settings:", exc_info=True)
            self._dirty = True
            self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).setEnabled(
                True
            )
            self.settings_feedback_label.setText("Settings could not be applied.")
            self.settings_feedback_label.setProperty("state", "dirty")
            self.settings_feedback_label.setVisible(True)
            return False

    def accept(self):
        """Apply settings and close the dialog."""
        # Apply non-password settings first
        if not self.apply_settings():
            return
        # Password changes are handled separately by the button click
        super().accept()

    def reject(self):
        """Close the dialog without applying changes since last Apply/Load."""
        logging.getLogger(__name__).debug("Settings dialog rejected.")
        super().reject()

    # --- UI helpers ---
    def _mark_dirty(self):
        """Enable Apply button when any setting changes."""
        # Record dirty state even if buttonBox not yet constructed
        self._dirty = True
        feedback = getattr(self, "settings_feedback_label", None)
        if feedback is not None:
            feedback.setText("Unsaved settings changes")
            feedback.setProperty("state", "dirty")
            feedback.setVisible(True)
            feedback.style().unpolish(feedback)
            feedback.style().polish(feedback)
        try:
            btn = self.buttonBox.button(QDialogButtonBox.StandardButton.Apply)
            if btn:
                btn.setEnabled(True)
        except AttributeError:
            # buttonBox not available yet during early construction; will enable later
            pass

    def _restore_defaults(self):
        """Restore sensible default settings for this dialog and update the UI."""
        self.appearance_page.restore_defaults()

        self.print_page.restore_defaults()

        self.logging_page.restore_defaults()

        # Mark dirty so user can Apply
        self._mark_dirty()


# Example usage for testing
if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication, QMainWindow

    class DummyMainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.print_font = QFont("Arial", 10)  # Dummy attribute

            class _DummyEstimateWidget(QWidget):
                def apply_table_font_size(self, size):
                    print(f"Dummy Apply Table Font: {size}")

            self.estimate_widget = _DummyEstimateWidget()
            # Add dummy methods needed by the dialog
            self.show_catalog_restore_dialog = lambda: print(
                "Dummy Show Catalog Restore Dialog"
            )
            self.show_catalog_backup_dialog = lambda: print(
                "Dummy Show Catalog Backup Dialog"
            )
            self.delete_all_estimates = lambda: print("Dummy Delete All Estimates")
            self.delete_all_data = lambda: print("Dummy Delete All Data")
            # Dummy db object for export handler check
            self.db = True  # Or a dummy object with needed methods if exporter uses them directly

    app = QApplication(sys.argv)
    dummy_main = DummyMainWindow()
    dialog = SettingsDialog(dummy_main)
    dialog.exec()
    sys.exit(app.exec())
