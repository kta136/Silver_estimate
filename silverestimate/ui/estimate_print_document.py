"""Typed input model for estimate printing."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, cast

from .print_format_spec import DEFAULT_ESTIMATE_FORMAT, normalize_estimate_format


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field} must be a mapping")
    return value


def _number(value: object, *, field: str, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    try:
        return float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc


def _flag(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


@dataclass(frozen=True)
class EstimatePrintHeader:
    voucher_no: str
    date: str
    silver_rate: float
    note: str = ""
    last_balance_silver: float = 0.0
    last_balance_amount: float = 0.0

    @classmethod
    def from_mapping(cls, value: object) -> EstimatePrintHeader:
        source = _mapping(value, field="header")
        voucher_no = str(source.get("voucher_no") or "").strip()
        if not voucher_no:
            raise ValueError("header.voucher_no is required")
        return cls(
            voucher_no=voucher_no,
            date=str(source.get("date") or "").strip(),
            silver_rate=_number(
                source.get("silver_rate"),
                field="header.silver_rate",
            ),
            note=str(source.get("note") or ""),
            last_balance_silver=_number(
                source.get("last_balance_silver"),
                field="header.last_balance_silver",
            ),
            last_balance_amount=_number(
                source.get("last_balance_amount"),
                field="header.last_balance_amount",
            ),
        )


@dataclass(frozen=True)
class EstimatePrintItem:
    item_code: str
    item_name: str
    gross: float
    poly: float
    net_wt: float
    purity: float
    wage_rate: float
    pieces: float
    fine: float
    wage: float
    is_return: bool = False
    is_silver_bar: bool = False

    @classmethod
    def from_mapping(cls, value: object, *, index: int) -> EstimatePrintItem:
        source = _mapping(value, field=f"items[{index}]")
        gross = _number(source.get("gross"), field=f"items[{index}].gross")
        poly = _number(source.get("poly"), field=f"items[{index}].poly")
        return cls(
            item_code=str(
                source.get("item_code") or source.get("code") or ""
            ).strip(),
            item_name=str(
                source.get("item_name") or source.get("name") or ""
            ).strip(),
            gross=gross,
            poly=poly,
            net_wt=_number(
                source.get("net_wt"),
                field=f"items[{index}].net_wt",
                default=gross - poly,
            ),
            purity=_number(
                source.get("purity"),
                field=f"items[{index}].purity",
            ),
            wage_rate=_number(
                source.get("wage_rate"),
                field=f"items[{index}].wage_rate",
            ),
            pieces=_number(
                source.get("pieces"),
                field=f"items[{index}].pieces",
            ),
            fine=_number(source.get("fine"), field=f"items[{index}].fine"),
            wage=_number(source.get("wage"), field=f"items[{index}].wage"),
            is_return=_flag(source.get("is_return")),
            is_silver_bar=_flag(source.get("is_silver_bar")),
        )


@dataclass(frozen=True)
class EstimatePrintDocument:
    header: EstimatePrintHeader
    items: tuple[EstimatePrintItem, ...]
    format_key: str = DEFAULT_ESTIMATE_FORMAT

    @classmethod
    def from_mapping(
        cls,
        value: object,
        *,
        format_key: str = DEFAULT_ESTIMATE_FORMAT,
    ) -> EstimatePrintDocument:
        normalized_format = normalize_estimate_format(format_key)
        if isinstance(value, cls):
            if value.format_key == normalized_format:
                return value
            return replace(value, format_key=normalized_format)
        source = _mapping(value, field="estimate print document")
        raw_items = source.get("items") or ()
        if isinstance(raw_items, str | bytes) or not hasattr(raw_items, "__iter__"):
            raise TypeError("items must be an iterable of mappings")
        return cls(
            header=EstimatePrintHeader.from_mapping(source.get("header")),
            items=tuple(
                EstimatePrintItem.from_mapping(item, index=index)
                for index, item in enumerate(raw_items)
            ),
            format_key=normalized_format,
        )


__all__ = [
    "EstimatePrintDocument",
    "EstimatePrintHeader",
    "EstimatePrintItem",
]
