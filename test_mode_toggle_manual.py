"""Manual test script to verify mode toggle buttons work in actual application."""

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtTest import QTest

# Add project root to path
sys.path.insert(0, r"D:\Projects\SilverEstimate")

from silverestimate.ui.estimate_entry import EstimateEntryWidget
from silverestimate.ui.estimate_entry_logic import COL_TYPE


class FakeDB:
    """Minimal fake database."""
    def __init__(self):
        self.item_cache_controller = None

    def generate_voucher_no(self):
        return "TEST001"

    def get_item_by_code(self, code):
        return {"wage_type": "WT", "wage_rate": 10}


class FakeRepository:
    """Minimal repository."""
    def __init__(self, db):
        self.db = db

    def generate_voucher_no(self):
        return self.db.generate_voucher_no()

    def load_estimate(self, voucher_no):
        return None

    def fetch_item(self, code):
        return self.db.get_item_by_code(code)

    def estimate_exists(self, voucher_no):
        return False

    def save_estimate(self, *args, **kwargs):
        return True

    def last_error(self):
        return None


class FakeMainWindow:
    """Minimal main window stub."""
    def show_inline_status(self, *args, **kwargs):
        pass

    def show_silver_bars_management(self):
        pass


def test_mode_toggle():
    """Test mode toggle buttons manually."""
    app = QApplication(sys.argv)

    # Create widget
    db = FakeDB()
    main_window = FakeMainWindow()
    repository = FakeRepository(db)

    widget = EstimateEntryWidget(db, main_window, repository)

    # Wait for initialization
    QTimer.singleShot(300, lambda: check_initial_state(widget))
    QTimer.singleShot(400, lambda: toggle_return_mode(widget))
    QTimer.singleShot(500, lambda: check_return_mode_state(widget))
    QTimer.singleShot(600, lambda: toggle_silver_bar_mode(widget))
    QTimer.singleShot(700, lambda: check_silver_bar_mode_state(widget))
    QTimer.singleShot(800, lambda: app.quit())

    widget.show()
    app.exec_()


def check_initial_state(widget):
    """Check initial state."""
    print("\n=== Initial State ===")
    last_row = widget.item_table.rowCount() - 1
    type_item = widget.item_table.item(last_row, COL_TYPE)

    print(f"Row count: {widget.item_table.rowCount()}")
    print(f"Last row: {last_row}")
    print(f"Type item: {type_item}")
    print(f"Type item text: {type_item.text() if type_item else 'None'}")
    print(f"Return mode: {widget.return_mode}")
    print(f"Silver bar mode: {widget.silver_bar_mode}")
    print(f"Return button checked: {widget.return_toggle_button.isChecked()}")
    print(f"Silver bar button checked: {widget.silver_bar_toggle_button.isChecked()}")


def toggle_return_mode(widget):
    """Toggle return mode."""
    print("\n=== Clicking Return Button ===")
    widget.return_toggle_button.click()


def check_return_mode_state(widget):
    """Check state after toggling return mode."""
    print("\n=== After Return Button Click ===")
    last_row = widget.item_table.rowCount() - 1
    type_item = widget.item_table.item(last_row, COL_TYPE)

    print(f"Type item: {type_item}")
    print(f"Type item text: {type_item.text() if type_item else 'None'}")
    print(f"Type item type: {type(type_item).__name__ if type_item else 'None'}")
    print(f"Return mode: {widget.return_mode}")
    print(f"Silver bar mode: {widget.silver_bar_mode}")
    print(f"Return button checked: {widget.return_toggle_button.isChecked()}")

    # Check if it's updating the model
    if type_item:
        model_index = widget.item_table._table_model.index(last_row, COL_TYPE)
        model_data = widget.item_table._table_model.data(model_index, Qt.DisplayRole)
        print(f"Model data: {model_data}")

    # Expected: type_item.text() should be "return"
    if type_item and type_item.text() == "return":
        print("✅ SUCCESS: Row type updated to 'return'")
    else:
        print(f"❌ FAILURE: Row type is '{type_item.text() if type_item else 'None'}', expected 'return'")


def toggle_silver_bar_mode(widget):
    """Toggle silver bar mode."""
    print("\n=== Clicking Silver Bar Button ===")
    widget.silver_bar_toggle_button.click()


def check_silver_bar_mode_state(widget):
    """Check state after toggling silver bar mode."""
    print("\n=== After Silver Bar Button Click ===")
    last_row = widget.item_table.rowCount() - 1
    type_item = widget.item_table.item(last_row, COL_TYPE)

    print(f"Type item text: {type_item.text() if type_item else 'None'}")
    print(f"Return mode: {widget.return_mode}")
    print(f"Silver bar mode: {widget.silver_bar_mode}")
    print(f"Silver bar button checked: {widget.silver_bar_toggle_button.isChecked()}")
    print(f"Return button checked: {widget.return_toggle_button.isChecked()}")

    # Expected: type_item.text() should be "silver_bar" and return mode should be off
    if type_item and type_item.text() == "silver_bar":
        print("✅ SUCCESS: Row type updated to 'silver_bar'")
    else:
        print(f"❌ FAILURE: Row type is '{type_item.text() if type_item else 'None'}', expected 'silver_bar'")

    if not widget.return_mode:
        print("✅ SUCCESS: Return mode was disabled (mutual exclusion working)")
    else:
        print("❌ FAILURE: Return mode still active (mutual exclusion NOT working)")


if __name__ == "__main__":
    test_mode_toggle()
