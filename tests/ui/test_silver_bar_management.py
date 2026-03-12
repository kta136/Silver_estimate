import logging

from PyQt5.QtCore import QItemSelectionModel
from PyQt5.QtWidgets import QApplication, QFrame, QMessageBox

from silverestimate.ui.silver_bar_list_print_controller import (
    SilverBarListPrintController,
)
from silverestimate.ui.silver_bar_management import SilverBarDialog


def _bar(
    bar_id: int,
    voucher: str,
    note: str,
    weight: float,
    purity: float,
    fine_weight: float,
    date_added: str,
    status: str,
    list_id=None,
):
    return {
        "bar_id": bar_id,
        "estimate_voucher_no": voucher,
        "estimate_note": note,
        "weight": weight,
        "purity": purity,
        "fine_weight": fine_weight,
        "date_added": date_added,
        "status": status,
        "list_id": list_id,
    }


class _FakeSilverBarManagementDb:
    def __init__(self):
        self.temp_db_path = None
        self.assigned_calls = []
        self.marked_calls = []
        self.available_rows = [
            _bar(
                1,
                "V001",
                "Alpha",
                10.0,
                99.0,
                9.90,
                "2026-02-15 10:00:00",
                "In Stock",
            ),
            _bar(
                2,
                "V002",
                "Beta",
                9.0,
                98.0,
                8.82,
                "2026-02-14 10:00:00",
                "In Stock",
            ),
        ]
        self.list_rows = {
            10: [
                _bar(
                    20,
                    "L001",
                    "Listed",
                    12.0,
                    97.0,
                    11.64,
                    "2026-02-13 10:00:00",
                    "Assigned",
                    10,
                )
            ]
        }
        self.lists = [
            {
                "list_id": 10,
                "list_identifier": "LIST-010",
                "list_note": "Active list",
                "creation_date": "2026-02-10 09:00:00",
                "issued_date": None,
            }
        ]

    @staticmethod
    def _clone_rows(rows):
        return [dict(row) for row in rows]

    def get_available_silver_bars_page(self, **kwargs):
        del kwargs
        rows = self._clone_rows(self.available_rows)
        return rows, len(rows)

    def get_silver_bars_in_list_page(self, list_id, *, limit=None, offset=0):
        rows = self._clone_rows(self.list_rows.get(int(list_id), []))
        total = len(rows)
        if isinstance(limit, int) and limit > 0:
            rows = rows[offset : offset + limit]
        return rows, total

    def get_silver_bar_lists(self, include_issued=False):
        del include_issued
        return self._clone_rows(self.lists)

    def get_silver_bar_list_details(self, list_id):
        for row in self.lists:
            if int(row["list_id"]) == int(list_id):
                return dict(row)
        return None

    def assign_bar_to_list(self, bar_id, list_id):
        self.assigned_calls.append((int(bar_id), int(list_id)))
        for index, row in enumerate(list(self.available_rows)):
            if int(row["bar_id"]) == int(bar_id):
                moved = dict(row)
                moved["list_id"] = int(list_id)
                moved["status"] = "Assigned"
                self.available_rows.pop(index)
                self.list_rows.setdefault(int(list_id), []).append(moved)
                return True
        return False

    def mark_silver_bar_list_as_issued(self, list_id):
        self.marked_calls.append(int(list_id))
        self.lists = [row for row in self.lists if int(row["list_id"]) != int(list_id)]
        return True


class _ThreadStub:
    def __init__(self):
        self.quit_called = False
        self.wait_called = False
        self.deleted = False

    def quit(self):
        self.quit_called = True

    def wait(self, _timeout):
        self.wait_called = True
        return True

    def deleteLater(self):
        self.deleted = True


class _WorkerStub:
    def __init__(self):
        self.deleted = False

    def deleteLater(self):
        self.deleted = True


class _ProgressStub:
    def __init__(self):
        self.closed = False
        self.deleted = False

    def close(self):
        self.closed = True

    def deleteLater(self):
        self.deleted = True


def _row_for_bar_id(model, bar_id: int) -> int:
    for row in range(model.rowCount()):
        if model.bar_id_at(row) == bar_id:
            return row
    raise AssertionError(f"Could not find bar_id={bar_id} in model")


def test_management_dialog_uses_model_ids_for_add_and_copy(
    qtbot, settings_stub, monkeypatch
):
    del settings_stub
    db = _FakeSilverBarManagementDb()
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes
    )
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok
    )
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)

    dialog = SilverBarDialog(db)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: dialog.isVisible(), timeout=1000)
    qtbot.waitUntil(lambda: dialog.available_bars_model.rowCount() == 2, timeout=1000)

    dialog.list_combo.setCurrentIndex(1)
    qtbot.waitUntil(lambda: dialog.list_bars_model.rowCount() == 1, timeout=1000)

    selected_row = _row_for_bar_id(dialog.available_bars_model, 1)
    dialog.available_bars_table.selectRow(selected_row)
    qtbot.waitUntil(
        lambda: len(dialog.available_bars_table.selectionModel().selectedRows()) == 1,
        timeout=1000,
    )

    dialog._copy_selected_rows(dialog.available_bars_table)
    copied = QApplication.clipboard().text()
    assert copied.startswith("V001 (Alpha)\t10.000\t99.00")
    assert not copied.startswith("1\t")

    dialog.add_selected_to_list()

    assert db.assigned_calls == [(1, 10)]
    assert dialog.available_bars_model.rowCount() == 1
    assert dialog.list_bars_model.rowCount() == 2


