"""Encrypted recovery snapshots without committing or closing the active editor."""

from __future__ import annotations

import json
import math
from dataclasses import fields
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from PySide6.QtCore import QDate, QSignalBlocker, QTimer
from PySide6.QtWidgets import QAbstractItemView, QApplication, QLineEdit, QMessageBox

from silverestimate.domain.estimate_entry import EstimateEntryRowState
from silverestimate.domain.estimate_models import EstimateLineCategory
from silverestimate.persistence.draft_repository import (
    MAX_DRAFT_BYTES,
    DraftRecord,
    DraftRepository,
)
from silverestimate.ui.confirmation_layout import polish_confirmation

if TYPE_CHECKING:
    from .estimate_entry import EstimateEntryWidget

DRAFT_VERSION = 1
MAX_DRAFT_ROWS = 20_000
ROW_FIELDS = tuple(field.name for field in fields(EstimateEntryRowState))


def _decode_row(raw: Any) -> EstimateEntryRowState:
    if not isinstance(raw, dict):
        raise ValueError("Invalid recovery row")
    row = dict(raw)
    row["category"] = EstimateLineCategory(row["category"])
    for name in ("code", "name", "wage_type", "line_key"):
        if not isinstance(row.get(name), str):
            raise ValueError("Invalid recovery row text")
    for name in (
        "gross",
        "poly",
        "net_weight",
        "purity",
        "wage_rate",
        "wage_amount",
        "fine_weight",
    ):
        if not isinstance(row.get(name), (int, float)) or not math.isfinite(row[name]):
            raise ValueError("Invalid recovery row number")
    for name in ("pieces", "row_index", "snapshot_version"):
        if type(row.get(name)) is not int:
            raise ValueError("Invalid recovery integer")
    if row.get("tunch") is not None and not isinstance(row["tunch"], str):
        raise ValueError("Invalid recovery Tunch")
    return EstimateEntryRowState(**row)


def decode_draft(payload: str) -> tuple[dict[str, Any], list[EstimateEntryRowState]]:
    if len(payload.encode("utf-8")) > MAX_DRAFT_BYTES:
        raise ValueError("Recovery copy is too large")
    data = json.loads(payload)
    if not isinstance(data, dict) or data.get("version") != DRAFT_VERSION:
        raise ValueError("Unsupported recovery format")
    for field in ("voucher_no", "active_voucher_no", "date", "note"):
        if not isinstance(data.get(field), str):
            raise ValueError(f"Invalid recovery field: {field}")
    if not QDate.fromString(data["date"], "yyyy-MM-dd").isValid():
        raise ValueError("Invalid recovery date")
    for field in ("silver_rate", "last_balance_silver", "last_balance_amount"):
        if not isinstance(data.get(field), (int, float)) or not math.isfinite(
            data[field]
        ):
            raise ValueError(f"Invalid recovery number: {field}")
    for field in ("return_mode", "silver_bar_mode", "estimate_loaded"):
        if not isinstance(data.get(field), bool):
            raise ValueError(f"Invalid recovery flag: {field}")
    raw_rows = data.get("rows")
    if not isinstance(raw_rows, list) or len(raw_rows) > MAX_DRAFT_ROWS:
        raise ValueError("Invalid recovery rows")
    rows = [_decode_row(raw) for raw in raw_rows]
    editor = data.get("editor")
    if editor is not None and (
        not isinstance(editor, dict)
        or type(editor.get("row")) is not int
        or type(editor.get("column")) is not int
        or not 0 <= editor["row"] < len(rows)
        or not 0 <= editor["column"] < 13
        or not isinstance(editor.get("text"), str)
    ):
        raise ValueError("Invalid recovery editor")
    return data, rows


def choose_recovery(parent: Any, record: DraftRecord) -> str:
    dialog = QMessageBox(parent)
    dialog.setWindowTitle("Recover Unfinished Estimate")
    dialog.setText("Continue your unfinished estimate?")
    dialog.setInformativeText(
        f"Voucher {record.voucher_no} · Last preserved {record.updated_utc} (UTC)\n\n"
        "Restore the recovery copy to continue editing.\n"
        "Restoring does not save the estimate or change inventory.\n\n"
        "Only the recovery copy is discarded. This does not delete any saved estimate."
    )
    restore = dialog.addButton("Restore && continue", QMessageBox.ButtonRole.AcceptRole)
    discard = dialog.addButton(
        "Discard recovery copy", QMessageBox.ButtonRole.DestructiveRole
    )
    restore.setStyleSheet("background: #007f89; color: white; padding: 8px 14px;")
    discard.setStyleSheet(
        "border: 1px solid #dc2638; color: #dc2638; padding: 8px 14px;"
    )
    cancel = dialog.addButton(QMessageBox.StandardButton.Cancel)
    dialog.setDefaultButton(restore)
    dialog.setEscapeButton(cancel)
    polish_confirmation(dialog)
    try:
        dialog.exec()
        clicked = dialog.clickedButton()
        return (
            "restore"
            if clicked is restore
            else "discard"
            if clicked is discard
            else "cancel"
        )
    finally:
        dialog.deleteLater()


