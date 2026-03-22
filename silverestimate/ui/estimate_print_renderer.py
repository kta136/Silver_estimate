"""Estimate print rendering helpers extracted from PrintManager."""

from __future__ import annotations

import html as html_lib
import logging
import math
from typing import Callable


def _split_estimate_items(items):
    regular_items, silver_bar_items, return_goods, return_silver_bars = (
        [],
        [],
        [],
        [],
    )
    for item in items:
        is_return = item.get("is_return", 0) == 1
        is_silver_bar = item.get("is_silver_bar", 0) == 1

        if is_return:
            if is_silver_bar:
                return_silver_bars.append(item)
            else:
                return_goods.append(item)
        else:
            if is_silver_bar:
                silver_bar_items.append(item)
            else:
                regular_items.append(item)
    return regular_items, silver_bar_items, return_goods, return_silver_bars


class EstimatePrintRenderer:
    """Render estimate payloads into the supported print HTML layouts."""

    def __init__(self, *, currency_formatter: Callable[[float | int], str]) -> None:
        self._format_currency_locale = currency_formatter

    @staticmethod
    def _build_preformatted_html(content: str, *, line_height: float = 1.0) -> str:
        escaped_content = html_lib.escape(content or "")
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
                    pre {{
                        line-height: {line_height};
                        white-space: pre;
                        margin: 0;
                        padding: 0;
                        page-break-inside: avoid;
                    }}
                    body {{ margin: 0; }}
                    </style></head><body><pre>{escaped_content}</pre></body></html>"""

    @staticmethod
    def _format_indian_grouped_integer(value: float | int) -> str:
        rounded_value = math.ceil(float(value))
        sign = "-" if rounded_value < 0 else ""
        digits = str(abs(rounded_value))
        if len(digits) <= 3:
            return f"{sign}{digits}"
        last_three = digits[-3:]
        remaining = digits[:-3]
        grouped = []
        while len(remaining) > 2:
            grouped.append(remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            grouped.append(remaining)
        return f"{sign}{','.join(reversed(grouped))},{last_three}"

    @staticmethod
    def _format_indian_grouped_decimal(
        value: float | int,
        *,
        decimals: int = 1,
    ) -> str:
        numeric_value = float(value)
        sign = "-" if numeric_value < 0 else ""
        absolute_value = abs(numeric_value)
        rounded_value = f"{absolute_value:.{decimals}f}"
        if "." in rounded_value:
            integer_text, fraction = rounded_value.split(".", 1)
        else:
            integer_text, fraction = rounded_value, ""
        grouped_integer = EstimatePrintRenderer._format_indian_grouped_integer(
            int(integer_text)
        )
        if decimals <= 0:
            return f"{sign}{grouped_integer}"
        return f"{sign}{grouped_integer}.{fraction}"

    def generate_old_format(self, estimate_data):
        """Generate manually formatted text using spaces, matching preview image."""
        header = estimate_data["header"]
        items = estimate_data["items"]
        voucher_no = header["voucher_no"]
        silver_rate = header["silver_rate"]

        regular_items, silver_bar_items, return_goods, return_silver_bars = (
            _split_estimate_items(items)
        )

        S = 1
        W_SNO = 3
        W_FINE = 9
        W_LBR = 8
        W_QTY = 10
        W_POLY = 7
        W_NAME = 18
        W_SPER = 7
        W_PCS = 8
        W_WRATE = 8
        TOTAL_WIDTH = (
            W_SNO
            + S
            + W_FINE
            + S
            + W_LBR
            + S
            + W_QTY
            + S
            + W_POLY
            + S
            + W_NAME
            + S
            + W_SPER
            + S
            + W_PCS
            + S
            + W_WRATE
        )

        def format_line(*args):
            try:
                sno = f"{args[0]:>{W_SNO}}"
                fine = f"{args[1]:>{W_FINE}.3f}"
                labour = f"{args[2]:>{W_LBR}.2f}"
                qty = f"{args[3]:>{W_QTY}.3f}"
                poly = f"{args[4]:>{W_POLY}.0f}"
                name = f"{str(args[5] or ''):<{W_NAME}.{W_NAME}}"
                sper = f"{args[6]:>{W_SPER}.2f}"
                pcs_val = args[7]
                pcs_display = str(pcs_val) if pcs_val and pcs_val > 0 else ""
                pcs = pcs_display.rjust(W_PCS)
                wrate = f"{args[8]:>{W_WRATE}.2f}"
                line = f"{sno} {fine} {labour} {qty} {poly} {name} {sper} {pcs} {wrate}"
                return f"{line:<{TOTAL_WIDTH}}"[:TOTAL_WIDTH]
            except Exception as err:
                logging.getLogger(__name__).error(
                    "Error formatting line: %s, Data: %s",
                    err,
                    args,
                )
                return " " * TOTAL_WIDTH

        def format_totals_line(fine, labour, qty, poly):
            fine_str = f"{fine:{W_FINE}.3f}"
            labour_str = f"{labour:{W_LBR}.0f}"
            qty_str = str(int(round(qty))).rjust(W_QTY)
            poly_str = f"{poly:{W_POLY}.0f}"
            sno_space = " " * (W_SNO + S)
            space_after_poly = " " * (S + W_NAME + S + W_SPER + S + W_PCS + S + W_WRATE)
            line = (
                f"{sno_space}{fine_str} {labour_str} {qty_str} "
                f"{poly_str}{space_after_poly}"
            )
            return f"{line:<{TOTAL_WIDTH}}"[:TOTAL_WIDTH]

        output = []
        note = header.get("note", "")
        title = "* * ESTIMATE SLIP ONLY * *"

        if note:
            title_len = len(title)
            note_len = len(note)
            title_pad = (TOTAL_WIDTH - title_len) // 2
            title_end_pos = title_pad + title_len
            space_after_title = TOTAL_WIDTH - title_end_pos - 5
            if note_len > space_after_title:
                note = note[: space_after_title - 3] + "..."
                note_len = len(note)
            final_pad = (TOTAL_WIDTH - title_len - note_len - 5) // 2
            if final_pad < 0:
                final_pad = 0
            line = " " * final_pad + title + " " * 5 + note
            if len(line) > TOTAL_WIDTH:
                line = line[:TOTAL_WIDTH]
            output.append(line)
        else:
            pad = (TOTAL_WIDTH - len(title)) // 2
            output.append(" " * pad + title)

        voucher_str = str(voucher_no).ljust(15)
        rate_str = f"S.Rate :{silver_rate:10.2f}"
        pad = max(1, TOTAL_WIDTH - len(voucher_str) - len(rate_str))
        output.append(f"{voucher_str}" + " " * pad + rate_str)
        sep_eq = "=" * TOTAL_WIDTH
        sep_dash = "-" * TOTAL_WIDTH
        output.append(sep_eq)
        h_sno = "SNo".center(W_SNO)
        h_fine = "Fine".center(W_FINE)
        h_labour = "Labour".center(W_LBR)
        h_qty = "Quantity".center(W_QTY)
        h_poly = "Poly".center(W_POLY)
        h_name = "Item Name".center(W_NAME)
        h_sper = "S.Per%".center(W_SPER)
        h_pcs = "Pcs/Doz.".center(W_PCS)
        h_wrate = "W.Rate".center(W_WRATE)
        header_line = (
            f"{h_sno} {h_fine} {h_labour} {h_qty} {h_poly} "
            f"{h_name} {h_sper} {h_pcs} {h_wrate}"
        )
        output.append(f"{header_line:<{TOTAL_WIDTH}}"[:TOTAL_WIDTH])
        output.append(sep_eq)

        reg_f = reg_w = reg_g = reg_p = 0.0
        sb_f = sb_w = sb_g = sb_p = 0.0
        ret_gf = ret_gw = ret_gg = ret_gp = 0.0
        ret_sf = ret_sw = ret_sg = ret_sp = 0.0

        if regular_items:
            sno = 1
            for item in regular_items:
                reg_f += item.get("fine", 0.0)
                reg_w += item.get("wage", 0.0)
                reg_g += item.get("gross", 0.0)
                reg_p += item.get("poly", 0.0)
                output.append(
                    format_line(
                        sno,
                        item.get("fine", 0.0),
                        item.get("wage", 0.0),
                        item.get("gross", 0.0),
                        item.get("poly", 0.0),
                        item.get("item_name", ""),
                        item.get("purity", 0.0),
                        item.get("pieces", 0),
                        item.get("wage_rate", 0.0),
                    )
                )
                sno += 1
            output.append(sep_dash)
            output.append(format_totals_line(reg_f, reg_w, reg_g, reg_p))
            output.append(sep_eq)

        if silver_bar_items:
            sb_title = "* * Silver Bars * *"
            pad = (TOTAL_WIDTH - len(sb_title)) // 2
            output.append(" " * pad + sb_title)
            output.append(sep_dash)
            output.append(header_line[:TOTAL_WIDTH])
            output.append(sep_dash)
            sno = 1
            for item in silver_bar_items:
                sb_f += item.get("fine", 0.0)
                sb_w += item.get("wage", 0.0)
                sb_g += item.get("gross", 0.0)
                sb_p += item.get("poly", 0.0)
                output.append(
                    format_line(
                        sno,
                        item.get("fine", 0.0),
                        item.get("wage", 0.0),
                        item.get("gross", 0.0),
                        item.get("poly", 0.0),
                        item.get("item_name", ""),
                        item.get("purity", 0.0),
                        0,
                        0,
                    )
                )
                sno += 1
            output.append(sep_dash)
            output.append(format_totals_line(sb_f, sb_w, sb_g, sb_p))
            output.append(sep_eq)

        if return_goods:
            rg_title = "* * Return Goods * *"
            pad = (TOTAL_WIDTH - len(rg_title)) // 2
            output.append(" " * pad + rg_title)
            output.append(sep_dash)
            output.append(header_line[:TOTAL_WIDTH])
            output.append(sep_dash)
            sno = 1
            for item in return_goods:
                ret_gf += item.get("fine", 0.0)
                ret_gw += item.get("wage", 0.0)
                ret_gg += item.get("gross", 0.0)
                ret_gp += item.get("poly", 0.0)
                output.append(
                    format_line(
                        sno,
                        item.get("fine", 0.0),
                        item.get("wage", 0.0),
                        item.get("gross", 0.0),
                        item.get("poly", 0.0),
                        item.get("item_name", ""),
                        item.get("purity", 0.0),
                        item.get("pieces", 0),
                        item.get("wage_rate", 0.0),
                    )
                )
                sno += 1
            output.append(sep_dash)
            output.append(format_totals_line(ret_gf, ret_gw, ret_gg, ret_gp))
            output.append(sep_eq)

        if return_silver_bars:
            rsb_title = "* * Return Silver Bar * *"
            pad = (TOTAL_WIDTH - len(rsb_title)) // 2
            output.append(" " * pad + rsb_title)
            output.append(sep_dash)
            output.append(header_line[:TOTAL_WIDTH])
            output.append(sep_dash)
            sno = 1
            for item in return_silver_bars:
                ret_sf += item.get("fine", 0.0)
                ret_sw += item.get("wage", 0.0)
                ret_sg += item.get("gross", 0.0)
                ret_sp += item.get("poly", 0.0)
                output.append(
                    format_line(
                        sno,
                        item.get("fine", 0.0),
                        item.get("wage", 0.0),
                        item.get("gross", 0.0),
                        item.get("poly", 0.0),
                        item.get("item_name", ""),
                        item.get("purity", 0.0),
                        0,
                        0,
                    )
                )
                sno += 1
            output.append(sep_dash)
            output.append(format_totals_line(ret_sf, ret_sw, ret_sg, ret_sp))
            output.append(sep_eq)

        last_balance_silver = header.get("last_balance_silver", 0.0)
        last_balance_amount = header.get("last_balance_amount", 0.0)

        if last_balance_silver > 0 or last_balance_amount > 0:
            lb_title = "* * Last Balance * *"
            lb_pad = (TOTAL_WIDTH - len(lb_title)) // 2
            output.append(" " * lb_pad + lb_title)
            output.append(sep_dash)
            lb_str = (
                f"Silver: {last_balance_silver:.3f} g   Amount: "
                f"{self._format_currency_locale(last_balance_amount)}"
            )
            lb_pad = (TOTAL_WIDTH - len(lb_str)) // 2
            output.append(" " * lb_pad + lb_str)
            output.append(sep_dash)

        final_title = "Final Silver & Amount"
        pad = (TOTAL_WIDTH - len(final_title)) // 2
        output.append(" " * pad + final_title)
        output.append(sep_eq)
        net_fine = reg_f - sb_f - ret_gf - ret_sf
        net_fine_display = (
            net_fine + last_balance_silver if last_balance_silver > 0 else net_fine
        )
        net_wage = reg_w - sb_w - ret_gw - ret_sw
        net_wage_display = (
            net_wage + last_balance_amount if last_balance_amount > 0 else net_wage
        )

        silver_cost = net_fine_display * silver_rate
        total_cost = net_wage_display + silver_cost

        net_wage_r = int(round(net_wage_display))
        silver_cost_r = int(round(silver_cost))
        total_cost_r = int(round(total_cost))

        fine_str = f"{net_fine_display:{W_FINE}.3f}"
        wage_str = f"{net_wage_r:{W_LBR}.0f}"
        scost_display = "S.Cost : " + self._format_currency_locale(silver_cost_r)
        total_display = "Total: " + self._format_currency_locale(total_cost_r)

        total_pad = total_display.rjust(18)
        scost_pad = scost_display.rjust(22)

        if silver_rate > 0:
            part1_len = W_SNO + S + W_FINE + S + W_LBR
            space_before = TOTAL_WIDTH - part1_len - len(scost_pad) - len(total_pad) - 2
            pad_after_labour = max(1, space_before - 1)
            final_line = (
                f"{' ' * (W_SNO + S)}{fine_str} {wage_str}"
                + (" " * pad_after_labour)
                + scost_pad
                + " "
                + total_pad
            )
        else:
            part1_len = W_SNO + S + W_FINE + S + W_LBR
            remaining_space = TOTAL_WIDTH - part1_len
            final_line = f"{' ' * (W_SNO + S)}{fine_str} {wage_str}" + (
                " " * remaining_space
            )

        output.append(final_line[:TOTAL_WIDTH])
        output.append(sep_eq)
        note_line = "Note :-  G O O D S   N O T   R E T U R N"
        pad = (TOTAL_WIDTH - len(note_line)) // 2
        output.append(" " * pad + note_line)
        output.append(" \f")

        return self._build_preformatted_html("\n".join(output), line_height=1.0)

    def generate_new_format(self, estimate_data):
        """Generate the new layout variant for estimates."""
        header = estimate_data["header"]
        items = estimate_data["items"]
        voucher_no = header["voucher_no"]
        silver_rate = header["silver_rate"]
        regular_items, silver_bar_items, return_goods, return_silver_bars = (
            _split_estimate_items(items)
        )

        S = 1
        W_SNO = 3
        W_NAME = 18
        W_GROSS = 9
        W_POLY = 9
        W_NET = 9
        W_SPER = 8
        W_WRATE = 9
        W_PCS = 9
        W_FINE = 9
        W_LBR = 9
        TOTAL_WIDTH = (
            W_SNO
            + S
            + W_NAME
            + S
            + W_GROSS
            + S
            + W_POLY
            + S
            + W_NET
            + S
            + W_SPER
            + S
            + W_WRATE
            + S
            + W_PCS
            + S
            + W_FINE
            + S
            + W_LBR
        )

        new_layout_decimals = 1

        def fmt_num(value, width):
            if value is None:
                return " " * width
            try:
                return (
                    f"{float(value):<{width}.{new_layout_decimals}f}"[:width].ljust(
                        width
                    )
                )
            except Exception:
                return " " * width

        def format_line(
            sno, name, gross, poly, net, sper, wrate, pcs, fine, labour_amt
        ):
            try:
                sno_str = "" if sno in (None, "") else str(sno)
                line_parts = [
                    sno_str[:W_SNO].ljust(W_SNO),
                    (str(name or "")[:W_NAME]).ljust(W_NAME),
                    fmt_num(gross, W_GROSS),
                    fmt_num(poly, W_POLY),
                    fmt_num(net, W_NET),
                    fmt_num(sper, W_SPER),
                    fmt_num(wrate, W_WRATE),
                    fmt_num(pcs, W_PCS) if pcs not in (None, "") else " " * W_PCS,
                    fmt_num(fine, W_FINE),
                    fmt_num(labour_amt, W_LBR),
                ]
                return f"{' '.join(line_parts):<{TOTAL_WIDTH}}"[:TOTAL_WIDTH]
            except Exception as err:
                logging.getLogger(__name__).error(
                    "Error formatting new layout line: %s",
                    err,
                )
                return " " * TOTAL_WIDTH

        output = []
        note = header.get("note", "")
        title = "* * ESTIMATE SLIP ONLY * *"

        if note:
            title_len = len(title)
            note_len = len(note)
            title_pad = (TOTAL_WIDTH - title_len) // 2
            title_end_pos = title_pad + title_len
            space_after_title = TOTAL_WIDTH - title_end_pos - 5
            if note_len > space_after_title:
                note = note[: space_after_title - 3] + "..."
                note_len = len(note)
            final_pad = (TOTAL_WIDTH - title_len - note_len - 5) // 2
            if final_pad < 0:
                final_pad = 0
            line = " " * final_pad + title + " " * 5 + note
            output.append(line[:TOTAL_WIDTH])
        else:
            output.append(" " * ((TOTAL_WIDTH - len(title)) // 2) + title)

        voucher_str = str(voucher_no).ljust(15)
        rate_str = f"S.Rate :{silver_rate:10.{new_layout_decimals}f}"
        pad = max(1, TOTAL_WIDTH - len(voucher_str) - len(rate_str))
        output.append(f"{voucher_str}" + " " * pad + rate_str)
        sep_eq = "=" * TOTAL_WIDTH
        sep_dash = "-" * TOTAL_WIDTH
        output.append(sep_eq)

        header_line = " ".join(
            [
                "SNo".ljust(W_SNO),
                "Item Name".ljust(W_NAME),
                "Gross".ljust(W_GROSS),
                "Poly".ljust(W_POLY),
                "Net".ljust(W_NET),
                "S.Per%".ljust(W_SPER),
                "W Rate".ljust(W_WRATE),
                "PCS/Doz.".ljust(W_PCS),
                "Fine".ljust(W_FINE),
                "Lbr".ljust(W_LBR),
            ]
        )
        output.append(f"{header_line:<{TOTAL_WIDTH}}"[:TOTAL_WIDTH])
        output.append(sep_eq)

        reg_f = reg_w = reg_g = reg_p = reg_n = 0.0
        sb_f = sb_w = sb_g = sb_p = sb_n = 0.0
        ret_gf = ret_gw = ret_gg = ret_gp = ret_gn = 0.0
        ret_sf = ret_sw = ret_sg = ret_sp = ret_sn = 0.0

        def item_values(item):
            gross = item.get("gross", 0.0) or 0.0
            poly = item.get("poly", 0.0) or 0.0
            net = item.get("net_wt", None)
            if net is None:
                net = gross - poly
            return (
                gross,
                poly,
                net,
                item.get("purity", 0.0),
                item.get("wage_rate", 0.0),
                item.get("pieces", 0),
                item.get("fine", 0.0) or 0.0,
                item.get("wage", 0.0) or 0.0,
            )

        def append_section(
            title_text, items_list, totals, *, include_wrate=True, include_pcs=True
        ):
            if title_text:
                output.append(" " * ((TOTAL_WIDTH - len(title_text)) // 2) + title_text)
                output.append(sep_dash)
                output.append(header_line[:TOTAL_WIDTH])
                output.append(sep_dash)
            sno = 1
            for item in items_list:
                gross, poly, net, purity, wage_rate, pieces, fine, wage = item_values(
                    item
                )
                totals[0] += fine
                totals[1] += wage
                totals[2] += gross
                totals[3] += poly
                totals[4] += net
                output.append(
                    format_line(
                        sno,
                        item.get("item_name", ""),
                        gross,
                        poly,
                        net,
                        purity,
                        wage_rate if include_wrate else None,
                        pieces if include_pcs else None,
                        fine,
                        wage,
                    )
                )
                sno += 1
            output.append(sep_dash)
            output.append(
                format_line(
                    "",
                    "TOTAL",
                    totals[2],
                    totals[3],
                    totals[4],
                    None,
                    None,
                    None,
                    totals[0],
                    totals[1],
                )
            )
            output.append(sep_eq)

        if regular_items:
            totals = [reg_f, reg_w, reg_g, reg_p, reg_n]
            append_section("", regular_items, totals)
            reg_f, reg_w, reg_g, reg_p, reg_n = totals
            if silver_bar_items or return_goods or return_silver_bars:
                output.append("")
        if silver_bar_items:
            totals = [sb_f, sb_w, sb_g, sb_p, sb_n]
            append_section(
                "* * Silver Bars * *",
                silver_bar_items,
                totals,
                include_wrate=False,
                include_pcs=False,
            )
            sb_f, sb_w, sb_g, sb_p, sb_n = totals
            if return_goods or return_silver_bars:
                output.append("")
        if return_goods:
            totals = [ret_gf, ret_gw, ret_gg, ret_gp, ret_gn]
            append_section("* * Return Goods * *", return_goods, totals)
            ret_gf, ret_gw, ret_gg, ret_gp, ret_gn = totals
            if return_silver_bars:
                output.append("")
        if return_silver_bars:
            totals = [ret_sf, ret_sw, ret_sg, ret_sp, ret_sn]
            append_section(
                "* * Return Silver Bar * *",
                return_silver_bars,
                totals,
                include_wrate=False,
                include_pcs=False,
            )
            ret_sf, ret_sw, ret_sg, ret_sp, ret_sn = totals

        last_balance_silver = header.get("last_balance_silver", 0.0)
        last_balance_amount = header.get("last_balance_amount", 0.0)
        if last_balance_silver > 0 or last_balance_amount > 0:
            lb_title = "* * Last Balance * *"
            output.append(" " * ((TOTAL_WIDTH - len(lb_title)) // 2) + lb_title)
            output.append(sep_dash)
            lb_str = (
                "Silver: "
                + self._format_indian_grouped_decimal(
                    last_balance_silver,
                    decimals=new_layout_decimals,
                )
                + " g   Amount: Rs. "
                + self._format_indian_grouped_decimal(
                    last_balance_amount,
                    decimals=new_layout_decimals,
                )
            )
            output.append(" " * ((TOTAL_WIDTH - len(lb_str)) // 2) + lb_str)
            output.append(sep_dash)

        final_title = "Final Silver & Amount"
        output.append(" " * ((TOTAL_WIDTH - len(final_title)) // 2) + final_title)
        output.append(sep_eq)

        net_fine = reg_f - sb_f - ret_gf - ret_sf
        net_fine_display = (
            net_fine + last_balance_silver if last_balance_silver > 0 else net_fine
        )
        net_wage = reg_w - sb_w - ret_gw - ret_sw
        net_wage_display = (
            net_wage + last_balance_amount if last_balance_amount > 0 else net_wage
        )
        silver_cost = net_fine_display * silver_rate
        total_cost = net_wage_display + silver_cost

        fine_display = (
            self._format_indian_grouped_decimal(
                net_fine_display,
                decimals=new_layout_decimals,
            )
            + " gm"
        )
        fine_str = fine_display.rjust(max(W_FINE, len(fine_display)))
        wage_display = self._format_indian_grouped_decimal(
            net_wage_display,
            decimals=new_layout_decimals,
        )
        wage_str = wage_display.rjust(max(W_LBR, len(wage_display)))
        scost_display = (
            "S.Cost : Rs. "
            + self._format_indian_grouped_decimal(
                silver_cost,
                decimals=new_layout_decimals,
            )
        )
        scost_pad = scost_display.rjust(max(22, len(scost_display)))
        total_display = (
            "Total: Rs. "
            + self._format_indian_grouped_decimal(
                total_cost,
                decimals=new_layout_decimals,
            )
        )
        total_pad = total_display.rjust(max(18, len(total_display)))

        if silver_rate > 0:
            part1_len = W_SNO + S + len(fine_str) + S + W_LBR
            space_before = TOTAL_WIDTH - part1_len - len(scost_pad) - len(total_pad) - 2
            pad_after_labour = max(1, space_before - 1)
            final_line = (
                f"{' ' * (W_SNO + S)}{fine_str} {wage_str}"
                + (" " * pad_after_labour)
                + scost_pad
                + " "
                + total_pad
            )
        else:
            amount_display = (
                "Rs. "
                + self._format_indian_grouped_decimal(
                    total_cost,
                    decimals=new_layout_decimals,
                )
            )
            amount_pad = amount_display.rjust(max(W_LBR, len(amount_display)))
            final_line = f"{' ' * (W_SNO + S)}{fine_str} {amount_pad}"

        output.append(final_line[:TOTAL_WIDTH])
        output.append(sep_eq)
        note_line = "Note :-  G O O D S   N O T   R E T U R N"
        output.append(" " * ((TOTAL_WIDTH - len(note_line)) // 2) + note_line)
        output.append(" \f")

        return self._build_preformatted_html("\n".join(output), line_height=1.0)

    def generate_thermal_format(self, estimate_data):
        """Generate thermal slip layout sized for ~80mm paper."""
        header = estimate_data["header"]
        items = estimate_data["items"]
        voucher_no = header["voucher_no"]
        silver_rate = header["silver_rate"]
        regular_items, silver_bar_items, return_goods, return_silver_bars = (
            _split_estimate_items(items)
        )

        TOTAL_WIDTH = 48
        W_SNO = 2
        W_NAME = TOTAL_WIDTH - W_SNO - 1
        W_GROSS = 10
        W_POLY = 10
        W_NET = 10
        W_SPER = 8
        W_FINE = 10
        W_PCS = 6
        W_LBR = 10

        def fmt_num(label, value, width):
            if value is None:
                return " " * width
            try:
                body = f"{float(value):.2f}"
            except Exception:
                body = str(value)
            return f"{label}:{body}"[:width].ljust(width)

        def fmt_text(label, value, width):
            if value in (None, ""):
                return " " * width
            return f"{label}:{value}"[:width].ljust(width)

        def append_item(
            lines,
            sno,
            name,
            gross,
            poly,
            net,
            sper,
            wrate,
            pcs,
            fine,
            labour,
            wage_type,
        ):
            sno_str = "" if sno in (None, "") else str(sno)
            lines.append(
                f"{sno_str:>2} {str(name or '')[:W_NAME]}"[:TOTAL_WIDTH].ljust(
                    TOTAL_WIDTH
                )
            )
            lines.append(
                " ".join(
                    [
                        fmt_num("G", gross, W_GROSS),
                        fmt_num("P", poly, W_POLY),
                        fmt_num("N", net, W_NET),
                    ]
                )[:TOTAL_WIDTH].ljust(TOTAL_WIDTH)
            )
            pcs_display = pcs
            if pcs_display is None:
                pcs_display = ""
            elif isinstance(pcs_display, float) and pcs_display.is_integer():
                pcs_display = int(pcs_display)

            labour_present = abs(labour or 0.0) > 1e-6
            labour_unit_code = (wage_type or "").strip().upper()
            labour_unit = (
                {"PC": "/pc", "WT": "/gm"}.get(labour_unit_code, "")
                if (labour_present or abs(wrate or 0.0) > 1e-6)
                else ""
            )
            lines.append(
                " ".join(
                    [
                        fmt_num("S%", sper, W_SPER),
                        fmt_num("Fi", fine, W_FINE),
                        fmt_text("Pc", pcs_display, W_PCS),
                    ]
                )[:TOTAL_WIDTH].ljust(TOTAL_WIDTH)
            )
            if labour_present:
                lines.append(
                    fmt_num("Lb", labour, W_LBR)[:TOTAL_WIDTH].ljust(TOTAL_WIDTH)
                )
            if labour_unit:
                lines.append(
                    fmt_text("Lbr", labour_unit, W_LBR)[:TOTAL_WIDTH].ljust(TOTAL_WIDTH)
                )

        output = []
        note = header.get("note", "")
        title = "* ESTIMATE SLIP *"
        output.append(
            (" " * max(0, (TOTAL_WIDTH - len(title)) // 2) + title)[:TOTAL_WIDTH].ljust(
                TOTAL_WIDTH
            )
        )
        if note:
            output.append(str(note)[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))

        voucher_str = str(voucher_no)
        rate_str = f"Rate:{silver_rate:0.2f}"
        spacer = max(1, TOTAL_WIDTH - len(voucher_str) - len(rate_str))
        output.append(
            f"{voucher_str}{' ' * spacer}{rate_str}"[:TOTAL_WIDTH].ljust(TOTAL_WIDTH)
        )
        sep = "-" * TOTAL_WIDTH
        output.append(sep)

        reg_f = reg_w = reg_g = reg_p = reg_n = 0.0
        sb_f = sb_w = sb_g = sb_p = sb_n = 0.0
        ret_gf = ret_gw = ret_gg = ret_gp = ret_gn = 0.0
        ret_sf = ret_sw = ret_sg = ret_sp = ret_sn = 0.0

        def append_group(group_title, items_list, totals, *, with_wage=True):
            if group_title:
                output.append(group_title[:TOTAL_WIDTH].center(TOTAL_WIDTH))
                output.append(sep)
            sno = 1
            for item in items_list:
                gross = item.get("gross", 0.0) or 0.0
                poly = item.get("poly", 0.0) or 0.0
                net = item.get("net_wt", gross - poly)
                purity = item.get("purity", 0.0)
                wage_rate = item.get("wage_rate", 0.0)
                wage_type = item.get("wage_type", "")
                pcs = item.get("pieces", 0)
                fine = item.get("fine", 0.0) or 0.0
                wage = item.get("wage", 0.0) or 0.0
                totals[0] += fine
                totals[1] += wage
                totals[2] += gross
                totals[3] += poly
                totals[4] += net
                append_item(
                    output,
                    sno,
                    item.get("item_name", ""),
                    gross,
                    poly,
                    net,
                    purity,
                    wage_rate if with_wage else None,
                    pcs if with_wage else None,
                    fine,
                    wage,
                    wage_type if with_wage else None,
                )
                sno += 1
            output.append(sep)
            output.append(
                f"TOTAL G:{totals[2]:9.2f} P:{totals[3]:9.2f} N:{totals[4]:9.2f}"[
                    :TOTAL_WIDTH
                ].ljust(TOTAL_WIDTH)
            )
            line = f"      Fi:{totals[0]:9.2f}"
            if abs(totals[1]) > 1e-6:
                line += f" Lb:{totals[1]:9.2f}"
            output.append(line[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
            output.append(sep)

        if regular_items:
            totals = [reg_f, reg_w, reg_g, reg_p, reg_n]
            append_group("", regular_items, totals)
            reg_f, reg_w, reg_g, reg_p, reg_n = totals
        if silver_bar_items:
            totals = [sb_f, sb_w, sb_g, sb_p, sb_n]
            append_group("* Bars *", silver_bar_items, totals, with_wage=False)
            sb_f, sb_w, sb_g, sb_p, sb_n = totals
        if return_goods:
            totals = [ret_gf, ret_gw, ret_gg, ret_gp, ret_gn]
            append_group("* Returns *", return_goods, totals)
            ret_gf, ret_gw, ret_gg, ret_gp, ret_gn = totals
        if return_silver_bars:
            totals = [ret_sf, ret_sw, ret_sg, ret_sp, ret_sn]
            append_group("* Ret Bars *", return_silver_bars, totals, with_wage=False)
            ret_sf, ret_sw, ret_sg, ret_sp, ret_sn = totals

        last_balance_silver = header.get("last_balance_silver", 0.0)
        last_balance_amount = header.get("last_balance_amount", 0.0)
        if last_balance_silver > 0 or last_balance_amount > 0:
            output.append("Last Balance".center(TOTAL_WIDTH))
            output.append(sep)
            lb_str = (
                f"Ag:{last_balance_silver:.2f} Amt:"
                f"{self._format_currency_locale(last_balance_amount)}"
            )
            output.append(lb_str[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
            output.append(sep)

        output.append("Final Silver & Amount".center(TOTAL_WIDTH))
        output.append(sep)
        net_fine = reg_f - sb_f - ret_gf - ret_sf
        net_fine_display = (
            net_fine + last_balance_silver if last_balance_silver > 0 else net_fine
        )
        net_wage = reg_w - sb_w - ret_gw - ret_sw
        net_wage_display = (
            net_wage + last_balance_amount if last_balance_amount > 0 else net_wage
        )
        silver_cost = net_fine_display * silver_rate
        total_cost = net_wage_display + silver_cost

        output.append(
            f"Fine:{net_fine_display:9.2f} Wage:{net_wage_display:9.2f}"[
                :TOTAL_WIDTH
            ].ljust(TOTAL_WIDTH)
        )
        output.append(
            f"S.Cost:{silver_cost:8.2f} Total:{total_cost:9.2f}"[:TOTAL_WIDTH].ljust(
                TOTAL_WIDTH
            )
        )
        output.append(sep)
        output.append("Note: Goods Not Return"[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
        output.append(" \f")

        return self._build_preformatted_html("\n".join(output), line_height=1.05)
