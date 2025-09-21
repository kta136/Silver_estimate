import threading
import time

import pytest

from silverestimate.persistence.flush_scheduler import FlushScheduler


@pytest.fixture()
def scheduler_events():
    return {
        "queued": threading.Event(),
        "done": threading.Event(),
    }


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

    scheduler = FlushScheduler(
        has_connection=lambda: True,
        commit=commit,
        checkpoint=checkpoint,
        encrypt=encrypt,
        on_queued_getter=lambda: scheduler_events["queued"].set,
        on_done_getter=lambda: scheduler_events["done"].set,
    )

    scheduler.schedule(delay_seconds=0.01)

    assert scheduler_events["queued"].wait(1), "Flush was not queued"
    assert scheduler_events["done"].wait(1), "Flush did not complete"

    scheduler.shutdown()

    assert counts == {"commit": 1, "checkpoint": 1, "encrypt": 1}


def test_flush_scheduler_debounces_multiple_requests(scheduler_events):
    counts, commit, checkpoint, encrypt = _make_counters()

    scheduler = FlushScheduler(
        has_connection=lambda: True,
        commit=commit,
        checkpoint=checkpoint,
        encrypt=encrypt,
        on_done_getter=lambda: scheduler_events["done"].set,
    )

    scheduler.schedule(delay_seconds=0.05)
    time.sleep(0.01)  # allow first timer to start counting down
    scheduler.schedule(delay_seconds=0.02)

    assert scheduler_events["done"].wait(1), "Debounced flush never completed"

    scheduler.shutdown()

    assert counts == {"commit": 1, "checkpoint": 1, "encrypt": 1}


def test_flush_scheduler_shutdown_cancels_timer(scheduler_events):
    counts, commit, checkpoint, encrypt = _make_counters()

    scheduler = FlushScheduler(
        has_connection=lambda: True,
        commit=commit,
        checkpoint=checkpoint,
        encrypt=encrypt,
        on_done_getter=lambda: scheduler_events["done"].set,
    )

    scheduler.schedule(delay_seconds=0.2)
    scheduler.shutdown(wait=False)

    time.sleep(0.1)

    assert not scheduler_events["done"].is_set(), "Flush should not have run after shutdown"
    assert counts == {"commit": 0, "checkpoint": 0, "encrypt": 0}

    scheduler.shutdown()


def test_flush_scheduler_skips_without_connection(scheduler_events):
    counts, commit, checkpoint, encrypt = _make_counters()

    scheduler = FlushScheduler(
        has_connection=lambda: False,
        commit=commit,
        checkpoint=checkpoint,
        encrypt=encrypt,
        on_queued_getter=lambda: scheduler_events["queued"].set,
        on_done_getter=lambda: scheduler_events["done"].set,
    )

    scheduler.schedule(delay_seconds=0.01)
    time.sleep(0.05)
    scheduler.shutdown()

    assert not scheduler_events["queued"].is_set()
    assert not scheduler_events["done"].is_set()
    assert counts == {"commit": 0, "checkpoint": 0, "encrypt": 0}
