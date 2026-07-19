from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pytest
from PyQt6.QtCore import QDate, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPixmap
from PyQt6.QtPrintSupport import QPrinter, QPrintPreviewDialog
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from silverestimate.controllers import startup_controller as startup_module
from silverestimate.controllers.startup_controller import (
    StartupController,
    StartupStatus,
)
from silverestimate.services import auth_service
from silverestimate.ui.application_theme import apply_light_application_theme
from silverestimate.ui.estimate_entry_logic.constants import (
    COL_CODE,
    COL_FINE_WT,
    COL_GROSS,
    COL_ITEM_NAME,
    COL_NET_WT,
    COL_POLY,
    COL_PURITY,
    COL_WAGE_AMT,
    COL_WAGE_RATE,
)
from silverestimate.ui.login_dialog import LoginDialog
from silverestimate.ui.main_window import MainWindow
from tests.factories import estimate_totals, regular_item, return_item, silver_bar_item

pytestmark = pytest.mark.smoke

SMOKE_MAIN_PASSWORD = "SilverSmokeMain#2026"
SMOKE_RECOVERY_PASSWORD = "SilverSmokeRecovery#2026"
SMOKE_SCREENSHOT_MIN_WIDTH = 1366
SMOKE_SCREENSHOT_MIN_HEIGHT = 768

_SMOKE_FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("C:/Windows/Fonts/calibri.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
)


def _configure_smoke_font(app: QApplication) -> None:
    for candidate in _SMOKE_FONT_CANDIDATES:
        if not candidate.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(candidate))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if font_id >= 0 and families:
            app.setFont(QFont(families[0], 9))
            return
    app.setFont(QFont("Sans Serif", 9))


class _MessageBoxStub:
    StandardButton = QMessageBox.StandardButton
    Icon = QMessageBox.Icon
    Yes = QMessageBox.StandardButton.Yes
    No = QMessageBox.StandardButton.No
    Ok = QMessageBox.StandardButton.Ok
    Cancel = QMessageBox.StandardButton.Cancel

    @staticmethod
    def information(*_args, **_kwargs):
        return QMessageBox.StandardButton.Ok

    @staticmethod
    def warning(*_args, **_kwargs):
        return QMessageBox.StandardButton.Yes

    @staticmethod
    def critical(*_args, **_kwargs):
        return QMessageBox.StandardButton.Ok

    @staticmethod
    def question(*_args, **_kwargs):
        return QMessageBox.StandardButton.Yes

    @staticmethod
    def about(*_args, **_kwargs):
        return QMessageBox.StandardButton.Ok


class _StubLiveRateController:
    def __init__(self, *, parent, widget_getter, status_callback, logger=None, **_):
        self.parent = parent
        self.widget_getter = widget_getter
        self.status_callback = status_callback
        self.logger = logger
        self.initialize_called = False
        self.shutdown_called = False

    def initialize(self) -> None:
        self.initialize_called = True

    def shutdown(self) -> None:
        self.shutdown_called = True

    def refresh_now(self) -> None:
        return None

    def apply_visibility_settings(self) -> bool:
        return True

    def apply_timer_settings(self, **_kwargs) -> None:
        return None


class _SmokePasswordContext:
    def __init__(self) -> None:
        from argon2 import PasswordHasher

        self._hasher = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1)

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        from argon2.exceptions import VerificationError

        try:
            return bool(self._hasher.verify(password_hash, password))
        except VerificationError:
            return False


