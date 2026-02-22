#!/usr/bin/env python
"""Estimate entry table constants and delegates."""

from PyQt5.QtCore import QEvent, QLocale, Qt
from PyQt5.QtGui import QDoubleValidator, QIntValidator
from PyQt5.QtWidgets import QLineEdit, QStyledItemDelegate

# --- Column Constants (shared by estimate entry table paths) ---
COL_CODE = 0
COL_ITEM_NAME = 1
COL_GROSS = 2
COL_POLY = 3
COL_NET_WT = 4
COL_PURITY = 5
COL_WAGE_RATE = 6
COL_PIECES = 7
COL_WAGE_AMT = 8
COL_FINE_WT = 9
COL_TYPE = 10


class NumericDelegate(QStyledItemDelegate):
    """Delegate that validates and normalizes numeric table cell input."""

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setProperty("modelIndex", index)
        col = index.column()
        locale = QLocale.system()

        if col in [COL_GROSS, COL_POLY, COL_PURITY, COL_WAGE_RATE]:
            decimals = 3 if col in [COL_GROSS, COL_POLY] else 2
            validator = QDoubleValidator(0.0, 999999.999, decimals, editor)
            validator.setNotation(QDoubleValidator.StandardNotation)
            validator.setLocale(locale)
            editor.setValidator(validator)
        elif col == COL_PIECES:
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
        if col in [COL_GROSS, COL_POLY]:
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

    def setModelData(self, editor, model, index):
        if not isinstance(editor, QLineEdit):
            super().setModelData(editor, model, index)
            return

        col = index.column()
        value = editor.text().strip()
        locale = QLocale.system()

        if col in [COL_GROSS, COL_POLY]:
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
            if col in [COL_PURITY, COL_WAGE_RATE]:
                double_val, ok = locale.toDouble(value)
                model.setData(index, double_val if ok else 0.0, Qt.EditRole)
            elif col == COL_PIECES:
                model.setData(index, int(value) if value else 0, Qt.EditRole)
            else:
                model.setData(index, value, Qt.EditRole)
        except ValueError:
            if col == COL_PIECES:
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
                    if col in [COL_GROSS, COL_POLY] and editor.text() == "":
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
