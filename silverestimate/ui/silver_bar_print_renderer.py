"""Silver bar print rendering helpers extracted from PrintManager."""

from __future__ import annotations

import html as html_lib

from PyQt5.QtCore import QDate


class SilverBarPrintRenderer:
    """Render silver bar reports into HTML tables for preview and export."""

    @staticmethod
    def generate_inventory_html_table(bars, status_filter=None):
        """Generate HTML table for the general inventory report."""
        status_text = (
            f" - {html_lib.escape(str(status_filter))}" if status_filter else " - All"
        )
        current_date = html_lib.escape(QDate.currentDate().toString("yyyy-MM-dd"))
        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Silver Bar Inventory</title><style>
                   body{{font-family:Arial,sans-serif;font-size:8pt;margin:0;}}
                   table{{border-collapse:collapse;width:100%;margin-bottom:10px;page-break-inside:auto}}
                   th,td{{border:1px solid #ccc;padding:4px 6px;text-align:left;word-wrap:break-word}}
                   tr{{page-break-inside:avoid;page-break-after:auto}} thead{{display:table-header-group}}
                   th{{border-bottom:1px solid #000;background-color:#f0f0f0;font-weight:bold}}
                   .header-title{{text-align:center;font-size:10pt;font-weight:bold;margin-bottom:5px}}
                   .sub-header{{display:flex;justify-content:space-between;margin-bottom:10px;font-weight:bold}}
                   .totals{{margin-top:10px;font-weight:bold;border-top:1px double #000;padding-top:5px;text-align:right}}
                   .right{{text-align:right}}</style></head><body>
                   <div class="header-title">SILVER BARS INVENTORY{status_text}</div>
                   <div class="sub-header"><span></span><span>Print Date: {current_date}</span></div>
                   <table><thead><tr><th>Bar ID</th><th>Estimate Vch</th><th class="right">Weight(g)</th><th class="right">Purity(%)</th>
                   <th class="right">Fine Wt(g)</th><th>Date Added</th><th>Status</th></tr></thead><tbody>"""
        total_weight = 0.0
        total_fine = 0.0
        bar_count = 0
        if bars:
            for bar in bars:
                bw = (
                    bar["weight"]
                    if "weight" in bar.keys() and bar["weight"] is not None
                    else 0.0
                )
                bfw = (
                    bar["fine_weight"]
                    if "fine_weight" in bar.keys() and bar["fine_weight"] is not None
                    else 0.0
                )
                bp = (
                    bar["purity"]
                    if "purity" in bar.keys() and bar["purity"] is not None
                    else 0.0
                )
                bid = (
                    bar["bar_id"]
                    if "bar_id" in bar.keys() and bar["bar_id"] is not None
                    else "N/A"
                )
                evch = (
                    bar["estimate_voucher_no"]
                    if "estimate_voucher_no" in bar.keys()
                    and bar["estimate_voucher_no"] is not None
                    else "N/A"
                )
                da = (
                    bar["date_added"]
                    if "date_added" in bar.keys() and bar["date_added"] is not None
                    else ""
                )
                st = (
                    bar["status"]
                    if "status" in bar.keys() and bar["status"] is not None
                    else ""
                )

                bar_count += 1
                total_weight += bw
                total_fine += bfw

                html += f"""<tr>
                    <td>{html_lib.escape(str(bid))}</td>
                    <td>{html_lib.escape(str(evch))}</td>
                    <td class="right">{bw:.3f}</td>
                    <td class="right">{bp:.2f}</td>
                    <td class="right">{bfw:.3f}</td>
                    <td>{html_lib.escape(str(da))}</td>
                    <td>{html_lib.escape(str(st))}</td>
                </tr>"""
        else:
            html += '<tr><td colspan="7" style="text-align:center;padding:5px 0;">-- No Bars Found --</td></tr>'
        html += f"""</tbody></table><div class="totals">TOTAL Bars: {bar_count} | TOTAL Weight: {total_weight:,.3f} g | TOTAL Fine Wt: {total_fine:,.3f} g</div></body></html>"""
        return html

    @staticmethod
    def generate_list_details_html(list_info, bars_in_list):
        """Generate HTML content for printing a single list's details."""
        li = (
            list_info["list_identifier"]
            if "list_identifier" in list_info.keys()
            and list_info["list_identifier"] is not None
            else "N/A"
        )
        ln = (
            list_info["list_note"]
            if "list_note" in list_info.keys() and list_info["list_note"] is not None
            else ""
        )
        li_display = html_lib.escape(str(li))
        ln_display = html_lib.escape(str(ln)) if ln else "N/A"

        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Silver Bar List - {li_display}</title><style>
                   body{{font-family:Arial,sans-serif;font-size:8pt;margin:0}}table{{border-collapse:collapse;width:100%;margin-top:15px;page-break-inside:auto}}
                   th,td{{border:1px solid #ccc;padding:4px 6px;text-align:left;word-wrap:break-word}}tr{{page-break-inside:avoid;page-break-after:auto}}
                   thead{{display:table-header-group}}th{{border-bottom:1px solid #000;background-color:#f0f0f0;font-weight:bold}}
                   .header-title{{text-align:center;font-size:12pt;font-weight:bold;margin-bottom:10px}}.list-info{{margin-bottom:15px}}
                   .list-info span{{display:inline-block;margin-right:20px}}.list-note{{margin-top:5px;border:1px solid #eee;padding:5px;background-color:#f9f9f9}}
                   .totals{{margin-top:15px;font-weight:bold;border-top:1px double #000;padding-top:5px;text-align:right}}.right{{text-align:right}}</style></head><body>
                   <div class="header-title">Silver Bar List Details</div>
                   <div class="list-info">
                       <span><b>List ID:</b> {li_display}</span>
                    </div>
                   <div class="list-note"><b>Note:</b> {ln_display}</div>
                    <table>
                        <thead>
                            <tr>
                                <th>#</th>
                                <th class="right">Weight (g)</th>
                                <th class="right">Purity (%)</th>
                                <th class="right">Fine Wt (g)</th>
                            </tr>
                        </thead>
                       <tbody>"""
        total_weight = 0.0
        total_fine = 0.0
        bar_count = 0
        if bars_in_list:
            for idx, bar in enumerate(bars_in_list):
                bw = (
                    bar["weight"]
                    if "weight" in bar.keys() and bar["weight"] is not None
                    else 0.0
                )
                bfw = (
                    bar["fine_weight"]
                    if "fine_weight" in bar.keys() and bar["fine_weight"] is not None
                    else 0.0
                )
                bp = (
                    bar["purity"]
                    if "purity" in bar.keys() and bar["purity"] is not None
                    else 0.0
                )

                bar_count += 1
                total_weight += bw
                total_fine += bfw
                html += f"""<tr>
                               <td>{idx + 1}</td>
                               <td class="right">{bw:.3f}</td>
                               <td class="right">{bp:.2f}</td>
                               <td class="right">{bfw:.3f}</td>
                           </tr>"""
        else:
            html += '<tr><td colspan="4" style="text-align:center;padding:10px 0;">-- No bars assigned --</td></tr>'

        html += f"""</tbody></table>
                   <div class="totals">TOTAL Bars: {bar_count} | TOTAL Weight: {total_weight:,.3f} g | TOTAL Fine Wt: {total_fine:,.3f} g</div>
                   </body></html>"""
        return html
