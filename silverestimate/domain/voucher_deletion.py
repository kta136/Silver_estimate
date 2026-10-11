"""Immutable selections and outcomes for reviewed voucher deletion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


def numeric_voucher_key(value: str) -> tuple[int, str]:
    """Compare arbitrary-size decimal identifiers without integer coercion."""
    value = value.strip()
    if not value or not value.isascii() or not value.isdecimal():
        raise ValueError("Voucher numbers must be whole numbers, such as 105.")
    normalized = value.lstrip("0") or "0"
    return len(normalized), normalized


@dataclass(frozen=True)
class VoucherDeletionRange:
    mode: Literal["date", "voucher"]
    start: str
    end: str

    def __post_init__(self) -> None:
        if self.mode == "date":
            try:
                start, end = (
                    date.fromisoformat(self.start),
                    date.fromisoformat(self.end),
                )
                if start.isoformat() != self.start or end.isoformat() != self.end:
                    raise ValueError
            except ValueError as exc:
                raise ValueError("Choose valid From and To dates.") from exc
            reversed_range = start > end
        elif self.mode == "voucher":
            reversed_range = numeric_voucher_key(self.start) > numeric_voucher_key(
                self.end
            )
        else:
            raise ValueError("Choose a date or voucher number range.")
        if reversed_range:
            raise ValueError("From must not be after To.")

    @property
    def description(self) -> str:
        label = "Dates" if self.mode == "date" else "Voucher numbers"
        return f"{label}: {self.start} to {self.end} (inclusive)"


@dataclass(frozen=True)
class VoucherDeletionRow:
    voucher_no: str
    date: str
    bar_count: int
    skip_reason: str = ""


@dataclass(frozen=True)
class VoucherDeletionPreview:
    criteria: VoucherDeletionRange
    rows: tuple[VoucherDeletionRow, ...]
    fingerprint: str

    @property
    def eligible(self) -> tuple[VoucherDeletionRow, ...]:
        return tuple(row for row in self.rows if not row.skip_reason)

    @property
    def skipped(self) -> tuple[VoucherDeletionRow, ...]:
        return tuple(row for row in self.rows if row.skip_reason)


@dataclass(frozen=True)
class VoucherDeletionResult:
    succeeded: bool
    deleted_vouchers: tuple[str, ...] = ()
    skipped: tuple[VoucherDeletionRow, ...] = ()
    deleted_draft_token: str | None = None
    stale: bool = False
    message: str = ""
