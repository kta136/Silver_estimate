import threading

import pytest
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication
from shiboken6 import delete

from silverestimate.infrastructure.latest_request_runner import (
    LatestRequestRunner,
    RequestCancelledError,
)


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
    assert runner.shutdown(timeout=1.0) is True
    with pytest.raises(RuntimeError, match="shut down"):
        runner.submit("late")


def test_a_runner_deleted_after_shutdown_is_not_an_error_for_its_worker(monkeypatch):
    # The worker checks that its request is still current and emits a moment
    # later. Shut down without waiting and deleted in that gap, the emit used to
    # raise "Signal source has been deleted" in the worker thread.
    started, release = threading.Event(), threading.Event()
    errors = []
    monkeypatch.setattr(threading, "excepthook", lambda args: errors.append(args))

    def work(request, cancel_event):
        started.set()
        release.wait(5)
        return request

    runner = LatestRequestRunner(work, name="test-deleted")
    thread = runner._thread
    runner.submit(1)
    assert started.wait(2)
    # The check has already passed by the time the owner goes away.
    monkeypatch.setattr(runner, "_is_current", lambda generation: True)
    monkeypatch.setattr(runner, "_is_current_locked", lambda generation: True)
    runner.shutdown(timeout=0)
    delete(runner)
    release.set()
    thread.join(5)

    assert not thread.is_alive()
    assert errors == []


def test_a_deleted_runner_that_was_never_shut_down_still_reports_the_error():
    runner = LatestRequestRunner(lambda request, cancel: request, name="test-live")
    try:
        delete(runner)
        with pytest.raises(RuntimeError):
            runner._emit("result", 1, "value")
    finally:
        runner._shutdown = True
