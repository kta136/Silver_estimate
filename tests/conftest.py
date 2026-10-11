import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QLocale

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _coerce_bool(value, default):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if value is None:
        if isinstance(default, bool):
            return default
        return False
    return bool(value)


class _SettingsStub:
    """In-memory replacement for QSettings during tests."""

    class Status:
        NoError = 0

    _data = {}

    def __init__(self, org="SilverEstimate", app="SilverEstimateApp"):
        self._key = (org, app)
        self._store = _SettingsStub._data.setdefault(self._key, {})

    def value(self, key, default=None, type=None, **kwargs):  # noqa: A002 - signature mirrors QSettings
        if "defaultValue" in kwargs and default is None:
            default = kwargs["defaultValue"]
        if "type" in kwargs and type is None:
            type = kwargs["type"]
        val = self._store.get(key, default)
        if type is bool:
            return _coerce_bool(val, default)
        return val

    def setValue(self, key, value):
        self._store[key] = value

    def remove(self, key):
        self._store.pop(key, None)

    def contains(self, key):
        return key in self._store

    def allKeys(self):
        return list(self._store)

    def status(self):
        return 0

    def sync(self):  # QSettings test double API
        return True

    @classmethod
    def clear(cls):
        cls._data.clear()


class _CredentialStoreStub:
    """In-memory stand-in for secure credential storage."""

    _store = {}

    @classmethod
    def reset(cls):
        cls._store = {}

    @classmethod
    def get_password_hash(cls, kind):
        return cls._store.get(kind)

    @classmethod
    def set_password_hash(cls, kind, value, *, logger=None):
        cls._store[kind] = value

    @classmethod
    def delete_password_hash(cls, kind, *, logger=None):
        cls._store.pop(kind, None)


@pytest.fixture(scope="session")
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    _load_offscreen_preview_fonts(app)
    return app


def _load_offscreen_preview_fonts(app):
    """Windows' headless QPA backend does not discover the native font directory."""
    if sys.platform != "win32" or app.platformName() not in {"offscreen", "minimal"}:
        return
    if app.property("silverestimatePreviewFontsLoaded"):
        return
    from PySide6.QtGui import QFontDatabase

    font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for filename in ("segoeui.ttf", "segoeuib.ttf", "seguisym.ttf"):
        path = font_dir / filename
        if path.is_file():
            QFontDatabase.addApplicationFont(str(path))
    app.setProperty("silverestimatePreviewFontsLoaded", True)


@pytest.fixture(autouse=True)
def isolate_credential_vault(monkeypatch):
    """Keep every test away from this PC's Windows Credential Manager entries."""
    from silverestimate.security import credential_store
    from tests.vault_support import TwinVault

    monkeypatch.setattr(credential_store, "vault", TwinVault())


@pytest.fixture(autouse=True)
def keep_test_console_attached(monkeypatch):
    """Stop the app hiding and detaching the console of the test run itself.

    Closing the main window does both. Once the run has no console, every
    process a later test starts opens a terminal window of its own.
    """
    monkeypatch.setattr(
        "silverestimate.infrastructure.windows_integration.hide_console_window",
        lambda *args, **kwargs: None,
    )


@pytest.fixture(autouse=True)
def load_preview_fonts_for_qt_tests(request):
    if "qtbot" in request.fixturenames or "qapp" in request.fixturenames:
        _load_offscreen_preview_fonts(request.getfixturevalue("qapp"))


@pytest.fixture(autouse=True)
def flush_qt_deferred_deletes():
    """Finish pytest-qt/widget deletion before the next test changes app state."""
    yield
    if QCoreApplication.instance() is not None:
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _confirmation_summary(dialog) -> str:
    return f"{dialog.windowTitle()}: {dialog.text()}"