class EstimateDraftRecovery:
    """One recovery slot per database, with explicit ownership and user choice."""

    def __init__(self, host: EstimateEntryWidget, repository: DraftRepository) -> None:
        self.host = host
        self.repository = repository
        self._token: str | None = None
        self._last_payload: str | None = None
        self._waiting: DraftRecord | None = None
        self._started = False
        self._revision = 0
        self._captured_revision = -1
        self._discarded_revision = -1
        self._discarded_editor: dict[str, Any] | None = None
        self._captured_editor: dict[str, Any] | None = None
        self._startup_timer = QTimer(host)
        self._startup_timer.setSingleShot(True)
        self._startup_timer.timeout.connect(self.start)
        self._timer = QTimer(host)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(
            lambda: self.flush() if self.host.isVisible() else None
        )
        self.status = "Ready"

    def bind_changes(self) -> None:
        model = self.host.item_table.get_model()
        for signal in (
            model.dataChanged,
            model.rowsInserted,
            model.rowsRemoved,
            model.modelReset,
            self.host.note_edit.textChanged,
            self.host.date_edit.dateChanged,
            self.host.silver_rate_spin.valueChanged,
            self.host.voucher_edit.textChanged,
        ):
            signal.connect(self.mark_changed)

    def mark_changed(self, *_args: Any) -> None:
        self._revision += 1

    def schedule_start(self) -> None:
        if not self._started:
            self._startup_timer.start(200)

    def stop(self) -> None:
        self._startup_timer.stop()
        self._started = False
        self._timer.stop()

    def _set_status(self, status: str) -> None:
        self.status = status
        self.host.refresh_bottom_status()

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self.offer_recovery()
        self._timer.start()

    def _editor(self) -> dict[str, Any] | None:
        table = self.host.item_table
        editor = table.focusWidget()
        index = table.currentIndex()
        if (
            table.state() == QAbstractItemView.State.EditingState
            and isinstance(editor, QLineEdit)
            and table.isAncestorOf(editor)
            and index.isValid()
        ):
            return {"row": index.row(), "column": index.column(), "text": editor.text()}
        return None

    def _has_edit(self) -> bool:
        editor = self.host.item_table.focusWidget()
        return self.host.has_unsaved_changes() or (
            self._editor() is not None
            and isinstance(editor, QLineEdit)
            and editor.isModified()
        )

    def capture(self) -> str:
        # Do not use get_all_rows() on the view: generating line keys refreshes editors.
        rows = self.host.item_table.get_model().get_all_rows()
        if len(rows) > MAX_DRAFT_ROWS:
            raise ValueError("Entry exceeds the 20,000-row recovery limit")
        data = {
            "version": DRAFT_VERSION,
            "voucher_no": self.host.voucher_edit.text(),
            "active_voucher_no": getattr(
                self.host, "_active_voucher_no", self.host.voucher_edit.text()
            ),
            "date": self.host.date_edit.date().toString("yyyy-MM-dd"),
            "note": self.host.note_edit.text(),
            "silver_rate": self.host.silver_rate_spin.value(),
            "last_balance_silver": self.host.last_balance_silver,
            "last_balance_amount": self.host.last_balance_amount,
            "return_mode": self.host.return_mode,
            "silver_bar_mode": self.host.silver_bar_mode,
            "estimate_loaded": self.host._estimate_loaded,
            "rows": [
                dict(
                    {name: getattr(row, name) for name in ROW_FIELDS},
                    category=row.category.value,
                )
                for row in rows
            ],
            "editor": self._editor(),
        }
        return json.dumps(
            data, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )

    def flush(self) -> bool:
        if (
            not self._started
            or self._waiting is not None
            or self.host.initializing
            or QApplication.activeModalWidget() is not None
            or not self._has_edit()
            or (
                self._discarded_revision == self._revision
                and self._editor() == self._discarded_editor
            )
        ):
            return False
        try:
            editor = self._editor()
            if (
                self._last_payload is not None
                and self._captured_revision == self._revision
                and editor == self._captured_editor
            ):
                return True
            payload = self.capture()
            if payload == self._last_payload:
                self._captured_revision = self._revision
                self._captured_editor = editor
                return True
            token = self._token or uuid4().hex
            if not self.repository.write(
                token,
                self.host.voucher_edit.text().strip(),
                payload,
                expected_token=self._token,
            ):
                self._set_status("Waiting")
                return False
            self._token = token
            self._last_payload = payload
            self._captured_revision = self._revision
            self._captured_editor = editor
            self._set_status(f"Captured {datetime.now():%H:%M:%S}")
            return True
        except Exception:
            self.host.logger.exception("Could not update encrypted entry recovery")
            self._set_status("Update failed")
            return False

    def discard_current(self) -> bool:
        if self._token is None:
            return True
        try:
            if not self.repository.delete(self._token):
                self._set_status("Waiting")
                return False
            self._token = None
            self._last_payload = None
            self._discarded_revision = self._revision
            self._discarded_editor = self._editor()
            self._set_status("Ready")
            return True
        except Exception:
            self.host.logger.exception("Could not remove entry recovery")
            self._set_status("Removal failed")
            return False

    def offer_recovery(self) -> None:
        try:
            record = self._waiting or self.repository.load()
            if record is None:
                return
            self._waiting = record
            self._set_status("Available")
            reply = choose_recovery(self.host, record)
            if reply == "discard":
                if not self.repository.delete(record.token):
                    raise RuntimeError("Recovery storage is busy; try again")
                self._waiting = None
                self._set_status("Ready")
            elif reply == "restore":
                data, rows = decode_draft(record.payload)
                if (
                    self.host.has_unsaved_changes()
                    and not self.host.workflow_controller._confirm_unsaved(
                        "restoring the recovery copy"
                    )
                ):
                    return
                self._apply(data, rows)
                self._token = record.token
                self._last_payload = None
                self._waiting = None
                self._set_status("Restored")
        except Exception:
            self.host.logger.exception("Could not restore encrypted entry recovery")
            self._set_status("Recovery needs attention")
            QMessageBox.warning(
                self.host,
                "Draft Recovery",
                "Could not restore the recovery copy. It has been retained. Use Tools → Recover Unfinished Estimate to retry or discard it.",
            )

    def _apply(self, data: dict[str, Any], rows: list[EstimateEntryRowState]) -> None:
        self.host._push_unsaved_block()
        blocker = QSignalBlocker(self.host.voucher_edit)
        try:
            self.host.item_table.replace_all_rows(rows)
            self.host.set_voucher_number(data["active_voucher_no"])
            self.host.voucher_edit.setText(data["voucher_no"])
            self.host.date_edit.setDate(QDate.fromString(data["date"], "yyyy-MM-dd"))
            self.host.note_edit.setText(data["note"])
            self.host.silver_rate_spin.setValue(data["silver_rate"])
            self.host.last_balance_silver = data["last_balance_silver"]
            self.host.last_balance_amount = data["last_balance_amount"]
            self.host.return_mode = data["return_mode"]
            self.host.silver_bar_mode = data["silver_bar_mode"]
            self.host._estimate_loaded = data["estimate_loaded"]
            self.host.delete_estimate_button.setEnabled(data["estimate_loaded"])
            self.host.return_toggle_button.setChecked(data["return_mode"])
            self.host.silver_bar_toggle_button.setChecked(data["silver_bar_mode"])
            self.host.workflow_controller._sync_mode_controls()
            self.host.workflow_controller._clear_row_undo()
            self.host.totals_controller.calculate_totals()
        finally:
            del blocker
            self.host._pop_unsaved_block()
        self.host._set_unsaved(True, force=True)
        self.host._active_voucher_no = data["active_voucher_no"]
        if data.get("editor"):
            QTimer.singleShot(
                0, self.host, lambda: self._restore_editor(data["editor"])
            )

    def _restore_editor(self, state: dict[str, Any]) -> None:
        table = self.host.item_table
        if table.begin_cell_edit(state["row"], state["column"]):
            editor = table.focusWidget()
            if isinstance(editor, QLineEdit):
                editor.setText(state["text"])
                editor.setModified(True)
                editor.setFocus()
