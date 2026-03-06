from PyQt5.QtWidgets import QApplication, QMessageBox

from silverestimate.ui.silver_bar_history import SilverBarHistoryDialog


def _history_bar(
    bar_id: int,
    voucher: str,
    note: str,
    weight: float,
    purity: float,
    fine_weight: float,
    date_added: str,
    status: str,
    list_id=None,
    list_identifier=None,
    issued_date=None,
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
        "list_identifier": list_identifier,
        "issued_date": issued_date,
    }


class _FakeSilverBarHistoryDb:
    def __init__(self):
        self.temp_db_path = None
        self.search_calls = []
        self.reactivated_calls = []
        self.history_rows = [
            _history_bar(
                101,
                "H001",
                "Issued note",
                10.0,
                99.0,
                9.90,
                "2026-02-15 10:00:00",
                "Issued",
                20,
                "LIST-020",
                "2026-02-15 12:00:00",
            ),
            _history_bar(
                102,
                "H002",
                "Stock note",
                9.5,
                98.0,
                9.31,
                "2026-02-14 10:00:00",
                "In Stock",
            ),
        ]
        self.issued_lists = [
            {
                "list_id": 20,
                "list_identifier": "LIST-020",
                "list_note": "Issued batch",
                "creation_date": "2026-02-14 09:00:00",
                "issued_date": "2026-02-15 12:00:00",
            }
        ]
        self.list_rows = {
            20: [
                _history_bar(
                    101,
                    "H001",
                    "Issued note",
                    10.0,
                    99.0,
                    9.90,
                    "2026-02-15 10:00:00",
                    "Issued",
                    20,
                    "LIST-020",
                    "2026-02-15 12:00:00",
                ),
                _history_bar(
                    103,
                    "H003",
                    "Issued note 2",
                    11.0,
                    97.0,
                    10.67,
                    "2026-02-13 10:00:00",
                    "Issued",
                    20,
                    "LIST-020",
                    "2026-02-15 12:00:00",
                ),
            ]
        }

    @staticmethod
    def _clone_rows(rows):
        return [dict(row) for row in rows]

    def search_silver_bar_history(self, **kwargs):
        self.search_calls.append(dict(kwargs))
        return self._clone_rows(self.history_rows)

    def get_silver_bar_lists(self, include_issued=True):
        del include_issued
        return self._clone_rows(self.issued_lists)

    def count_silver_bars_by_list_ids(self, list_ids):
        return {
            int(list_id): len(self.list_rows.get(int(list_id), []))
            for list_id in list_ids
        }

    def get_bars_in_list(self, list_id, limit=None, offset=0):
        rows = self._clone_rows(self.list_rows.get(int(list_id), []))
        if isinstance(limit, int) and limit > 0:
            rows = rows[offset : offset + limit]
        return rows

    def reactivate_silver_bar_list(self, list_id):
        self.reactivated_calls.append(int(list_id))
        return True


def _row_for_bar_id(model, bar_id: int) -> int:
    for row in range(model.rowCount()):
        if model.bar_id_at(row) == bar_id:
            return row
    raise AssertionError(f"Could not find bar_id={bar_id} in model")


def test_history_dialog_loads_models_and_reactivates_list(
    qtbot, settings_stub, monkeypatch
):
    del settings_stub
    db = _FakeSilverBarHistoryDb()
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes
    )
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok
    )
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.Ok)

    dialog = SilverBarHistoryDialog(db)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: dialog.isVisible(), timeout=1000)
    qtbot.waitUntil(lambda: dialog.bars_model.rowCount() == 2, timeout=1000)

    assert dialog.lists_model.rowCount() == 1
    assert dialog._table_cell_text(dialog.lists_table, 0, 5) == "2"

    selected_row = _row_for_bar_id(dialog.bars_model, 101)
    dialog.bars_table.selectRow(selected_row)
    qtbot.waitUntil(
        lambda: len(dialog.bars_table.selectionModel().selectedRows()) == 1,
        timeout=1000,
    )
    dialog.copy_selected_rows(dialog.bars_table)
    copied = QApplication.clipboard().text()
    assert copied.startswith("101\tH001 (Issued note)\t10.0")

    dialog.lists_table.selectRow(0)
    qtbot.waitUntil(lambda: dialog.list_bars_model.rowCount() == 2, timeout=1000)
    assert dialog.reactivate_button.isEnabled() is True

    dialog.reactivate_list()

    assert db.reactivated_calls == [20]
