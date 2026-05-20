#!/usr/bin/env python
"""Estimate entry table delegates."""

from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QDoubleValidator, QIntValidator
from PyQt6.QtWidgets import QLineEdit, QStyledItemDelegate

from silverestimate.ui import estimate_table_formatting
from silverestimate.ui.numeric_font import numeric_table_font

from .estimate_entry_logic.column_specs import (
    column_uses_blank_zero_editor,
    get_column_spec,
)


class NumericDelegate(QStyledItemDelegate):
    """Delegate that validates and normalizes numeric table cell input."""

    reverse_requested = pyqtSignal()
    manual_row_navigation_requested = pyqtSignal()

    @staticmethod
    def _style_editor(editor: QLineEdit) -> None:
        editor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        editor.setClearButtonEnabled(False)
        editor.setFont(numeric_table_font(editor.font()))

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setProperty("modelIndex", index)
        self._style_editor(editor)
        col = index.column()
        locale = estimate_table_formatting.get_estimate_table_locale()
        spec = get_column_spec(col)

        if spec is not None and spec.precision == 0:
            validator = QIntValidator(0, 999999, editor)
            editor.setValidator(validator)
        elif spec is not None and spec.precision is not None:
            validator = QDoubleValidator(0.0, 999999.999, spec.precision, editor)
            validator.setNotation(QDoubleValidator.Notation.StandardNotation)
            validator.setLocale(locale)
            editor.setValidator(validator)
        else:
            return editor

        editor.installEventFilter(self)
        return editor

    def setEditorData(self, editor, index):
        if not isinstance(editor, QLineEdit):
            super().setEditorData(editor, index)
            return

        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        col = index.column()
        if column_uses_blank_zero_editor(col):
            try:
                if value is not None and float(value) == 0.0:
                    display_text = ""
                else:
                    display_text = str(value) if value is not None else ""
            except ValueError, TypeError:
                display_text = str(value) if value is not None else ""
        else:
            display_text = str(value) if value is not None else ""

        editor.setText(display_text)
        editor.selectAll()

    def setModelData(self, editor, model, index):
        if not isinstance(editor, QLineEdit):
            super().setModelData(editor, model, index)
            return

        col = index.column()
        value = editor.text().strip()
        locale = estimate_table_formatting.get_estimate_table_locale()
        spec = get_column_spec(col)

        if column_uses_blank_zero_editor(col):
            if not value:
                model.setData(index, 0.0, Qt.ItemDataRole.EditRole)
            else:
                double_val, ok = locale.toDouble(value)
                if ok and double_val == 0.0:
                    model.setData(index, 0.0, Qt.ItemDataRole.EditRole)
                elif ok:
                    model.setData(index, double_val, Qt.ItemDataRole.EditRole)
                else:
                    model.setData(index, 0.0, Qt.ItemDataRole.EditRole)
            return

        try:
            if spec is not None and spec.precision == 0:
                model.setData(
                    index, int(value) if value else 0, Qt.ItemDataRole.EditRole
                )
            elif spec is not None and spec.precision is not None:
                double_val, ok = locale.toDouble(value)
                model.setData(
                    index, double_val if ok else 0.0, Qt.ItemDataRole.EditRole
                )
            else:
                model.setData(index, value, Qt.ItemDataRole.EditRole)
        except ValueError:
            if spec is not None and spec.precision == 0:
                model.setData(index, 0, Qt.ItemDataRole.EditRole)
            else:
                model.setData(index, value, Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        if isinstance(editor, QLineEdit):
            editor.setGeometry(option.rect)
        else:
            super().updateEditorGeometry(editor, option, index)

    def eventFilter(self, editor, event):
        if event.type() == QEvent.Type.KeyPress and isinstance(editor, QLineEdit):
            index = editor.property("modelIndex")
            if index and index.isValid():
                col = index.column()
                key = event.key()
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                    if column_uses_blank_zero_editor(col) and editor.text() == "":
                        index.model().setData(index, 0.0, Qt.ItemDataRole.EditRole)
                        self.closeEditor.emit(
                            editor, QStyledItemDelegate.EndEditHint.SubmitModelCache
                        )
                        return True
                elif key == Qt.Key.Key_Backspace and editor.text() == "":
                    self.closeEditor.emit(
                        editor, QStyledItemDelegate.EndEditHint.NoHint
                    )
                    QTimer.singleShot(0, self.reverse_requested.emit)
                    return True
                elif key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                    self.manual_row_navigation_requested.emit()

        return super().eventFilter(editor, event)


class CodeDelegate(QStyledItemDelegate):
    """Delegate that normalizes code edits and preserves Enter navigation."""

    advance_requested = pyqtSignal()

    @staticmethod
    def _normalize_code(value) -> str:
        return str(value or "").strip().upper()

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setProperty("modelIndex", index)
        editor.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        editor.installEventFilter(self)
        return editor

    def setEditorData(self, editor, index):
        if not isinstance(editor, QLineEdit):
            super().setEditorData(editor, index)
            return

        value = index.model().data(index, Qt.ItemDataRole.EditRole)
        text = str(value) if value is not None else ""
        editor.setText(text)
        editor.setProperty("originalCode", self._normalize_code(text))
        editor.selectAll()

    def setModelData(self, editor, model, index):
        if not isinstance(editor, QLineEdit):
            super().setModelData(editor, model, index)
            return

        model.setData(
            index, self._normalize_code(editor.text()), Qt.ItemDataRole.EditRole
        )

    def eventFilter(self, editor, event):
        if event.type() == QEvent.Type.KeyPress and isinstance(editor, QLineEdit):
            index = editor.property("modelIndex")
            if index and index.isValid():
                key = event.key()
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                    original_code = str(editor.property("originalCode") or "")
                    unchanged_code = (
                        self._normalize_code(editor.text()) == original_code
                    )
                    self.commitData.emit(editor)
                    self.closeEditor.emit(
                        editor, QStyledItemDelegate.EndEditHint.NoHint
                    )

                    if unchanged_code:
                        QTimer.singleShot(0, self.advance_requested.emit)
                    return True

        return super().eventFilter(editor, event)
