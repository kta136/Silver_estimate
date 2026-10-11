from PySide6.QtWidgets import QDialog

from silverestimate.ui.silver_bar_management import OptimalListDialog


def test_optimal_list_dialog_accepts_valid_inputs(qtbot):
    dialog = OptimalListDialog()
    qtbot.addWidget(dialog)
    try:
        dialog.min_weight_spin.setValue(90.0)
        dialog.max_weight_spin.setValue(110.0)
        dialog.list_name_edit.setText("Target Batch")
        dialog.max_bars_radio.setChecked(True)

        dialog.accept()

        assert dialog.result() == QDialog.DialogCode.Accepted
        assert dialog.min_target == 90.0
        assert dialog.max_target == 110.0
        assert dialog.list_name == "Target Batch"
        assert dialog.optimization_type == "max_bars"
        assert dialog.range_summary_label.text() == (
            "90.00–110.00 g fine · midpoint 100.00 g"
        )
    finally:
        dialog.deleteLater()


def test_optimal_list_dialog_explains_a_bad_range_in_place(qtbot):
    dialog = OptimalListDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.min_weight_spin.setValue(110.0)
    dialog.max_weight_spin.setValue(90.0)

    dialog.accept()

    assert dialog.result() != QDialog.DialogCode.Accepted
    # Said once, under the two weights, in place of a nonsense summary.
    assert dialog.range_summary_label.text() == (
        "The first weight must be lower than the second."
    )
    assert dialog.range_summary_label.property("invalid") is True
    assert not dialog.error_label.isVisible()
    dialog.min_weight_spin.setValue(80.0)
    assert dialog.range_summary_label.property("invalid") is False
    assert "midpoint 85.00 g" in dialog.range_summary_label.text()
    dialog.list_name_edit.clear()
    dialog.accept()
    assert dialog.error_label.text() == "Enter a note for the new list."
