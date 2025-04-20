#!/usr/bin/env python
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QPushButton, QTextEdit,
                             QLabel, QMessageBox, QApplication)
from PyQt5.QtGui import QFont, QTextCursor, QPageSize, QTextDocument
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
import traceback # Keep for debugging


from PyQt5.QtGui import QFont, QTextCursor, QPageSize, QTextDocument, QFontDatabase # Added QFontDatabase

class PrintManager:
    """Class to handle print functionality using manual formatting."""

    def __init__(self, db_manager, print_font=None):
        """Initialize the print manager, accepting an optional print font."""
        self.db_manager = db_manager
        # Store the custom print font if provided, otherwise use a default
        if print_font:
            self.print_font = print_font
        else:
            # Default font if none is provided via settings
            self.print_font = QFont("Courier New", 5)
            self.print_font.float_size = 5.0 # Set default float size

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
        """Prints the INVENTORY list of silver bars using preview."""
        bars = self.db_manager.get_silver_bars(status_filter)
        if not bars:
            status_msg = f" with status '{status_filter}'" if status_filter else ""
            QMessageBox.warning(parent_widget, "Print Error",
                                f"No silver bars{status_msg} found.")
            return False

        try:
            # Generate HTML table for silver bars inventory report
            html_text = self._generate_silver_bars_html_table(bars, status_filter)

            preview = QPrintPreviewDialog(self.printer, parent_widget)
            preview.setWindowTitle("Print Preview - Silver Bar Inventory")
            # Use table mode for printing
            preview.paintRequested.connect(lambda printer: self._print_html(printer, html_text, table_mode=True))
            preview.exec_()
            return True

        except Exception as e:
            QMessageBox.critical(parent_widget, "Print Error", f"Error preparing inventory print preview: {e}\n{traceback.format_exc()}")
            return False

    # --- NEW METHOD for Printing Specific List Details ---
    def print_silver_bar_list_details(self, list_info, bars_in_list, parent_widget=None):
        """Generates and previews/prints details of a specific silver bar list."""
        if not list_info:
            QMessageBox.warning(parent_widget, "Print Error", "List information is missing.")
            return False

        try:
            html_content = self._generate_list_details_html(list_info, bars_in_list)
            preview = QPrintPreviewDialog(self.printer, parent_widget)
            preview.setWindowTitle(f"Print Preview - List {list_info.get('list_identifier', 'N/A')}")
            # Use table mode for printing
            preview.paintRequested.connect(lambda printer: self._print_html(printer, html_content, table_mode=True))
            preview.exec_()
            return True
        except Exception as e:
            QMessageBox.critical(parent_widget, "Print Error", f"Error preparing list print preview: {e}\n{traceback.format_exc()}")
            return False
    # --- END NEW METHOD ---


    def _print_html(self, printer, html_content, table_mode=False):
        """Renders the HTML text (containing PRE or TABLE) to the printer."""
        document = QTextDocument()
        if table_mode:
            # Font for tables - Use a readable size
            # Font for tables (Inventory, List Details) - Use a readable size, independent of print_font setting
            table_font = QFont("Arial", 8)
            document.setDefaultFont(table_font)
        else:
            # Font for the fixed-width estimate slip - Use the stored print_font
            # QFont needs integer size, use rounded value from stored float size
            font_size_int = int(round(getattr(self.print_font, 'float_size', 5.0)))
            font_to_use = QFont(self.print_font.family(), font_size_int)
            font_to_use.setBold(self.print_font.bold())
            document.setDefaultFont(font_to_use)

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
                if is_silver_bar: return_silver_bars.append(item)
                else: return_goods.append(item)
            else:
                if is_silver_bar: silver_bar_items.append(item)
                else: regular_items.append(item)

        # --- Column Widths ---
        W_FINE=7; W_LABOUR=8; W_QTY=9; W_POLY=7; W_NAME=19; W_SPER=7; W_PCS=8; W_WRATE=8
        TOTAL_WIDTH = W_FINE+1+W_LABOUR+1+W_QTY+1+W_POLY+1+W_NAME+1+W_SPER+1+W_PCS+1+W_WRATE

        # --- Format Helpers ---
        def format_line(*args):
            try:
                fine = f"{args[0]:>{W_FINE}.3f}"; labour = f"{args[1]:>{W_LABOUR}.2f}"
                qty = f"{args[2]:>{W_QTY}.3f}"; poly = f"{args[3]:>{W_POLY}.3f}"
                name = f"{str(args[4] or ''):<{W_NAME}.{W_NAME}}"; sper = f"{args[5]:>{W_SPER}.2f}"
                pcs_val = args[6]; pcs_display = str(pcs_val) if pcs_val and pcs_val > 0 else ""
                pcs = pcs_display.rjust(W_PCS); wrate = f"{args[7]:>{W_WRATE}.2f}"
                line = "|".join([fine, labour, qty, poly, name, sper, pcs, wrate])
                return line[:TOTAL_WIDTH]
            except Exception as e: print(f"Error formatting line: {e}, Data: {args}"); return " " * TOTAL_WIDTH

        def format_totals_line(fine, labour, qty, poly):
            fine_str=f"{fine:{W_FINE}.3f}"; labour_str=f"{labour:{W_LABOUR}.2f}"
            qty_str=str(int(round(qty))).rjust(W_QTY); poly_str=f"{poly:{W_POLY}.3f}"
            line_part="|".join([fine_str, labour_str, qty_str, poly_str])
            rem_w = TOTAL_WIDTH - len(line_part)
            return line_part + (" " * rem_w if rem_w > 0 else "")

        # --- Build Output ---
        output = []; title = "* * ESTIMATE SLIP ONLY * *"; pad = (TOTAL_WIDTH - len(title)) // 2
        output.append(" " * pad + title); output.append(" ")
        voucher_str = str(voucher_no).ljust(15); rate_str = f"S.Rate :{silver_rate:9.2f}"
        pad = max(1, TOTAL_WIDTH - len(voucher_str) - len(rate_str)); output.append(f"{voucher_str}" + " " * pad + rate_str)
        sep_eq = "=" * TOTAL_WIDTH; sep_dash = "-" * TOTAL_WIDTH; output.append(sep_eq)
        h_fine="Fine".center(W_FINE); h_labour="Labour".center(W_LABOUR); h_qty="Quantity".center(W_QTY); h_poly="Poly".center(W_POLY)
        h_name="Item Name".center(W_NAME); h_sper="S.Per%".center(W_SPER); h_pcs="Pcs/Doz.".center(W_PCS); h_wrate="W.Rate".center(W_WRATE)
        header_line = "|".join([h_fine, h_labour, h_qty, h_poly, h_name, h_sper, h_pcs, h_wrate]); output.append(header_line[:TOTAL_WIDTH]); output.append(sep_eq)

        # Totals vars
        reg_f, reg_w, reg_g, reg_p = 0.0,0.0,0.0,0.0; sb_f, sb_w, sb_g, sb_p = 0.0,0.0,0.0,0.0
        ret_gf, ret_gw, ret_gg, ret_gp = 0.0,0.0,0.0,0.0; ret_sf, ret_sw, ret_sg, ret_sp = 0.0,0.0,0.0,0.0

        # Process Sections
        if regular_items:
            for item in regular_items:
                reg_f+=item['fine']; reg_w+=item['wage']; reg_g+=item['gross']; reg_p+=item['poly']
                output.append(format_line(item['fine'],item['wage'],item['gross'],item['poly'],item['item_name'],item['purity'],item['pieces'],item['wage_rate']))
        else: output.append(" " * ((TOTAL_WIDTH - 22)//2) + "-- No Regular Items --")

        if silver_bar_items:
            output.append(" "); sb_title="* * Silver Bars * *"; pad=(TOTAL_WIDTH-len(sb_title))//2; output.append(" "*pad+sb_title); output.append(sep_dash); output.append(header_line[:TOTAL_WIDTH]); output.append(sep_dash)
            for item in silver_bar_items:
                sb_f+=item['fine']; sb_w+=item['wage']; sb_g+=item['gross']; sb_p+=item['poly']
                output.append(format_line(item['fine'],item['wage'],item['gross'],item['poly'],item['item_name'],item['purity'],0,0))
            output.append(sep_dash); output.append(format_totals_line(sb_f,sb_w,sb_g,sb_p)); output.append(sep_dash)

        output.append(sep_eq); comb_f=reg_f+sb_f; comb_w=reg_w+sb_w; comb_g=reg_g+sb_g; comb_p=reg_p+sb_p; output.append(format_totals_line(comb_f,comb_w,comb_g,comb_p)); output.append(sep_eq)

        if return_goods:
            output.append(" "); rg_title="* * Return Goods * *"; pad=(TOTAL_WIDTH-len(rg_title))//2; output.append(" "*pad+rg_title); output.append(sep_dash); output.append(header_line[:TOTAL_WIDTH]); output.append(sep_dash)
            for item in return_goods:
                ret_gf+=item['fine']; ret_gw+=item['wage']; ret_gg+=item['gross']; ret_gp+=item['poly']
                output.append(format_line(item['fine'],item['wage'],item['gross'],item['poly'],item['item_name'],item['purity'],item['pieces'],item['wage_rate']))
            output.append(sep_dash); output.append(format_totals_line(ret_gf,ret_gw,ret_gg,ret_gp)); output.append(sep_dash)

        if return_silver_bars:
            output.append(" "); rsb_title="* * Return Silver Bar * *"; pad=(TOTAL_WIDTH-len(rsb_title))//2; output.append(" "*pad+rsb_title); output.append(sep_dash); output.append(header_line[:TOTAL_WIDTH]); output.append(sep_dash)
            for item in return_silver_bars:
                ret_sf+=item['fine']; ret_sw+=item['wage']; ret_sg+=item['gross']; ret_sp+=item['poly']
                output.append(format_line(item['fine'],item['wage'],item['gross'],item['poly'],item['item_name'],item['purity'],0,0))
            output.append(sep_dash); output.append(format_totals_line(ret_sf,ret_sw,ret_sg,ret_sp)); output.append(sep_dash)

        # Final Summary
        output.append(" "); final_title="Final Silver & Amount"; pad=(TOTAL_WIDTH-len(final_title))//2; output.append(" "*pad+final_title); output.append(sep_eq)
        net_fine = comb_f - (ret_gf + ret_sf); net_wage = comb_w - (ret_gw + ret_sw)
        silver_cost = net_fine * silver_rate; total_cost = net_wage + silver_cost
        fine_str = f"{net_fine:{W_FINE}.3f}"; wage_str = f"{net_wage:{W_LABOUR}.2f}"
        scost_str = f"S.Cost : {silver_cost:,.2f}"; total_str = f"Total: {total_cost:,.2f}"
        part1_len=W_FINE+1+W_LABOUR; tfw=18; scfw=22; total_pad=total_str.rjust(tfw); scost_pad=scost_str.rjust(scfw)
        space_before = TOTAL_WIDTH - part1_len - len(scost_pad) - len(total_pad)
        pad_after_labour=max(1, space_before - 1); pad_between=1
        final_line = f"{fine_str}|{wage_str}" + (" "*pad_after_labour) + scost_pad + (" "*pad_between) + total_pad
        output.append(final_line[:TOTAL_WIDTH]); output.append(sep_eq); output.append(" ")
        note = "Note :-  G O O D S   N O T   R E T U R N"; pad=(TOTAL_WIDTH-len(note))//2; output.append(" "*pad+note); output.append(" \f")

        # --- Combine into HTML ---
        # Use the stored print font SIZE and WEIGHT, but FORCE MONOSPACE family for alignment
        # font_family = self.print_font.family() # Ignore selected family for estimate print
        font_size_pt = getattr(self.print_font, 'float_size', 5.0) # Use selected size
        font_weight = "bold" if self.print_font.bold() else "normal" # Use selected weight

        html_content = "\n".join(output)
        # Update CSS: Force Courier New / monospace, but use selected size and weight
        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
                    pre {{
                        font-family: 'Courier New', Courier, monospace; /* FORCE monospace */
                        font-size: {font_size_pt}pt; /* Use selected size */
                        font-weight: {font_weight}; /* Use selected weight */
                        line-height: 1.0;
                        white-space: pre;
                        margin: 0;
                        padding: 0;
                        page-break-inside: avoid;
                    }}
                    body {{ margin: 10mm; }}
                    </style></head><body><pre>{html_content}</pre></body></html>"""
        return html # Correct indentation

    def _generate_silver_bars_html_table(self, bars, status_filter=None):
        """Generates HTML table for the general INVENTORY report."""
        status_text = f" - {status_filter}" if status_filter else " - All"; current_date = QDate.currentDate().toString("yyyy-MM-dd")
        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Silver Bar Inventory</title><style>
                   body{{font-family:Arial,sans-serif;font-size:8pt;margin:10mm;}} /* Increased font size */
                   table{{border-collapse:collapse;width:100%;margin-bottom:10px;page-break-inside:auto}}
                   th,td{{border:1px solid #ccc;padding:4px 6px;text-align:left;word-wrap:break-word}}
                   tr{{page-break-inside:avoid;page-break-after:auto}} thead{{display:table-header-group}}
                   th{{border-bottom:1px solid #000;background-color:#f0f0f0;font-weight:bold}}
                   .header-title{{text-align:center;font-size:10pt;font-weight:bold;margin-bottom:5px}} /* Increased font size */
                   .sub-header{{display:flex;justify-content:space-between;margin-bottom:10px;font-weight:bold}}
                   .totals{{margin-top:10px;font-weight:bold;border-top:1px double #000;padding-top:5px;text-align:right}}
                   .right{{text-align:right}}</style></head><body>
                   <div class="header-title">SILVER BARS INVENTORY{status_text}</div>
                   <div class="sub-header"><span></span><span>Print Date: {current_date}</span></div>
                   <table><thead><tr><th>Bar No.</th><th class="right">Weight(g)</th><th class="right">Purity(%)</th>
                   <th class="right">Fine Wt(g)</th><th>Date Added</th><th>Status</th></tr></thead><tbody>"""
        total_weight = 0.0; total_fine = 0.0; bar_count = 0
        if bars:
            for bar in bars: # Assume bar is sqlite3.Row
                bw=bar['weight'] if bar['weight'] is not None else 0.0; bfw=bar['fine_weight'] if bar['fine_weight'] is not None else 0.0
                bp=bar['purity'] if bar['purity'] is not None else 0.0; bno=bar['bar_no'] if bar['bar_no'] is not None else ''
                da=bar['date_added'] if bar['date_added'] is not None else ''; st=bar['status'] if bar['status'] is not None else ''
                bar_count+=1; total_weight+=bw; total_fine+=bfw
                html += f"""<tr><td>{bno}</td><td class="right">{bw:.3f}</td><td class="right">{bp:.2f}</td><td class="right">{bfw:.3f}</td><td>{da}</td><td>{st}</td></tr>"""
        else: html += '<tr><td colspan="6" style="text-align:center;padding:5px 0;">-- No Bars Found --</td></tr>'
        html += f"""</tbody></table><div class="totals">TOTAL Bars: {bar_count} | TOTAL Weight: {total_weight:,.3f} g | TOTAL Fine Wt: {total_fine:,.3f} g</div></body></html>"""
        return html

    def _generate_list_details_html(self, list_info, bars_in_list):
        """Generates HTML content for printing a single list's details."""
        li=list_info.get('list_identifier','N/A'); cd=list_info.get('creation_date','N/A'); ln=list_info.get('list_note',''); pd=QDate.currentDate().toString("yyyy-MM-dd")
        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Silver Bar List - {li}</title><style>
                   body{{font-family:Arial,sans-serif;font-size:8pt;margin:10mm}}table{{border-collapse:collapse;width:100%;margin-top:15px;page-break-inside:auto}}
                   th,td{{border:1px solid #ccc;padding:4px 6px;text-align:left;word-wrap:break-word}}tr{{page-break-inside:avoid;page-break-after:auto}}
                   thead{{display:table-header-group}}th{{border-bottom:1px solid #000;background-color:#f0f0f0;font-weight:bold}}
                   .header-title{{text-align:center;font-size:12pt;font-weight:bold;margin-bottom:10px}}.list-info{{margin-bottom:15px}}
                   .list-info span{{display:inline-block;margin-right:20px}}.list-note{{margin-top:5px;border:1px solid #eee;padding:5px;background-color:#f9f9f9}}
                   .totals{{margin-top:15px;font-weight:bold;border-top:1px double #000;padding-top:5px;text-align:right}}.right{{text-align:right}}</style></head><body>
                   <div class="header-title">Silver Bar List Details</div><div class="list-info"><span><b>List ID:</b> {li}</span><span><b>Created:</b> {cd}</span><span><b>Printed:</b> {pd}</span></div>
                   <div class="list-note"><b>Note:</b> {ln if ln else 'N/A'}</div>
                   <table><thead><tr><th>#</th><th>Bar Number</th><th class="right">Weight (g)</th><th class="right">Purity (%)</th><th class="right">Fine Wt (g)</th><th>Status</th></tr></thead><tbody>"""
        tw=0.0; tf=0.0; bc=0
        if bars_in_list:
            for idx, bar in enumerate(bars_in_list):
                bw=bar['weight'] if bar['weight'] is not None else 0.0; bfw=bar['fine_weight'] if bar['fine_weight'] is not None else 0.0
                bp=bar['purity'] if bar['purity'] is not None else 0.0; bno=bar['bar_no'] if bar['bar_no'] is not None else 'N/A'; st=bar['status'] if bar['status'] is not None else 'N/A'
                bc+=1; tw+=bw; tf+=bfw
                html += f"""<tr><td>{idx+1}</td><td>{bno}</td><td class="right">{bw:.3f}</td><td class="right">{bp:.2f}</td><td class="right">{bfw:.3f}</td><td>{st}</td></tr>"""
        else: html += '<tr><td colspan="6" style="text-align:center;padding:10px 0;">-- No bars assigned --</td></tr>'
        html += f"""</tbody></table><div class="totals">TOTAL Bars: {bc} | TOTAL Weight: {tw:,.3f} g | TOTAL Fine Wt: {tf:,.3f} g</div></body></html>"""
        return html
