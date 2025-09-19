"""Async flush scheduling for database encryption writes."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

Callback = Optional[Callable[[], None]]


class FlushScheduler:
    """Debounce and execute encrypted flushes on a background thread."""

    def __init__(
        self,
        *,
        has_connection: Callable[[], bool],
        commit: Callable[[], bool],
        checkpoint: Callable[[], bool],
        encrypt: Callable[[], bool],
        logger: Optional[logging.Logger] = None,
        on_queued_getter: Optional[Callable[[], Callback]] = None,
        on_done_getter: Optional[Callable[[], Callback]] = None,
    ) -> None:
        self._has_connection = has_connection
        self._commit = commit
        self._checkpoint = checkpoint
        self._encrypt = encrypt
        self._logger = logger or logging.getLogger(__name__)
        self._on_queued_getter = on_queued_getter or (lambda: None)
        self._on_done_getter = on_done_getter or (lambda: None)

        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None
        self._thread: Optional[threading.Thread] = None
        self._in_progress = False

    def schedule(self, delay_seconds: float = 2.0) -> None:
        """Request a flush after ``delay_seconds`` unless one is already pending."""
        if not self._has_connection():
            self._debug("schedule skipped: no connection available")
            return

        def _start_worker() -> None:
            with self._lock:
                self._timer = None
                if self._in_progress:
                    return
                self._in_progress = True

            def _worker() -> None:
                try:
                    try:
                        self._commit()
                    except Exception as exc:  # pragma: no cover - defensive logging
                        self._logger.debug("Commit before flush failed: %s", exc, exc_info=True)
                    try:
                        self._checkpoint()
                    except Exception as exc:  # pragma: no cover - best effort only
                        self._logger.debug("Checkpoint before flush failed: %s", exc, exc_info=True)
                    self._encrypt()
                except Exception as exc:  # pragma: no cover - error bubbled to logs
                    self._logger.error("Async flush failed: %s", exc, exc_info=True)
                finally:
                    with self._lock:
                        self._in_progress = False
                    self._invoke_callback(self._on_done_getter())

            thread = threading.Thread(target=_worker, name="DBEncryptFlush", daemon=True)
            thread.start()
            with self._lock:
                self._thread = thread

        with self._lock:
            if self._timer and hasattr(self._timer, "cancel"):
                try:
                    self._timer.cancel()
                except Exception:
                    pass
            self._timer = threading.Timer(delay_seconds, _start_worker)
            try:
                self._timer.daemon = True
            except Exception:
                pass
            self._timer.start()

        self._invoke_callback(self._on_queued_getter())

    def shutdown(self, *, wait: bool = True, join_timeout: float = 8.0, poll_timeout: float = 2.0) -> None:
        """Cancel pending timers and optionally wait for active work."""
        with self._lock:
            timer = self._timer
            thread = self._thread
            self._timer = None
        if timer and hasattr(timer, "cancel"):
            try:
                timer.cancel()
            except Exception:
                pass
        if wait and thread and thread.is_alive():
            thread.join(timeout=join_timeout)
            if thread.is_alive():
                deadline = time.time() + poll_timeout
                while self._in_progress and time.time() < deadline:
                    time.sleep(0.1)

    def _invoke_callback(self, callback: Callback) -> None:
        if callable(callback):
            try:
                callback()
            except Exception as exc:  # pragma: no cover - UI callback must not break flush
                self._logger.debug("Flush callback raised: %s", exc, exc_info=True)

    def _debug(self, message: str) -> None:
        try:
            self._logger.debug(message)
        except Exception:
            pass
