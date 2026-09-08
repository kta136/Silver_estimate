"""Helpers for tracking the thread that owns a SQLite connection."""

from __future__ import annotations

import logging
import threading
from typing import Optional


class ConnectionThreadGuard:
    """Keep track of which thread is allowed to mutate the SQLite connection."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._owner_thread_id: Optional[int] = None

    def attach_to_current_thread(self) -> None:
        """Remember the current thread as the connection owner."""
        try:
            self._owner_thread_id = threading.get_ident()
        except Exception:
            self._owner_thread_id = None

    def clear(self) -> None:
        """Forget the previously recorded owner thread."""
        self._owner_thread_id = None

    def is_owner(self) -> bool:
        """Return `True` when called from the owning thread."""
        try:
            return (
                self._owner_thread_id is not None
                and threading.get_ident() == self._owner_thread_id
            )
        except Exception:
            return False
