import logging
import types

from silverestimate.services import main_commands


class _MessageBoxStub:
    Yes = 1
    Cancel = 0
    return_warning = Yes
    information_calls = []
    critical_calls = []
    warning_calls = []

    @classmethod
    def reset(cls):
        cls.return_warning = cls.Yes
        cls.information_calls = []
        cls.critical_calls = []
        cls.warning_calls = []

    @classmethod
    def information(cls, *args):
        cls.information_calls.append(args)
        return None

    @classmethod
    def critical(cls, *args):
        cls.critical_calls.append(args)
        return None

    @classmethod
    def warning(cls, *args, **kwargs):
        cls.warning_calls.append((args, kwargs))
        return cls.return_warning


class _InputDialogStub:
    next_result = ("", False)

    @classmethod
    def getText(cls, *args, **kwargs):  # noqa: D401 - mimic Qt signature
        return cls.next_result


def _install_stubs(monkeypatch):
    _MessageBoxStub.reset()
    _InputDialogStub.next_result = ("", False)
    monkeypatch.setattr(main_commands, "QMessageBox", _MessageBoxStub)
    monkeypatch.setattr(main_commands, "QInputDialog", _InputDialogStub)


def test_save_estimate_invokes_widget(monkeypatch):
    _install_stubs(monkeypatch)

    calls = []

    class _EstimateWidget:
        def save_estimate(self):
            calls.append("save")

    main_window = types.SimpleNamespace(estimate_widget=_EstimateWidget())
    commands = main_commands.MainCommands(main_window, db_manager=object(), logger=logging.getLogger("test"))

    commands.save_estimate()

    assert calls == ["save"]
    assert _MessageBoxStub.information_calls == []


def test_save_estimate_shows_info_when_missing(monkeypatch):
    _install_stubs(monkeypatch)

    main_window = types.SimpleNamespace()
    commands = main_commands.MainCommands(main_window, db_manager=object(), logger=logging.getLogger("test"))

    commands.save_estimate()

    assert _MessageBoxStub.information_calls


def test_delete_all_data_success(monkeypatch):
    _install_stubs(monkeypatch)
    _MessageBoxStub.return_warning = _MessageBoxStub.Yes
    _InputDialogStub.next_result = ("DELETE", True)

    actions = []

    class _DB:
        def drop_tables(self):
            actions.append("drop")
            return True

        def setup_database(self):
            actions.append("setup")

    main_window = types.SimpleNamespace()
    commands = main_commands.MainCommands(main_window, db_manager=_DB(), logger=logging.getLogger("test"))

    commands.delete_all_data()

    assert actions == ["drop", "setup"]
    assert any(args[1] == "Success" for args in _MessageBoxStub.information_calls)


def test_delete_all_data_cancel_on_confirmation(monkeypatch):
    _install_stubs(monkeypatch)
    _MessageBoxStub.return_warning = _MessageBoxStub.Yes
    _InputDialogStub.next_result = ("nope", True)

    class _DB:
        def drop_tables(self):
            raise AssertionError("should not be called")

    main_window = types.SimpleNamespace()
    commands = main_commands.MainCommands(main_window, db_manager=_DB(), logger=logging.getLogger("test"))

    commands.delete_all_data()

    assert _MessageBoxStub.information_calls


def test_delete_all_estimates_clears_form(monkeypatch):
    _install_stubs(monkeypatch)
    _MessageBoxStub.return_warning = _MessageBoxStub.Yes

    class _DB:
        def delete_all_estimates(self):
            return True

    clear_calls = []

    class _EstimateWidget:
        def clear_form(self, confirm=True):
            clear_calls.append(confirm)

    main_window = types.SimpleNamespace(
        estimate_widget=_EstimateWidget(),
    )
    commands = main_commands.MainCommands(main_window, db_manager=_DB(), logger=logging.getLogger("test"))

    commands.delete_all_estimates()

    assert clear_calls == [False]
    assert any(args[1] == "Success" for args in _MessageBoxStub.information_calls)
