import logging
import types
from typing import Any

from silverestimate.services import main_commands


class _SignalStub:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self.callbacks):
            callback(*args)


class _MessageBoxInstanceStub:
    return_value = None
    instances: list["_MessageBoxInstanceStub"] = []

    def __init__(self, parent=None):
        self.parent = parent
        self.icon = None
        self.window_title = None
        self.text = None
        self.informative_text = None
        self.checkbox = None
        self.standard_buttons = None
        self.default_button = None
        _MessageBoxInstanceStub.instances.append(self)

    @classmethod
    def reset(cls):
        cls.return_value = _MessageBoxStub.Yes
        cls.instances = []

    def setIcon(self, icon):
        self.icon = icon

    def setWindowTitle(self, title):
        self.window_title = title

    def setText(self, text):
        self.text = text

    def setInformativeText(self, text):
        self.informative_text = text

    def setCheckBox(self, checkbox):
        self.checkbox = checkbox

    def setStandardButtons(self, buttons):
        self.standard_buttons = buttons

    def setDefaultButton(self, button):
        self.default_button = button

    def exec_(self):
        return type(self).return_value


class _MessageBoxStub:
    Yes = 1
    Cancel = 0
    Question = 3

    return_warning = Yes
    information_calls: list[tuple[Any, ...]] = []
    critical_calls: list[tuple[Any, ...]] = []
    warning_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    @classmethod
    def reset(cls):
        cls.return_warning = cls.Yes
        cls.information_calls = []
        cls.critical_calls = []
        cls.warning_calls = []
        _MessageBoxInstanceStub.reset()

    def __new__(cls, *args, **kwargs):
        return _MessageBoxInstanceStub(*args, **kwargs)

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


class _FileDialogStub:
    next_save_result = ("", "")
    next_open_result = ("", "")

    @classmethod
    def getSaveFileName(cls, *args, **kwargs):  # noqa: D401 - mimic Qt signature
        return cls.next_save_result

    @classmethod
    def getOpenFileName(cls, *args, **kwargs):  # noqa: D401 - mimic Qt signature
        return cls.next_open_result


class _InputDialogStub:
    next_result = ("", False)

    @classmethod
    def getText(cls, *args, **kwargs):  # noqa: D401 - mimic Qt signature
        return cls.next_result


class _CheckBoxStub:
    checked = False

    def __init__(self, text):
        self.text = text

    def isChecked(self):
        return type(self).checked


class _ThreadStub:
    def __init__(self, parent=None):
        self.parent = parent
        self.started = _SignalStub()
        self.finished = _SignalStub()
        self.started_flag = False
        self.quit_called = False
        self.deleted = False

    def start(self):
        self.started_flag = True

    def quit(self, *args, **kwargs):
        del args, kwargs
        self.quit_called = True

    def deleteLater(self):
        self.deleted = True


class _WorkerStub:
    instances: list["_WorkerStub"] = []

    def __init__(self, *, db_path, file_path):
        self.db_path = db_path
        self.file_path = file_path
        self.finished = _SignalStub()
        self.error = _SignalStub()
        self.thread = None
        self.deleted = False
        type(self).instances.append(self)

    @classmethod
    def reset(cls):
        cls.instances = []

    def moveToThread(self, thread):
        self.thread = thread

    def run(self):
        return None

    def deleteLater(self):
        self.deleted = True


def _install_stubs(monkeypatch):
    _MessageBoxStub.reset()
    _WorkerStub.reset()
    _FileDialogStub.next_save_result = ("", "")
    _FileDialogStub.next_open_result = ("", "")
    _InputDialogStub.next_result = ("", False)
    _CheckBoxStub.checked = False
    monkeypatch.setattr(main_commands, "QMessageBox", _MessageBoxStub)
    monkeypatch.setattr(main_commands, "QFileDialog", _FileDialogStub)
    monkeypatch.setattr(main_commands, "QInputDialog", _InputDialogStub)
    monkeypatch.setattr(main_commands, "QCheckBox", _CheckBoxStub)
    monkeypatch.setattr(main_commands, "QThread", _ThreadStub)
    monkeypatch.setattr(main_commands, "_ItemCatalogExportWorker", _WorkerStub)


def _make_commands(main_window=None, db_manager=None):
    return main_commands.MainCommands(
        main_window or types.SimpleNamespace(),
        db_manager=db_manager,
        logger=logging.getLogger("test.main_commands"),
    )


