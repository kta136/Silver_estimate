from __future__ import annotations

import inspect
from functools import cache
from pathlib import Path
from typing import get_args

import pytest
from PySide6.QtWidgets import QWidget

from silverestimate.controllers.startup_controller import StartupController
from silverestimate.infrastructure.paged_load_state import PagedLoadState
from silverestimate.infrastructure.settings import (
    SETTINGS_SCHEMA_VERSION,
    SettingsKey,
)
from silverestimate.persistence.database_protocols import (
    ItemCatalogDatabase,
    MainCommandsDatabase,
    RepositoryDatabase,
    StartupDatabase,
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
from silverestimate.services.item_catalog_transfer import (
    export_item_catalog,
    import_item_catalog,
)
from silverestimate.services.main_commands import MainCommands
from silverestimate.services.settings_service import SettingsService
from silverestimate.ui.estimate_entry import EstimateEntryWidget
from silverestimate.ui.estimate_entry_layout_controller import (
    EstimateEntryLayoutController,
)
from silverestimate.ui.estimate_entry_table_controller import (
    EstimateEntryTableController,
)
from silverestimate.ui.estimate_entry_totals_controller import (
    EstimateEntryTotalsController,
)
from silverestimate.ui.estimate_entry_workflow_controller import (
    EstimateEntryWorkflowController,
)
from silverestimate.ui.estimate_history import EstimateHistoryDialog
from silverestimate.ui.estimate_print_document import EstimatePrintDocument
from silverestimate.ui.item_master import ItemMasterWidget
from silverestimate.ui.print_format_spec import (
    CLASSIC_ESTIMATE_FORMAT_SPEC,
    ESTIMATE_FORMAT_SPECS,
    MODERN_ESTIMATE_FORMAT_SPEC,
)
from silverestimate.ui.print_payload_builder import PrintDocument
from silverestimate.ui.print_preview_controller import PrintPreviewController
from silverestimate.ui.print_preview_output import (
    PrintOutputOutcome,
)
from silverestimate.ui.print_preview_preferences import (
    PreviewZoomPreference,
)
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
from silverestimate.ui.silver_bar_history import SilverBarHistoryDialog
from silverestimate.ui.silver_bar_load_controller import SilverBarLoadController
from silverestimate.ui.silver_bar_management import SilverBarDialog
from silverestimate.ui.silver_bar_management_facade import SilverBarManagementFacade
from silverestimate.ui.silver_bar_print_document import (
    SilverBarInventoryPrintDocument,
    SilverBarListPrintDocument,
)


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


def test_estimate_entry_uses_explicit_controller_composition() -> None:
    assert issubclass(EstimateEntryWidget, QWidget)
    assert issubclass(SilverBarDialog, SilverBarManagementFacade)
    assert "setattr(" not in inspect.getsource(EstimateEntryWidget)
    assert "setattr(" not in inspect.getsource(SilverBarDialog)
    assert isinstance(EstimateEntryWidget.workflow_controller, property)
    assert isinstance(EstimateEntryWidget.layout_controller, property)
    assert isinstance(EstimateEntryWidget.table_controller, property)
    assert isinstance(EstimateEntryWidget.totals_controller, property)
    controller_properties = {
        EstimateEntryWidget.workflow_controller: EstimateEntryWorkflowController,
        EstimateEntryWidget.layout_controller: EstimateEntryLayoutController,
        EstimateEntryWidget.table_controller: EstimateEntryTableController,
        EstimateEntryWidget.totals_controller: EstimateEntryTotalsController,
    }
    for controller_property, controller_type in controller_properties.items():
        assert controller_property.fget.__annotations__["return"] in {
            controller_type.__name__,
            controller_type,
        }
        assert "HostProxy" not in inspect.getsource(controller_type)
        assert (
            inspect.signature(controller_type.__init__).parameters["host"].annotation
            == "EstimateEntryWidget"
        )
    assert "__getattr__" not in inspect.getsource(EstimateEntryWidget)


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


def test_database_consumers_use_narrow_structural_contracts() -> None:
    expected_parameters = (
        (ItemsRepository, "db_manager", RepositoryDatabase),
        (EstimatesRepository, "db_manager", RepositoryDatabase),
        (MainCommands, "db_manager", MainCommandsDatabase),
        (export_item_catalog, "db_manager", ItemCatalogDatabase),
        (import_item_catalog, "db_manager", ItemCatalogDatabase),
        (StartupController._start_background_preload, "db_manager", StartupDatabase),
    )
    for callable_object, parameter_name, expected_type in expected_parameters:
        annotation = (
            inspect.signature(callable_object).parameters[parameter_name].annotation
        )
        assert expected_type.__name__ in str(annotation)
        assert "Any" not in str(annotation)

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


def test_paged_screens_share_state_but_keep_feature_policy_local() -> None:
    paged_screen_types = (
        ItemMasterWidget,
        EstimateHistoryDialog,
        SilverBarHistoryDialog,
        SilverBarLoadController,
    )
    for screen_type in paged_screen_types:
        source = inspect.getsource(screen_type)
        assert "PagedLoadState" in source
        assert "LatestRequestRunner" in source
        assert ".shutdown()" in source

    item_master_module = inspect.getmodule(ItemMasterWidget)
    estimate_history_module = inspect.getmodule(EstimateHistoryDialog)
    silver_bar_load_module = inspect.getmodule(SilverBarLoadController)
    assert item_master_module is not None
    assert estimate_history_module is not None
    assert silver_bar_load_module is not None
    assert "fetch_item_catalog_page" in inspect.getsource(item_master_module)
    assert "fetch_estimate_history_page" in inspect.getsource(estimate_history_module)
    assert "SilverBarsSnapshotRepository" in inspect.getsource(silver_bar_load_module)
    assert "QMessageBox" not in inspect.getsource(PagedLoadState)

    estimate_entry_owner = inspect.getsource(EstimateEntryWidget)
    assert "_live_rate_runner" in estimate_entry_owner
    assert "live_rate_runner.shutdown()" in estimate_entry_owner


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


def test_classic_and_modern_are_the_only_estimate_formats() -> None:
    assert tuple(ESTIMATE_FORMAT_SPECS) == ("classic", "modern")
    assert ESTIMATE_FORMAT_SPECS["classic"] is CLASSIC_ESTIMATE_FORMAT_SPEC
    assert ESTIMATE_FORMAT_SPECS["modern"] is MODERN_ESTIMATE_FORMAT_SPEC
    assert CLASSIC_ESTIMATE_FORMAT_SPEC.key == "classic"
    assert MODERN_ESTIMATE_FORMAT_SPEC.key == "modern"


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
        SilverBarInventoryPrintDocument,
        SilverBarListPrintDocument,
    }
    assert not {
        f"{path.relative_to(root)}: {token}"
        for path in production_sources
        for token in forbidden
        if token in _source_text(path)
    }


