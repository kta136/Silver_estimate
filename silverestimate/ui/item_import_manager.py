import logging
import sqlite3
import threading
import time

from PyQt5.QtCore import QObject, pyqtSignal

from silverestimate.services.item_import_parser import (
    ItemImportParseError,
    parse_adjustment_factor,
    parse_item_row,
    should_include_line,
)


class ItemImportManager(QObject):
    """Handles the actual item import process."""

    _EXISTING_CODE_CHUNK_SIZE = 900
    _PROGRESS_EMIT_INTERVAL = 25
    _STATUS_EMIT_INTERVAL = 25
    _EMIT_INTERVAL_SECONDS = 0.05

    progress_updated = pyqtSignal(int, int)  # current, total
    status_updated = pyqtSignal(str)  # message
    import_summary_updated = pyqtSignal(dict)  # inserted/updated/skipped/errors
    import_finished = pyqtSignal(
        int, int, str
    )  # success_count, total_count, error_message (None if success)

    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self._logger = logging.getLogger(__name__)
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
        self._logger.info("Import cancellation requested.")
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

        last_progress_emit_count = -1
        last_progress_emit_time = 0.0
        last_status_emit_count = -1
        last_status_emit_time = 0.0

        def _emit_progress(current: int, total: int, *, force: bool = False) -> None:
            nonlocal last_progress_emit_count, last_progress_emit_time
            now = time.perf_counter()
            should_emit = force
            if not should_emit:
                should_emit = (
                    current <= 10
                    or current >= total
                    or current - last_progress_emit_count
                    >= self._PROGRESS_EMIT_INTERVAL
                    or (now - last_progress_emit_time) >= self._EMIT_INTERVAL_SECONDS
                )
            if not should_emit:
                return
            last_progress_emit_count = current
            last_progress_emit_time = now
            self.progress_updated.emit(current, total)

        def _emit_status(
            message: str,
            *,
            current: int | None = None,
            force: bool = False,
        ) -> None:
            nonlocal last_status_emit_count, last_status_emit_time
            now = time.perf_counter()
            count_marker = int(current or 0)
            should_emit = force
            if not should_emit:
                should_emit = (
                    count_marker <= 10
                    or count_marker - last_status_emit_count
                    >= self._STATUS_EMIT_INTERVAL
                    or (now - last_status_emit_time) >= self._EMIT_INTERVAL_SECONDS
                )
            if not should_emit:
                return
            last_status_emit_count = count_marker
            last_status_emit_time = now
            self.status_updated.emit(message)

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
                except Exception as pragma_error:
                    self._logger.debug(
                        "Worker import connection pragma configuration failed: %s",
                        pragma_error,
                    )
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
                    self._logger.debug("Successfully read file with encoding: %s", enc)
                    break  # Stop trying encodings if one works
                except UnicodeDecodeError:
                    self._logger.debug(
                        "Failed to decode file with %s, trying next...", enc
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

            _emit_progress(0, total_items, force=True)
            _emit_status(
                f"Found {total_items} potential items. Starting import...",
                force=True,
            )

            # Begin a transaction for faster bulk import
            try:
                worker_conn.execute("BEGIN TRANSACTION")
            except Exception as exc:
                self._logger.debug("Failed to begin item import transaction: %s", exc)

            parsed_entries = []
            for i, line in enumerate(filtered_lines):
                if self._cancel_event.is_set():
                    _emit_status("Import cancelled by user.", force=True)
                    break

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
                    processed_count = i + 1
                    _emit_status(
                        f"Skipping line {i + 1}: {ve}",
                        current=processed_count,
                        force=True,
                    )
                    _emit_progress(processed_count, total_items)
                    continue

                parsed_entries.append((i + 1, parsed))

            if self._cancel_event.is_set():
                try:
                    if worker_conn:
                        worker_conn.commit()
                except Exception as exc:
                    self._logger.debug(
                        "Failed to commit item import before cancellation: %s", exc
                    )
                _emit_summary()
                self.import_finished.emit(
                    imported_count,
                    processed_count or 1,
                    "Import Cancelled",
                )
                return

            existing_codes = self._load_existing_codes(
                worker_cur,
                (parsed.code for _, parsed in parsed_entries),
            )

            # Process items
            for processed_count, parsed in parsed_entries:
                if self._cancel_event.is_set():
                    _emit_status("Import cancelled by user.", force=True)
                    break
                try:
                    # Handle based on duplicate mode
                    should_import = True
                    action = "Adding"
                    existing_item = parsed.code in existing_codes

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

                    _emit_status(
                        f"{action}: {parsed.code} - {parsed.name}",
                        current=processed_count,
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
                                _emit_status(
                                    f"Failed to update existing item: {parsed.code}",
                                    current=processed_count,
                                    force=True,
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
                            existing_codes.add(parsed.code)
                            imported_count += 1
                            summary["inserted"] += 1
                        else:  # Should be a skip
                            imported_count += 1
                    else:
                        imported_count += 1  # skipped duplicate is still processed
                except Exception as e_item:
                    summary["errors"] += 1
                    _emit_status(
                        f"Error processing line {processed_count}: {e_item}",
                        current=processed_count,
                        force=True,
                    )
                    continue  # Skip to next item on error

                if processed_count % batch_size == 0 and worker_conn is not None:
                    try:
                        worker_conn.commit()
                        worker_conn.execute("BEGIN TRANSACTION")
                    except Exception as exc:
                        self._logger.debug(
                            "Failed to rotate item import batch transaction: %s", exc
                        )
                    if self._cancel_event.is_set():
                        _emit_status("Import cancelled by user.", force=True)
                        break

                # Update progress
                _emit_progress(processed_count, total_items)

            # Commit changes and trigger encryption flush
            try:
                if worker_conn:
                    worker_conn.commit()
            except Exception as exc:
                self._logger.debug(
                    "Failed to commit final item import transaction: %s", exc
                )
            try:
                # Request background encryption flush (debounced)
                if hasattr(self.db_manager, "request_flush"):
                    self.db_manager.request_flush()
            except Exception as exc:
                self._logger.debug(
                    "Failed to request encrypted flush after item import: %s", exc
                )

            # Finish
            _emit_summary()
            if self._cancel_event.is_set():
                # If cancelled, report counts up to the point of cancellation
                self.import_finished.emit(
                    imported_count, processed_count, "Import Cancelled"
                )
            else:
                _emit_progress(total_items, total_items, force=True)
                self.import_finished.emit(
                    imported_count, total_items, None
                )  # None indicates success

        except Exception as e:
            self._logger.error("Import failed:", exc_info=True)
            _emit_status(f"Error: {str(e)}", force=True)
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
                    except Exception as close_error:
                        self._logger.debug(
                            "Failed to close item import worker cursor: %s",
                            close_error,
                        )
                if worker_conn is not None:
                    worker_conn.close()
            except Exception as close_error:
                self._logger.debug(
                    "Failed to close item import worker connection: %s", close_error
                )

    def _load_existing_codes(
        self,
        cursor,
        codes,
    ) -> set[str]:
        normalized_codes = list(
            dict.fromkeys(
                code
                for code in (
                    str(raw_code or "").strip().upper() for raw_code in (codes or [])
                )
                if code
            )
        )
        if not normalized_codes:
            return set()

        existing_codes: set[str] = set()
        for start in range(0, len(normalized_codes), self._EXISTING_CODE_CHUNK_SIZE):
            chunk = normalized_codes[
                start : start + self._EXISTING_CODE_CHUNK_SIZE
            ]
            placeholders = ",".join("?" for _ in chunk)
            cursor.execute(
                f"SELECT code FROM items WHERE UPPER(code) IN ({placeholders})",  # nosec B608
                chunk,
            )
            existing_codes.update(
                str(row[0] or "").strip().upper()
                for row in cursor.fetchall()
                if row and str(row[0] or "").strip()
            )
        return existing_codes
