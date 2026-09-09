from __future__ import annotations

from dataclasses import replace

import pytest

from silverestimate.infrastructure.settings import get_app_settings
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