def test_save_estimate_invokes_widget(monkeypatch):
    _install_stubs(monkeypatch)

    calls = []

    class _EstimateWidget:
        def save_estimate(self):
            calls.append("save")

    commands = _make_commands(types.SimpleNamespace(estimate_widget=_EstimateWidget()))

    commands.save_estimate()

    assert calls == ["save"]
    assert _MessageBoxStub.information_calls == []


def test_save_estimate_shows_info_when_missing(monkeypatch):
    _install_stubs(monkeypatch)

    commands = _make_commands(types.SimpleNamespace())

    commands.save_estimate()

    assert _MessageBoxStub.information_calls


def test_save_estimate_handles_errors(monkeypatch):
    _install_stubs(monkeypatch)

    class _EstimateWidget:
        def save_estimate(self):
            raise RuntimeError("boom")

    commands = _make_commands(types.SimpleNamespace(estimate_widget=_EstimateWidget()))

    commands.save_estimate()

    assert _MessageBoxStub.critical_calls


def test_print_estimate_invokes_widget(monkeypatch):
    _install_stubs(monkeypatch)

    calls = []

    class _EstimateWidget:
        def print_estimate(self):
            calls.append("print")

    commands = _make_commands(types.SimpleNamespace(estimate_widget=_EstimateWidget()))

    commands.print_estimate()

    assert calls == ["print"]
    assert _MessageBoxStub.information_calls == []


def test_print_estimate_shows_info_when_missing(monkeypatch):
    _install_stubs(monkeypatch)

    commands = _make_commands(types.SimpleNamespace())

    commands.print_estimate()

    assert _MessageBoxStub.information_calls


def test_print_estimate_handles_errors(monkeypatch):
    _install_stubs(monkeypatch)

    class _EstimateWidget:
        def print_estimate(self):
            raise RuntimeError("boom")

    commands = _make_commands(types.SimpleNamespace(estimate_widget=_EstimateWidget()))

    commands.print_estimate()

    assert _MessageBoxStub.critical_calls


def test_delete_all_data_success_refreshes_views(monkeypatch):
    _install_stubs(monkeypatch)
    _MessageBoxStub.return_warning = _MessageBoxStub.Yes
    _InputDialogStub.next_result = ("DELETE", True)
    actions: list[Any] = []

    class _DB:
        def drop_tables(self):
            actions.append("drop")
            return True

        def setup_database(self):
            actions.append("setup")

    class _ItemMaster:
        def load_items(self):
            actions.append("load_items")

    class _EstimateWidget:
        def clear_form(self, confirm=True):
            actions.append(("clear_form", confirm))

    commands = _make_commands(
        types.SimpleNamespace(
            item_master_widget=_ItemMaster(),
            estimate_widget=_EstimateWidget(),
        ),
        db_manager=_DB(),
    )

    commands.delete_all_data()

    assert actions == ["drop", "setup", "load_items", ("clear_form", False)]
    assert any(args[1] == "Success" for args in _MessageBoxStub.information_calls)


def test_delete_all_data_cancelled_at_warning(monkeypatch):
    _install_stubs(monkeypatch)
    _MessageBoxStub.return_warning = _MessageBoxStub.Cancel

    class _DB:
        def drop_tables(self):
            raise AssertionError("should not be called")

    commands = _make_commands(db_manager=_DB())

    commands.delete_all_data()

    assert _MessageBoxStub.information_calls == []
    assert _MessageBoxStub.critical_calls == []


def test_delete_all_data_cancelled_on_text_prompt(monkeypatch):
    _install_stubs(monkeypatch)
    _MessageBoxStub.return_warning = _MessageBoxStub.Yes
    _InputDialogStub.next_result = ("nope", True)

    class _DB:
        def drop_tables(self):
            raise AssertionError("should not be called")

    commands = _make_commands(db_manager=_DB())

    commands.delete_all_data()

    assert any(args[1] == "Cancelled" for args in _MessageBoxStub.information_calls)


def test_delete_all_data_handles_drop_tables_failure(monkeypatch):
    _install_stubs(monkeypatch)
    _MessageBoxStub.return_warning = _MessageBoxStub.Yes
    _InputDialogStub.next_result = ("DELETE", True)

    class _DB:
        def drop_tables(self):
            return False

    commands = _make_commands(db_manager=_DB())

    commands.delete_all_data()

    assert _MessageBoxStub.critical_calls


def test_delete_all_data_handles_exceptions(monkeypatch):
    _install_stubs(monkeypatch)
    _MessageBoxStub.return_warning = _MessageBoxStub.Yes
    _InputDialogStub.next_result = ("DELETE", True)

    class _DB:
        def drop_tables(self):
            raise RuntimeError("db boom")

    commands = _make_commands(db_manager=_DB())

    commands.delete_all_data()

    assert any("db boom" in args[2] for args in _MessageBoxStub.critical_calls)


