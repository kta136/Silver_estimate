from __future__ import annotations

import inspect
from pathlib import Path

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
from silverestimate.ui.estimate_entry import EstimateEntryWidget
from silverestimate.ui.estimate_entry_facade import EstimateEntryFacade
from silverestimate.ui.print_format_spec import (
    CLASSIC_ESTIMATE_FORMAT_SPEC,
    ESTIMATE_FORMAT_SPECS,
    MODERN_ESTIMATE_FORMAT_SPEC,
)
from silverestimate.ui.settings_live_rates_page import LiveRatesSettingsPage
from silverestimate.ui.silver_bar_management import SilverBarDialog
from silverestimate.ui.silver_bar_management_facade import SilverBarManagementFacade


def test_composed_widgets_use_explicit_facades() -> None:
    assert issubclass(EstimateEntryWidget, EstimateEntryFacade)
    assert issubclass(SilverBarDialog, SilverBarManagementFacade)
    assert "setattr(" not in inspect.getsource(EstimateEntryWidget)
    assert "setattr(" not in inspect.getsource(SilverBarDialog)
    assert callable(EstimateEntryFacade.save_estimate)
    assert callable(SilverBarManagementFacade.load_available_bars)


def test_silver_bar_persistence_roles_are_independent() -> None:
    assert SilverBarQueryRepository is not SilverBarCommandRepository
    assert SilverBarSynchronizationRepository is not SilverBarCommandRepository
    assert SilverBarSyncResult(added=3, failed=0).succeeded
    assert not SilverBarSyncResult(added=2, failed=1).succeeded


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


def test_live_rate_settings_are_an_independent_page() -> None:
    assert LiveRatesSettingsPage.__module__.endswith("settings_live_rates_page")
    assert callable(LiveRatesSettingsPage.load_state)
    assert callable(LiveRatesSettingsPage.save)


def test_classic_and_modern_are_the_only_estimate_formats() -> None:
    assert tuple(ESTIMATE_FORMAT_SPECS) == ("classic", "modern")
    assert ESTIMATE_FORMAT_SPECS["classic"] is CLASSIC_ESTIMATE_FORMAT_SPEC
    assert ESTIMATE_FORMAT_SPECS["modern"] is MODERN_ESTIMATE_FORMAT_SPEC
    assert CLASSIC_ESTIMATE_FORMAT_SPEC.key == "classic"
    assert MODERN_ESTIMATE_FORMAT_SPEC.key == "modern"


def test_explicit_facade_methods_delegate_without_dynamic_widget_composition() -> None:
    def return_one(_self, *_args, **_kwargs):
        return 1

    facade_controllers = {
        EstimateEntryFacade: (
            "_workflow_controller",
            "_layout_controller",
            "_table_controller",
            "_totals_controller",
        ),
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
            if callable(member) and name != "_facade_call"
        }
        controller_type = type(
            f"{facade_type.__name__}ControllerStub",
            (),
            {name: return_one for name in facade_methods},
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
            getattr(facade, method_name)(*required_args)

        assert getattr(facade, "table_adapter", 1) == 1


def test_production_database_access_is_confined_to_sqlcipher_broker() -> None:
    root = Path(__file__).resolve().parents[2]
    imports = [
        path.relative_to(root).as_posix()
        for path in (root / "silverestimate").rglob("*.py")
        if "import sqlite3" in path.read_text(encoding="utf-8")
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
        if reference in path.read_text(encoding="utf-8").lower()
    }

    assert not forbidden_ui_references
    password_service = (
        root / "silverestimate" / "security" / "password_service.py"
    ).read_text(encoding="utf-8")
    assert "PasswordHasher" in password_service
    assert "check_needs_rehash" not in password_service
