import sqlite3
import threading
import time
from contextlib import closing

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QApplication

from silverestimate.infrastructure.latest_request_runner import (
    LatestRequestRunner,
    RequestCancelledError,
)
from silverestimate.infrastructure.sqlite_worker import cancellable_sqlite_connection


def test_latest_request_replaces_pending_and_rejects_stale_results(qtbot):
    started = threading.Event()
    executed = []

    def work(value, cancel_event):
        executed.append(value)
        if value == 1:
            started.set()
            while not cancel_event.wait(0.005):
                pass
            raise RequestCancelledError
        return value * 10

    runner = LatestRequestRunner(work, name="test-latest-runner")
    results = []
    gui_thread_results = []
    runner.result.connect(
        lambda generation, value: (
            results.append((generation, value)),
            gui_thread_results.append(
                QThread.currentThread() is QApplication.instance().thread()
            ),
        )
    )
    try:
        assert runner.submit(1) == 1
        assert started.wait(1.0)
        assert runner.submit(2) == 2
        assert runner.submit(3) == 3

        qtbot.waitUntil(lambda: results == [(3, 30)], timeout=2000)
        assert executed == [1, 3]
        assert gui_thread_results == [True]
    finally:
        assert runner.shutdown()
        runner.deleteLater()


def test_shutdown_cooperatively_cancels_active_request():
    started = threading.Event()

    def work(_value, cancel_event):
        started.set()
        while not cancel_event.wait(0.005):
            pass
        raise RequestCancelledError

    runner = LatestRequestRunner(work, name="test-cancel-runner")
    runner.submit("slow")
    assert started.wait(1.0)
    assert runner.shutdown(timeout=1.0) is True


def test_sqlite_worker_progress_handler_interrupts_query(tmp_path):
    database_path = tmp_path / "cancel.sqlite"
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("CREATE TABLE values_table(value INTEGER)")
        connection.executemany(
            "INSERT INTO values_table(value) VALUES (?)",
            ((value,) for value in range(2000)),
        )
        connection.commit()

    cancel_event = threading.Event()

    def connection_factory(event):
        connection = sqlite3.connect(database_path)
        connection.set_progress_handler(lambda: int(event.is_set()), 1)
        return connection

    with cancellable_sqlite_connection(
        connection_factory, cancel_event, progress_opcodes=1
    ) as connection:
        cancel_event.set()
        started_at = time.perf_counter()
        try:
            connection.execute(
                "SELECT SUM(a.value * b.value) FROM values_table a, values_table b"
            ).fetchone()
        except sqlite3.OperationalError as exc:
            assert "interrupted" in str(exc).lower()
        else:
            raise AssertionError("Expected SQLite query cancellation.")
        assert time.perf_counter() - started_at < 1.0
