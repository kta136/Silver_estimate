from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtGui import QPageSize

from silverestimate.infrastructure.settings import get_app_settings
from silverestimate.ui.print_page_settings import (
    PrintPageSettings,
    save_print_page_settings,
)
from silverestimate.ui.settings_print_controller import (
    PrintSettingsState,
    SettingsPrintController,
)


def test_default_print_settings_state_is_valid() -> None:
    SettingsPrintController.validate_state(PrintSettingsState())


def test_removed_classic_preference_is_normalized_to_modern(settings_stub) -> None:
    settings = get_app_settings()
    settings.setValue("print/estimate_layout", "classic")

    state = SettingsPrintController(settings).load_state()

    assert state.estimate_format == "modern"
    assert settings.value("print/estimate_layout") == "modern"


def test_removed_thermal_page_size_falls_back_to_a4(settings_stub) -> None:
    settings = get_app_settings()
    settings.setValue("print/page_size", "Thermal 80mm")
    settings.setValue("print/page_size_name", "Thermal 80mm")
    settings.setValue("print/page_width_mm", 79.5)
    settings.setValue("print/page_height_mm", 200.0)

    state = SettingsPrintController(settings).load_state()

    assert state.page_size == "A4"
    assert state.page_size_name == "A4"
    assert state.page_width_mm == 0.0
    assert state.page_height_mm == 0.0


def test_thermal_custom_page_state_cannot_create_a_thermal_page() -> None:
    page_size = PrintPageSettings(
        page_size="Custom",
        page_size_name="Thermal Receipt",
        page_width_mm=80.0,
        page_height_mm=200.0,
    ).to_qpage_size()

    assert page_size.id() == QPageSize.PageSizeId.A4


def test_thermal_page_state_cannot_be_persisted(settings_stub) -> None:
    settings = get_app_settings()

    save_print_page_settings(
        settings,
        PrintPageSettings(
            page_size="Thermal 80mm",
            page_size_name="Thermal 80mm",
            page_width_mm=79.5,
            page_height_mm=200.0,
        ),
    )

    assert settings.value("print/page_size") == "A4"
    assert settings.value("print/page_size_name") == "A4"
    assert settings.value("print/page_width_mm") is None
    assert settings.value("print/page_height_mm") is None


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"margins": (51, 2, 10, 2)}, "margins"),
        ({"preview_zoom": 8.0}, "zoom"),
        ({"page_size": ""}, "page size"),
        ({"orientation": "Sideways"}, "orientation"),
        ({"estimate_format": "future"}, "format"),
    ],
)
def test_invalid_print_settings_are_rejected_before_persistence(
    changes: dict[str, object],
    message: str,
) -> None:
    state = replace(PrintSettingsState(), **changes)

    with pytest.raises(ValueError, match=message):
        SettingsPrintController.validate_state(state)