@dataclass
class _SmokeCapture:
    enabled: bool
    output_dir: Path

    @staticmethod
    def _minimum_canvas(pixmap: QPixmap) -> QPixmap:
        target_width = max(SMOKE_SCREENSHOT_MIN_WIDTH, pixmap.width())
        target_height = max(SMOKE_SCREENSHOT_MIN_HEIGHT, pixmap.height())
        if target_width == pixmap.width() and target_height == pixmap.height():
            return pixmap

        canvas = QPixmap(target_width, target_height)
        canvas.fill(QColor("#f3f6fb"))
        painter = QPainter(canvas)
        try:
            x = (target_width - pixmap.width()) // 2
            y = (target_height - pixmap.height()) // 2
            painter.drawPixmap(x, y, pixmap)
        finally:
            painter.end()
        return canvas

    def __call__(self, widget, filename: str) -> Path | None:
        if not self.enabled:
            return None
        self.output_dir.mkdir(parents=True, exist_ok=True)
        QApplication.processEvents()
        path = self.output_dir / filename
        self._minimum_canvas(widget.grab()).save(str(path), "PNG")
        return path


@pytest.fixture()
def smoke_capture(request) -> _SmokeCapture:
    artifact_dir = Path(request.config.getoption("--smoke-artifact-dir")).resolve()
    return _SmokeCapture(
        enabled=bool(request.config.getoption("--smoke-screenshots")),
        output_dir=artifact_dir,
    )


@pytest.fixture()
def smoke_environment(monkeypatch, settings_stub, tmp_path):
    del settings_stub
    db_path = tmp_path / "database" / "estimation.db"

    app = QApplication.instance()
    if app is not None:
        apply_light_application_theme(app, logging.getLogger("test.smoke.theme"))
        _configure_smoke_font(app)

    monkeypatch.setattr(startup_module, "DB_PATH", str(db_path))
    monkeypatch.setattr(startup_module, "DatabaseManager", None, raising=False)
    monkeypatch.setattr(startup_module, "QMessageBox", _MessageBoxStub)
    monkeypatch.setattr(auth_service, "LoginDialog", LoginDialog, raising=False)
    monkeypatch.setattr(auth_service, "QMessageBox", _MessageBoxStub)
    monkeypatch.setattr(
        "silverestimate.ui.estimate_entry_workflow_controller.QMessageBox",
        _MessageBoxStub,
    )
    monkeypatch.setattr(
        "silverestimate.ui.estimate_history.QMessageBox", _MessageBoxStub
    )
    for message_box_target in (
        "silverestimate.ui.print_preview_controller.QMessageBox",
        "silverestimate.ui.settings_dialog.QMessageBox",
        "silverestimate.ui.silver_bar_history.QMessageBox",
        "silverestimate.ui.silver_bar_list_lifecycle_controller.QMessageBox",
        "silverestimate.ui.silver_bar_load_controller.QMessageBox",
        "silverestimate.ui.silver_bar_management.QMessageBox",
        "silverestimate.ui.silver_bar_optimization_controller.QMessageBox",
        "silverestimate.ui.silver_bar_table_controller.QMessageBox",
        "silverestimate.ui.silver_bar_transfer_controller.QMessageBox",
    ):
        monkeypatch.setattr(message_box_target, _MessageBoxStub)
    monkeypatch.setattr(
        "silverestimate.controllers.navigation_controller.QMessageBox",
        _MessageBoxStub,
    )
    monkeypatch.setattr(
        "silverestimate.services.navigation_service.QMessageBox",
        _MessageBoxStub,
    )
    monkeypatch.setattr(
        "silverestimate.controllers.live_rate_controller.LiveRateController",
        _StubLiveRateController,
    )
    monkeypatch.setattr(
        "silverestimate.infrastructure.windows_integration.apply_taskbar_icon",
        lambda *args, **kwargs: 0,
    )
    monkeypatch.setattr(
        "silverestimate.infrastructure.windows_integration.destroy_icon_handle",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "silverestimate.ui.login_dialog.bring_window_to_front",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "silverestimate.ui.login_dialog._get_pwd_context",
        lambda: _SmokePasswordContext(),
    )
    monkeypatch.setattr(
        "PyQt6.QtWidgets.QApplication.quit",
        lambda self=None: None,
    )

    return db_path


