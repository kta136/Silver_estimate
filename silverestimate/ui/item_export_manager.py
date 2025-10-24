import csv
import traceback
from PyQt5.QtCore import QObject, pyqtSignal

class ItemExportManager(QObject):
    """Handles exporting the item list to a file."""

    export_finished = pyqtSignal(bool, str)  # success (bool), message (str)

    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager

    def export_to_file(self, file_path):
        """Exports all items to the specified file path."""
        if not self.db_manager:
            self.export_finished.emit(False, "Database connection not available.")
            return

        try:
            items = self.db_manager.get_all_items()
            if not items:
                self.export_finished.emit(False, "No items found in the database to export.")
                return

            # Define the header - matches the default import order
            header = ["Code", "Name", "Purity", "Wage Type", "Wage Rate"]

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                # Use csv writer with pipe delimiter for consistency
                writer = csv.writer(f, delimiter='|', quoting=csv.QUOTE_MINIMAL)

                # Write header
                writer.writerow(header)

                # Write item data
                exported_count = 0
                for item_row in items:
                    # Convert Row object to dictionary if needed, or access by index/key
                    item = dict(item_row) # Assuming db_manager returns Row objects

                    # Prepare data row - ensure order matches header
                    data_row = [
                        item.get('code', ''),
                        item.get('name', ''),
                        item.get('purity', 0.0),
                        item.get('wage_type', ''),
                        item.get('wage_rate', 0.0)
                    ]
                    writer.writerow(data_row)
                    exported_count += 1

            success_message = f"Successfully exported {exported_count} items to:\n{file_path}"
            import logging
            logging.getLogger(__name__).info(success_message)
            self.export_finished.emit(True, success_message)

        except Exception as e:
            error_message = f"Error exporting items: {str(e)}"
            import logging
            logging.getLogger(__name__).error(error_message, exc_info=True)
            self.export_finished.emit(False, error_message)
