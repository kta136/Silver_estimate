from __future__ import annotations

from typing import Any

import pytest

from silverestimate.services.settings_service import FontSettings
from silverestimate.ui.settings_appearance_page import (
    AppearanceSettingsActions,
    AppearanceSettingsState,
    SettingsAppearanceController,
)


class _MemorySettings:
    def __init__(self, values: dict[str, object] | None = None) -> None:
        self.values = dict(values or {})

    def value(  # noqa: A002 - mirrors the QSettings API
        self,
        key: str,
        default: Any = None,
        type: Any = None,
    ) -> Any:
        del type
        return self.values.get(key, default)

    def setValue(self, key: str, value: Any) -> None:
        self.values[key] = value

    def remove(self, key: str) -> None:
        self.values.pop(key, None)

    def sync(self) -> bool:
        return True


def _recording_actions(
    calls: list[tuple[str, object]],
    *,
    rejected: str | None = None,
) -> AppearanceSettingsActions:
    def record(label: str, value: object) -> object:
        calls.append((label, value))
        return label != rejected

    return AppearanceSettingsActions(
        apply_print_font=lambda value: record("font", value),
        apply_table_font_size=lambda value: record("table", value),
        apply_breakdown_font_size=lambda value: record("breakdown", value),
        apply_final_calc_font_size=lambda value: record("final", value),
        apply_totals_position=lambda value: record("position", value),
    )


def test_load_state_normalizes_invalid_and_out_of_range_values() -> None:
    settings = _MemorySettings(
        {
            "font/family": "",
            "font/size_float": "invalid",
            "font/bold": "yes",
            "ui/table_font_size": 99,
            "ui/breakdown_font_size": -4,
            "ui/final_calc_font_size": "huge",
            "ui/estimate_totals_position": "sideways",
        }
    )
    controller = SettingsAppearanceController(
        settings,
        _recording_actions([]),
    )

    assert controller.load_state() == AppearanceSettingsState(
        print_font=FontSettings("Arial", 8.0, True),
        table_font_size=16,
        breakdown_font_size=7,
        final_calc_font_size=10,
        totals_position="right",
    )


def test_apply_state_uses_narrow_actions_then_persists_typed_values() -> None:
    settings = _MemorySettings()
    calls: list[tuple[str, object]] = []
    controller = SettingsAppearanceController(
        settings,
        _recording_actions(calls),
    )
    state = AppearanceSettingsState(
        print_font=FontSettings("Segoe UI", 9.5, True),
        table_font_size=12,
        breakdown_font_size=11,
        final_calc_font_size=18,
        totals_position="bottom",
    )

    controller.apply_state(state)

    assert calls == [
        ("font", state.print_font),
        ("table", 12),
        ("breakdown", 11),
        ("final", 18),
        ("position", "bottom"),
    ]
    assert settings.values == {
        "font/family": "Segoe UI",
        "font/size_float": 9.5,
        "font/bold": True,
        "ui/table_font_size": 12,
        "ui/breakdown_font_size": 11,
        "ui/final_calc_font_size": 18,
        "ui/estimate_totals_position": "bottom",
    }


def test_rejected_runtime_value_does_not_persist_appearance_settings() -> None:
    settings = _MemorySettings({"existing": "value"})
    calls: list[tuple[str, object]] = []
    controller = SettingsAppearanceController(
        settings,
        _recording_actions(calls, rejected="breakdown"),
    )

    with pytest.raises(RuntimeError, match="breakdown font size"):
        controller.apply_state(AppearanceSettingsState())

    assert settings.values == {"existing": "value"}
    assert [label for label, _value in calls] == ["font", "table", "breakdown"]


def test_validation_runs_before_runtime_or_persistence_changes() -> None:
    settings = _MemorySettings()
    calls: list[tuple[str, object]] = []
    controller = SettingsAppearanceController(
        settings,
        _recording_actions(calls),
    )
    invalid_state = AppearanceSettingsState(table_font_size=20)

    with pytest.raises(ValueError, match="Table font size"):
        controller.apply_state(invalid_state)

    assert not calls
    assert not settings.values
