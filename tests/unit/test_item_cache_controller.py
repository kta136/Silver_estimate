import sqlite3
import threading

from silverestimate.infrastructure.item_cache import ItemCacheController


def test_item_cache_crud_and_atomic_replacement() -> None:
    cache = ItemCacheController()

    assert cache.cache == {}
    assert cache.get("") is None
    cache.store("", {"code": "ignored"})
    cache.store("none", None)
    cache.store("bad", object())
    cache.store("abc", {"code": "abc", "name": "Alpha"})
    cache.store("pairs", [("code", "pairs"), ("name", "Pairs")])
    assert cache.get("ABC")["name"] == "Alpha"
    assert cache.get("pairs")["name"] == "Pairs"

    cache.invalidate("")
    cache.invalidate("abc")
    assert cache.get("abc") is None

    cache.replace_all(
        [
            {"code": "one", "name": "One"},
            [("code", "two"), ("name", "Two")],
            object(),
            {"code": ""},
        ]
    )
    snapshot = cache.cache
    assert set(snapshot) == {"ONE", "TWO"}
    snapshot["MUTATED"] = {}
    assert "MUTATED" not in cache.cache


def test_item_cache_background_preload_success_and_guards(tmp_path) -> None:
    db_path = tmp_path / "items.sqlite"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE items "
        "(code TEXT, name TEXT, tunch TEXT, purity REAL, wage_type TEXT, wage_rate REAL)"
    )
    connection.executemany(
        "INSERT INTO items VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("a1", "Alpha", "91 + loss", 92.5, "P", 1.0),
            (None, "No code", None, 0, "P", 0),
        ],
    )
    connection.commit()
    connection.close()

    cache = ItemCacheController()
    cache.start_preload(None)
    cache.start_preload(str(db_path))
    assert cache._thread is not None
    cache._thread.join(2)
    assert cache.get("A1")["purity"] == 92.5
    assert cache.get("A1")["tunch"] == "91 + loss"
    assert "" in cache.cache

    completed_thread = cache._thread
    cache.start_preload(str(db_path))
    assert cache._thread is completed_thread

    release = threading.Event()
    waiting = threading.Thread(target=lambda: release.wait(2))
    cache._preloaded = False
    cache._thread = waiting
    waiting.start()
    cache.start_preload(str(db_path))
    assert cache._thread is waiting
    release.set()
    waiting.join()


def test_item_cache_preload_failure_and_thread_start_failure(
    tmp_path, monkeypatch
) -> None:
    cache = ItemCacheController()
    cache.start_preload(str(tmp_path / "missing" / "items.sqlite"))
    assert cache._thread is not None
    cache._thread.join(2)
    assert cache.cache == {}
    assert cache._preloaded is False

    class StartFailureThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            raise RuntimeError("cannot start")

    monkeypatch.setattr(threading, "Thread", StartFailureThread)
    cache.start_preload(str(tmp_path / "items.sqlite"))
    assert cache._thread is None
