from silverestimate.domain.pagination import ItemCursor, Page
from silverestimate.infrastructure.paged_load_state import PagedLoadState


def test_paged_load_state_replaces_then_appends_pages() -> None:
    state = PagedLoadState[str, ItemCursor]()
    first_cursor = ItemCursor("B", "b")

    rows = state.apply(Page(("a", "b"), 3, first_cursor))

    assert rows == ["a", "b"]
    assert state.loaded == 2
    assert state.total == 3
    assert state.cursor is first_cursor
    assert state.has_more

    rows = state.apply(Page(("c",), 3), append=True)

    assert rows == ["a", "b", "c"]
    assert state.loaded == state.total == 3
    assert not state.has_more


def test_paged_load_state_reset_clears_rows_cursor_and_total() -> None:
    state = PagedLoadState[int, int]()
    state.apply(Page((1, 2), 10, 2))

    state.reset()

    assert state.rows == []
    assert state.loaded == state.total == 0
    assert state.cursor is None
    assert not state.has_more


def test_paged_load_state_does_not_share_default_row_lists() -> None:
    first = PagedLoadState[int, int]()
    second = PagedLoadState[int, int]()

    first.apply(Page((1,), 1))

    assert first.rows == [1]
    assert second.rows == []
