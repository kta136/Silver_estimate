from __future__ import annotations

import pytest

from silverestimate.infrastructure import qt_bootstrap


@pytest.mark.parametrize(
    "platform, configured, expected",
    [
        pytest.param("win32", None, "windows:darkmode=0", id="sets-default-when-unset"),
        pytest.param(
            "linux", "windows:darkmode=2", "windows:darkmode=2", id="noop-off-windows"
        ),
        pytest.param("win32", "offscreen", "offscreen", id="keeps-offscreen"),
        pytest.param(
            "win32",
            "windows:fontengine=freetype,darkmode=2",
            "windows:fontengine=freetype,darkmode=0",
            id="replaces-existing-darkmode",
        ),
        pytest.param(
            "win32",
            "windows:fontengine=freetype,menus=native,darkmode=1",
            "windows:fontengine=freetype,menus=native,darkmode=0",
            id="keeps-other-options",
        ),
    ],
)
def test_disable_windows_dark_mode(platform, configured, expected) -> None:
    environ: dict[str, str] = {}
    if configured is not None:
        environ[qt_bootstrap.QT_QPA_PLATFORM] = configured

    qt_bootstrap.disable_windows_dark_mode(environ=environ, platform=platform)

    assert environ[qt_bootstrap.QT_QPA_PLATFORM] == expected


def test_set_pass_through_high_dpi_rounding_policy_uses_available_policy() -> None:
    calls: list[str] = []

    class StubPolicy:
        PassThrough = "pass-through"

    class StubQt:
        HighDpiScaleFactorRoundingPolicy = StubPolicy

    class StubQGuiApplication:
        @staticmethod
        def setHighDpiScaleFactorRoundingPolicy(policy: str) -> None:
            calls.append(policy)

    applied = qt_bootstrap.set_pass_through_high_dpi_rounding_policy(
        qgui_application=StubQGuiApplication,
        qt=StubQt,
    )

    assert applied is True
    assert calls == ["pass-through"]


def test_set_pass_through_high_dpi_rounding_policy_skips_missing_policy() -> None:
    class StubQt:
        pass

    class StubQGuiApplication:
        @staticmethod
        def setHighDpiScaleFactorRoundingPolicy(policy: object) -> None:
            raise AssertionError("setter should not be called")

    applied = qt_bootstrap.set_pass_through_high_dpi_rounding_policy(
        qgui_application=StubQGuiApplication,
        qt=StubQt,
    )

    assert applied is False


def test_available_application_attributes_guards_missing_qt_attrs() -> None:
    class StubApplicationAttribute:
        AA_EnableHighDpiScaling = "enable-high-dpi"
        AA_DontUseNativeDialogs = "dont-use-native-dialogs"

    class StubQt:
        ApplicationAttribute = StubApplicationAttribute

    attrs = qt_bootstrap.available_application_attributes(qt=StubQt)

    assert attrs == ("enable-high-dpi", "dont-use-native-dialogs")
