from __future__ import annotations

import types
from pathlib import Path

import pytest

from silverestimate.controllers.startup_controller import StartupResult, StartupStatus
from silverestimate.infrastructure import application as application_module
from silverestimate.infrastructure.application import ApplicationBuilder, StartupError


class StubLogger:
    def __init__(self) -> None:
        self.records: list[tuple[str, str, dict]] = []

    def _record(self, level: str, message: str, *args, **kwargs) -> None:
        if args:
            try:
                message = message % args
            except Exception:
                message = f"{message} {args}"
        self.records.append((level, message, kwargs))

    def info(self, message: str, *args, **kwargs) -> None:
        self._record("info", message, *args, **kwargs)

    def debug(self, message: str, *args, **kwargs) -> None:
        self._record("debug", message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        self._record("warning", message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        self._record("error", message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs) -> None:
        self._record("critical", message, *args, **kwargs)


@pytest.fixture
def stub_qt(monkeypatch):
    class StubQtCore:
        handler = None

        @staticmethod
        def qInstallMessageHandler(handler):
            StubQtCore.handler = handler

    class StubQApplication:
        instance_ref = None
        set_attrs: list[int] = []
        exec_result = 0

        def __init__(self, args):
            type(self).instance_ref = self
            self.args = list(args)
            self.icon = None
            self.exec_calls = 0

        @classmethod
        def instance(cls):
            return cls.instance_ref

        @classmethod
        def setAttribute(cls, attr):
            cls.set_attrs.append(attr)

        def setWindowIcon(self, icon):
            self.icon = icon

        def exec_(self):
            self.exec_calls += 1
            return type(self).exec_result

    class StubMessageBox:
        last_call = None

        @staticmethod
        def critical(parent, title, message):
            StubMessageBox.last_call = (parent, title, message)

    monkeypatch.setattr(application_module, "QtCore", StubQtCore)
    monkeypatch.setattr(application_module, "QApplication", StubQApplication)
    monkeypatch.setattr(application_module, "QMessageBox", StubMessageBox)
    monkeypatch.setattr(application_module, "set_app_user_model_id", lambda *_: None)
    return StubQApplication, StubMessageBox


def _make_builder(startup_result, main_window_factory, tmp_path):
    log_config = {
        "log_dir": str(tmp_path / "logs"),
        "debug_mode": False,
        "enable_info": True,
        "enable_error": True,
        "enable_debug": False,
        "cleanup_days": 7,
        "auto_cleanup": False,
    }

    def startup_controller_factory(logger=None):
        return types.SimpleNamespace(
            authenticate_and_prepare=lambda: startup_result
        )

    return ApplicationBuilder(
        main_window_factory=main_window_factory,
        startup_controller_factory=startup_controller_factory,
        log_config_getter=lambda: log_config,
        logging_setup=lambda **kwargs: StubLogger(),
        asset_resolver=lambda *parts: Path(tmp_path / "missing.ico"),
        icon_factory=lambda path: f"icon:{path}",
        qt_handler=lambda *args, **kwargs: None,
        qt_attributes=(11, 22),
    )


def test_run_returns_zero_when_auth_cancelled(tmp_path, stub_qt):
    stub_app, message_box = stub_qt
    factory_called = {"value": False}

    def main_window_factory(*, db_manager, logger):
        factory_called["value"] = True
        return object()

    builder = _make_builder(
        StartupResult(status=StartupStatus.CANCELLED),
        main_window_factory,
        tmp_path,
    )

    exit_code = builder.run()

    assert exit_code == 0
    assert factory_called["value"] is False
    assert stub_app.instance_ref.exec_calls == 0
    assert message_box.last_call is None


def test_run_returns_zero_when_data_wiped(tmp_path, stub_qt):
    stub_app, message_box = stub_qt
    factory_called = {"value": False}

    def main_window_factory(*, db_manager, logger):
        factory_called["value"] = True
        return object()

    builder = _make_builder(
        StartupResult(status=StartupStatus.WIPED, silent_wipe=False),
        main_window_factory,
        tmp_path,
    )

    exit_code = builder.run()

    assert exit_code == 0
    assert factory_called["value"] is False
    assert stub_app.instance_ref.exec_calls == 0
    assert message_box.last_call is None


def test_run_returns_error_when_auth_fails(tmp_path, stub_qt):
    stub_app, message_box = stub_qt
    factory_called = {"value": False}

    def main_window_factory(*, db_manager, logger):
        factory_called["value"] = True
        return object()

    builder = _make_builder(
        StartupResult(status=StartupStatus.FAILED, db=None),
        main_window_factory,
        tmp_path,
    )

    exit_code = builder.run()

    assert exit_code == 1
    assert factory_called["value"] is False
    assert stub_app.instance_ref.exec_calls == 0
    assert message_box.last_call is None


def test_run_initialises_main_window_and_enters_event_loop(tmp_path, stub_qt):
    stub_app, message_box = stub_qt
    stub_app.exec_result = 42

    class StubDbManager:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    class StubMainWindow:
        def __init__(self, *, db_manager, logger):
            self.db = db_manager
            self.logger = logger
            self.shown = False

        def show(self):
            self.shown = True

    db_manager = StubDbManager()
    created_windows: list[StubMainWindow] = []

    def main_window_factory(*, db_manager, logger):
        window = StubMainWindow(db_manager=db_manager, logger=logger)
        created_windows.append(window)
        return window

    builder = _make_builder(
        StartupResult(status=StartupStatus.OK, db=db_manager),
        main_window_factory,
        tmp_path,
    )

    exit_code = builder.run()

    assert exit_code == 42
    assert len(created_windows) == 1
    window = created_windows[0]
    assert window.shown is True
    assert window.db is db_manager
    assert db_manager.closed is True
    assert stub_app.instance_ref.exec_calls == 1
    assert message_box.last_call is None


def test_run_handles_startup_error_from_main_window(tmp_path, stub_qt):
    stub_app, message_box = stub_qt
    stub_app.exec_result = 7

    class StubDbManager:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    db_manager = StubDbManager()

    def main_window_factory(*, db_manager, logger):
        raise StartupError("boom")

    builder = _make_builder(
        StartupResult(status=StartupStatus.OK, db=db_manager),
        main_window_factory,
        tmp_path,
    )

    exit_code = builder.run()

    assert exit_code == 1
    assert db_manager.closed is True
    assert stub_app.instance_ref.exec_calls == 0
    assert message_box.last_call == (None, "Initialization Error", "boom")
