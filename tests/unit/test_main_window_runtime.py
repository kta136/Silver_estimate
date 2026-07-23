from silverestimate.infrastructure import main_window_runtime


def test_preload_post_auth_runtime_imports_deferred_dependencies(monkeypatch):
    imported = []
    monkeypatch.setattr(
        main_window_runtime,
        "import_module",
        lambda module_name: imported.append(module_name),
    )

    main_window_runtime.preload_post_auth_runtime()

    assert imported == list(main_window_runtime.POST_AUTH_RUNTIME_MODULES)


def test_create_main_window_defers_heavy_runtime(monkeypatch):
    captured = {}

    class _MainWindowStub:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("silverestimate.ui.main_window.MainWindow", _MainWindowStub)

    result = main_window_runtime.create_main_window(db_manager="db", logger="logger")

    assert isinstance(result, _MainWindowStub)
    assert captured["defer_runtime"] is True
    assert captured["runtime_builder"] is main_window_runtime.build_main_window_runtime
