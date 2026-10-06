"""Recorded sale and return weights, independent of current catalog values."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

ReportLevel = Literal["period", "item", "voucher"]
ReportGrouping = Literal["day", "month"]


@dataclass(frozen=True)
class SalesReportQuery:
    date_from: str
    date_to: str
    grouping: ReportGrouping = "day"
    item_search: str = ""
    level: ReportLevel = "period"
    period: str | None = None
    item_code: str | None = None

    def validate(self) -> None:
        start, end = (
            date.fromisoformat(self.date_from),
            date.fromisoformat(self.date_to),
        )
        if start.isoformat() != self.date_from or end.isoformat() != self.date_to:
            raise ValueError("Use dates in yyyy-MM-dd format.")
        if start > end:
            raise ValueError("From date must be on or before To date.")
        if self.grouping not in ("day", "month"):
            raise ValueError("Choose daily or monthly grouping.")
        if self.level not in ("period", "item", "voucher"):
            raise ValueError("Unknown report view.")
        if self.level == "voucher" and self.item_code is None:
            raise ValueError("Select an item to view its vouchers.")


@dataclass(frozen=True)
class SalesWeights:
    sale_net: Decimal = Decimal(0)
    sale_fine: Decimal = Decimal(0)
    return_net: Decimal = Decimal(0)
    return_fine: Decimal = Decimal(0)

    def values(self) -> tuple[Decimal, ...]:
        return self.sale_net, self.sale_fine, self.return_net, self.return_fine

    def plus(self, other: "SalesWeights") -> "SalesWeights":
        return SalesWeights(
            *(a + b for a, b in zip(self.values(), other.values(), strict=True))
        )


@dataclass(frozen=True)
class SalesReportRow:
    key: str
    detail: str
    weights: SalesWeights


@dataclass(frozen=True)
class SalesReportResult:
    rows: tuple[SalesReportRow, ...]
    totals: SalesWeights
