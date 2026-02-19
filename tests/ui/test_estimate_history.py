from silverestimate.ui.estimate_history import EstimateHistoryDialog


class _ButtonStub:
    def __init__(self, enabled=False):
        self.enabled = enabled

    def setEnabled(self, value):
        self.enabled = bool(value)


class _ThreadStub:
    def __init__(self):
        self.quit_called = False
        self.wait_called = False

    def quit(self):
        self.quit_called = True

    def wait(self, _timeout):
        self.wait_called = True
        return True


class _WorkerStub:
    def __init__(self):
        self.deleted = False

    def deleteLater(self):
        self.deleted = True


class _HistoryHarness:
    pass


def _build_harness():
    harness = _HistoryHarness()
    harness._load_request_id = 2
    harness._active_load_workers = {}
    harness.search_button = _ButtonStub(enabled=False)
    harness.open_button = _ButtonStub(enabled=False)
    harness.print_button = _ButtonStub(enabled=False)
    harness.delete_button = _ButtonStub(enabled=False)
    return harness


def test_loading_done_re_enables_buttons_for_current_request():
    harness = _build_harness()
    thread = _ThreadStub()
    worker = _WorkerStub()
    harness._active_load_workers[thread] = worker

    EstimateHistoryDialog._loading_done(harness, thread, worker, 2)

    assert thread.quit_called is True
    assert thread.wait_called is True
    assert worker.deleted is True
    assert thread not in harness._active_load_workers
    assert harness.search_button.enabled is True
    assert harness.open_button.enabled is True
    assert harness.print_button.enabled is True
    assert harness.delete_button.enabled is True


def test_loading_done_does_not_touch_buttons_for_stale_request():
    harness = _build_harness()
    thread = _ThreadStub()
    worker = _WorkerStub()
    harness._active_load_workers[thread] = worker

    EstimateHistoryDialog._loading_done(harness, thread, worker, 1)

    assert thread.quit_called is True
    assert thread.wait_called is True
    assert worker.deleted is True
    assert thread not in harness._active_load_workers
    assert harness.search_button.enabled is False
    assert harness.open_button.enabled is False
    assert harness.print_button.enabled is False
    assert harness.delete_button.enabled is False