def test_print_preview_uses_focused_collaborators_and_typed_outcomes() -> None:
    assert PrintOutputOutcome.__dataclass_params__.frozen
    assert PreviewZoomPreference.__dataclass_params__.frozen

    controller_source = inspect.getsource(PrintPreviewController)
    assert not {
        token
        for token in (
            "QAction",
            "QFileDialog",
            "QMessageBox",
            "QPageSetupDialog",
            "QPrintDialog",
        )
        if token in controller_source
    }


def test_silver_bar_facade_methods_delegate_without_dynamic_widget_composition() -> (
    None
):
    def return_one(_self, *_args, **_kwargs):
        return 1

    facade_controllers = {
        SilverBarManagementFacade: (
            "_ui_builder",
            "_load_controller",
            "_transfer_controller",
            "_list_lifecycle_controller",
            "_list_print_controller",
            "_table_controller",
            "_state_store",
            "_selection_state_controller",
        ),
    }

    for facade_type, controller_attributes in facade_controllers.items():
        facade_methods = {
            name: member
            for name, member in vars(facade_type).items()
            if callable(member)
        }
        controller_type = type(
            f"{facade_type.__name__}ControllerStub",
            (),
            dict({name: return_one for name in facade_methods}, shutdown=return_one),
        )
        facade = facade_type()
        controller = controller_type()
        for attribute in controller_attributes:
            setattr(facade, attribute, controller)

        for method_name, method in facade_methods.items():
            required_args = [
                1
                for parameter in list(inspect.signature(method).parameters.values())[1:]
                if parameter.default is inspect.Parameter.empty
                and parameter.kind
                in {
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                }
            ]
            required_keywords = {
                parameter.name: 1
                for parameter in inspect.signature(method).parameters.values()
                if parameter.default is inspect.Parameter.empty
                and parameter.kind is inspect.Parameter.KEYWORD_ONLY
            }
            getattr(facade, method_name)(*required_args, **required_keywords)

        assert getattr(facade, "table_adapter", 1) == 1


def test_retired_graph_bridge_and_silver_bar_backend_stay_removed() -> None:
    root = Path(__file__).resolve().parents[2]
    production_sources = sorted((root / "silverestimate").rglob("*.py"))
    forbidden = (
        "EstimateEntryFacade",
        "_SilverBarsRepositoryBackend",
        "SilverBarsRepository",
    )

    assert not (root / "silverestimate" / "ui" / "estimate_entry_facade.py").exists()
    assert not (
        root / "silverestimate" / "persistence" / "silver_bars_repository.py"
    ).exists()
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


def test_silver_bar_controllers_do_not_redirect_attribute_access() -> None:
    root = Path(__file__).resolve().parents[2]
    assert not (root / "silverestimate/ui/_host_proxy.py").exists()
    assert "__getattr__" not in inspect.getsource(SilverBarDialog)
    assert "_facade_call" not in inspect.getsource(SilverBarManagementFacade)
    for path in (root / "silverestimate/ui").glob("silver_bar*.py"):
        assert "HostProxy" not in _source_text(path)
