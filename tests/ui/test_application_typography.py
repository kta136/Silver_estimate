"""Exercise the production font setup without registering test-only fonts."""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QMenuBar

from silverestimate.infrastructure.settings import SettingsKey, get_app_settings
from silverestimate.ui.application_theme import apply_light_application_theme
from silverestimate.ui.settings_appearance_page import (
    AppearanceSettingsActions,
    AppearanceSettingsState,
    SettingsAppearanceController,
)


def test_startup_and_apply_keep_controls_headers_and_totals_consistent(
    qtbot, qt_application_state, settings_stub, make_estimate_widget, fake_db
):
    app = qt_application_state
    settings = get_app_settings()
    settings.set(SettingsKey.UI_TABLE_FONT_SIZE, 14)
    settings.set(SettingsKey.UI_BREAKDOWN_FONT_SIZE, 9)
    settings.set(SettingsKey.UI_FINAL_CALC_FONT_SIZE, 12)
    # Simulate Windows' distinct class fonts, including on offscreen CI.
    for widget_class in ("QMenu", "QMenuBar", "QHeaderView"):
        app.setFont(QFont("Segoe UI", 9), widget_class)
    apply_light_application_theme(app)
    widget = make_estimate_widget(fake_db)
    widget.resize(1366, 768)
    widget.show()
    menu = QMenuBar(widget)
    menu.addMenu("File")
    qtbot.wait(80)
    panel = widget.totals_panel
    assert menu.font().pointSize() == 14
    assert widget.item_table.horizontalHeader().font().pointSize() == 14
    assert panel.category_table.horizontalHeader().font().pointSize() == 9
    assert panel.grand_total_label.font().pointSize() == 12

    controller = widget.layout_controller
    appearance = SettingsAppearanceController(
        settings,
        AppearanceSettingsActions(
            apply_print_font=lambda _font: True,
            apply_table_font_size=controller.apply_table_font_size,
            apply_breakdown_font_size=controller.apply_breakdown_font_size,
            apply_final_calc_font_size=controller.apply_final_calc_font_size,
            apply_totals_position=lambda _position: True,
        ),
    )
    appearance.apply_state(AppearanceSettingsState())
    qtbot.wait(80)
    assert widget.save_button.font().pointSize() == 11
    assert menu.font().pointSize() == 11
    assert widget.item_table.font().pointSize() == 11
    assert widget.item_table.horizontalHeader().font().pointSize() == 11
    assert panel.category_table.horizontalHeader().font().pointSize() == 11
    assert panel.net_fine_label.font().pointSize() == 11
    assert panel.grand_total_label.font().pointSize() == 16
    assert appearance.load_state() == AppearanceSettingsState()
