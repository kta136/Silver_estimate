import threading

import pytest

from silverestimate.persistence.flush_scheduler import FlushScheduler


@pytest.fixture()
def scheduler_events():
    return {
        "queued": threading.Event(),
        "done": threading.Event(),
    }


class _ManualTimer:
    def __init__(self, delay, callback):
        self.delay = delay
        self.callback = callback
        self.daemon = False
        self.cancelled = False
        self.started = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def fire(self):
        if not self.cancelled:
            self.callback()


class _ImmediateThread:
    def __init__(self, target=None, daemon=None, name=None):
        self._target = target
        self.daemon = daemon
        self.name = name
        self._alive = False

    def start(self):
        self._alive = True
        try:
            if self._target:
                self._target()
        finally:
            self._alive = False

    def join(self, timeout=None):
        return None

    def is_alive(self):
        return self._alive


def _make_counters():
    lock = threading.Lock()
    counts = {"commit": 0, "checkpoint": 0, "encrypt": 0}

    def record(name):
        with lock:
            counts[name] += 1

    def commit():
        record("commit")
        return True

    def checkpoint():
        record("checkpoint")
        return True

    def encrypt():
        record("encrypt")
        return True

    return counts, commit, checkpoint, encrypt


def test_flush_scheduler_runs_after_delay(scheduler_events):
    counts, commit, checkpoint, encrypt = _make_counters()
    timers = []

    def timer_factory(delay, callback):
        timer = _ManualTimer(delay, callback)
        timers.append(timer)
        return timer

    scheduler = FlushScheduler(
        has_connection=lambda: True,
        commit=commit,
        checkpoint=checkpoint,
        encrypt=encrypt,
        on_queued_getter=lambda: scheduler_events["queued"].set,
        on_done_getter=lambda: scheduler_events["done"].set,
        timer_factory=timer_factory,
        thread_factory=lambda **kwargs: _ImmediateThread(**kwargs),
    )

    scheduler.schedule(delay_seconds=0.01)

    assert scheduler_events["queued"].is_set(), "Flush was not queued"
    assert len(timers) == 1
    timers[0].fire()
    assert scheduler_events["done"].is_set(), "Flush did not complete"

    scheduler.shutdown()

    assert counts == {"commit": 1, "checkpoint": 1, "encrypt": 1}


def test_flush_scheduler_debounces_multiple_requests(scheduler_events):
    counts, commit, checkpoint, encrypt = _make_counters()
    timers = []

    def timer_factory(delay, callback):
        timer = _ManualTimer(delay, callback)
        timers.append(timer)
        return timer

    scheduler = FlushScheduler(
        has_connection=lambda: True,
        commit=commit,
        checkpoint=checkpoint,
        encrypt=encrypt,
        on_done_getter=lambda: scheduler_events["done"].set,
        timer_factory=timer_factory,
        thread_factory=lambda **kwargs: _ImmediateThread(**kwargs),
    )

    scheduler.schedule(delay_seconds=0.05)
    scheduler.schedule(delay_seconds=0.02)

    assert len(timers) == 2
    assert timers[0].cancelled is True

    timers[0].fire()
    assert not scheduler_events["done"].is_set()

    timers[1].fire()
    assert scheduler_events["done"].is_set(), "Debounced flush never completed"

    scheduler.shutdown()

    assert counts == {"commit": 1, "checkpoint": 1, "encrypt": 1}


def test_flush_scheduler_shutdown_cancels_timer(scheduler_events):
    counts, commit, checkpoint, encrypt = _make_counters()
    timers = []

    def timer_factory(delay, callback):
        timer = _ManualTimer(delay, callback)
        timers.append(timer)
        return timer

    scheduler = FlushScheduler(
        has_connection=lambda: True,
        commit=commit,
        checkpoint=checkpoint,
        encrypt=encrypt,
        on_done_getter=lambda: scheduler_events["done"].set,
        timer_factory=timer_factory,
        thread_factory=lambda **kwargs: _ImmediateThread(**kwargs),
    )

    scheduler.schedule(delay_seconds=0.2)
    scheduler.shutdown(wait=False)

    assert len(timers) == 1
    assert timers[0].cancelled is True
    assert not scheduler_events["done"].is_set()
    assert counts == {"commit": 0, "checkpoint": 0, "encrypt": 0}


def test_flush_scheduler_skips_without_connection(scheduler_events):
    counts, commit, checkpoint, encrypt = _make_counters()
    timers = []

    def timer_factory(delay, callback):
        timer = _ManualTimer(delay, callback)
        timers.append(timer)
        return timer

    scheduler = FlushScheduler(
        has_connection=lambda: False,
        commit=commit,
        checkpoint=checkpoint,
        encrypt=encrypt,
        on_queued_getter=lambda: scheduler_events["queued"].set,
        on_done_getter=lambda: scheduler_events["done"].set,
        timer_factory=timer_factory,
        thread_factory=lambda **kwargs: _ImmediateThread(**kwargs),
    )

    scheduler.schedule(delay_seconds=0.01)
    scheduler.shutdown()

    assert len(timers) == 0
    assert not scheduler_events["queued"].is_set()
    assert not scheduler_events["done"].is_set()
    assert counts == {"commit": 0, "checkpoint": 0, "encrypt": 0}