def _submit_next_login_dialog(
    *,
    password: str,
    recovery_password: str | None,
    screenshot_name: str,
    capture: _SmokeCapture,
) -> None:
    def _attempt(remaining: int = 100) -> None:
        dialog = next(
            (
                widget
                for widget in QApplication.topLevelWidgets()
                if isinstance(widget, LoginDialog) and widget.isVisible()
            ),
            None,
        )
        if dialog is None:
            if remaining > 0:
                QTimer.singleShot(20, lambda: _attempt(remaining - 1))
            return

        dialog.password_input.setText(password)
        if dialog.is_setup:
            assert recovery_password is not None
            dialog.confirm_main_password_input.setText(password)
            dialog.backup_password_input.setText(recovery_password)
            dialog.confirm_password_input.setText(recovery_password)
        capture(dialog, screenshot_name)
        dialog.ok_button.click()

    QTimer.singleShot(0, _attempt)


def _authenticate_with_dialog(
    *,
    password: str,
    recovery_password: str | None,
    screenshot_name: str,
    capture: _SmokeCapture,
):
    _submit_next_login_dialog(
        password=password,
        recovery_password=recovery_password,
        screenshot_name=screenshot_name,
        capture=capture,
    )
    controller = StartupController(logger=logging.getLogger("test.smoke.startup"))
    result = controller.authenticate_and_prepare()
    assert result.status is StartupStatus.OK
    assert result.db is not None
    return result.db


def _seed_smoke_database(db_manager) -> None:
    item_rows = [
        ("RING001", "Gold Ring", 91.6, "WT", 250.0),
        ("NECK001", "Gold Necklace", 75.0, "WT", 325.0),
        ("BRAC001", "Gold Bracelet", 91.6, "WT", 275.0),
        ("ANKL001", "Silver Anklet", 92.5, "PC", 85.0),
        ("BAR001", "Silver Bar", 99.9, "WT", 0.0),
    ]
    for row in item_rows:
        assert db_manager.items_repo.add_item(*row)

    estimate_one_regular = regular_item(
        code="RING001",
        name="Gold Ring",
        gross=12.0,
        poly=0.5,
        net_wt=11.5,
        purity=91.6,
        wage_rate=250.0,
        pieces=1,
        wage=2875.0,
        fine=10.534,
    )
    estimate_one_return = return_item(
        code="ANKL001",
        name="Silver Anklet",
        gross=3.0,
        poly=0.0,
        net_wt=3.0,
        purity=92.5,
        wage_rate=85.0,
        pieces=2,
        wage=170.0,
        fine=2.775,
        wage_type="PC",
    )
    assert db_manager.estimates_repo.save_estimate_with_returns(
        voucher_no="1",
        date="2026-01-15",
        silver_rate=75000.0,
        regular_items=[estimate_one_regular],
        return_items=[estimate_one_return],
        totals=estimate_totals(
            total_gross=12.0,
            total_net=11.5,
            net_fine=7.759,
            net_wage=2705.0,
            note="Smoke estimate one",
        ),
    )

    estimate_two_regular = regular_item(
        code="NECK001",
        name="Gold Necklace",
        gross=20.0,
        poly=1.25,
        net_wt=18.75,
        purity=75.0,
        wage_rate=325.0,
        pieces=1,
        wage=6094.0,
        fine=14.0625,
    )
    estimate_two_bar = silver_bar_item(
        code="BAR001",
        name="Silver Bar",
        gross=5.0,
        poly=0.0,
        net_wt=5.0,
        purity=99.9,
        wage_rate=0.0,
        pieces=1,
        wage=0.0,
        fine=4.995,
    )
    assert db_manager.estimates_repo.save_estimate_with_returns(
        voucher_no="2",
        date="2026-01-16",
        silver_rate=75250.0,
        regular_items=[estimate_two_regular],
        return_items=[estimate_two_bar],
        totals=estimate_totals(
            total_gross=20.0,
            total_net=18.75,
            net_fine=19.0575,
            net_wage=6094.0,
            note="Smoke estimate two",
        ),
    )

    available_bar_id = db_manager.silver_bars_repo.add_silver_bar("2", 40.0, 99.9)
    active_bar_id = db_manager.silver_bars_repo.add_silver_bar("2", 35.0, 99.5)
    issued_bar_id = db_manager.silver_bars_repo.add_silver_bar("2", 25.0, 99.0)
    active_list_id = db_manager.create_silver_bar_list("Smoke active list")
    issued_list_id = db_manager.create_silver_bar_list("Smoke issued list")
    assert available_bar_id is not None
    assert active_bar_id is not None
    assert issued_bar_id is not None
    assert active_list_id is not None
    assert issued_list_id is not None
    assert db_manager.assign_bar_to_list(
        active_bar_id,
        active_list_id,
        note="Smoke active assignment",
    )
    assert db_manager.assign_bar_to_list(
        issued_bar_id,
        issued_list_id,
        note="Smoke issued assignment",
    )
    assert db_manager.mark_silver_bar_list_as_issued(
        issued_list_id,
        issued_date="2026-01-18 09:00:00",
    )

    deterministic_updates = (
        (
            "UPDATE silver_bars SET date_added = ? WHERE bar_id = ?",
            ("2026-01-17 09:00:00", available_bar_id),
        ),
        (
            "UPDATE silver_bars SET date_added = ? WHERE bar_id = ?",
            ("2026-01-17 09:05:00", active_bar_id),
        ),
        (
            "UPDATE silver_bars SET date_added = ? WHERE bar_id = ?",
            ("2026-01-17 09:10:00", issued_bar_id),
        ),
        (
            "UPDATE silver_bar_lists SET creation_date = ? WHERE list_id = ?",
            ("2026-01-17 10:00:00", active_list_id),
        ),
        (
            "UPDATE silver_bar_lists SET creation_date = ? WHERE list_id = ?",
            ("2026-01-17 11:00:00", issued_list_id),
        ),
    )
    for statement, params in deterministic_updates:
        db_manager.cursor.execute(statement, params)
    db_manager.conn.commit()


