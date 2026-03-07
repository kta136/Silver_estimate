#!/usr/bin/env python
"""Estimate entry table delegates."""

from PyQt5.QtCore import QEvent, Qt, QTimer
from PyQt5.QtGui import QDoubleValidator, QIntValidator
from PyQt5.QtWidgets import QLineEdit, QStyledItemDelegate

from silverestimate.ui import estimate_table_formatting
from silverestimate.ui.numeric_font import numeric_table_font
from .estimate_entry_logic import constants as table_cols


class NumericDelegate(QStyledItemDelegate):
    """Delegate that validates and normalizes numeric table cell input."""

    @staticmethod
    def _style_editor(editor: QLineEdit) -> None:
        editor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        editor.setClearButtonEnabled(False)
        editor.setFont(numeric_table_font(editor.font()))

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setProperty("modelIndex", index)
        self._style_editor(editor)
        col = index.column()
        locale = estimate_table_formatting.get_estimate_table_locale()
        validator: QDoubleValidator | QIntValidator

        if col in (
            table_cols.COL_GROSS,
            table_cols.COL_POLY,
            table_cols.COL_PURITY,
            table_cols.COL_WAGE_RATE,
        ):
            decimals = (
                3
                if col in (table_cols.COL_GROSS, table_cols.COL_POLY)
                else 2
            )
            validator = QDoubleValidator(0.0, 999999.999, decimals, editor)
            validator.setNotation(QDoubleValidator.StandardNotation)
            validator.setLocale(locale)
            editor.setValidator(validator)
        elif col == table_cols.COL_PIECES:
            validator = QIntValidator(0, 999999, editor)
            editor.setValidator(validator)
        else:
            return editor

        editor.installEventFilter(self)
        return editor

    def setEditorData(self, editor, index):
        if not isinstance(editor, QLineEdit):
            super().setEditorData(editor, index)
            return

        value = index.model().data(index, Qt.EditRole)
        col = index.column()
        if col in (table_cols.COL_GROSS, table_cols.COL_POLY):
            try:
                if value is not None and float(value) == 0.0:
                    display_text = ""
                else:
                    display_text = str(value) if value is not None else ""
            except (ValueError, TypeError):
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

        if col in (table_cols.COL_GROSS, table_cols.COL_POLY):
            if not value:
                model.setData(index, 0.0, Qt.EditRole)
            else:
                double_val, ok = locale.toDouble(value)
                if ok and double_val == 0.0:
                    model.setData(index, 0.0, Qt.EditRole)
                elif ok:
                    model.setData(index, double_val, Qt.EditRole)
                else:
                    model.setData(index, 0.0, Qt.EditRole)
            return

        try:
            if col in (table_cols.COL_PURITY, table_cols.COL_WAGE_RATE):
                double_val, ok = locale.toDouble(value)
                model.setData(index, double_val if ok else 0.0, Qt.EditRole)
            elif col == table_cols.COL_PIECES:
                model.setData(index, int(value) if value else 0, Qt.EditRole)
            else:
                model.setData(index, value, Qt.EditRole)
        except ValueError:
            if col == table_cols.COL_PIECES:
                model.setData(index, 0, Qt.EditRole)
            else:
                model.setData(index, value, Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        if isinstance(editor, QLineEdit):
            editor.setGeometry(option.rect)
        else:
            super().updateEditorGeometry(editor, option, index)

    def eventFilter(self, editor, event):
        if event.type() == QEvent.KeyPress and isinstance(editor, QLineEdit):
            index = editor.property("modelIndex")
            if index and index.isValid():
                col = index.column()
                key = event.key()
                if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab):
                    if col in (
                        table_cols.COL_GROSS,
                        table_cols.COL_POLY,
                    ) and editor.text() == "":
                        index.model().setData(index, 0.0, Qt.EditRole)
                        self.closeEditor.emit(
                            editor, QStyledItemDelegate.SubmitModelCache
                        )
                        return True
                elif key == Qt.Key_Backspace and editor.text() == "":
                    self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)
                    table_widget = self.parent()
                    if table_widget:
                        estimate_widget = (
                            getattr(table_widget, "host_widget", None)
                            or table_widget.parent()
                        )
                        if estimate_widget and hasattr(
                            estimate_widget, "move_to_previous_cell"
                        ):
                            from PyQt5.QtCore import QTimer

                            QTimer.singleShot(0, estimate_widget.move_to_previous_cell)
                    return True
                elif key in (Qt.Key_Up, Qt.Key_Down):
                    table_widget = self.parent()
                    if table_widget:
                        estimate_widget = (
                            getattr(table_widget, "host_widget", None)
                            or table_widget.parent()
                        )
                        if estimate_widget and hasattr(
                            estimate_widget, "_mark_manual_row_navigation"
                        ):
                            estimate_widget._mark_manual_row_navigation()

        return super().eventFilter(editor, event)


class CodeDelegate(QStyledItemDelegate):
    """Delegate that normalizes code edits and preserves Enter navigation."""

    @staticmethod
    def _normalize_code(value) -> str:
        return str(value or "").strip().upper()

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setProperty("modelIndex", index)
        editor.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        editor.installEventFilter(self)
        return editor

    def setEditorData(self, editor, index):
        if not isinstance(editor, QLineEdit):
            super().setEditorData(editor, index)
            return

        value = index.model().data(index, Qt.EditRole)
        text = str(value) if value is not None else ""
        editor.setText(text)
        editor.setProperty("originalCode", self._normalize_code(text))
        editor.selectAll()

    def setModelData(self, editor, model, index):
        if not isinstance(editor, QLineEdit):
            super().setModelData(editor, model, index)
            return

        model.setData(index, self._normalize_code(editor.text()), Qt.EditRole)

    def eventFilter(self, editor, event):
        if event.type() == QEvent.KeyPress and isinstance(editor, QLineEdit):
            index = editor.property("modelIndex")
            if index and index.isValid():
                key = event.key()
                if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab):
                    original_code = str(editor.property("originalCode") or "")
                    unchanged_code = (
                        self._normalize_code(editor.text()) == original_code
                    )
                    self.commitData.emit(editor)
                    self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)

                    if unchanged_code:
                        table_widget = self.parent()
                        if table_widget:
                            estimate_widget = (
                                getattr(table_widget, "host_widget", None)
                                or table_widget.parent()
                            )
                            if estimate_widget and hasattr(
                                estimate_widget, "move_to_next_cell"
                            ):
                                QTimer.singleShot(0, estimate_widget.move_to_next_cell)
                    return True

        return super().eventFilter(editor, event)
