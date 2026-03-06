from silverestimate.ui.item_import_dialog import ItemImportDialog


def _make_dialog(qtbot):
    dialog = ItemImportDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: dialog.isVisible(), timeout=1000)
    return dialog


def test_preview_file_data_populates_model_and_formats_q_rates(qtbot, tmp_path):
    import_file = tmp_path / "items.txt"
    import_file.write_text(
        "X001|Regular Item|92.5|WT|10.0\nQ001|Q Item|95.0|Q|1000\n",
        encoding="utf-8",
    )
    dialog = _make_dialog(qtbot)
    try:
        dialog.wage_adjustment_input.setText("*1.1")
        dialog.preview_file_data(str(import_file))

        assert dialog.preview_table.isVisible() is True
        assert dialog.preview_model.rowCount() == 2
        assert dialog.preview_model.data(dialog.preview_model.index(0, 0)) == "X001"
        assert dialog.preview_model.data(dialog.preview_model.index(0, 3)) == "10.0"
        assert (
            dialog.preview_model.data(dialog.preview_model.index(1, 3))
            == "1.000 → 1.100 (*1.1)"
        )
        assert "Found 2 valid items" in dialog.status_label.text()
    finally:
        dialog.deleteLater()


def test_preview_file_data_marks_short_rows_as_parsing_errors(qtbot, tmp_path):
    import_file = tmp_path / "bad_items.txt"
    import_file.write_text("X001|Only Name\n", encoding="utf-8")
    dialog = _make_dialog(qtbot)
    try:
        dialog.preview_file_data(str(import_file))

        assert dialog.preview_model.rowCount() == 1
        row = dialog.preview_model.row_payload(0)
        assert row is not None
        assert row.code == "PARSING ERROR"
        assert row.name == "PARSING ERROR"
        assert row.wage_type == "PARSING ERROR"
        assert row.wage_rate == "PARSING ERROR"
        assert row.purity == "PARSING ERROR"
    finally:
        dialog.deleteLater()
