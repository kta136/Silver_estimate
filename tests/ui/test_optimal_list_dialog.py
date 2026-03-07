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

        assert dialog.result() == dialog.Accepted
        assert dialog.min_target == 90.0
        assert dialog.max_target == 110.0
        assert dialog.list_name == "Target Batch"
        assert dialog.optimization_type == "max_bars"
    finally:
        dialog.deleteLater()
