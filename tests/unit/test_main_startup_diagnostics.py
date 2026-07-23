from __future__ import annotations

import main as main_module


def test_startup_event_falls_back_to_writable_candidate(monkeypatch, tmp_path):
    blocked = tmp_path / "blocked"
    fallback = tmp_path / "fallback"

    def fail_mkdir(*args, **kwargs):
        raise PermissionError("blocked")

    monkeypatch.setattr(main_module, "_STARTUP_LOG_PATH", None)
    monkeypatch.setattr(
        main_module,
        "_startup_log_candidates",
        lambda: (blocked, fallback),
    )
    original_mkdir = main_module.Path.mkdir

    def selective_mkdir(path, *args, **kwargs):
        if path == blocked:
            fail_mkdir()
        return original_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(main_module.Path, "mkdir", selective_mkdir)

    log_path = main_module._write_startup_event("unit-test")

    assert log_path == fallback / "SilverEstimate-startup.log"
    assert "unit-test" in log_path.read_text(encoding="utf-8")


def test_entrypoint_records_and_reports_early_exception(monkeypatch, tmp_path):
    events = []
    shown = []
    log_path = tmp_path / "SilverEstimate-startup.log"

    def write_event(event, exc=None):
        events.append((event, exc))
        return log_path

    monkeypatch.setattr(main_module, "_write_startup_event", write_event)
    monkeypatch.setattr(main_module, "_enable_native_fault_log", lambda: None)
    monkeypatch.setattr(
        main_module,
        "_show_early_error",
        lambda exc, path: shown.append((exc, path)),
    )
    monkeypatch.setattr(
        main_module,
        "main",
        lambda: (_ for _ in ()).throw(RuntimeError("early failure")),
    )

    exit_code = main_module._run_entrypoint()

    assert exit_code == 1
    assert events[0] == ("process-start", None)
    assert events[1][0] == "unhandled-startup-exception"
    assert isinstance(events[1][1], RuntimeError)
    assert len(shown) == 1
    assert isinstance(shown[0][0], RuntimeError)
    assert shown[0][1] == log_path