def test_management_dialog_disables_list_actions_when_no_list_selected(
    qtbot, settings_stub
):
    del settings_stub
    dialog = SilverBarDialog(_FakeSilverBarManagementDb())
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: dialog.isVisible(), timeout=1000)
    qtbot.waitUntil(lambda: dialog.available_bars_model.rowCount() == 2, timeout=1000)

    assert dialog.current_list_id is None
    assert dialog.list_info_label.text() == "No list selected"
    assert dialog.add_to_list_button.isEnabled() is False
    assert dialog.add_all_button.isEnabled() is False
    assert dialog.remove_from_list_button.isEnabled() is False
    assert dialog.remove_all_button.isEnabled() is False
    assert dialog.edit_note_button.isEnabled() is False
    assert dialog.delete_list_button.isEnabled() is False
    assert dialog.mark_issued_button.isEnabled() is False
    assert dialog.print_list_button.isEnabled() is False
    assert dialog.export_list_button.isEnabled() is False
    assert dialog.list_bars_table.isEnabled() is False
    assert dialog.list_bars_table.property("listState") == "inactive"
    assert dialog.list_bars_table.horizontalHeader().property("listState") == "inactive"


def test_management_dialog_activates_list_table_visual_state_when_list_selected(
    qtbot, settings_stub
):
    del settings_stub
    dialog = SilverBarDialog(_FakeSilverBarManagementDb())
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: dialog.isVisible(), timeout=1000)
    qtbot.waitUntil(lambda: dialog.available_bars_model.rowCount() == 2, timeout=1000)

    dialog.list_combo.setCurrentIndex(1)
    qtbot.waitUntil(lambda: dialog.current_list_id == 10, timeout=1000)
    qtbot.waitUntil(lambda: dialog.list_bars_table.isEnabled() is True, timeout=1000)

    assert dialog.list_bars_table.property("listState") == "active"
    assert dialog.list_bars_table.horizontalHeader().property("listState") == "active"


def test_management_dialog_marks_selected_list_as_issued(
    qtbot, settings_stub, monkeypatch
):
    del settings_stub
    db = _FakeSilverBarManagementDb()
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes
    )
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok
    )
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)

    dialog = SilverBarDialog(db)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: dialog.isVisible(), timeout=1000)

    dialog.list_combo.setCurrentIndex(1)
    qtbot.waitUntil(lambda: dialog.current_list_id == 10, timeout=1000)

    dialog.mark_list_as_issued()

    assert db.marked_calls == [10]
    assert dialog.list_combo.count() == 1


def test_management_dialog_preserves_multi_selection_across_reload_and_adds_bars(
    qtbot, settings_stub, monkeypatch
):
    del settings_stub
    db = _FakeSilverBarManagementDb()
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes
    )
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok
    )
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)

    dialog = SilverBarDialog(db)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: dialog.isVisible(), timeout=1000)
    qtbot.waitUntil(lambda: dialog.available_bars_model.rowCount() == 2, timeout=1000)

    dialog.list_combo.setCurrentIndex(1)
    qtbot.waitUntil(lambda: dialog.current_list_id == 10, timeout=1000)

    selection_model = dialog.available_bars_table.selectionModel()
    first_row = _row_for_bar_id(dialog.available_bars_model, 1)
    second_row = _row_for_bar_id(dialog.available_bars_model, 2)
    selection_model.select(
        dialog.available_bars_model.index(first_row, 0),
        QItemSelectionModel.Select | QItemSelectionModel.Rows,
    )
    selection_model.select(
        dialog.available_bars_model.index(second_row, 0),
        QItemSelectionModel.Select | QItemSelectionModel.Rows,
    )
    qtbot.waitUntil(
        lambda: len(dialog.available_bars_table.selectionModel().selectedRows()) == 2,
        timeout=1000,
    )

    dialog.load_available_bars()

    qtbot.waitUntil(
        lambda: len(dialog.available_bars_table.selectionModel().selectedRows()) == 2,
        timeout=1000,
    )
    qtbot.waitUntil(lambda: dialog.add_to_list_button.isEnabled() is True, timeout=1000)

    dialog.add_selected_to_list()

    assert db.assigned_calls == [(1, 10), (2, 10)]
    assert dialog.available_bars_model.rowCount() == 0
    assert dialog.list_bars_model.rowCount() == 3


def test_management_dialog_omits_purity_range_filters(qtbot, settings_stub):
    del settings_stub
    dialog = SilverBarDialog(_FakeSilverBarManagementDb())
    qtbot.addWidget(dialog)

    assert dialog.findChild(QFrame, "SilverBarManagementHeaderCard") is None
    assert hasattr(dialog, "purity_min_spin") is False
    assert hasattr(dialog, "purity_max_spin") is False
    assert hasattr(dialog, "weight_tol_spin") is False
    assert hasattr(dialog, "available_limit_spin") is False
    assert hasattr(dialog, "refresh_available_button") is False
    assert hasattr(dialog, "auto_refresh_checkbox") is False


def test_list_print_preview_cleanup_removes_worker():
    harness = type(
        "_Harness",
        (),
        {
            "_active_print_preview_workers": {},
            "logger": logging.getLogger("test-list-preview"),
        },
    )()
    thread = _ThreadStub()
    worker = _WorkerStub()
    progress = _ProgressStub()
    harness._active_print_preview_workers[thread] = worker

    SilverBarListPrintController._finish_list_print_preview_build(
        harness,
        1,
        thread=thread,
        worker=worker,
        progress=progress,
    )

    assert thread.quit_called is True
    assert thread.wait_called is True
    assert thread.deleted is True
    assert worker.deleted is True
    assert progress.closed is True
    assert progress.deleted is True
    assert thread not in harness._active_print_preview_workers