def test_restore_item_catalog_returns_when_file_not_selected(monkeypatch):
    _install_stubs(monkeypatch)
    _FileDialogStub.next_open_result = ("", "")
    commands = _make_commands(db_manager=object())

    commands.restore_item_catalog()

    assert _MessageBoxInstanceStub.instances == []


def test_restore_item_catalog_returns_when_confirmation_cancelled(monkeypatch):
    _install_stubs(monkeypatch)
    _FileDialogStub.next_open_result = ("backup.seitems.json", "Silver Estimate")
    _MessageBoxInstanceStub.return_value = _MessageBoxStub.Cancel
    import_calls: list[Any] = []

    monkeypatch.setitem(
        __import__("sys").modules,
        "silverestimate.services.item_catalog_transfer",
        types.SimpleNamespace(
            ITEM_CATALOG_FILE_FILTER="filter",
            import_item_catalog=lambda *args, **kwargs: import_calls.append((args, kwargs)),
        ),
    )

    commands = _make_commands(db_manager=object())
    commands.restore_item_catalog()

    assert import_calls == []


def test_restore_item_catalog_success_refreshes_visible_item_master(monkeypatch):
    _install_stubs(monkeypatch)
    _FileDialogStub.next_open_result = ("backup.seitems.json", "Silver Estimate")
    _MessageBoxInstanceStub.return_value = _MessageBoxStub.Yes
    _CheckBoxStub.checked = True
    import_calls: list[Any] = []
    load_calls: list[str] = []

    def _import_item_catalog(db, file_path, *, replace_existing=False):
        import_calls.append((db, file_path, replace_existing))
        return {"total": 4, "inserted": 1, "updated": 2, "deleted": 1}

    monkeypatch.setitem(
        __import__("sys").modules,
        "silverestimate.services.item_catalog_transfer",
        types.SimpleNamespace(
            ITEM_CATALOG_FILE_FILTER="filter",
            import_item_catalog=_import_item_catalog,
        ),
    )

    class _ItemMaster:
        def isVisible(self):
            return True

        def load_items(self):
            load_calls.append("load")

    db = object()
    commands = _make_commands(
        types.SimpleNamespace(item_master_widget=_ItemMaster()),
        db_manager=db,
    )

    commands.restore_item_catalog()

    assert import_calls == [(db, "backup.seitems.json", True)]
    assert load_calls == ["load"]
    assert any(args[1] == "Restore Complete" for args in _MessageBoxStub.information_calls)


def test_restore_item_catalog_handles_import_failure(monkeypatch):
    _install_stubs(monkeypatch)
    _FileDialogStub.next_open_result = ("backup.seitems.json", "Silver Estimate")
    _MessageBoxInstanceStub.return_value = _MessageBoxStub.Yes

    monkeypatch.setitem(
        __import__("sys").modules,
        "silverestimate.services.item_catalog_transfer",
        types.SimpleNamespace(
            ITEM_CATALOG_FILE_FILTER="filter",
            import_item_catalog=lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError("import failed")
            ),
        ),
    )

    commands = _make_commands(db_manager=object())
    commands.restore_item_catalog()

    assert any(args[1] == "Restore Failed" for args in _MessageBoxStub.critical_calls)


def test_delete_all_estimates_clears_form(monkeypatch):
    _install_stubs(monkeypatch)
    _MessageBoxStub.return_warning = _MessageBoxStub.Yes

    class _DB:
        def delete_all_estimates(self):
            return True

    clear_calls: list[bool] = []

    class _EstimateWidget:
        def clear_form(self, confirm=True):
            clear_calls.append(confirm)

    commands = _make_commands(
        types.SimpleNamespace(estimate_widget=_EstimateWidget()),
        db_manager=_DB(),
    )

    commands.delete_all_estimates()

    assert clear_calls == [False]
    assert any(args[1] == "Success" for args in _MessageBoxStub.information_calls)


def test_delete_all_estimates_handles_database_failure(monkeypatch):
    _install_stubs(monkeypatch)
    _MessageBoxStub.return_warning = _MessageBoxStub.Yes

    class _DB:
        def delete_all_estimates(self):
            return False

    commands = _make_commands(db_manager=_DB())

    commands.delete_all_estimates()

    assert _MessageBoxStub.critical_calls


