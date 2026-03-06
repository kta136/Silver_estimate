from silverestimate.infrastructure.logger import get_log_config
from silverestimate.infrastructure.settings import get_app_settings


def test_get_log_config_migrates_legacy_enable_error_setting(settings_stub):
    settings = get_app_settings()
    settings.setValue("logging/enable_error", False)

    config = get_log_config()

    assert config["enable_error"] is False
    assert settings.value("logging/enable_critical") is False
    assert settings.value("logging/enable_error") is None
