from __future__ import annotations

import inspect
from functools import cache
from pathlib import Path
from typing import get_args

import pytest

from silverestimate.infrastructure.settings import (
    SETTINGS_SCHEMA_VERSION,
    SettingsKey,
)
from silverestimate.persistence.estimates_repository import EstimatesRepository
from silverestimate.persistence.items_repository import ItemsRepository
from silverestimate.persistence.repository_results import (
    RepositoryFailureKind,
    RepositoryOperationError,
    RepositoryResult,
)
from silverestimate.persistence.silver_bar_command_repository import (
    SilverBarCommandRepository,
)
from silverestimate.persistence.silver_bar_query_repository import (
    SilverBarQueryRepository,
)
from silverestimate.persistence.silver_bar_synchronization_repository import (
    SilverBarSynchronizationRepository,
    SilverBarSyncResult,
)
from silverestimate.services.settings_service import SettingsService
from silverestimate.ui.estimate_print_document import EstimatePrintDocument
from silverestimate.ui.print_payload_builder import PrintDocument
from silverestimate.ui.settings_appearance_page import (
    AppearanceSettingsPage,
)
from silverestimate.ui.settings_data_page import (
    DataManagementPage,
)
from silverestimate.ui.settings_logging_page import (
    LoggingSettingsPage,
)
from silverestimate.ui.settings_print_page import PrintSettingsPage
from silverestimate.ui.settings_security_page import (
    SecuritySettingsPage,
)
from silverestimate.ui.silver_bar_print_document import SilverBarListPrintDocument


@cache
def _source_text(path: Path) -> str:
    """Read each immutable production source once across boundary checks."""
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "page,forbidden",
    [
        (AppearanceSettingsPage, ("main_window",)),
        (LoggingSettingsPage, ("main_window",)),
        (DataManagementPage, ("main_window",)),
        (SecuritySettingsPage, ("main_window", "credential_store")),
        (PrintSettingsPage, ("SettingsDialog",)),
    ],
    ids=["appearance", "logging", "data", "security", "print"],
)
def test_settings_pages_keep_dependencies_narrow(page, forbidden):
    source = inspect.getsource(page)
    assert not {token for token in forbidden if token in source}


def test_silver_bar_persistence_roles_are_independent() -> None:
    assert SilverBarQueryRepository is not SilverBarCommandRepository
    assert SilverBarSynchronizationRepository is not SilverBarCommandRepository
    assert SilverBarSyncResult(added=3, failed=0).succeeded
    assert not SilverBarSyncResult(added=2, failed=1).succeeded
    for repository_type in (
        SilverBarQueryRepository,
        SilverBarCommandRepository,
        SilverBarSynchronizationRepository,
    ):
        assert "db_manager" in inspect.signature(repository_type).parameters
        assert "self._backend" not in inspect.getsource(repository_type)


def test_repository_failures_are_typed_and_distinguishable() -> None:
    result = RepositoryResult[str].failed(
        RepositoryFailureKind.NOT_FOUND, "List was not found."
    )
    assert not result.succeeded
    assert result.failure is not None
    assert result.failure.kind is RepositoryFailureKind.NOT_FOUND
    try:
        result.unwrap()
    except RepositoryOperationError as exc:
        assert exc.failure.kind is RepositoryFailureKind.NOT_FOUND
    else:  # pragma: no cover - assertion guard
        raise AssertionError("A failed result must not unwrap.")


def test_database_parameters_are_typed_and_repositories_own_their_sql() -> None:
    root = Path(__file__).resolve().parents[2]
    production_sources = sorted((root / "silverestimate").rglob("*.py"))
    assert not {
        path.relative_to(root).as_posix()
        for path in production_sources
        if "db_manager: Any" in _source_text(path)
    }
    repository_sources = (
        inspect.getsource(ItemsRepository),
        inspect.getsource(EstimatesRepository),
    )
    assert not any(
        private_cursor in source
        for source in repository_sources
        for private_cursor in (
            "_c_get_item_by_code",
            "_c_insert_estimate_item",
        )
    )


def test_settings_boundary_is_typed_versioned_and_centralized() -> None:
    root = Path(__file__).resolve().parents[2]
    settings_source = root / "silverestimate" / "infrastructure" / "settings.py"
    production_sources = sorted((root / "silverestimate").rglob("*.py"))
    raw_key_references = {
        f"{path.relative_to(root)}: {key.value}"
        for path in production_sources
        if path != settings_source
        for key in SettingsKey
        if key.value in _source_text(path)
    }

    assert SETTINGS_SCHEMA_VERSION >= 1
    assert not raw_key_references
    assert not {"get", "set", "raw"} & vars(SettingsService).keys()
    assert "QSettings" not in inspect.getsource(SettingsService)


def test_print_pipeline_uses_typed_direct_documents_and_custom_preview() -> None:
    root = Path(__file__).resolve().parents[2]
    production_sources = (
        root / "main.py",
        *sorted((root / "silverestimate").rglob("*.py")),
    )
    forbidden = (
        "HtmlPrintDocument",
        "QPrintPreviewDialog",
        "QTextDocument",
        "setHtml(",
        "_print_html",
        "<!DOCTYPE",
    )

    assert set(get_args(PrintDocument)) == {
        EstimatePrintDocument,
        SilverBarListPrintDocument,
    }
    assert not {
        f"{path.relative_to(root)}: {token}"
        for path in production_sources
        for token in forbidden
        if token in _source_text(path)
    }


def test_production_database_access_is_confined_to_sqlcipher_broker() -> None:
    root = Path(__file__).resolve().parents[2]
    imports = [
        path.relative_to(root).as_posix()
        for path in (root / "silverestimate").rglob("*.py")
        if "import sqlite3" in _source_text(path)
    ]
    assert not imports
    assert [
        path.relative_to(root).as_posix()
        for path in (root / "silverestimate").rglob("*.py")
        if "import apsw\n" in _source_text(path)
    ] == ["silverestimate/persistence/apsw_dbapi.py"]

    removed = (
        "database_lifecycle.py",
        "database_startup.py",
        "encrypted_database_store.py",
        "flush_scheduler.py",
        "migrations.py",
        "sqlite_database_runtime.py",
        "temp_database_store.py",
    )
    persistence = root / "silverestimate" / "persistence"
    assert not [name for name in removed if (persistence / name).exists()]
    assert not (root / "silverestimate" / "security" / "encrypted_envelope.py").exists()


def test_password_hashing_is_confined_to_the_security_service() -> None:
    root = Path(__file__).resolve().parents[2]
    ui_root = root / "silverestimate" / "ui"
    forbidden_ui_references = {
        path.relative_to(root).as_posix(): reference
        for path in ui_root.rglob("*.py")
        for reference in ("import argon2", "from argon2", "passlib")
        if reference in _source_text(path).lower()
    }

    assert not forbidden_ui_references
    password_service = _source_text(
        root / "silverestimate" / "security" / "password_service.py"
    )
    assert "PasswordHasher" in password_service
    assert "check_needs_rehash" not in password_service