def test_delete_all_estimates_handles_clear_form_exception(monkeypatch):
    _install_stubs(monkeypatch)
    _MessageBoxStub.return_warning = _MessageBoxStub.Yes

    class _DB:
        def delete_all_estimates(self):
            return True

    class _EstimateWidget:
        def clear_form(self, confirm=True):
            raise RuntimeError("clear failed")

    commands = _make_commands(
        types.SimpleNamespace(estimate_widget=_EstimateWidget()),
        db_manager=_DB(),
    )

    commands.delete_all_estimates()

    assert any(args[1] == "Success" for args in _MessageBoxStub.information_calls)


def test_create_item_catalog_backup_starts_worker(monkeypatch):
    _install_stubs(monkeypatch)
    _FileDialogStub.next_save_result = ("backup.json", "JSON Files (*.json)")
    started: list[dict[str, str]] = []

    class _DB:
        temp_db_path = "/tmp/catalog.sqlite"

    commands = _make_commands(db_manager=_DB())
    monkeypatch.setattr(
        commands,
        "_start_item_catalog_export_worker",
        lambda **kwargs: started.append(kwargs),
    )

    commands.create_item_catalog_backup()

    assert started == [
        {
            "db_path": "/tmp/catalog.sqlite",
            "file_path": "backup.json.seitems.json",
        }
    ]


def test_create_item_catalog_backup_requires_temp_db_path(monkeypatch):
    _install_stubs(monkeypatch)
    _FileDialogStub.next_save_result = ("backup", "Silver Estimate Item Catalog")

    class _DB:
        temp_db_path = None

    commands = _make_commands(db_manager=_DB())

    commands.create_item_catalog_backup()

    assert _MessageBoxStub.critical_calls


def test_start_item_catalog_export_worker_rejects_duplicate(monkeypatch):
    _install_stubs(monkeypatch)
    commands = _make_commands()
    commands._catalog_export_thread = object()

    commands._start_item_catalog_export_worker(
        db_path="/tmp/catalog.sqlite",
        file_path="backup.seitems.json",
    )

    assert any(args[1] == "Catalog Backup" for args in _MessageBoxStub.information_calls)


def test_start_item_catalog_export_worker_wires_thread_and_cleanup(monkeypatch):
    _install_stubs(monkeypatch)
    commands = _make_commands(main_window=types.SimpleNamespace())

    commands._start_item_catalog_export_worker(
        db_path="/tmp/catalog.sqlite",
        file_path="backup.seitems.json",
    )

    worker = commands._catalog_export_worker
    thread = commands._catalog_export_thread
    assert isinstance(worker, _WorkerStub)
    assert isinstance(thread, _ThreadStub)
    assert worker.thread is thread
    assert thread.started_flag is True

    worker.finished.emit(7)
    assert any(args[1] == "Export Successful" for args in _MessageBoxStub.information_calls)
    assert thread.quit_called is True

    thread.finished.emit()
    assert commands._catalog_export_worker is None
    assert commands._catalog_export_thread is None
    assert worker.deleted is True
    assert thread.deleted is True


def test_on_item_catalog_export_failed_shows_error(monkeypatch):
    _install_stubs(monkeypatch)
    commands = _make_commands()

    commands._on_item_catalog_export_failed("bad export")

    assert _MessageBoxStub.critical_calls == [
        (commands.main_window, "Export Failed", "bad export")
    ]


def test_update_db_resets_export_worker_state(monkeypatch):
    _install_stubs(monkeypatch)
    commands = _make_commands(db_manager=object())
    commands._catalog_export_thread = object()
    commands._catalog_export_worker = object()
    replacement_db = object()

    commands.update_db(replacement_db)

    assert commands.db is replacement_db
    assert commands._catalog_export_thread is None
    assert commands._catalog_export_worker is None


def test_ensure_db_shows_error_when_missing(monkeypatch):
    _install_stubs(monkeypatch)
    commands = _make_commands(db_manager=None)

    assert commands._ensure_db() is False
    assert _MessageBoxStub.critical_calls


def test_refresh_views_after_data_reset_tolerates_view_failures(monkeypatch):
    _install_stubs(monkeypatch)
    calls: list[Any] = []

    class _ItemMaster:
        def load_items(self):
            calls.append("item_master")
            raise RuntimeError("item-master-failed")

    class _EstimateWidget:
        def clear_form(self, confirm=True):
            calls.append(("estimate_widget", confirm))
            raise RuntimeError("estimate-clear-failed")

    commands = _make_commands(
        types.SimpleNamespace(
            item_master_widget=_ItemMaster(),
            estimate_widget=_EstimateWidget(),
        )
    )

    commands._refresh_views_after_data_reset()

    assert calls == ["item_master", ("estimate_widget", False)]
