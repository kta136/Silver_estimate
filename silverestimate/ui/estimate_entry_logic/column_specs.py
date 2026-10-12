"""Column registry for the estimate-entry table."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from silverestimate.domain.numeric_policy import (
    MONEY_PLACES,
    PURITY_PLACES,
    WEIGHT_PLACES,
)

from .constants import (
    COL_CODE,
    COL_FINE_WT,
    COL_GROSS,
    COL_ITEM_NAME,
    COL_NET_WT,
    COL_PIECES,
    COL_POLY,
    COL_PURITY,
    COL_TYPE,
    COL_WAGE_AMT,
    COL_WAGE_RATE,
)

EDITOR_CODE: Final = "code"
EDITOR_NUMERIC: Final = "numeric"
EDITOR_TEXT: Final = "text"
EDITOR_READ_ONLY: Final = "read_only"


@dataclass(frozen=True)
class EstimateColumnSpec:
    index: int
    key: str
    header: str
    precision: int | None = None
    editable: bool = True
    editor_type: str = EDITOR_TEXT
    default_width: int = 80
    min_width: int = 60
    max_width: int = 700
    stretch: bool = False
    shrinks: bool = False
    navigation_order: int | None = None
    auto_edit: bool = False
    blank_zero_editor: bool = False
    recalculates_row: bool = False
    auto_advance_after_edit: bool = False
    tooltip: str = ""


ESTIMATE_TABLE_COLUMN_SPECS: Final[tuple[EstimateColumnSpec, ...]] = (
    EstimateColumnSpec(
        COL_CODE,
        "code",
        "Code",
        editor_type=EDITOR_CODE,
        default_width=76,
        min_width=66,
        max_width=220,
        navigation_order=0,
        auto_edit=True,
    ),
    EstimateColumnSpec(
        COL_ITEM_NAME,
        "item_name",
        "Item Name",
        editor_type=EDITOR_TEXT,
        default_width=200,
        min_width=100,
        max_width=1200,
        stretch=True,
    ),
    EstimateColumnSpec(
        COL_GROSS,
        "gross",
        "Gross",
        precision=WEIGHT_PLACES,
        editor_type=EDITOR_NUMERIC,
        default_width=78,
        min_width=72,
        max_width=220,
        navigation_order=1,
        auto_edit=True,
        blank_zero_editor=True,
        recalculates_row=True,
        auto_advance_after_edit=True,
    ),
    EstimateColumnSpec(
        COL_POLY,
        "poly",
        "Poly",
        precision=WEIGHT_PLACES,
        editor_type=EDITOR_NUMERIC,
        default_width=74,
        min_width=68,
        max_width=220,
        navigation_order=2,
        auto_edit=True,
        blank_zero_editor=True,
        recalculates_row=True,
        auto_advance_after_edit=True,
    ),
    EstimateColumnSpec(
        COL_NET_WT,
        "net_weight",
        "Net",
        precision=WEIGHT_PLACES,
        editable=False,
        editor_type=EDITOR_NUMERIC,
        default_width=84,
        min_width=80,
        max_width=240,
    ),
    EstimateColumnSpec(
        COL_PURITY,
        "purity",
        "%",
        precision=PURITY_PLACES,
        editor_type=EDITOR_NUMERIC,
        tooltip="Purity (%)",
        default_width=72,
        min_width=64,
        max_width=160,
        navigation_order=3,
        auto_edit=True,
        recalculates_row=True,
        auto_advance_after_edit=True,
    ),
    EstimateColumnSpec(
        COL_WAGE_RATE,
        "wage_rate",
        "Lbr",
        precision=MONEY_PLACES,
        editor_type=EDITOR_NUMERIC,
        tooltip="Labour rate (₹ per gram, or per piece)",
        default_width=64,
        min_width=64,
        max_width=92,
        navigation_order=4,
        auto_edit=True,
        recalculates_row=True,
        auto_advance_after_edit=True,
    ),
    EstimateColumnSpec(
        COL_PIECES,
        "pieces",
        "Pc",
        precision=0,
        editor_type=EDITOR_NUMERIC,
        tooltip="Pieces",
        default_width=56,
        min_width=52,
        max_width=64,
        navigation_order=5,
        auto_edit=True,
        recalculates_row=True,
    ),
    EstimateColumnSpec(
        COL_WAGE_AMT,
        "wage_amount",
        "Lbr",
        precision=MONEY_PLACES,
        tooltip="Labour amount (₹)",
        editable=False,
        editor_type=EDITOR_NUMERIC,
        default_width=84,
        min_width=80,
        max_width=120,
    ),
    EstimateColumnSpec(
        COL_FINE_WT,
        "fine_weight",
        "Fine",
        precision=WEIGHT_PLACES,
        editable=False,
        editor_type=EDITOR_NUMERIC,
        default_width=90,
        min_width=82,
        max_width=240,
    ),
    EstimateColumnSpec(
        COL_TYPE,
        "type",
        "Type",
        editable=False,
        editor_type=EDITOR_READ_ONLY,
        # Wide enough for "Silver Bar", the longest type, at the default size.
        # In a narrow table it gives way after the item name, down to the
        # minimum, where "Silver Bar" is cut short.
        default_width=92,
        min_width=64,
        max_width=180,
        shrinks=True,
    ),
)

_SPECS_BY_INDEX: Final = {spec.index: spec for spec in ESTIMATE_TABLE_COLUMN_SPECS}

NUMERIC_COLUMNS: Final = frozenset(
    spec.index for spec in ESTIMATE_TABLE_COLUMN_SPECS if spec.precision is not None
)
EDITABLE_COLUMNS: Final = frozenset(
    spec.index for spec in ESTIMATE_TABLE_COLUMN_SPECS if spec.editable
)
AUTO_EDIT_COLUMNS: Final = frozenset(
    spec.index for spec in ESTIMATE_TABLE_COLUMN_SPECS if spec.auto_edit
)
ROW_RECALCULATION_COLUMNS: Final = frozenset(
    spec.index for spec in ESTIMATE_TABLE_COLUMN_SPECS if spec.recalculates_row
)
STRETCH_COLUMNS: Final = frozenset(
    spec.index for spec in ESTIMATE_TABLE_COLUMN_SPECS if spec.stretch
)
SHRINKABLE_COLUMNS: Final = frozenset(
    spec.index for spec in ESTIMATE_TABLE_COLUMN_SPECS if spec.shrinks
)
NAVIGATION_COLUMNS: Final = tuple(
    spec.index
    for spec in sorted(
        ESTIMATE_TABLE_COLUMN_SPECS,
        key=lambda item: (
            item.navigation_order is None,
            item.navigation_order if item.navigation_order is not None else 999,
        ),
    )
    if spec.navigation_order is not None
)


def get_column_spec(column: int) -> EstimateColumnSpec | None:
    try:
        return _SPECS_BY_INDEX[int(column)]
    except KeyError, TypeError, ValueError:
        return None


def column_count() -> int:
    return len(ESTIMATE_TABLE_COLUMN_SPECS)


def header_for_column(column: int) -> str | None:
    spec = get_column_spec(column)
    return spec.header if spec is not None else None


def tooltip_for_column(column: int) -> str | None:
    spec = get_column_spec(column)
    return spec.tooltip or None if spec is not None else None


def precision_for_column(column: int) -> int | None:
    spec = get_column_spec(column)
    return spec.precision if spec is not None else None


def is_editable_column(column: int) -> bool:
    return column in EDITABLE_COLUMNS


def is_auto_edit_column(column: int) -> bool:
    return column in AUTO_EDIT_COLUMNS


def is_row_recalculation_column(column: int) -> bool:
    return column in ROW_RECALCULATION_COLUMNS


def should_auto_advance_after_edit(column: int) -> bool:
    spec = get_column_spec(column)
    return bool(spec and spec.auto_advance_after_edit)


def column_uses_blank_zero_editor(column: int) -> bool:
    spec = get_column_spec(column)
    return bool(spec and spec.blank_zero_editor)


def is_stretch_column(column: int) -> bool:
    return column in STRETCH_COLUMNS


def is_shrinkable_column(column: int) -> bool:
    """A fixed-width column that narrows, after the stretch column, to save room."""
    return column in SHRINKABLE_COLUMNS


def columns_for_editor_type(
    editor_type: str, *, editable_only: bool = False
) -> tuple[int, ...]:
    return tuple(
        spec.index
        for spec in ESTIMATE_TABLE_COLUMN_SPECS
        if spec.editor_type == editor_type and (spec.editable or not editable_only)
    )


def default_column_widths() -> dict[int, int]:
    return {
        spec.index: spec.default_width
        for spec in ESTIMATE_TABLE_COLUMN_SPECS
        if not spec.stretch
    }


def column_width_limits() -> dict[int, tuple[int, int]]:
    return {
        spec.index: (spec.min_width, spec.max_width)
        for spec in ESTIMATE_TABLE_COLUMN_SPECS
    }


def navigation_columns() -> tuple[int, ...]:
    return NAVIGATION_COLUMNS


def first_navigation_column() -> int:
    return NAVIGATION_COLUMNS[0] if NAVIGATION_COLUMNS else COL_CODE
