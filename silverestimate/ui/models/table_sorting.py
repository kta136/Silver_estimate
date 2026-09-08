"""Reorder flat model rows without changing what Qt selections identify."""

from collections.abc import Callable
from typing import Any, TypeVar

from PySide6.QtCore import QAbstractTableModel, QModelIndex

RowT = TypeVar("RowT")


def sort_model_rows(
    model: QAbstractTableModel,
    rows: list[RowT],
    *,
    key: Callable[[RowT], Any],
    reverse: bool,
) -> None:
    ordered = sorted(enumerate(rows), key=lambda pair: key(pair[1]), reverse=reverse)
    model.layoutAboutToBeChanged.emit()
    # Views may create persistent indexes in response to the about-to-change signal.
    previous_indexes = model.persistentIndexList()
    new_positions = {old: new for new, (old, _) in enumerate(ordered)}
    rows[:] = [row for _, row in ordered]
    model.changePersistentIndexList(
        previous_indexes,
        [
            model.index(new_positions[index.row()], index.column())
            for index in previous_indexes
        ],
    )
    model.layoutChanged.emit()


def insert_model_rows(
    model: QAbstractTableModel,
    rows: list[RowT],
    incoming: list[RowT],
    *,
    key: Callable[[RowT], Any] | None = None,
    reverse: bool = False,
) -> None:
    """Insert only new rows, keeping existing persistent selections and row objects."""
    if not incoming:
        return
    if key is None or not rows:
        ordered = sorted(incoming, key=key, reverse=reverse) if key else incoming
        start = len(rows)
        model.beginInsertRows(QModelIndex(), start, start + len(ordered) - 1)
        rows.extend(ordered)
        model.endInsertRows()
        return
    ordered = sorted(incoming, key=key, reverse=reverse)
    groups: list[tuple[int, list[RowT]]] = []
    for row in ordered:
        value = key(row)
        low, high = 0, len(rows)
        while low < high:
            middle = (low + high) // 2
            before = value > key(rows[middle]) if reverse else value < key(rows[middle])
            if before:
                high = middle
            else:
                low = middle + 1
        if groups and groups[-1][0] == low:
            groups[-1][1].append(row)
        else:
            groups.append((low, [row]))
    # Insert from the end so earlier positions remain valid; Qt shifts selections.
    for position, batch in reversed(groups):
        model.beginInsertRows(QModelIndex(), position, position + len(batch) - 1)
        rows[position:position] = batch
        model.endInsertRows()
