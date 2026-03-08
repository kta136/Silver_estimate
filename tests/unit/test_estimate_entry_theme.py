from silverestimate.ui.estimate_entry_theme import ESTIMATE_ENTRY_STYLESHEET


def test_save_button_uses_primary_strip_specific_selector():
    assert "QWidget#PrimaryActionStrip QPushButton#SavePrimaryButton {" in (
        ESTIMATE_ENTRY_STYLESHEET
    )
    assert "QWidget#PrimaryActionStrip QPushButton#SavePrimaryButton:hover {" in (
        ESTIMATE_ENTRY_STYLESHEET
    )
    assert "QWidget#PrimaryActionStrip QPushButton#SavePrimaryButton:pressed {" in (
        ESTIMATE_ENTRY_STYLESHEET
    )
