#!/usr/bin/env python
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QPushButton, QTextEdit,
                             QLabel, QMessageBox, QApplication)
from PyQt5.QtGui import QFont, QTextCursor, QPageSize, QTextDocument, QFontDatabase
from PyQt5.QtCore import Qt, QDate
# Import QPrintPreviewWidget
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog, QPrintPreviewWidget
import traceback # Keep for debugging
import math # For rounding

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
            # Force Courier New for estimate slip, but use size/bold from settings
            default_size = 7.0 # Default size if setting unavailable
            font_size_int = int(round(getattr(print_font, 'float_size', default_size)))
            is_bold = getattr(print_font, 'bold', lambda: False)() # Check if bold exists and call
            self.print_font = QFont("Courier New", font_size_int)
            self.print_font.setBold(is_bold)
            # Store float size for consistency if needed elsewhere, though not used directly here
            self.print_font.float_size = float(font_size_int) if not hasattr(print_font, 'float_size') else print_font.float_size


        self.printer = QPrinter(QPrinter.HighResolution)
        self.printer.setPageSize(QPageSize(QPageSize.A4))
        self.printer.setOrientation(QPrinter.Portrait)
        # Use margins appropriate for the fixed-width text format
        self.printer.setPageMargins(10, 10, 10, 10, QPrinter.Millimeter)

    def format_indian_rupees(self, number):
        """Formats a number into Indian Rupees notation (Lakhs, Crores)."""
        # Ensure number is integer after rounding
        num = int(round(number))
        s = str(num)
        n = len(s)
        if n <= 3:
            return s
        # Format the last three digits
        last_three = s[-3:]
        # Format the remaining digits in groups of two
        other_digits = s[:-3]
        if not other_digits:
             return last_three # Handle cases like 123

        # Reverse the other_digits string for easier processing
        other_digits_rev = other_digits[::-1]
        formatted_other_rev = ""
        for i, digit in enumerate(other_digits_rev):
            formatted_other_rev += digit
            # Add comma after every second digit (except at the end)
            if (i + 1) % 2 == 0 and (i + 1) != len(other_digits_rev):
                formatted_other_rev += ","

        # Reverse the formatted string back
        formatted_other = formatted_other_rev[::-1]
        return formatted_other + "," + last_three


    def print_estimate(self, voucher_no, parent_widget=None):
        """Print an estimate using manual formatting and preview."""
        estimate_data = self.db_manager.get_estimate_by_voucher(voucher_no)
        if not estimate_data:
            QMessageBox.warning(parent_widget, "Print Error",
                                f"Estimate {voucher_no} not found.")
            return False
        try:
            html_text = self._generate_estimate_manual_format(estimate_data)

            preview = QPrintPreviewDialog(self.printer, parent_widget)
            preview.setWindowTitle(f"Print Preview - Estimate {voucher_no}")
            preview.paintRequested.connect(lambda printer: self._print_html(printer, html_text))

            # --- Set initial zoom and maximize ---
            try:
                preview_widget = preview.findChild(QPrintPreviewWidget)
                if preview_widget:
                    preview_widget.setZoomFactor(1.25) # Set zoom to 125%
                else:
                    print("Warning: Could not find QPrintPreviewWidget to set zoom.")
            except Exception as zoom_err:
                print(f"Warning: Error setting initial zoom: {zoom_err}")

            preview.showMaximized() # Show maximized
            # ------------------------------------

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
            html_text = self._generate_silver_bars_html_table(bars, status_filter)

            preview = QPrintPreviewDialog(self.printer, parent_widget)
            preview.setWindowTitle("Print Preview - Silver Bar Inventory")
            preview.paintRequested.connect(lambda printer: self._print_html(printer, html_text, table_mode=True))
            preview.exec_()
            return True

        except Exception as e:
            QMessageBox.critical(parent_widget, "Print Error", f"Error preparing inventory print preview: {e}\n{traceback.format_exc()}")
            return False

    def print_silver_bar_list_details(self, list_info, bars_in_list, parent_widget=None):
        """Generates and previews/prints details of a specific silver bar list."""
        if not list_info:
            QMessageBox.warning(parent_widget, "Print Error", "List information is missing.")
            return False

        try:
            html_content = self._generate_list_details_html(list_info, bars_in_list)
            preview = QPrintPreviewDialog(self.printer, parent_widget)
            preview.setWindowTitle(f"Print Preview - List {list_info['list_identifier'] if 'list_identifier' in list_info.keys() and list_info['list_identifier'] is not None else 'N/A'}")
            preview.paintRequested.connect(lambda printer: self._print_html(printer, html_content, table_mode=True))
            preview.exec_()
            return True
        except Exception as e:
            QMessageBox.critical(parent_widget, "Print Error", f"Error preparing list print preview: {e}\n{traceback.format_exc()}")
            return False


    def _print_html(self, printer, html_content, table_mode=False):
        """Renders the HTML text (containing PRE or TABLE) to the printer."""
        document = QTextDocument()
        if table_mode:
            table_font = QFont("Arial", 8)
            document.setDefaultFont(table_font)
        else:
            # Estimate slip: Use the stored print_font settings
            font_size_int = int(round(getattr(self.print_font, 'float_size', 7.0))) # Default 7pt
            # Force Courier New for alignment, but use stored size/bold
            font_to_use = QFont("Courier New", font_size_int)
            is_bold = getattr(self.print_font, 'bold', lambda: False)() # Safely check bold
            font_to_use.setBold(is_bold)
            document.setDefaultFont(font_to_use)

        document.setHtml(html_content)
        document.setPageSize(printer.pageRect(QPrinter.Point).size())
        document.print_(printer)

    def _generate_estimate_manual_format(self, estimate_data):
        """Generate manually formatted text using spaces, matching preview image."""
        header = estimate_data['header']
        items = estimate_data['items']
        voucher_no = header['voucher_no']
        silver_rate = header['silver_rate']

        regular_items, silver_bar_items, return_goods, return_silver_bars = [], [], [], []
        for item in items:
            # Use the flags stored in the database item data
            is_return = item.get('is_return', 0) == 1
            is_silver_bar = item.get('is_silver_bar', 0) == 1 # Use the flag directly

            if is_return:
                if is_silver_bar:
                    return_silver_bars.append(item)
                else:
                    return_goods.append(item)
            else: # Not a return item
                if is_silver_bar:
                    silver_bar_items.append(item)
                else:
                    regular_items.append(item)

        S = 1; W_SNO=3; W_FINE=9; W_LABOUR=8; W_QTY=10; W_POLY=7; W_NAME=18; W_SPER=7; W_PCS=8; W_WRATE=8
        TOTAL_WIDTH = W_SNO+S+W_FINE+S+W_LABOUR+S+W_QTY+S+W_POLY+S+W_NAME+S+W_SPER+S+W_PCS+S+W_WRATE

        def format_line(*args):
            # args[0] is now sno
            try:
                sno = f"{args[0]:>{W_SNO}}"; fine = f"{args[1]:>{W_FINE}.3f}"; labour = f"{args[2]:>{W_LABOUR}.2f}"
                qty = f"{args[3]:>{W_QTY}.3f}"; poly = f"{args[4]:>{W_POLY}.0f}" # Poly as integer
                name = f"{str(args[5] or ''):<{W_NAME}.{W_NAME}}"; sper = f"{args[6]:>{W_SPER}.2f}"
                pcs_val = args[7]; pcs_display = str(pcs_val) if pcs_val and pcs_val > 0 else ""
                pcs = pcs_display.rjust(W_PCS); wrate = f"{args[8]:>{W_WRATE}.2f}"
                # Construct line with padding
                line = (f"{sno} {fine} {labour} {qty} {poly} {name} {sper} {pcs} {wrate}")
                return f"{line:<{TOTAL_WIDTH}}"[:TOTAL_WIDTH]
            except Exception as e: print(f"Error formatting line: {e}, Data: {args}"); return " " * TOTAL_WIDTH

        def format_totals_line(fine, labour, qty, poly):
            # Format values, including Poly and Labour as integer
            fine_str=f"{fine:{W_FINE}.3f}"; labour_str=f"{labour:{W_LABOUR}.0f}"
            qty_str=str(int(round(qty))).rjust(W_QTY); poly_str=f"{poly:{W_POLY}.0f}"
            # Construct the line with correct spacing
            sno_space=" "*(W_SNO+S); space_after_poly=" "*(S+W_NAME+S+W_SPER+S+W_PCS+S+W_WRATE)
            line = f"{sno_space}{fine_str} {labour_str} {qty_str} {poly_str}{space_after_poly}"
            return f"{line:<{TOTAL_WIDTH}}"[:TOTAL_WIDTH]

        output = []; title="* * ESTIMATE SLIP ONLY * *"; pad=(TOTAL_WIDTH-len(title))//2
        output.append(" "*pad+title); output.append(" ")
        voucher_str=str(voucher_no).ljust(15); rate_str=f"S.Rate :{silver_rate:10.2f}"
        pad=max(1,TOTAL_WIDTH-len(voucher_str)-len(rate_str)); output.append(f"{voucher_str}"+" "*pad+rate_str)
        sep_eq="="*TOTAL_WIDTH; sep_dash="-"*TOTAL_WIDTH; output.append(sep_eq)
        h_sno="SNo".center(W_SNO); h_fine="Fine".center(W_FINE); h_labour="Labour".center(W_LABOUR); h_qty="Quantity".center(W_QTY); h_poly="Poly".center(W_POLY)
        h_name="Item Name".center(W_NAME); h_sper="S.Per%".center(W_SPER); h_pcs="Pcs/Doz.".center(W_PCS); h_wrate="W.Rate".center(W_WRATE)
        header_line=f"{h_sno} {h_fine} {h_labour} {h_qty} {h_poly} {h_name} {h_sper} {h_pcs} {h_wrate}"
        output.append(f"{header_line:<{TOTAL_WIDTH}}"[:TOTAL_WIDTH]); output.append(sep_eq)

        reg_f,reg_w,reg_g,reg_p=0.0,0.0,0.0,0.0; sb_f,sb_w,sb_g,sb_p=0.0,0.0,0.0,0.0
        ret_gf,ret_gw,ret_gg,ret_gp=0.0,0.0,0.0,0.0; ret_sf,ret_sw,ret_sg,ret_sp=0.0,0.0,0.0,0.0

        if regular_items:
            sno=1;
            for item in regular_items:
                reg_f+=item.get('fine',0.0); reg_w+=item.get('wage',0.0); reg_g+=item.get('gross',0.0); reg_p+=item.get('poly',0.0)
                output.append(format_line(sno,item.get('fine',0.0),item.get('wage',0.0),item.get('gross',0.0),item.get('poly',0.0),item.get('item_name',''),item.get('purity',0.0),item.get('pieces',0),item.get('wage_rate',0.0))); sno+=1
            output.append(sep_dash); output.append(format_totals_line(reg_f,reg_w,reg_g,reg_p)); output.append(sep_dash)

        if silver_bar_items:
            output.append(" "); sb_title="* * Silver Bars * *"; pad=(TOTAL_WIDTH-len(sb_title))//2; output.append(" "*pad+sb_title); output.append(sep_dash); output.append(header_line[:TOTAL_WIDTH]); output.append(sep_dash)
            sno=1;
            for item in silver_bar_items:
                sb_f+=item.get('fine',0.0); sb_w+=item.get('wage',0.0); sb_g+=item.get('gross',0.0); sb_p+=item.get('poly',0.0)
                output.append(format_line(sno,item.get('fine',0.0),item.get('wage',0.0),item.get('gross',0.0),item.get('poly',0.0),item.get('item_name',''),item.get('purity',0.0),0,0)); sno+=1
            output.append(sep_dash); output.append(format_totals_line(sb_f,sb_w,sb_g,sb_p)); output.append(sep_dash)

        if return_goods:
            output.append(" "); rg_title="* * Return Goods * *"; pad=(TOTAL_WIDTH-len(rg_title))//2; output.append(" "*pad+rg_title); output.append(sep_dash); output.append(header_line[:TOTAL_WIDTH]); output.append(sep_dash)
            sno=1;
            for item in return_goods:
                ret_gf+=item.get('fine',0.0); ret_gw+=item.get('wage',0.0); ret_gg+=item.get('gross',0.0); ret_gp+=item.get('poly',0.0)
                output.append(format_line(sno,item.get('fine',0.0),item.get('wage',0.0),item.get('gross',0.0),item.get('poly',0.0),item.get('item_name',''),item.get('purity',0.0),item.get('pieces',0),item.get('wage_rate',0.0))); sno+=1
            output.append(sep_dash); output.append(format_totals_line(ret_gf,ret_gw,ret_gg,ret_gp)); output.append(sep_dash)

        if return_silver_bars:
            output.append(" "); rsb_title="* * Return Silver Bar * *"; pad=(TOTAL_WIDTH-len(rsb_title))//2; output.append(" "*pad+rsb_title); output.append(sep_dash); output.append(header_line[:TOTAL_WIDTH]); output.append(sep_dash)
            sno=1;
            for item in return_silver_bars:
                ret_sf+=item.get('fine',0.0); ret_sw+=item.get('wage',0.0); ret_sg+=item.get('gross',0.0); ret_sp+=item.get('poly',0.0)
                output.append(format_line(sno,item.get('fine',0.0),item.get('wage',0.0),item.get('gross',0.0),item.get('poly',0.0),item.get('item_name',''),item.get('purity',0.0),0,0)); sno+=1
            output.append(sep_dash); output.append(format_totals_line(ret_sf,ret_sw,ret_sg,ret_sp)); output.append(sep_dash)

        output.append(" "); final_title="Final Silver & Amount"; pad=(TOTAL_WIDTH-len(final_title))//2; output.append(" "*pad+final_title); output.append(sep_eq)
        net_fine=reg_f-sb_f-ret_gf-ret_sf; net_wage=reg_w-sb_w-ret_gw-ret_sw
        silver_cost=net_fine*silver_rate; total_cost=net_wage+silver_cost
        net_wage_r=round(net_wage); silver_cost_r=round(silver_cost); total_cost_r=round(total_cost)

        fine_str=f"{net_fine:{W_FINE}.3f}"
        wage_str=f"{net_wage_r:{W_LABOUR}.0f}"
        scost_label="S.Cost : "
        scost_value_formatted = self.format_indian_rupees(silver_cost_r)
        scost_display = scost_label + scost_value_formatted
        total_label="Total: "
        total_value_formatted = self.format_indian_rupees(total_cost_r)
        total_display = total_label + total_value_formatted

        tfw = 18; scfw = 22
        total_pad = total_display.rjust(tfw)
        scost_pad = scost_display.rjust(scfw)

        part1_len=W_SNO+S+W_FINE+S+W_LABOUR
        space_before=TOTAL_WIDTH - part1_len - len(scost_pad) - len(total_pad) - 2
        pad_after_labour=max(1, space_before - 1); pad_between=1
        final_line = f"{' '*(W_SNO+S)}{fine_str} {wage_str}" + (" "*pad_after_labour) + scost_pad + (" "*pad_between) + total_pad
        output.append(final_line[:TOTAL_WIDTH]); output.append(sep_eq); output.append(" ")
        note = "Note :-  G O O D S   N O T   R E T U R N"; pad=(TOTAL_WIDTH-len(note))//2; output.append(" "*pad+note); output.append(" \f")

        html_content = "\n".join(output)
        # Rely on _print_html's setDefaultFont for styling
        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
                    pre {{
                        line-height: 1.0;
                        white-space: pre;
                        margin: 0;
                        padding: 0;
                        page-break-inside: avoid;
                    }}
                    body {{ margin: 10mm; }}
                    </style></head><body><pre>{html_content}</pre></body></html>"""
        return html

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
                   <table><thead><tr><th>Bar ID</th><th>Estimate Vch</th><th class="right">Weight(g)</th><th class="right">Purity(%)</th>
                   <th class="right">Fine Wt(g)</th><th>Date Added</th><th>Status</th></tr></thead><tbody>"""
        total_weight = 0.0; total_fine = 0.0; bar_count = 0
        if bars:
            for bar in bars: # Assume bar is sqlite3.Row
                # Use the new schema column names
                bw = bar['weight'] if 'weight' in bar.keys() and bar['weight'] is not None else 0.0
                bfw = bar['fine_weight'] if 'fine_weight' in bar.keys() and bar['fine_weight'] is not None else 0.0
                bp = bar['purity'] if 'purity' in bar.keys() and bar['purity'] is not None else 0.0
                bid = bar['bar_id'] if 'bar_id' in bar.keys() and bar['bar_id'] is not None else 'N/A'
                evch = bar['estimate_voucher_no'] if 'estimate_voucher_no' in bar.keys() and bar['estimate_voucher_no'] is not None else 'N/A'
                da = bar['date_added'] if 'date_added' in bar.keys() and bar['date_added'] is not None else ''
                st = bar['status'] if 'status' in bar.keys() and bar['status'] is not None else ''
                
                bar_count += 1
                total_weight += bw
                total_fine += bfw
                
                html += f"""<tr>
                    <td>{bid}</td>
                    <td>{evch}</td>
                    <td class="right">{bw:.3f}</td>
                    <td class="right">{bp:.2f}</td>
                    <td class="right">{bfw:.3f}</td>
                    <td>{da}</td>
                    <td>{st}</td>
                </tr>"""
        else: html += '<tr><td colspan="7" style="text-align:center;padding:5px 0;">-- No Bars Found --</td></tr>'
        html += f"""</tbody></table><div class="totals">TOTAL Bars: {bar_count} | TOTAL Weight: {total_weight:,.3f} g | TOTAL Fine Wt: {total_fine:,.3f} g</div></body></html>"""
        return html

    def _generate_list_details_html(self, list_info, bars_in_list):
        """Generates HTML content for printing a single list's details (v2.0 schema)."""
        # Use dictionary-style access with checks for sqlite3.Row compatibility
        li = list_info['list_identifier'] if 'list_identifier' in list_info.keys() and list_info['list_identifier'] is not None else 'N/A'
        cd = list_info['creation_date'] if 'creation_date' in list_info.keys() and list_info['creation_date'] is not None else 'N/A'
        ln = list_info['list_note'] if 'list_note' in list_info.keys() and list_info['list_note'] is not None else ''
        pd = QDate.currentDate().toString("yyyy-MM-dd")

        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Silver Bar List - {li}</title><style>
                   body{{font-family:Arial,sans-serif;font-size:8pt;margin:10mm}}table{{border-collapse:collapse;width:100%;margin-top:15px;page-break-inside:auto}}
                   th,td{{border:1px solid #ccc;padding:4px 6px;text-align:left;word-wrap:break-word}}tr{{page-break-inside:avoid;page-break-after:auto}}
                   thead{{display:table-header-group}}th{{border-bottom:1px solid #000;background-color:#f0f0f0;font-weight:bold}}
                   .header-title{{text-align:center;font-size:12pt;font-weight:bold;margin-bottom:10px}}.list-info{{margin-bottom:15px}}
                   .list-info span{{display:inline-block;margin-right:20px}}.list-note{{margin-top:5px;border:1px solid #eee;padding:5px;background-color:#f9f9f9}}
                   .totals{{margin-top:15px;font-weight:bold;border-top:1px double #000;padding-top:5px;text-align:right}}.right{{text-align:right}}</style></head><body>
                   <div class="header-title">Silver Bar List Details</div>
                   <div class="list-info">
                       <span><b>List ID:</b> {li}</span>
                       <span><b>Created:</b> {cd}</span>
                       <span><b>Printed:</b> {pd}</span>
                   </div>
                   <div class="list-note"><b>Note:</b> {ln if ln else 'N/A'}</div>
                   <table>
                       <thead>
                           <tr>
                               <th>#</th>
                               <th>Estimate Vch</th>
                               <th class="right">Weight (g)</th>
                               <th class="right">Purity (%)</th>
                               <th class="right">Fine Wt (g)</th>
                           </tr>
                       </thead>
                       <tbody>"""
        tw = 0.0; tf = 0.0; bc = 0
        if bars_in_list:
            for idx, bar in enumerate(bars_in_list):
                # Use dictionary-style access with checks for sqlite3.Row compatibility
                est_vch = bar['estimate_voucher_no'] if 'estimate_voucher_no' in bar.keys() and bar['estimate_voucher_no'] is not None else 'N/A'
                bw = bar['weight'] if 'weight' in bar.keys() and bar['weight'] is not None else 0.0
                bfw = bar['fine_weight'] if 'fine_weight' in bar.keys() and bar['fine_weight'] is not None else 0.0
                bp = bar['purity'] if 'purity' in bar.keys() and bar['purity'] is not None else 0.0
                # Note: bar_no and status are no longer primary fields in this context

                bc += 1
                tw += bw
                tf += bfw
                html += f"""<tr>
                               <td>{idx+1}</td>
                               <td>{est_vch}</td>
                               <td class="right">{bw:.3f}</td>
                               <td class="right">{bp:.2f}</td>
                               <td class="right">{bfw:.3f}</td>
                           </tr>"""
        else:
            # Adjust colspan for the new number of columns
            html += '<tr><td colspan="5" style="text-align:center;padding:10px 0;">-- No bars assigned --</td></tr>'

        html += f"""</tbody></table>
                   <div class="totals">TOTAL Bars: {bc} | TOTAL Weight: {tw:,.3f} g | TOTAL Fine Wt: {tf:,.3f} g</div>
                   </body></html>"""
        return html