def _wait_for(condition: Callable[[], bool], qtbot, *, timeout: int = 2000) -> None:
    qtbot.waitUntil(condition, timeout=timeout)


def _show_main_window_for_smoke(window: MainWindow, qtbot) -> None:
    window.showNormal()
    window.setWindowState(Qt.WindowState.WindowNoState)
    window.setGeometry(0, 0, SMOKE_SCREENSHOT_MIN_WIDTH, SMOKE_SCREENSHOT_MIN_HEIGHT)
    window.resize(SMOKE_SCREENSHOT_MIN_WIDTH, SMOKE_SCREENSHOT_MIN_HEIGHT)
    window.show()
    QApplication.processEvents()
    _wait_for(
        lambda: (
            window.isVisible()
            and window.width() >= SMOKE_SCREENSHOT_MIN_WIDTH
            and window.height() >= SMOKE_SCREENSHOT_MIN_HEIGHT
        ),
        qtbot,
        timeout=3000,
    )


def _cell_float(value: str) -> float:
    return float(str(value).replace(",", ""))


def _dict_rows(rows) -> list[dict]:
    return [dict(row) if not isinstance(row, dict) else dict(row) for row in rows or []]


def _show_and_capture_dialog(
    dialog: QDialog,
    *,
    qtbot,
    capture: _SmokeCapture,
    filename: str,
    width: int,
    height: int,
) -> None:
    qtbot.addWidget(dialog)
    dialog.resize(width, height)
    dialog.show()
    _wait_for(lambda: dialog.isVisible(), qtbot)
    QApplication.processEvents()
    capture(dialog, filename)


