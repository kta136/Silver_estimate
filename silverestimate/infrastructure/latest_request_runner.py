"""Cooperative, latest-request-only background execution for Qt controllers."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Generic, TypeVar

from PyQt6.QtCore import QObject, pyqtSignal

RequestT = TypeVar("RequestT")
ResultT = TypeVar("ResultT")


class RequestCancelledError(RuntimeError):
    """Raised by cooperative work when cancellation has been requested."""


class LatestRequestRunner(QObject, Generic[RequestT, ResultT]):
    """Run one request at a time and retain at most one pending replacement.

    The worker thread is persistent for the lifetime of the controller. Submitting a
    new request cancels the active request, replaces any pending request, and prevents
    stale results from reaching the UI.
    """

    result = pyqtSignal(int, object)
    failed = pyqtSignal(int, object)
    settled = pyqtSignal(int)

    def __init__(
        self,
        worker: Callable[[RequestT, threading.Event], ResultT],
        parent: QObject | None = None,
        *,
        name: str = "latest-request",
    ) -> None:
        super().__init__(parent)
        self._worker = worker
        self._condition = threading.Condition()
        self._generation = 0
        self._pending: tuple[int, RequestT] | None = None
        self._active_cancel: threading.Event | None = None
        self._shutdown = False
        self._thread = threading.Thread(
            target=self._run,
            name=name,
            daemon=True,
        )
        self._thread.start()

    @property
    def generation(self) -> int:
        with self._condition:
            return self._generation

    def submit(self, request: RequestT) -> int:
        """Cancel older work, queue ``request``, and return its generation ID."""
        with self._condition:
            if self._shutdown:
                raise RuntimeError("LatestRequestRunner has been shut down.")
            self._generation += 1
            generation = self._generation
            if self._active_cancel is not None:
                self._active_cancel.set()
            self._pending = (generation, request)
            self._condition.notify()
            return generation

    def cancel(self) -> None:
        """Cancel active work and discard the pending replacement request."""
        with self._condition:
            self._generation += 1
            self._pending = None
            if self._active_cancel is not None:
                self._active_cancel.set()
            self._condition.notify_all()

    def shutdown(self, timeout: float = 5.0) -> bool:
        """Request cooperative shutdown and wait briefly for the worker to exit."""
        with self._condition:
            self._generation += 1
            self._pending = None
            self._shutdown = True
            if self._active_cancel is not None:
                self._active_cancel.set()
            self._condition.notify_all()
        if threading.current_thread() is not self._thread:
            self._thread.join(max(0.0, timeout))
        return not self._thread.is_alive()

    def _is_current(self, generation: int) -> bool:
        with self._condition:
            return not self._shutdown and generation == self._generation

    def _run(self) -> None:
        while True:
            with self._condition:
                while self._pending is None and not self._shutdown:
                    self._condition.wait()
                if self._shutdown:
                    return
                pending = self._pending
                if pending is None:  # pragma: no cover - guarded by the condition
                    continue
                generation, request = pending
                self._pending = None
                cancel_event = threading.Event()
                self._active_cancel = cancel_event

            try:
                value = self._worker(request, cancel_event)
            except RequestCancelledError:
                pass
            except Exception as exc:
                if not cancel_event.is_set() and self._is_current(generation):
                    self.failed.emit(generation, exc)
            else:
                if not cancel_event.is_set() and self._is_current(generation):
                    self.result.emit(generation, value)
            finally:
                should_emit_settled = False
                with self._condition:
                    if self._active_cancel is cancel_event:
                        self._active_cancel = None
                    should_emit_settled = self._is_current_locked(generation)
                if should_emit_settled:
                    self.settled.emit(generation)

    def _is_current_locked(self, generation: int) -> bool:
        return not self._shutdown and generation == self._generation
