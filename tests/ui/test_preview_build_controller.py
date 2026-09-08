"""Reusable preview work remains bounded, GUI-delivered and safe after close."""

import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid

from silverestimate.ui.estimate_history import EstimateHistoryDialog
from silverestimate.ui.preview_build_worker import PreviewBuildController
from silverestimate.ui.print_payload_builder import PrintPayloadBuilder
from silverestimate.ui.silver_bar_management import SilverBarDialog
from tests.ui.test_history_safeguards import history_db

__all__ = ["history_db"]


@pytest.fixture
def previews(qtbot):
    owner = QWidget()
    controller = PreviewBuildController(owner)
    yield owner, controller
    controller.shutdown()
    if isValid(owner):
        owner.close()
        owner.deleteLater()


def payload():
    return PrintPayloadBuilder().build_estimate_preview_payload(
        "1",
        fetch_estimate=lambda _: None,
        estimate_data={"header": {"voucher_no": "1"}, "items": []},
    )


def start(controller, build, shown, errors):
    controller.start(
        build,
        on_ready=shown.append,
        on_error=errors.append,
        empty_message="Nothing to preview",
    )


def test_repeated_previews_reuse_worker_and_deliver_on_gui_thread(previews, qtbot):
    _owner, controller = previews
    assert controller._runner is None
    built = []
    displayed = []
    gui_thread = threading.get_ident()

    def build():
        built.append(threading.get_ident())
        return payload()

    def show(value):
        displayed.append((threading.get_ident(), value.identifier))

    controller.start(build, on_ready=show, on_error=pytest.fail, empty_message="empty")
    qtbot.waitUntil(lambda: len(displayed) == 1)
    runner = controller._runner
    worker = runner._thread
    controller.start(build, on_ready=show, on_error=pytest.fail, empty_message="empty")
    qtbot.waitUntil(lambda: len(displayed) == 2)
    assert controller._runner is runner and runner._thread is worker
    assert built[0] == built[1] != gui_thread
    assert displayed == [(gui_thread, "1"), (gui_thread, "1")]
    assert controller._progress is None


def test_active_build_keeps_only_latest_pending_request(previews, qtbot):
    _owner, controller = previews
    entered, release = threading.Event(), threading.Event()
    built, shown, errors = [], [], []

    def first():
        entered.set()
        release.wait(3)
        built.append(1)
        return payload()

    try:
        start(controller, first, shown, errors)
        assert entered.wait(2)
        start(controller, lambda: (built.append(2), payload())[1], shown, errors)
        start(controller, lambda: (built.append(3), payload())[1], shown, errors)
        release.set()
        qtbot.waitUntil(lambda: len(shown) == 1)
        assert built == [1, 3] and not errors
    finally:
        release.set()


@pytest.mark.parametrize("close", ["shutdown", "destroy"])
def test_blocked_build_cannot_deliver_after_owner_closes(previews, qtbot, close):
    owner, controller = previews
    entered, release = threading.Event(), threading.Event()
    shown, errors = [], []

    def build():
        entered.set()
        release.wait(3)
        return payload()

    try:
        start(controller, build, shown, errors)
        assert entered.wait(2)
        runner = controller._runner
        if close == "destroy":
            owner.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        else:
            controller.shutdown()
        assert controller._closed and controller._callbacks is None
        assert controller._progress is None
        assert runner._thread.is_alive()  # Closing does not wait for a blocked build.
        release.set()
        qtbot.waitUntil(lambda: not runner._thread.is_alive())
        assert not shown and not errors
    finally:
        release.set()


def test_already_queued_result_cannot_deliver_after_shutdown(previews, qtbot):
    _owner, controller = previews
    release, queued = threading.Event(), threading.Event()
    shown, errors = [], []
    start(controller, lambda: (release.wait(3), payload())[1], shown, errors)
    runner = controller._runner
    runner.result.connect(lambda *a: queued.set(), Qt.ConnectionType.DirectConnection)
    release.set()
    assert queued.wait(2)
    controller.shutdown()
    qtbot.wait(10)
    assert not shown and not errors and controller._progress is None


@pytest.mark.parametrize("failure", ["exception", "empty", "display"])
def test_failure_cleans_progress_and_allows_retry(previews, qtbot, failure):
    _owner, controller = previews
    errors, shown = [], []

    def build():
        if failure == "exception":
            raise ValueError("Build failed")
        return None if failure == "empty" else payload()

    def show(_value):
        raise ValueError("Display failed")

    controller.start(
        build, on_ready=show, on_error=errors.append, empty_message="Nothing to preview"
    )
    qtbot.waitUntil(lambda: len(errors) == 1)
    assert controller._progress is None
    worker = controller._runner._thread
    start(controller, payload, shown, errors)
    qtbot.waitUntil(lambda: len(shown) == 1)
    assert controller._runner._thread is worker
    assert len(errors) == 1


def test_reentrant_preview_keeps_new_progress(previews, qtbot):
    _owner, controller = previews
    second_entered, release = threading.Event(), threading.Event()
    shown, errors = [], []

    def second():
        second_entered.set()
        release.wait(3)
        return payload()

    def show(_value):
        start(controller, second, shown, errors)

    try:
        controller.start(
            payload, on_ready=show, on_error=errors.append, empty_message="empty"
        )
        qtbot.waitUntil(second_entered.is_set)
        assert controller._progress is not None
        release.set()
        qtbot.waitUntil(lambda: len(shown) == 1)
        assert not errors and controller._progress is None
    finally:
        release.set()


@pytest.mark.parametrize("screen", ["entry", "history", "list"])
def test_screens_use_shared_worker_and_cancel_on_close(
    screen, history_db, make_estimate_widget, qtbot
):
    shown = []
    entered, release = threading.Event(), threading.Event()

    def build(*a, **k):
        entered.set()
        release.wait(3)
        return payload()

    manager = SimpleNamespace(
        build_estimate_preview_payload=build,
        show_preview=lambda *a, **k: shown.append(True),
    )
    if screen == "entry":
        owner = make_estimate_widget(history_db)
        owner.workflow_controller._start_estimate_print_preview_build(
            print_manager=manager, voucher_no="1", estimate_data={}
        )
        controller = owner.workflow_controller._preview_builder
    elif screen == "history":
        owner = EstimateHistoryDialog(history_db, None)
        qtbot.addWidget(owner)
        owner._start_print_preview_build(print_manager=manager, build_preview=build)
        controller = owner._preview_builder
    else:
        owner = SilverBarDialog(history_db)
        qtbot.addWidget(owner)
        owner._list_print_controller._start_list_print_preview_build(
            print_manager=manager, build_preview=build
        )
        controller = owner._list_print_controller._preview_builder
    try:
        assert isinstance(controller, PreviewBuildController)
        assert entered.wait(2)
        runner = controller._runner
        owner.close()
        assert controller._closed
        release.set()
        qtbot.waitUntil(lambda: not runner._thread.is_alive())
        assert not shown and controller._progress is None
    finally:
        release.set()
        owner.close()