def _populate_silver_bar_management_dialog(dialog, db_manager) -> None:
    dialog._cancel_active_loads()
    available_rows, available_total = db_manager.get_available_silver_bars_page()
    dialog._populate_table(
        dialog.available_bars_table,
        _dict_rows(available_rows),
        total_rows=available_total,
    )

    active_list_index = next(
        (
            index
            for index in range(dialog.list_combo.count())
            if dialog.list_combo.itemData(index) is not None
        ),
        -1,
    )
    assert active_list_index >= 0
    dialog.list_combo.setCurrentIndex(active_list_index)
    dialog._cancel_active_loads()
    list_rows, list_total = db_manager.get_silver_bars_in_list_page(
        dialog.current_list_id
    )
    dialog._populate_table(
        dialog.list_bars_table,
        _dict_rows(list_rows),
        total_rows=list_total,
    )
    dialog._update_transfer_buttons_state()
    dialog._update_selection_summaries()


def _capture_print_preview_screen(
    *,
    parent_widget,
    capture: _SmokeCapture,
) -> None:
    from silverestimate.ui.print_payload_builder import (
        HtmlPrintDocument,
        PrintPreviewPayload,
    )
    from silverestimate.ui.print_preview_controller import PrintPreviewController

    captured = {"done": False}

    def render_document(printer, document) -> None:
        assert isinstance(document, HtmlPrintDocument)
        painter = QPainter(printer)
        painter.drawText(20, 40, "Smoke Estimate 100")
        painter.end()

    def capture_and_close(remaining: int = 100) -> None:
        preview = next(
            (
                widget
                for widget in QApplication.topLevelWidgets()
                if isinstance(widget, QPrintPreviewDialog) and widget.isVisible()
            ),
            None,
        )
        if preview is None:
            if remaining > 0:
                QTimer.singleShot(20, lambda: capture_and_close(remaining - 1))
            return
        capture(preview, "13-print-preview.png")
        captured["done"] = True
        preview.accept()

    def force_close_preview() -> None:
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QPrintPreviewDialog):
                widget.reject()

    payload = PrintPreviewPayload(
        document=HtmlPrintDocument("Smoke Estimate 100", table_mode=False),
        title="Print Preview - Smoke Estimate 100",
        document_kind="estimate",
        identifier="100",
        suggested_filename="Smoke-Estimate-100.pdf",
    )
    controller = PrintPreviewController(
        printer=QPrinter(QPrinter.PrinterMode.ScreenResolution),
        render_document=render_document,
    )
    QTimer.singleShot(0, capture_and_close)
    QTimer.singleShot(3000, force_close_preview)
    controller.open_preview(payload, parent_widget=parent_widget)
    assert captured["done"]


