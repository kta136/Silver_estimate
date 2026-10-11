import logging
import logging.handlers
import os
import time

import pytest

from silverestimate.infrastructure import logger as app_logger
from silverestimate.infrastructure.settings import get_app_settings

DAY = 24 * 60 * 60


@pytest.fixture()
def root_logging():
    """Give a test the root logger and restore its handlers afterwards."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield root
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(level)


def _file_handlers(root):
    return [h for h in root.handlers if isinstance(h, logging.FileHandler)]


def _age(path, days):
    stamp = time.time() - days * DAY
    os.utime(path, (stamp, stamp))


@pytest.mark.parametrize(
    ("level", "debug_mode", "enable_info"),
    [
        ("errors", False, False),
        ("normal", False, True),
        ("detailed", True, True),
        ("something-else", False, True),
    ],
)
def test_get_log_config_derives_the_switches_from_the_stored_level(
    settings_stub, monkeypatch, level, debug_mode, enable_info
):
    monkeypatch.delenv("SILVER_APP_DEBUG", raising=False)
    get_app_settings().setValue("logging/level", level)

    config = app_logger.get_log_config()

    assert config["debug_mode"] is debug_mode
    assert config["enable_info"] is enable_info
    assert config["enable_error"] is True


def test_backup_days_follow_the_retention_setting_only_when_enabled():
    assert app_logger.backup_days_for({"auto_cleanup": True, "cleanup_days": 7}) == 7
    assert (
        app_logger.backup_days_for({"auto_cleanup": False, "cleanup_days": 7})
        == app_logger.DEFAULT_BACKUP_DAYS
    )


def test_log_files_roll_over_at_midnight_and_keep_the_configured_days(
    tmp_path, root_logging
):
    app_logger.setup_logging(log_dir=tmp_path, debug_mode=True, backup_days=7)

    handlers = _file_handlers(root_logging)

    assert {os.path.basename(h.baseFilename) for h in handlers} == {
        "silver_app.log",
        "silver_app_error.log",
        "silver_app_debug.log",
    }
    for handler in handlers:
        assert isinstance(handler, logging.handlers.TimedRotatingFileHandler)
        assert handler.when == "MIDNIGHT"
        assert handler.backupCount == 7


def test_a_log_from_an_earlier_day_rolls_over_on_the_next_start(tmp_path, root_logging):
    stale = tmp_path / "silver_app.log"
    stale.write_text("written before the app was closed\n", encoding="utf-8")
    _age(stale, 2)
    for day in ("2026-01-01", "2026-01-02", "2026-01-03"):
        (tmp_path / f"silver_app.log.{day}").write_text(day, encoding="utf-8")

    app_logger.setup_logging(log_dir=tmp_path, enable_error=False, backup_days=2)

    rotated = sorted(p.name for p in tmp_path.glob("silver_app.log.*"))
    assert len(rotated) == 2
    assert rotated[0] == "silver_app.log.2026-01-03"
    assert "written before" in (tmp_path / rotated[1]).read_text(encoding="utf-8")
    assert "Logging initialized" in stale.read_text(encoding="utf-8")


def test_reconfiguring_releases_the_previous_log_files(tmp_path, root_logging):
    app_logger.setup_logging(log_dir=tmp_path)
    previous = _file_handlers(root_logging)

    app_logger.setup_logging(log_dir=tmp_path)

    assert previous
    assert all(handler.stream is None for handler in previous)
    assert not set(previous) & set(root_logging.handlers)


def test_cleanup_removes_old_files_but_not_the_ones_in_use(tmp_path, root_logging):
    app_logger.setup_logging(log_dir=tmp_path)
    in_use = tmp_path / "silver_app_error.log"
    leftover = tmp_path / "silver_app.log.3"
    recent = tmp_path / "silver_app.log.2026-01-01"
    leftover.write_text("size-rotated before daily rotation", encoding="utf-8")
    recent.write_text("recent", encoding="utf-8")
    _age(in_use, 10)
    _age(leftover, 10)

    removed = app_logger.cleanup_old_logs(tmp_path, max_age_days=7)

    assert removed == 1
    assert not leftover.exists()
    assert in_use.exists()
    assert recent.exists()