@pytest.fixture(autouse=True)
def confirmations(monkeypatch, request):
    """Answer confirmation dialogs without showing a window.

    A test names the button to press with ``confirmations.answer("Delete Item")``
    (or ``answer("Cancel")``), or ``confirmations.always("Discard")`` to change
    the answer part-way through; every dialog shown is recorded in
    ``confirmations.shown``. A dialog nobody answered fails the test instead of
    blocking the run on a modal window.

    Text prompts are answered with ``confirmations.type_text("DELETE")``;
    ``type_text(None)`` backs out of the prompt. Each prompt is recorded in
    ``confirmations.prompts``.
    """

    class _Confirmations:
        def __init__(self):
            self.shown = []
            self.prompts = []
            self._answers = []
            self._typed = []

        def answer(self, *labels):
            self._answers.extend(labels)

        def always(self, label):
            """From now on press ``label`` in every dialog."""
            self._answers[:] = [label]

        def type_text(self, *texts):
            self._typed.extend(texts)

        def always_type(self, text):
            """From now on type ``text`` into every prompt (None backs out)."""
            self._typed[:] = [text]

        def _run_prompt(self, dialog):
            summary = f"{dialog.windowTitle()}: {dialog.input.accessibleName()}"
            self.prompts.append(summary)
            if not self._typed:
                raise AssertionError(f"Unanswered text prompt: {summary}")
            text = self._typed.pop(0) if len(self._typed) > 1 else self._typed[0]
            if text is None:
                return False
            dialog.input.setText(text)
            return dialog.action_button.isEnabled()

        def _run(self, dialog):
            summary = _confirmation_summary(dialog)
            self.shown.append(summary)
            if not self._answers:
                raise AssertionError(f"Unanswered confirmation dialog: {summary}")
            label = self._answers.pop(0) if len(self._answers) > 1 else self._answers[0]
            buttons = {button.text(): button for button in dialog.buttons()}
            assert label in buttons, (summary, sorted(buttons))
            buttons[label].click()

    recorder = _Confirmations()
    # Smoke tests drive the real windows and close each dialog themselves.
    if "/tests/smoke/" not in request.node.path.as_posix():
        monkeypatch.setattr(
            "silverestimate.ui.message_dialogs._run_dialog", recorder._run
        )
        monkeypatch.setattr(
            "silverestimate.ui.message_dialogs._run_prompt", recorder._run_prompt
        )
    return recorder


@pytest.fixture()
def qt_application_state(qt_app):
    """Restore application-wide appearance after tests that change the theme."""
    previous_style = qt_app.style().objectName()
    previous_font = qt_app.font()
    previous_class_fonts = {
        name: qt_app.font(name) for name in ("QMenu", "QMenuBar", "QHeaderView")
    }
    previous_palette = qt_app.palette()
    previous_stylesheet = qt_app.styleSheet()
    try:
        yield qt_app
    finally:
        if qt_app.style().objectName() != previous_style:
            qt_app.setStyle(previous_style)
        qt_app.setFont(previous_font)
        qt_app.setPalette(previous_palette)
        qt_app.setStyleSheet(previous_stylesheet)
        for name, font in previous_class_fonts.items():
            qt_app.setFont(font, name)


@pytest.fixture()
def settings_stub(monkeypatch):
    _SettingsStub.clear()
    _CredentialStoreStub.reset()
    monkeypatch.setattr(
        "silverestimate.persistence.database_manager.QSettings",
        _SettingsStub,
        raising=False,
    )
    monkeypatch.setattr(
        "silverestimate.services.auth_service.QSettings", _SettingsStub, raising=False
    )
    monkeypatch.setattr(
        "silverestimate.ui.estimate_entry.QSettings", _SettingsStub, raising=False
    )
    monkeypatch.setattr(
        "silverestimate.infrastructure.logger.QSettings", _SettingsStub, raising=False
    )
    monkeypatch.setattr(
        "silverestimate.infrastructure.settings.QSettings", _SettingsStub, raising=False
    )
    monkeypatch.setattr(
        "silverestimate.security.credential_store.get_password_hash",
        _CredentialStoreStub.get_password_hash,
        raising=False,
    )
    monkeypatch.setattr(
        "silverestimate.security.credential_store.set_password_hash",
        _CredentialStoreStub.set_password_hash,
        raising=False,
    )
    monkeypatch.setattr(
        "silverestimate.security.credential_store.delete_password_hash",
        _CredentialStoreStub.delete_password_hash,
        raising=False,
    )
    monkeypatch.setattr(
        "silverestimate.security.credential_store.get_backend_status",
        lambda: SimpleNamespace(
            available=True, backend_name="tests.stub.keyring", reason=""
        ),
        raising=False,
    )
    yield _SettingsStub
    _SettingsStub.clear()
    _CredentialStoreStub.reset()


def pytest_collection_modifyitems(items):
    run_smoke = bool(items and items[0].config.getoption("--run-smoke"))
    skip_smoke = pytest.mark.skip(reason="use --run-smoke to run smoke tests")
    for item in items:
        path = item.path.as_posix()
        if "/tests/smoke/" in path:
            item.add_marker(pytest.mark.smoke)
        if item.get_closest_marker("smoke") and not run_smoke:
            item.add_marker(skip_smoke)


@pytest.fixture(autouse=True)
def estimate_table_locale(monkeypatch):
    monkeypatch.setattr(
        "silverestimate.ui.estimate_table_formatting.get_estimate_table_locale",
        lambda: QLocale(QLocale.Language.English, QLocale.Country.India),
    )


def pytest_addoption(parser):
    parser.addoption(
        "--run-smoke",
        action="store_true",
        default=False,
        help="Run opt-in full-startup smoke tests.",
    )
    parser.addoption(
        "--smoke-screenshots",
        action="store_true",
        default=False,
        help="Capture UI screenshots during smoke tests.",
    )
    parser.addoption(
        "--smoke-artifact-dir",
        action="store",
        default="artifacts/smoke-ui",
        help="Directory where smoke screenshots are written.",
    )
