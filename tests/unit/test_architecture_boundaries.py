from __future__ import annotations

import inspect

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
    ESTIMATE_FORMAT_SPECS,
    FunctionRendererStrategy,
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


def test_print_strategy_carries_shared_format_spec() -> None:
    strategy = FunctionRendererStrategy(
        ESTIMATE_FORMAT_SPECS["new"], lambda payload: f"rendered:{payload}"
    )
    assert strategy.spec.document_kind == "estimate"
    assert strategy.render("voucher") == "rendered:voucher"
