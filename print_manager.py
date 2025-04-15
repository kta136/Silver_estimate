#!/usr/bin/env python
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QPushButton, QTextEdit,
                             QLabel, QMessageBox, QApplication)
from PyQt5.QtGui import QFont, QTextCursor, QPageSize, QTextDocument
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
import traceback # Keep for debugging


class PrintManager:
    """Class to handle print functionality using manual formatting."""

    def __init__(self, db_manager):
        """Initialize the print manager."""
        self.db_manager = db_manager
        self.printer = QPrinter(QPrinter.HighResolution)
        self.printer.setPageSize(QPageSize(QPageSize.A4))
        self.printer.setOrientation(QPrinter.Portrait)
        # Use margins appropriate for the fixed-width text format
        self.printer.setPageMargins(10, 10, 10, 10, QPrinter.Millimeter)

    def print_estimate(self, voucher_no, parent_widget=None):
        """Print an estimate using manual formatting and preview."""
        estimate_data = self.db_manager.get_estimate_by_voucher(voucher_no)
        if not estimate_data:
            QMessageBox.warning(parent_widget, "Print Error",
                                f"Estimate {voucher_no} not found.")
            return False
        try:
            # Generate manually formatted text based on TBOOK.TXT format
            # using the new flags for identification
            html_text = self._generate_estimate_manual_format(estimate_data)

            preview = QPrintPreviewDialog(self.printer, parent_widget)
            preview.setWindowTitle(f"Print Preview - Estimate {voucher_no}")
            preview.paintRequested.connect(lambda printer: self._print_html(printer, html_text))
            preview.exec_()
            return True
        except Exception as e:
            QMessageBox.critical(parent_widget, "Print Error", f"Error preparing print preview: {e}\n{traceback.format_exc()}")
            return False

    def print_silver_bars(self, status_filter=None, parent_widget=None):
        """Print a list of silver bars using preview."""
        bars = self.db_manager.get_silver_bars(status_filter)
        if not bars:
            status_msg = f" with status '{status_filter}'" if status_filter else ""
            QMessageBox.warning(parent_widget, "Print Error",
                                f"No silver bars{status_msg} found.")
            return False

        try:
            # Generate HTML table for silver bars
            html_text = self._generate_silver_bars_html_table(bars, status_filter)

            preview = QPrintPreviewDialog(self.printer, parent_widget)
            preview.setWindowTitle("Print Preview - Silver Bars")
            # Use a different font/size for the table print if needed
            preview.paintRequested.connect(lambda printer: self._print_html(printer, html_text, table_mode=True))
            preview.exec_()
            return True

        except Exception as e:
            QMessageBox.critical(parent_widget, "Print Error", f"Error preparing print preview: {e}\n{traceback.format_exc()}")
            return False

    def _print_html(self, printer, html_content, table_mode=False):
        """Renders the HTML text (containing PRE or TABLE) to the printer."""
        document = QTextDocument()
        if table_mode:
            # Font for tables - Reverted to 5pt
            font = QFont("Arial", 5)
            document.setDefaultFont(font)
        else:
            # Font for the fixed-width estimate slip - Reverted to 5pt
            font = QFont("Courier New", 5)
            document.setDefaultFont(font)

        document.setHtml(html_content)
        # Match document size to printer paper Rect for potentially better scaling
        document.setPageSize(printer.pageRect(QPrinter.Point).size())
        document.print_(printer)

    def _generate_estimate_manual_format(self, estimate_data):
        """Generate manually formatted text using '|' separators, using flags."""
        header = estimate_data['header']
        items = estimate_data['items']
        voucher_no = header['voucher_no']
        silver_rate = header['silver_rate']

        # Separate items based on is_return and is_silver_bar flags
        regular_items = []      # is_return=0, is_silver_bar=0
        silver_bar_items = []   # is_return=0, is_silver_bar=1
        return_goods = []       # is_return=1, is_silver_bar=0
        return_silver_bars = [] # is_return=1, is_silver_bar=1

        for item in items:
            is_return = item.get('is_return', 0) == 1
            is_silver_bar = item.get('is_silver_bar', 0) == 1

            if is_return:
                if is_silver_bar:
                    return_silver_bars.append(item)
                else:
                    return_goods.append(item)
            else: # Not a return
                if is_silver_bar:
                    silver_bar_items.append(item)
                else:
                    regular_items.append(item)

        # --- Define Column Widths based on TBOOK.TXT ---
        W_FINE = 7
        W_LABOUR = 8
        W_QTY = 9
        W_POLY = 7
        W_NAME = 19
        W_SPER = 7
        W_PCS = 8
        W_WRATE = 8
        TOTAL_WIDTH = W_FINE + 1 + W_LABOUR + 1 + W_QTY + 1 + W_POLY + 1 + W_NAME + 1 + W_SPER + 1 + W_PCS + 1 + W_WRATE # 77

        # --- Helper Function for Formatting Data Line (same as before) ---
        def format_line(*args):
            try:
                fine_str = f"{args[0]:>{W_FINE}.3f}"
                labour_str = f"{args[1]:>{W_LABOUR}.2f}"
                qty_str = f"{args[2]:>{W_QTY}.3f}"  # Gross Wt
                poly_str = f"{args[3]:>{W_POLY}.3f}"
                name_str = f"{str(args[4] or ''):<{W_NAME}.{W_NAME}}"
                sper_str = f"{args[5]:>{W_SPER}.2f}"  # Purity
                pcs_val = args[6]
                pcs_display = str(pcs_val) if pcs_val and pcs_val > 0 else ""
                pcs_str = pcs_display.rjust(W_PCS)
                wrate_str = f"{args[7]:>{W_WRATE}.2f}"

                line = "|".join([fine_str, labour_str, qty_str, poly_str, name_str, sper_str, pcs_str, wrate_str])
                return line[:TOTAL_WIDTH]
            except Exception as e:
                print(f"Error formatting line: {e}, Data: {args}")
                return " " * TOTAL_WIDTH

        # --- Helper Function for Formatting Totals Line (same as before) ---
        def format_totals_line(fine, labour, qty, poly):
            fine_str = f"{fine:{W_FINE}.3f}"
            labour_str = f"{labour:{W_LABOUR}.2f}"
            qty_str = str(int(round(qty))).rjust(W_QTY) # Gross Qty total as integer
            poly_str = f"{poly:{W_POLY}.3f}"
            line_part = "|".join([fine_str, labour_str, qty_str, poly_str])
            remaining_width = TOTAL_WIDTH - len(line_part)
            return line_part + (" " * remaining_width if remaining_width > 0 else "")

        # --- Build the Text Output (Structure remains similar) ---
        output = []
        title = "* * ESTIMATE SLIP ONLY * *"
        pad = (TOTAL_WIDTH - len(title)) // 2
        output.append(" " * pad + title)
        output.append(" ")

        voucher_str = str(voucher_no).ljust(15)
        rate_str = f"S.Rate :{silver_rate:9.2f}"
        pad = max(1, TOTAL_WIDTH - len(voucher_str) - len(rate_str))
        output.append(f"{voucher_str}" + " " * pad + rate_str)

        separator_eq = "=" * TOTAL_WIDTH
        separator_dash = "-" * TOTAL_WIDTH
        output.append(separator_eq)

        h_fine = "Fine".center(W_FINE)
        h_labour = "Labour".center(W_LABOUR)
        h_qty = "Quantity".center(W_QTY)
        h_poly = "Poly".center(W_POLY)
        h_name = "Item Name".center(W_NAME)
        h_sper = "S.Per%".center(W_SPER)
        h_pcs = "Pcs/Doz.".center(W_PCS)
        h_wrate = "W.Rate".center(W_WRATE)
        header_line = "|".join([h_fine, h_labour, h_qty, h_poly, h_name, h_sper, h_pcs, h_wrate])
        output.append(header_line[:TOTAL_WIDTH])
        output.append(separator_eq)

        # --- Process Items and Calculate Totals ---
        reg_fine, reg_wage, reg_gross, reg_poly = 0.0, 0.0, 0.0, 0.0
        sb_fine, sb_wage, sb_gross, sb_poly = 0.0, 0.0, 0.0, 0.0
        ret_goods_fine, ret_goods_wage, ret_goods_gross, ret_goods_poly = 0.0, 0.0, 0.0, 0.0
        ret_silver_fine, ret_silver_wage, ret_silver_gross, ret_silver_poly = 0.0, 0.0, 0.0, 0.0

        # Regular Items Section
        if regular_items:
            for item in regular_items:
                reg_fine += item['fine']
                reg_wage += item['wage']
                reg_gross += item['gross']
                reg_poly += item['poly']
                output.append(format_line(item['fine'], item['wage'], item['gross'], item['poly'],
                                          item['item_name'], item['purity'], item['pieces'], item['wage_rate']))
        else:
            no_items_msg = "-- No Regular Items --"
            pad = (TOTAL_WIDTH - len(no_items_msg)) // 2
            output.append(" " * pad + no_items_msg)

        # Silver Bar Items Section (Non-Return)
        if silver_bar_items:
            output.append(" ")
            sb_title = "* * Silver Bars * *"
            pad = (TOTAL_WIDTH - len(sb_title)) // 2
            output.append(" " * pad + sb_title)
            output.append(separator_dash)
            output.append(header_line[:TOTAL_WIDTH])
            output.append(separator_dash)
            for item in silver_bar_items:
                sb_fine += item['fine']
                sb_wage += item['wage'] # Usually 0
                sb_gross += item['gross']
                sb_poly += item['poly'] # Usually 0
                output.append(format_line(item['fine'], item['wage'], item['gross'], item['poly'],
                                          item['item_name'], item['purity'], 0, 0)) # Pcs/Rate=0 for bars
            output.append(separator_dash)
            output.append(format_totals_line(sb_fine, sb_wage, sb_gross, sb_poly))
            output.append(separator_dash)

        # Combined Regular + Bar Totals Line
        output.append(separator_eq)
        combined_reg_bar_fine = reg_fine + sb_fine
        combined_reg_bar_wage = reg_wage + sb_wage
        combined_reg_bar_gross = reg_gross + sb_gross
        combined_reg_bar_poly = reg_poly + sb_poly
        output.append(format_totals_line(combined_reg_bar_fine, combined_reg_bar_wage, combined_reg_bar_gross, combined_reg_bar_poly))
        output.append(separator_eq)

        # Return Goods Section
        if return_goods:
            output.append(" ")
            rg_title = "* * Return Goods * *"
            pad = (TOTAL_WIDTH - len(rg_title)) // 2
            output.append(" " * pad + rg_title)
            output.append(separator_dash)
            output.append(header_line[:TOTAL_WIDTH])
            output.append(separator_dash)
            for item in return_goods:
                ret_goods_fine += item['fine']
                ret_goods_wage += item['wage']
                ret_goods_gross += item['gross']
                ret_goods_poly += item['poly']
                output.append(format_line(item['fine'], item['wage'], item['gross'], item['poly'],
                                          item['item_name'], item['purity'], item['pieces'], item['wage_rate']))
            output.append(separator_dash)
            output.append(format_totals_line(ret_goods_fine, ret_goods_wage, ret_goods_gross, ret_goods_poly))
            output.append(separator_dash)

        # Return Silver Bars Section
        if return_silver_bars:
            output.append(" ")
            rsb_title = "* * Return Silver Bar * *"
            pad = (TOTAL_WIDTH - len(rsb_title)) // 2
            output.append(" " * pad + rsb_title)
            output.append(separator_dash)
            output.append(header_line[:TOTAL_WIDTH])
            output.append(separator_dash)
            for item in return_silver_bars:
                ret_silver_fine += item['fine']
                ret_silver_wage += item['wage'] # Usually 0
                ret_silver_gross += item['gross']
                ret_silver_poly += item['poly'] # Usually 0
                output.append(format_line(item['fine'], item['wage'], item['gross'], item['poly'],
                                          item['item_name'], item['purity'], 0, 0)) # Pcs/Rate=0 for bars
            output.append(separator_dash)
            output.append(format_totals_line(ret_silver_fine, ret_silver_wage, ret_silver_gross, ret_silver_poly))
            output.append(separator_dash)

        # Final Summary Section
        output.append(" ")
        final_title = "Final Silver & Amount"
        pad = (TOTAL_WIDTH - len(final_title)) // 2
        output.append(" " * pad + final_title)
        output.append(separator_eq)

        # Calculate Net Fine and Wage based on the summed categories
        net_fine = combined_reg_bar_fine - (ret_goods_fine + ret_silver_fine)
        net_wage = combined_reg_bar_wage - (ret_goods_wage + ret_silver_wage)
        silver_cost = net_fine * silver_rate
        total_cost = net_wage + silver_cost

        fine_str = f"{net_fine:{W_FINE}.3f}"
        wage_str = f"{net_wage:{W_LABOUR}.2f}"
        scost_str = f"S.Cost : {silver_cost:,.2f}"
        total_str = f"Total: {total_cost:,.2f}"

        # Formatting the final line (same logic as before)
        part1_len = W_FINE + 1 + W_LABOUR
        total_field_width = 18
        scost_field_width = 22
        total_padded = total_str.rjust(total_field_width)
        scost_padded = scost_str.rjust(scost_field_width)
        space_before_scost_total = TOTAL_WIDTH - part1_len - len(scost_padded) - len(total_padded)
        pad_after_labour = max(1, space_before_scost_total - 1)
        pad_between_fields = 1
        final_line = f"{fine_str}|{wage_str}" + (" " * pad_after_labour) + scost_padded + (" " * pad_between_fields) + total_padded

        output.append(final_line[:TOTAL_WIDTH])
        output.append(separator_eq)
        output.append(" ")
        note = "Note :-  G O O D S   N O T   R E T U R N"
        pad = (TOTAL_WIDTH - len(note)) // 2
        output.append(" " * pad + note)
        output.append(" \f") # Form feed character

        # --- Combine into HTML ---
        html_content = "\n".join(output)

        # HTML structure - Reverted font size in <pre> tag
        html = f"""<!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">
    <style>
        pre {{
            font-family: 'Courier New', Courier, monospace;
            font-size: 5pt; /* Reverted font size */
            line-height: 1.0;
            white-space: pre;
            margin: 0; padding: 0;
            page-break-inside: avoid;
        }}
        body {{ margin: 10mm; }}
    </style>
    </head>
    <body>
    <pre>{html_content}</pre>
    </body>
    </html>"""
        return html

    def _generate_silver_bars_html_table(self, bars, status_filter=None):
        # --- HTML TABLE version - Reverted font sizes in CSS ---
        status_text = f" - {status_filter}" if status_filter else " - All"
        current_date = QDate.currentDate().toString("yyyy-MM-dd")

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Silver Bar Inventory</title>
            <style>
                body {{ font-family: Arial, sans-serif; font-size: 5pt; margin: 10mm; }} /* Reverted size */
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 10px; page-break-inside: auto; }}
                th, td {{ border: 1px solid #ccc; padding: 3px 5px; text-align: left; word-wrap: break-word; }}
                tr {{ page-break-inside: avoid; page-break-after: auto; }}
                thead {{ display: table-header-group; }}
                th {{ border-bottom: 1px solid #000; background-color: #f0f0f0; font-weight: bold;}}
                .header-title {{ text-align: center; font-size: 5pt; font-weight: bold; margin-bottom: 5px; }} /* Reverted size */
                .sub-header {{ display: flex; justify-content: space-between; margin-bottom: 10px; font-weight: bold;}}
                .totals {{ margin-top: 10px; font-weight: bold; border-top: 1px double #000; padding-top: 5px; }}
                .right {{ text-align: right; }}
            </style>
        </head>
        <body>
            <div class="header-title">SILVER BARS INVENTORY{status_text}</div>
            <div class="sub-header">
                <span></span> <!-- Spacer -->
                <span>Print Date: {current_date}</span>
            </div>

            <table>
                <thead>
                    <tr>
                        <th>Bar No.</th>
                        <th class="right">Weight(g)</th>
                        <th class="right">Purity(%)</th>
                        <th class="right">Fine Wt(g)</th>
                        <th>Date Added</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
        """

        total_weight = 0
        total_fine = 0
        bar_count = 0

        if bars:
            for bar in bars:
                bar_weight = bar.get('weight', 0.0)
                bar_fine_weight = bar.get('fine_weight', 0.0)
                bar_purity = bar.get('purity', 0.0)
                bar_no = bar.get('bar_no', '')
                date_added = bar.get('date_added', '')
                status = bar.get('status', '')

                bar_count += 1
                total_weight += bar_weight
                total_fine += bar_fine_weight
                html += f"""
                    <tr>
                        <td>{bar_no}</td>
                        <td class="right">{bar_weight:.3f}</td>
                        <td class="right">{bar_purity:.2f}</td>
                        <td class="right">{bar_fine_weight:.3f}</td>
                        <td>{date_added}</td>
                        <td>{status}</td>
                    </tr>"""
        else:
            html += '<tr><td colspan="6" style="text-align:center; padding: 5px 0;">-- No Bars Found --</td></tr>'

        html += f"""
                </tbody>
            </table>
            <div class="totals">
                TOTAL Weight: {total_weight:,.3f} g | TOTAL Fine Wt: {total_fine:,.3f} g | TOTAL Bars: {bar_count}
            </div>
        </body>
        </html>
        """
        return html