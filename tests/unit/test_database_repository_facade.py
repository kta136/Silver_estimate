from silverestimate.persistence.database_repository_facade import (
    DatabaseRepositoryFacadeMixin,
)


class _StubItemRepo:
    def __init__(self):
        self.calls = []

    def add_item(self, *args):
        self.calls.append(("add_item", args))
        return "added"


class _StubEstimateRepo:
    def __init__(self):
        self.calls = []

    def save_estimate_with_returns(self, *args):
        self.calls.append(("save_estimate_with_returns", args))
        return "saved"


class _StubSilverBarsRepo:
    def __init__(self):
        self.calls = []

    def create_list(self, note):
        self.calls.append(("create_list", (note,)))
        return 17

    def get_silver_bars(self, **kwargs):
        self.calls.append(("get_silver_bars", kwargs))
        return ["bars"]


class _StubItemCacheController:
    def __init__(self):
        self.calls = []

    def start_preload(self, temp_db_path):
        self.calls.append(temp_db_path)


class _FacadeHarness(DatabaseRepositoryFacadeMixin):
    def __init__(self):
        self.items_repo = _StubItemRepo()
        self.estimates_repo = _StubEstimateRepo()
        self.silver_bars_repo = _StubSilverBarsRepo()
        self._item_cache_controller = _StubItemCacheController()
        self.temp_db_path = "/tmp/db.sqlite"
        self.last_error = "existing"


def test_item_facade_delegates_and_preload_uses_temp_db_path():
    facade = _FacadeHarness()

    assert facade.add_item("ITM001", "Sample", 92.5, "WT", 10.0) == "added"
    facade.start_preload_item_cache()

    assert facade.items_repo.calls == [
        ("add_item", ("ITM001", "Sample", 92.5, "WT", 10.0))
    ]
    assert facade._item_cache_controller.calls == ["/tmp/db.sqlite"]


def test_estimate_facade_clears_last_error_before_delegating():
    facade = _FacadeHarness()

    result = facade.save_estimate_with_returns(
        "100",
        "2025-01-01",
        70000.0,
        [{"code": "REG001"}],
        [{"code": "RET001"}],
        {"total_net": 1.0},
    )

    assert result == "saved"
    assert facade.last_error is None
    assert facade.estimates_repo.calls == [
        (
            "save_estimate_with_returns",
            (
                "100",
                "2025-01-01",
                70000.0,
                [{"code": "REG001"}],
                [{"code": "RET001"}],
                {"total_net": 1.0},
            ),
        )
    ]


def test_silver_bar_facade_delegates_keyword_arguments():
    facade = _FacadeHarness()

    assert facade.create_silver_bar_list("Test List") == 17
    assert (
        facade.get_silver_bars(
            status="In Stock",
            weight_query="10",
            limit=5,
            offset=2,
        )
        == ["bars"]
    )
    assert facade.silver_bars_repo.calls == [
        ("create_list", ("Test List",)),
        (
            "get_silver_bars",
            {
                "status": "In Stock",
                "weight_query": "10",
                "estimate_voucher_no": None,
                "unassigned_only": False,
                "weight_tolerance": 0.001,
                "min_purity": None,
                "max_purity": None,
                "date_range": None,
                "limit": 5,
                "offset": 2,
            },
        ),
    ]
