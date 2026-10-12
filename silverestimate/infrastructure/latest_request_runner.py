"""Cooperative, latest-request-only background execution for Qt controllers."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Generic, TypeVar

from PySide6.QtCore import QObject, Signal

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

    result = Signal(int, object)
    failed = Signal(int, object)
    settled = Signal(int)

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
                    self._emit("failed", generation, exc)
            else:
                if not cancel_event.is_set() and self._is_current(generation):
                    self._emit("result", generation, value)
            finally:
                should_emit_settled = False
                with self._condition:
                    if self._active_cancel is cancel_event:
                        self._active_cancel = None
                    should_emit_settled = self._is_current_locked(generation)
                if should_emit_settled:
                    self._emit("settled", generation)

    def _is_current_locked(self, generation: int) -> bool:
        return not self._shutdown and generation == self._generation

    def _emit(self, signal_name: str, *args: object) -> None:
        """Emit from the worker thread, tolerating an owner deleted just now.

        The worker checks that its request is still wanted and emits a moment
        later. A runner shut down without waiting (``timeout=0``) can be
        deleted in between; nobody is listening then, so that is not an error.
        """
        try:
            getattr(self, signal_name).emit(*args)
        except RuntimeError:
            with self._condition:
                shut_down = self._shutdown
            if not shut_down:
                raise
