from __future__ import annotations

from silverestimate.infrastructure import qt_bootstrap


def test_disable_windows_dark_mode_sets_default_when_env_missing() -> None:
    environ: dict[str, str] = {}

    qt_bootstrap.disable_windows_dark_mode(environ=environ, platform="win32")

    assert environ[qt_bootstrap.QT_QPA_PLATFORM] == "windows:darkmode=0"


def test_disable_windows_dark_mode_is_noop_outside_windows() -> None:
    environ = {qt_bootstrap.QT_QPA_PLATFORM: "windows:darkmode=2"}

    qt_bootstrap.disable_windows_dark_mode(environ=environ, platform="linux")

    assert environ[qt_bootstrap.QT_QPA_PLATFORM] == "windows:darkmode=2"


def test_disable_windows_dark_mode_preserves_offscreen_platform() -> None:
    environ = {qt_bootstrap.QT_QPA_PLATFORM: "offscreen"}

    qt_bootstrap.disable_windows_dark_mode(environ=environ, platform="win32")

    assert environ[qt_bootstrap.QT_QPA_PLATFORM] == "offscreen"


def test_disable_windows_dark_mode_replaces_existing_darkmode() -> None:
    environ = {qt_bootstrap.QT_QPA_PLATFORM: "windows:fontengine=freetype,darkmode=2"}

    qt_bootstrap.disable_windows_dark_mode(environ=environ, platform="win32")

    assert (
        environ[qt_bootstrap.QT_QPA_PLATFORM]
        == "windows:fontengine=freetype,darkmode=0"
    )


def test_windows_platform_parser_preserves_non_darkmode_options() -> None:
    platform = "windows:fontengine=freetype,menus=native,darkmode=1"

    parsed = qt_bootstrap.windows_platform_without_dark_mode(platform)

    assert parsed == "windows:fontengine=freetype,menus=native,darkmode=0"


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
