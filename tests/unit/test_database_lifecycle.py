import logging

from silverestimate.persistence.database_lifecycle import (
    DatabaseLifecycleCoordinator,
)


class _StubEncryptedStore:
    def __init__(self):
        self.key = None
        self.encrypt_result = True
        self.decrypt_result = "success"
        self.encrypt_calls = []
        self.decrypt_calls = []

    def set_key(self, key):
        self.key = key

    def encrypt_from_path(self, path):
        self.encrypt_calls.append(path)
        return self.encrypt_result

    def decrypt_to_path(self, path):
        self.decrypt_calls.append(path)
        return self.decrypt_result


class _ManualTimer:
    def __init__(self, delay, callback):
        self.delay = delay
        self.callback = callback
        self.daemon = False
        self.cancelled = False

    def start(self):
        return None

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


def test_encrypt_current_state_uses_commit_checkpoint_and_store(tmp_path):
    temp_db_path = tmp_path / "plain.sqlite"
    temp_db_path.write_bytes(b"payload")
    store = _StubEncryptedStore()
    counts = {"commit": 0, "checkpoint": 0}
    state = {"key": b"1" * 32}

    coordinator = DatabaseLifecycleCoordinator(
        encrypted_store=store,
        connection_getter=lambda: object(),
        temp_db_path_getter=lambda: str(temp_db_path),
        key_getter=lambda: state["key"],
        key_setter=lambda value: state.__setitem__("key", value),
        commit=lambda: counts.__setitem__("commit", counts["commit"] + 1) or True,
        checkpoint=lambda: (
            counts.__setitem__("checkpoint", counts["checkpoint"] + 1) or True
        ),
        logger=logging.getLogger("test.database_lifecycle"),
    )

    assert coordinator.encrypt_current_state() is True
    assert counts == {"commit": 1, "checkpoint": 1}
    assert store.key == b"1" * 32
    assert store.encrypt_calls == [str(temp_db_path)]


def test_decrypt_current_temp_runs_error_callback(tmp_path):
    temp_db_path = tmp_path / "plain.sqlite"
    store = _StubEncryptedStore()
    store.decrypt_result = "error"
    state = {"key": b"1" * 32}
    cleanup_called = {"value": False}

    coordinator = DatabaseLifecycleCoordinator(
        encrypted_store=store,
        connection_getter=lambda: object(),
        temp_db_path_getter=lambda: str(temp_db_path),
        key_getter=lambda: state["key"],
        key_setter=lambda value: state.__setitem__("key", value),
        commit=lambda: True,
        checkpoint=lambda: True,
        logger=logging.getLogger("test.database_lifecycle"),
    )

    assert (
        coordinator.decrypt_current_temp(
            on_error=lambda: cleanup_called.__setitem__("value", True)
        )
        == "error"
    )
    assert cleanup_called["value"] is True
    assert store.decrypt_calls == [str(temp_db_path)]


def test_reencrypt_with_new_password_restores_old_key_on_failure(tmp_path):
    temp_db_path = tmp_path / "plain.sqlite"
    temp_db_path.write_bytes(b"payload")
    store = _StubEncryptedStore()
    store.encrypt_result = False
    state = {"key": b"old-key"}

    coordinator = DatabaseLifecycleCoordinator(
        encrypted_store=store,
        connection_getter=lambda: object(),
        temp_db_path_getter=lambda: str(temp_db_path),
        key_getter=lambda: state["key"],
        key_setter=lambda value: state.__setitem__("key", value),
        commit=lambda: True,
        checkpoint=lambda: True,
        logger=logging.getLogger("test.database_lifecycle"),
    )

    assert (
        coordinator.reencrypt_with_new_password(
            "new-password",
            salt=b"salt",
            derive_key=lambda password, salt: b"new-key",
        )
        is False
    )
    assert state["key"] == b"old-key"


def test_close_deletes_temp_db_when_encryption_fails_by_default(tmp_path):
    temp_db_path = tmp_path / "plain.sqlite"
    temp_db_path.write_bytes(b"payload")
    store = _StubEncryptedStore()
    store.encrypt_result = False
    state = {"key": b"1" * 32}
    close_calls = {"count": 0}
    cleanup_calls = []

    coordinator = DatabaseLifecycleCoordinator(
        encrypted_store=store,
        connection_getter=lambda: object(),
        temp_db_path_getter=lambda: str(temp_db_path),
        key_getter=lambda: state["key"],
        key_setter=lambda value: state.__setitem__("key", value),
        commit=lambda: True,
        checkpoint=lambda: True,
        logger=logging.getLogger("test.database_lifecycle"),
    )

    coordinator.close(
        close_connection=lambda: close_calls.__setitem__(
            "count", close_calls["count"] + 1
        ),
        cleanup_temp_db=lambda preserve: cleanup_calls.append(preserve),
    )

    assert close_calls["count"] == 1
    assert cleanup_calls == [False]


def test_close_preserves_temp_db_when_encryption_fails_and_recovery_enabled(tmp_path):
    temp_db_path = tmp_path / "plain.sqlite"
    temp_db_path.write_bytes(b"payload")
    store = _StubEncryptedStore()
    store.encrypt_result = False
    state = {"key": b"1" * 32}
    close_calls = {"count": 0}
    cleanup_calls = []

    coordinator = DatabaseLifecycleCoordinator(
        encrypted_store=store,
        connection_getter=lambda: object(),
        temp_db_path_getter=lambda: str(temp_db_path),
        key_getter=lambda: state["key"],
        key_setter=lambda value: state.__setitem__("key", value),
        commit=lambda: True,
        checkpoint=lambda: True,
        logger=logging.getLogger("test.database_lifecycle"),
    )

    coordinator.close(
        close_connection=lambda: close_calls.__setitem__(
            "count", close_calls["count"] + 1
        ),
        cleanup_temp_db=lambda preserve: cleanup_calls.append(preserve),
        preserve_plaintext_on_failure=True,
    )

    assert close_calls["count"] == 1
    assert cleanup_calls == [True]


def test_request_flush_runs_scheduled_background_encrypt(tmp_path):
    temp_db_path = tmp_path / "plain.sqlite"
    temp_db_path.write_bytes(b"payload")
    store = _StubEncryptedStore()
    state = {"key": b"1" * 32}
    timers = []
    counts = {"commit": 0, "checkpoint": 0}

    def timer_factory(delay, callback):
        timer = _ManualTimer(delay, callback)
        timers.append(timer)
        return timer

    coordinator = DatabaseLifecycleCoordinator(
        encrypted_store=store,
        connection_getter=lambda: object(),
        temp_db_path_getter=lambda: str(temp_db_path),
        key_getter=lambda: state["key"],
        key_setter=lambda value: state.__setitem__("key", value),
        commit=lambda: counts.__setitem__("commit", counts["commit"] + 1) or True,
        checkpoint=lambda: (
            counts.__setitem__("checkpoint", counts["checkpoint"] + 1) or True
        ),
        logger=logging.getLogger("test.database_lifecycle"),
        timer_factory=timer_factory,
        thread_factory=lambda **kwargs: _ImmediateThread(**kwargs),
    )

    coordinator.request_flush(delay_seconds=0.01)
    timers[0].fire()

    assert counts == {"commit": 2, "checkpoint": 2}
    assert store.encrypt_calls == [str(temp_db_path)]
