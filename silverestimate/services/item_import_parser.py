"""Parsing helpers for item import workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from silverestimate.domain.item_validation import ItemValidationError, validate_item


class ItemImportParseError(ValueError):
    """Raised when a source row cannot be parsed into an importable item."""


@dataclass(frozen=True)
class ParsedImportItem:
    code: str
    name: str
    wage_type: str
    wage_rate: float
    purity: float


def parse_adjustment_factor(raw_value: str) -> Tuple[Optional[str], Optional[float]]:
    text = (raw_value or "").strip()
    if not text:
        return None, None
    if not (text.startswith("*") or text.startswith("/")):
        raise ItemImportParseError(
            f"Invalid wage adjustment factor '{text}'. Use *value or /value."
        )

    operator = text[0]
    try:
        value = float(text[1:])
    except (TypeError, ValueError) as exc:
        raise ItemImportParseError(
            f"Invalid wage adjustment factor '{text}'. Use *value or /value."
        ) from exc

    if operator == "/" and value == 0:
        raise ItemImportParseError(
            "Invalid wage adjustment factor '/0': divide by zero."
        )
    return operator, value


def should_include_line(line: str, *, delimiter: str, use_filter: bool) -> bool:
    if not line:
        return False
    if use_filter:
        parts = line.split(delimiter, 1)
        if not parts:
            return False
        first_part = parts[0].strip()
        return first_part.endswith(".") and first_part[:-1].strip().isdigit()
    return delimiter in line


def parse_item_row(
    parts: Sequence[str],
    *,
    code_column: int,
    name_column: int,
    type_column: int,
    rate_column: int,
    purity_column: int,
    adjustment_op: Optional[str] = None,
    adjustment_val: Optional[float] = None,
) -> ParsedImportItem:
    max_column = max(code_column, name_column, type_column, rate_column, purity_column)
    if len(parts) <= max_column:
        raise ItemImportParseError(
            f"Not enough columns (needs {max_column + 1}, has {len(parts)})."
        )

    try:
        item_code = parts[code_column].strip().upper()
        item_name = parts[name_column].strip()
        wage_type = parts[type_column].strip().upper()
        wage_rate_value = float(parts[rate_column].strip())
        purity_value = float(parts[purity_column].strip())
    except (TypeError, ValueError, IndexError) as exc:
        raise ItemImportParseError(f"Invalid numeric or column data: {exc}") from exc

    if not item_code:
        raise ItemImportParseError("Missing item code.")

    if wage_type == "Q":
        wage_rate_value /= 1000.0

    if adjustment_op and adjustment_val is not None:
        if adjustment_op == "*":
            wage_rate_value *= adjustment_val
        elif adjustment_op == "/":
            wage_rate_value /= adjustment_val

    try:
        validated = validate_item(
            code=item_code,
            name=item_name,
            purity=purity_value,
            wage_type=wage_type,
            wage_rate=wage_rate_value,
        )
    except ItemValidationError as exc:
        raise ItemImportParseError(str(exc)) from exc

    return ParsedImportItem(
        code=validated.code,
        name=validated.name,
        wage_type=validated.wage_type,
        wage_rate=validated.wage_rate,
        purity=validated.purity,
    )
