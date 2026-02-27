from PyQt5.QtWidgets import QApplication, QMessageBox

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


def _row_for_bar_id(model, bar_id: int) -> int:
    for row in range(model.rowCount()):
        if model.bar_id_at(row) == bar_id:
            return row
    raise AssertionError(f"Could not find bar_id={bar_id} in model")


def test_management_dialog_uses_model_ids_for_add_and_copy(qtbot, settings_stub, monkeypatch):
    del settings_stub
    db = _FakeSilverBarManagementDb()
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
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


def test_management_dialog_marks_selected_list_as_issued(qtbot, settings_stub, monkeypatch):
    del settings_stub
    db = _FakeSilverBarManagementDb()
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
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
