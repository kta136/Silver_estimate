from silverestimate.infrastructure.logger import get_log_config
from silverestimate.infrastructure.settings import get_app_settings


def test_get_log_config_reads_enable_critical_setting(settings_stub):
    settings = get_app_settings()
    settings.setValue("logging/enable_critical", False)

    config = get_log_config()

    assert config["enable_error"] is False
