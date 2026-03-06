from pathlib import Path

import pytest

from silverestimate.persistence.database_startup import DatabaseStartupCoordinator


class _StubTempStore:
    def __init__(self, path: Path):
        self._path = path
        self.create_calls = 0
        self.register_calls = 0

    def create(self):
        self.create_calls += 1
        self._path.touch()
        return self._path

    def register_for_recovery(self):
        self.register_calls += 1


def test_initialize_existing_database_connects_and_sets_up(tmp_path):
    temp_path = tmp_path / "session.sqlite"
    temp_store = _StubTempStore(temp_path)
    events = {
        "temp_db_path": None,
        "connect": 0,
        "setup": 0,
        "cleanup": 0,
        "reset": 0,
    }

    coordinator = DatabaseStartupCoordinator(
        temp_store=temp_store,
        set_temp_db_path=lambda value: events.__setitem__("temp_db_path", value),
        decrypt_db=lambda: "success",
        connect_temp_db=lambda: events.__setitem__("connect", events["connect"] + 1),
        setup_database=lambda: events.__setitem__("setup", events["setup"] + 1),
        cleanup_temp_db=lambda: events.__setitem__("cleanup", events["cleanup"] + 1),
        reset_connection_state=lambda: events.__setitem__("reset", events["reset"] + 1),
    )

    coordinator.initialize()

    assert events == {
        "temp_db_path": str(temp_path),
        "connect": 1,
        "setup": 1,
        "cleanup": 0,
        "reset": 0,
    }
    assert temp_store.create_calls == 1
    assert temp_store.register_calls == 1


def test_initialize_first_run_still_connects_and_sets_up(tmp_path):
    temp_path = tmp_path / "session.sqlite"
    temp_store = _StubTempStore(temp_path)
    events = {"connect": 0, "setup": 0}

    coordinator = DatabaseStartupCoordinator(
        temp_store=temp_store,
        set_temp_db_path=lambda _value: None,
        decrypt_db=lambda: "first_run",
        connect_temp_db=lambda: events.__setitem__("connect", events["connect"] + 1),
        setup_database=lambda: events.__setitem__("setup", events["setup"] + 1),
        cleanup_temp_db=lambda: None,
        reset_connection_state=lambda: None,
    )

    coordinator.initialize()

    assert events == {"connect": 1, "setup": 1}


def test_initialize_failure_cleans_up_and_resets_state(tmp_path):
    temp_path = tmp_path / "session.sqlite"
    temp_store = _StubTempStore(temp_path)
    events = {"cleanup": 0, "reset": 0}

    coordinator = DatabaseStartupCoordinator(
        temp_store=temp_store,
        set_temp_db_path=lambda _value: None,
        decrypt_db=lambda: "error",
        connect_temp_db=lambda: None,
        setup_database=lambda: None,
        cleanup_temp_db=lambda: events.__setitem__("cleanup", events["cleanup"] + 1),
        reset_connection_state=lambda: events.__setitem__("reset", events["reset"] + 1),
    )

    with pytest.raises(Exception, match="Database decryption failed"):
        coordinator.initialize()

    assert events == {"cleanup": 1, "reset": 1}


def test_initialize_setup_failure_cleans_up_and_resets_state(tmp_path):
    temp_path = tmp_path / "session.sqlite"
    temp_store = _StubTempStore(temp_path)
    events = {"cleanup": 0, "reset": 0}

    coordinator = DatabaseStartupCoordinator(
        temp_store=temp_store,
        set_temp_db_path=lambda _value: None,
        decrypt_db=lambda: "success",
        connect_temp_db=lambda: None,
        setup_database=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        cleanup_temp_db=lambda: events.__setitem__("cleanup", events["cleanup"] + 1),
        reset_connection_state=lambda: events.__setitem__("reset", events["reset"] + 1),
    )

    with pytest.raises(RuntimeError, match="boom"):
        coordinator.initialize()

    assert events == {"cleanup": 1, "reset": 1}