def test_full_startup_smoke_with_seeded_database_and_screenshots(
    qtbot,
    qt_app,
    smoke_environment,
    smoke_capture,
):
    assert not smoke_environment.exists()

    setup_db = _authenticate_with_dialog(
        password=SMOKE_MAIN_PASSWORD,
        recovery_password=SMOKE_RECOVERY_PASSWORD,
        screenshot_name="01-login-setup.png",
        capture=smoke_capture,
    )
    try:
        _seed_smoke_database(setup_db)
    finally:
        setup_db.close()

    reopened_db = _authenticate_with_dialog(
        password=SMOKE_MAIN_PASSWORD,
        recovery_password=None,
        screenshot_name="02-login-existing-password.png",
        capture=smoke_capture,
    )

    window = None
    open_dialogs = []
    try:
        seeded_codes = {
            dict(row)["code"] for row in reopened_db.items_repo.get_all_items()
        }
        assert {"RING001", "NECK001", "BRAC001", "ANKL001", "BAR001"} <= seeded_codes
        assert reopened_db.estimates_repo.get_estimate_by_voucher("1") is not None
        assert reopened_db.estimates_repo.get_estimate_by_voucher("2") is not None

        window = MainWindow(
            db_manager=reopened_db,
            logger=logging.getLogger("test.smoke.main-window"),
        )
        qtbot.addWidget(window)
        _show_main_window_for_smoke(window, qtbot)
        smoke_capture(window, "03-main-window.png")

        widget = window.estimate_widget
        widget.print_estimate = lambda: None
        table = widget.item_table
        _wait_for(lambda: table.rowCount() > 0, qtbot)
        assert widget.voucher_edit.text() == "3"

        assert widget.presenter.handle_item_code(0, "RING001") is True
        _wait_for(
            lambda: table.get_cell_text(0, COL_CODE).strip().upper() == "RING001",
            qtbot,
        )
        assert table.get_cell_text(0, COL_ITEM_NAME) == "Gold Ring"

        widget.voucher_edit.setText("100")
        widget.date_edit.setDate(QDate(2026, 1, 17))
        widget.note_edit.setText("Automated smoke estimate")
        widget.current_row = 0
        table.set_cell_text(0, COL_GROSS, "10.000")
        table.set_cell_text(0, COL_POLY, "0.500")
        table.set_cell_text(0, COL_PURITY, "91.6")
        table.set_cell_text(0, COL_WAGE_RATE, "250")
        widget.calculate_net_weight()
        widget.calculate_totals()
        _wait_for(
            lambda: table.get_cell_text(0, COL_WAGE_AMT).strip() not in {"", "0"},
            qtbot,
        )
        assert _cell_float(table.get_cell_text(0, COL_NET_WT)) == pytest.approx(9.5)
        assert _cell_float(table.get_cell_text(0, COL_FINE_WT)) == pytest.approx(
            8.702, abs=0.01
        )
        assert _cell_float(table.get_cell_text(0, COL_WAGE_AMT)) == pytest.approx(
            2375.0
        )
        smoke_capture(widget, "04-estimate-entry.png")

        widget.save_estimate()
        assert reopened_db.estimates_repo.get_estimate_by_voucher("100") is not None

        widget.voucher_edit.setText("100")
        widget.safe_load_estimate()
        _wait_for(
            lambda: table.get_cell_text(0, COL_CODE).strip().upper() == "RING001",
            qtbot,
        )
        assert table.get_cell_text(0, COL_ITEM_NAME) == "Gold Ring"
        assert _cell_float(table.get_cell_text(0, COL_NET_WT)) == pytest.approx(9.5)

        window.show_item_master()
        _wait_for(
            lambda: (
                window.item_master_widget is not None
                and window.item_master_widget.items_model.rowCount() >= 5
            ),
            qtbot,
            timeout=3000,
        )
        assert window.stack.currentWidget() is window.item_master_widget
        smoke_capture(window.item_master_widget, "05-item-master.png")

        from silverestimate.ui.estimate_history import EstimateHistoryDialog

        history_dialog = EstimateHistoryDialog(reopened_db, window, parent=window)
        open_dialogs.append(history_dialog)
        _show_and_capture_dialog(
            history_dialog,
            qtbot=qtbot,
            capture=smoke_capture,
            filename="06-estimate-history.png",
            width=1000,
            height=680,
        )
        history_dialog._cancel_active_loads()
        history_rows = history_dialog._load_estimates_sync()
        history_dialog._populate_table(history_rows)
        assert history_dialog.estimates_model.rowCount() >= 2
        visible_vouchers = {
            history_dialog.estimates_model.row_payload(row).voucher_no
            for row in range(history_dialog.estimates_model.rowCount())
            if history_dialog.estimates_model.row_payload(row) is not None
        }
        assert {"1", "2"} <= visible_vouchers
        smoke_capture(history_dialog, "06-estimate-history.png")

        from silverestimate.ui.custom_font_dialog import CustomFontDialog
        from silverestimate.ui.item_selection_dialog import ItemSelectionDialog
        from silverestimate.ui.settings_dialog import SettingsDialog
        from silverestimate.ui.silver_bar_history import SilverBarHistoryDialog
        from silverestimate.ui.silver_bar_management import (
            OptimalListDialog,
            SilverBarDialog,
        )

        settings_dialog = SettingsDialog(main_window_ref=window, parent=window)
        open_dialogs.append(settings_dialog)
        _show_and_capture_dialog(
            settings_dialog,
            qtbot=qtbot,
            capture=smoke_capture,
            filename="07-settings.png",
            width=900,
            height=720,
        )
        assert settings_dialog.sidebar.count() >= 6

        font_dialog = CustomFontDialog(window.print_font, parent=window)
        open_dialogs.append(font_dialog)
        _show_and_capture_dialog(
            font_dialog,
            qtbot=qtbot,
            capture=smoke_capture,
            filename="08-custom-font.png",
            width=520,
            height=470,
        )
        assert font_dialog.size_spinbox.value() >= 5

        item_selection_dialog = ItemSelectionDialog(reopened_db, "RING", parent=window)
        open_dialogs.append(item_selection_dialog)
        _show_and_capture_dialog(
            item_selection_dialog,
            qtbot=qtbot,
            capture=smoke_capture,
            filename="09-item-selection.png",
            width=860,
            height=520,
        )
        assert item_selection_dialog.items_model.rowCount() >= 1
        assert item_selection_dialog.detail_code.text() == "RING001"

        silver_bar_dialog = SilverBarDialog(reopened_db, parent=window)
        open_dialogs.append(silver_bar_dialog)
        _show_and_capture_dialog(
            silver_bar_dialog,
            qtbot=qtbot,
            capture=smoke_capture,
            filename="10-silver-bar-management.png",
            width=1200,
            height=760,
        )
        _populate_silver_bar_management_dialog(silver_bar_dialog, reopened_db)
        assert silver_bar_dialog.available_bars_model.rowCount() >= 1
        assert silver_bar_dialog.list_bars_model.rowCount() >= 1
        smoke_capture(silver_bar_dialog, "10-silver-bar-management.png")

        optimal_dialog = OptimalListDialog(parent=silver_bar_dialog)
        open_dialogs.append(optimal_dialog)
        _show_and_capture_dialog(
            optimal_dialog,
            qtbot=qtbot,
            capture=smoke_capture,
            filename="11-silver-bar-optimization.png",
            width=500,
            height=560,
        )
        assert optimal_dialog.min_weight_spin.value() > 0

        silver_history_dialog = SilverBarHistoryDialog(reopened_db, parent=window)
        open_dialogs.append(silver_history_dialog)
        _show_and_capture_dialog(
            silver_history_dialog,
            qtbot=qtbot,
            capture=smoke_capture,
            filename="12-silver-bar-history.png",
            width=1000,
            height=680,
        )
        silver_history_dialog._cancel_active_loads()
        silver_history_dialog.populate_bars_table(
            _dict_rows(reopened_db.search_silver_bar_history(limit=2000))
        )
        silver_history_dialog.load_issued_lists()
        assert silver_history_dialog.bars_model.rowCount() >= 3
        assert silver_history_dialog.lists_model.rowCount() >= 1
        smoke_capture(silver_history_dialog, "12-silver-bar-history.png")

        _capture_print_preview_screen(
            parent_widget=window,
            capture=smoke_capture,
        )

        if smoke_capture.enabled:
            expected = {
                "01-login-setup.png",
                "02-login-existing-password.png",
                "03-main-window.png",
                "04-estimate-entry.png",
                "05-item-master.png",
                "06-estimate-history.png",
                "07-settings.png",
                "08-custom-font.png",
                "09-item-selection.png",
                "10-silver-bar-management.png",
                "11-silver-bar-optimization.png",
                "12-silver-bar-history.png",
                "13-print-preview.png",
            }
            assert expected <= {
                path.name for path in smoke_capture.output_dir.glob("*.png")
            }
    finally:
        for dialog in reversed(open_dialogs):
            dialog.close()
            dialog.deleteLater()
        if window is not None:
            window.close()
            window.deleteLater()
            qt_app.processEvents()
        elif reopened_db is not None:
            reopened_db.close()
