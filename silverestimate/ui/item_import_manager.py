import sqlite3
import threading

from PyQt5.QtCore import QObject, pyqtSignal

from silverestimate.services.item_import_parser import (
    ItemImportParseError,
    parse_adjustment_factor,
    parse_item_row,
    should_include_line,
)


class ItemImportManager(QObject):
    """Handles the actual item import process."""

    progress_updated = pyqtSignal(int, int)  # current, total
    status_updated = pyqtSignal(str)  # message
    import_summary_updated = pyqtSignal(dict)  # inserted/updated/skipped/errors
    import_finished = pyqtSignal(
        int, int, str
    )  # success_count, total_count, error_message (None if success)

    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.cancel_requested = False
        self._cancel_event = threading.Event()
        self._last_summary = {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
        }

    def cancel_import(self):
        """Flags the import process to stop."""
        import logging

        logging.getLogger(__name__).info("Import cancellation requested.")
        self.cancel_requested = True
        self._cancel_event.set()

    def import_from_file(self, file_path, import_settings):
        """Import items from the specified file using the provided settings."""
        self.cancel_requested = False
        self._cancel_event.clear()
        summary = {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
        }
        imported_count = 0
        processed_count = 0
        total_items = 0
        worker_conn = None
        worker_cur = None

        def _emit_summary() -> None:
            snapshot = dict(summary)
            self._last_summary = snapshot
            self.import_summary_updated.emit(snapshot)

        try:
            # Extract settings
            delimiter = import_settings["delimiter"]
            code_column = import_settings["code_column"]
            name_column = import_settings["name_column"]
            type_column = import_settings["type_column"]
            rate_column = import_settings["rate_column"]
            purity_column = import_settings["purity_column"]
            skip_header = import_settings["skip_header"]
            use_filter = import_settings["use_filter"]
            wage_adjustment_factor_str = import_settings.get(
                "wage_adjustment_factor", ""
            )  # Get adjustment factor
            duplicate_mode = import_settings["duplicate_mode"]
            try:
                batch_size = int(import_settings.get("batch_size", 200))
            except (TypeError, ValueError):
                batch_size = 200
            if batch_size < 1:
                batch_size = 200

            adjustment_op, adjustment_val = parse_adjustment_factor(
                wage_adjustment_factor_str
            )

            # Open a dedicated SQLite connection for this worker thread
            try:
                temp_db_path = getattr(self.db_manager, "temp_db_path", None)
                if not temp_db_path:
                    raise RuntimeError("Temporary database path not available.")
                worker_conn = sqlite3.connect(temp_db_path)
                worker_conn.row_factory = sqlite3.Row
                worker_cur = worker_conn.cursor()
                try:
                    worker_conn.execute("PRAGMA foreign_keys = ON")
                    worker_conn.execute("PRAGMA journal_mode=WAL")
                    worker_conn.execute("PRAGMA synchronous=NORMAL")
                except Exception:
                    pass
            except Exception as ce:
                raise RuntimeError(f"Failed to open worker DB connection: {ce}")

            # Read the file
            # Try common encodings if utf-8 fails
            lines = []
            encodings_to_try = ["utf-8", "cp1252", "latin-1"]
            for enc in encodings_to_try:
                try:
                    with open(file_path, "r", encoding=enc) as f:
                        for raw_line in f:
                            if self._cancel_event.is_set():
                                self.status_updated.emit("Import cancelled by user.")
                                break
                            lines.append(raw_line)
                    import logging

                    logging.getLogger(__name__).debug(
                        f"Successfully read file with encoding: {enc}"
                    )
                    break  # Stop trying encodings if one works
                except UnicodeDecodeError:
                    import logging

                    logging.getLogger(__name__).debug(
                        f"Failed to decode file with {enc}, trying next..."
                    )
                    continue
                except Exception as e_read:  # Catch other file reading errors
                    raise IOError(
                        f"Could not read file '{file_path}': {e_read}"
                    ) from e_read
            else:  # If loop completes without break
                raise ValueError(
                    f"Could not decode file '{file_path}' with any attempted encoding."
                )

            if self._cancel_event.is_set():
                _emit_summary()
                self.import_finished.emit(0, 1, "Import Cancelled")
                return

            # Filter lines based on settings
            filtered_lines = []

            # Skip first line if option is checked
            start_idx = 1 if skip_header and len(lines) > 0 else 0

            # Process lines
            for line in lines[start_idx:]:
                if self._cancel_event.is_set():
                    self.status_updated.emit("Import cancelled by user.")
                    break
                line = line.strip()
                if not line:
                    continue

                if should_include_line(
                    line, delimiter=delimiter, use_filter=use_filter
                ):
                    filtered_lines.append(line)

            if self._cancel_event.is_set():
                _emit_summary()
                self.import_finished.emit(0, 1, "Import Cancelled")
                return

            total_items = len(filtered_lines)
            if total_items == 0:
                raise ValueError("No valid item lines found in the file.")

            self.progress_updated.emit(0, total_items)
            self.status_updated.emit(
                f"Found {total_items} potential items. Starting import..."
            )

            # Begin a transaction for faster bulk import
            try:
                worker_conn.execute("BEGIN TRANSACTION")
            except Exception:
                pass

            # Process items
            for i, line in enumerate(filtered_lines):
                processed_count = i + 1
                if self._cancel_event.is_set():
                    self.status_updated.emit("Import cancelled by user.")
                    break  # Exit the loop

                # Parse the line using configured column indices
                parts = [part.strip() for part in line.split(delimiter)]

                try:
                    parsed = parse_item_row(
                        parts,
                        code_column=code_column,
                        name_column=name_column,
                        type_column=type_column,
                        rate_column=rate_column,
                        purity_column=purity_column,
                        adjustment_op=adjustment_op,
                        adjustment_val=adjustment_val,
                    )
                except ItemImportParseError as ve:
                    summary["errors"] += 1
                    self.status_updated.emit(f"Skipping line {i+1}: {ve}")
                    self.progress_updated.emit(processed_count, total_items)
                    continue

                try:
                    worker_cur.execute(
                        "SELECT 1 FROM items WHERE code = ? COLLATE NOCASE",
                        (parsed.code,),
                    )
                    existing_item = worker_cur.fetchone()

                    # Handle based on duplicate mode
                    should_import = True
                    action = "Adding"

                    if existing_item:
                        if duplicate_mode == 0:  # SKIP
                            should_import = False
                            action = "Skipping duplicate"
                            summary["skipped"] += 1
                        elif duplicate_mode == 1:  # UPDATE
                            should_import = True
                            action = "Updating existing"
                        else:  # Default to SKIP for any other mode
                            should_import = False
                            action = "Skipping duplicate (unknown mode)"
                            summary["skipped"] += 1

                    self.status_updated.emit(
                        f"{action}: {parsed.code} - {parsed.name}"
                    )

                    # Add or update item
                    if should_import:
                        if existing_item and duplicate_mode == 1:  # UPDATE
                            worker_cur.execute(
                                "UPDATE items SET name = ?, purity = ?, wage_type = ?, wage_rate = ? WHERE code = ? COLLATE NOCASE",
                                (
                                    parsed.name,
                                    parsed.purity,
                                    parsed.wage_type,
                                    parsed.wage_rate,
                                    parsed.code,
                                ),
                            )
                            if worker_cur.rowcount > 0:
                                imported_count += 1
                                summary["updated"] += 1
                            else:
                                summary["errors"] += 1
                                self.status_updated.emit(
                                    f"Failed to update existing item: {parsed.code}"
                                )
                        elif not existing_item:
                            worker_cur.execute(
                                "INSERT INTO items (code, name, purity, wage_type, wage_rate) VALUES (?, ?, ?, ?, ?)",
                                (
                                    parsed.code,
                                    parsed.name,
                                    parsed.purity,
                                    parsed.wage_type,
                                    parsed.wage_rate,
                                ),
                            )
                            imported_count += 1
                            summary["inserted"] += 1
                        else:  # Should be a skip
                            imported_count += 1
                    else:
                        imported_count += 1  # skipped duplicate is still processed
                except Exception as e_item:
                    summary["errors"] += 1
                    self.status_updated.emit(f"Error processing line {i+1}: {e_item}")
                    continue  # Skip to next item on error

                if processed_count % batch_size == 0 and worker_conn is not None:
                    try:
                        worker_conn.commit()
                        worker_conn.execute("BEGIN TRANSACTION")
                    except Exception:
                        pass
                    if self._cancel_event.is_set():
                        self.status_updated.emit("Import cancelled by user.")
                        break

                # Update progress
                self.progress_updated.emit(processed_count, total_items)

            # Commit changes and trigger encryption flush
            try:
                if worker_conn:
                    worker_conn.commit()
            except Exception:
                pass
            try:
                # Request background encryption flush (debounced)
                if hasattr(self.db_manager, "request_flush"):
                    self.db_manager.request_flush()
            except Exception:
                pass

            # Finish
            _emit_summary()
            if self._cancel_event.is_set():
                # If cancelled, report counts up to the point of cancellation
                self.import_finished.emit(
                    imported_count, processed_count, "Import Cancelled"
                )
            else:
                self.import_finished.emit(
                    imported_count, total_items, None
                )  # None indicates success

        except Exception as e:
            import logging

            logging.getLogger(__name__).error("Import failed:", exc_info=True)
            self.status_updated.emit(f"Error: {str(e)}")
            summary["errors"] += 1
            _emit_summary()
            # Emit finished signal with error message
            self.import_finished.emit(imported_count, processed_count or 1, str(e))
        finally:
            # Ensure worker DB resources are released
            try:
                if worker_cur is not None:
                    try:
                        worker_cur.close()
                    except Exception:
                        pass
                if worker_conn is not None:
                    worker_conn.close()
            except Exception:
                pass
