"""Read sales from saved lines without recalculating or joining the live catalog."""

from threading import Event

from silverestimate.domain.numeric_policy import decimal_value
from silverestimate.domain.sales_report import (
    SalesReportQuery,
    SalesReportResult,
    SalesReportRow,
    SalesWeights,
)
from silverestimate.infrastructure.latest_request_runner import RequestCancelledError
from silverestimate.persistence.database_driver import Cursor


def fetch_sales_report(
    cursor: Cursor,
    query: SalesReportQuery,
    cancel_event: Event | None = None,
) -> SalesReportResult:
    """Stream matching lines and add their recorded values using decimal arithmetic.

    Only aggregated groups are retained in memory. A code's latest saved name in
    the selected scope labels its row, even if the catalog item has been deleted.
    Returns remain positive in separate columns; silver bars are always excluded.
    """
    query.validate()
    code_sql = "UPPER(TRIM(COALESCE(ei.item_code_snapshot, ei.item_code, '')))"
    sql = f"""
        SELECT e.date, e.voucher_no, ei.id, {code_sql} AS code,
               ei.item_name, ei.net_wt, ei.fine, ei.is_return
        FROM estimates e
        JOIN estimate_items ei ON ei.voucher_no = e.voucher_no
        WHERE e.date >= ? AND e.date <= ?
          AND COALESCE(ei.is_silver_bar, 0) = 0
    """  # noqa: S608 - the only interpolation is the constant column expression
    params: list[object] = [query.date_from, query.date_to]
    if query.item_search.strip():
        sql += f" AND INSTR({code_sql}, ?) > 0"  # noqa: S608
        params.append(query.item_search.strip().upper())
    if query.period is not None:
        sql += " AND SUBSTR(e.date, 1, ?) = ?"
        params.extend([7 if query.grouping == "month" else 10, query.period])
    if query.item_code is not None:
        sql += f" AND {code_sql} = ?"  # noqa: S608
        params.append(query.item_code.strip().upper())
    cursor.execute(sql, params)

    groups: dict[str, SalesWeights] = {}
    details: dict[str, tuple[tuple[str, int], str]] = {}
    totals = SalesWeights()
    while batch := cursor.fetchmany(500):
        for saved_date, voucher, line_id, code, name, net, fine, is_return in batch:
            if cancel_event is not None and cancel_event.is_set():
                raise RequestCancelledError("Sales report cancelled.")
            weights = _line_weights(net, fine, bool(is_return))
            key, detail = _group_identity(query, saved_date, voucher, code, name)
            groups[key] = groups.get(key, SalesWeights()).plus(weights)
            totals = totals.plus(weights)
            rank = (saved_date, line_id)
            if key not in details or rank > details[key][0]:
                details[key] = (rank, detail)

    rows = [
        SalesReportRow(key, details[key][1], weights) for key, weights in groups.items()
    ]
    if query.level == "voucher":
        rows.sort(key=lambda row: (row.detail, row.key), reverse=True)
    else:
        rows.sort(key=lambda row: row.key, reverse=query.level == "period")
    return SalesReportResult(tuple(rows), totals)


def _line_weights(net: object, fine: object, is_return: bool) -> SalesWeights:
    net_value = decimal_value(str(net or 0))
    fine_value = decimal_value(str(fine or 0))
    if is_return:
        return SalesWeights(return_net=net_value, return_fine=fine_value)
    return SalesWeights(sale_net=net_value, sale_fine=fine_value)


def _group_identity(
    query: SalesReportQuery, saved_date: str, voucher: str, code: str, name: str | None
) -> tuple[str, str]:
    if query.level == "period":
        return saved_date[:7] if query.grouping == "month" else saved_date, ""
    if query.level == "item":
        return code, name or ""
    return voucher, saved_date
