#!/usr/bin/env python
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QPushButton, QTextEdit,
                             QLabel, QMessageBox, QApplication, QToolBar, QAction, QFileDialog, QWidgetAction)
from PyQt5.QtGui import QFont, QTextCursor, QPageSize, QTextDocument, QFontDatabase
from PyQt5.QtCore import Qt, QDate, QLocale, QSizeF
# Import QPrintPreviewWidget
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog, QPrintPreviewWidget, QPageSetupDialog, QPrinterInfo
import traceback # Keep for debugging
import math # For rounding

from silverestimate.infrastructure.settings import get_app_settings


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
        # Load printer defaults
        settings = get_app_settings()
        # Default printer
        try:
            default_printer_name = settings.value("print/default_printer", "", type=str)
            if default_printer_name:
                self.printer.setPrinterName(default_printer_name)
        except Exception:
            pass
        # Page size
        try:
            page_size_name = settings.value("print/page_size", "A4", type=str)
            if page_size_name == 'Thermal 80mm':
                thermal_size = QPageSize(QSizeF(79.5, 200), QPageSize.Millimeter, 'Thermal 80mm')
                self.printer.setPageSize(thermal_size)
            else:
                size_map = {
                    'A4': QPageSize.A4,
                    'A5': QPageSize.A5,
                    'Letter': QPageSize.Letter,
                    'Legal': QPageSize.Legal,
                }
                self.printer.setPageSize(QPageSize(size_map.get(page_size_name, QPageSize.A4)))
        except Exception:
            self.printer.setPageSize(QPageSize(QPageSize.A4))
        # Orientation
        try:
            orientation_name = settings.value("print/orientation", "Portrait", type=str)
            self.printer.setOrientation(QPrinter.Landscape if orientation_name == 'Landscape' else QPrinter.Portrait)
        except Exception:
            self.printer.setOrientation(QPrinter.Portrait)

        try:
            layout_mode = settings.value("print/estimate_layout", "old", type=str)
            self.estimate_layout_mode = (layout_mode or "old").lower()
            if self.estimate_layout_mode not in {"old", "new", "thermal"}:
                self.estimate_layout_mode = "old"
        except Exception:
            self.estimate_layout_mode = "old"
        # Load margin settings
        default_margins = "10,5,10,5" # Default: 10mm L/R, 5mm T/B
        margins_str = settings.value("print/margins", defaultValue=default_margins, type=str)
        try:
            margins = [int(m.strip()) for m in margins_str.split(',')]
            if len(margins) != 4:
                raise ValueError("Invalid margin format")
            # Ensure margins are non-negative
            margins = [max(0, m) for m in margins]
            import logging
            logging.getLogger(__name__).debug(f"Using margins (L,T,R,B): {margins} mm")
        except (ValueError, TypeError):
            import logging
            logging.getLogger(__name__).warning(f"Using default margins ({default_margins} mm) due to invalid setting '{margins_str}'")
            margins = [10, 5, 10, 5]

        self.printer.setPageMargins(margins[0], margins[1], margins[2], margins[3], QPrinter.Millimeter) # Left, Top, Right, Bottom
        import logging
        logging.getLogger(__name__).debug(f"Printer margins set to: L={margins[0]}, T={margins[1]}, R={margins[2]}, B={margins[3]}")

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

    def _format_currency_locale(self, number):
        """Format currency using system locale; fallback to Indian format with ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¹."""
        try:
            locale = QLocale.system()
            return locale.toCurrencyString(float(round(number)))
        except Exception:
            return f"ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¹ {self.format_indian_rupees(int(round(number)))}"


    def print_estimate(self, voucher_no, parent_widget=None):
        """Print an estimate using manual formatting and preview."""
        estimate_data = self.db_manager.get_estimate_by_voucher(voucher_no)
        if not estimate_data:
            QMessageBox.warning(parent_widget, "Print Error",
                                f"Estimate {voucher_no} not found.")
            return False
        try:
            layout_mode = getattr(self, "estimate_layout_mode", "old")
            layout_mode = (layout_mode or "old").lower()
            if layout_mode == "new":
                html_text = self._generate_estimate_new_format(estimate_data)
            elif layout_mode == "thermal":
                html_text = self._generate_estimate_thermal_format(estimate_data)
            else:
                html_text = self._generate_estimate_old_format(estimate_data)

            self._open_preview_with_enhancements(
                html_text,
                parent_widget=parent_widget,
                title=f"Print Preview - Estimate {voucher_no}",
                table_mode=False
            )
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

            self._open_preview_with_enhancements(
                html_text,
                parent_widget=parent_widget,
                title="Print Preview - Silver Bar Inventory",
                table_mode=True
            )
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
            self._open_preview_with_enhancements(
                html_content,
                parent_widget=parent_widget,
                title=f"Print Preview - List {list_info['list_identifier'] if 'list_identifier' in list_info.keys() and list_info['list_identifier'] is not None else 'N/A'}",
                table_mode=True
            )
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

    def _generate_estimate_old_format(self, estimate_data):
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

        S = 1; W_SNO=3; W_FINE=9; W_LBR=8; W_QTY=10; W_POLY=7; W_NAME=18; W_SPER=7; W_PCS=8; W_WRATE=8
        TOTAL_WIDTH = W_SNO+S+W_FINE+S+W_LBR+S+W_QTY+S+W_POLY+S+W_NAME+S+W_SPER+S+W_PCS+S+W_WRATE

        def format_line(*args):
            # args[0] is now sno
            try:
                sno = f"{args[0]:>{W_SNO}}"; fine = f"{args[1]:>{W_FINE}.3f}"; labour = f"{args[2]:>{W_LBR}.2f}"
                qty = f"{args[3]:>{W_QTY}.3f}"; poly = f"{args[4]:>{W_POLY}.0f}" # Poly as integer
                name = f"{str(args[5] or ''):<{W_NAME}.{W_NAME}}"; sper = f"{args[6]:>{W_SPER}.2f}"
                pcs_val = args[7]; pcs_display = str(pcs_val) if pcs_val and pcs_val > 0 else ""
                pcs = pcs_display.rjust(W_PCS); wrate = f"{args[8]:>{W_WRATE}.2f}"
                # Construct line with padding
                line = (f"{sno} {fine} {labour} {qty} {poly} {name} {sper} {pcs} {wrate}")
                return f"{line:<{TOTAL_WIDTH}}"[:TOTAL_WIDTH]
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error formatting line: {e}, Data: {args}")
                return " " * TOTAL_WIDTH

        def format_totals_line(fine, labour, qty, poly):
            # Format values, including Poly and Labour as integer
            fine_str=f"{fine:{W_FINE}.3f}"; labour_str=f"{labour:{W_LBR}.0f}"
            qty_str=str(int(round(qty))).rjust(W_QTY); poly_str=f"{poly:{W_POLY}.0f}"
            # Construct the line with correct spacing
            sno_space=" "*(W_SNO+S); space_after_poly=" "*(S+W_NAME+S+W_SPER+S+W_PCS+S+W_WRATE)
            line = f"{sno_space}{fine_str} {labour_str} {qty_str} {poly_str}{space_after_poly}"
            return f"{line:<{TOTAL_WIDTH}}"[:TOTAL_WIDTH]

        output = []
        
        # Get note from header if it exists
        note = header.get('note', '')
        
        # Original title text
        title = "* * ESTIMATE SLIP ONLY * *"
        
        if note:
            # Calculate available space
            title_len = len(title)
            note_len = len(note)
            
            # Keep title centered, add note after it with some spacing
            # First, calculate how much space the title would take if centered
            title_pad = (TOTAL_WIDTH - title_len) // 2
            
            # Calculate where the title would end if centered
            title_end_pos = title_pad + title_len
            
            # Calculate space available for note after title
            space_after_title = TOTAL_WIDTH - title_end_pos - 5  # 5 for spacing
            
            # Truncate note if needed
            if note_len > space_after_title:
                note = note[:space_after_title-3] + "..."
                note_len = len(note)
            
            # Calculate final padding to keep title centered
            final_pad = (TOTAL_WIDTH - title_len - note_len - 5) // 2
            if final_pad < 0:
                final_pad = 0
            
            # Create the line with title centered and note after it
            line = " " * final_pad + title + " " * 5 + note
            
            # Ensure line doesn't exceed TOTAL_WIDTH
            if len(line) > TOTAL_WIDTH:
                line = line[:TOTAL_WIDTH]
                
            output.append(line)
        else:
            # Original title centered without note
            pad = (TOTAL_WIDTH-len(title))//2
            output.append(" "*pad+title)
        
        # output.append(" ")  # REMOVED Empty line after title
        
        # Add voucher and rate line (unchanged)
        voucher_str = str(voucher_no).ljust(15)
        rate_str = f"S.Rate :{silver_rate:10.2f}"
        pad = max(1, TOTAL_WIDTH-len(voucher_str)-len(rate_str))
        output.append(f"{voucher_str}"+" "*pad+rate_str)
        sep_eq="="*TOTAL_WIDTH; sep_dash="-"*TOTAL_WIDTH; output.append(sep_eq)
        h_sno="SNo".center(W_SNO); h_fine="Fine".center(W_FINE); h_labour="Labour".center(W_LBR); h_qty="Quantity".center(W_QTY); h_poly="Poly".center(W_POLY)
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
            output.append(sep_dash); output.append(format_totals_line(reg_f,reg_w,reg_g,reg_p)); output.append(sep_eq) # Use equals after totals

        if silver_bar_items:
            # output.append(" "); # REMOVED Blank line
            sb_title="* * Silver Bars * *"; pad=(TOTAL_WIDTH-len(sb_title))//2; output.append(" "*pad+sb_title); output.append(sep_dash); output.append(header_line[:TOTAL_WIDTH]); output.append(sep_dash)
            sno=1;
            for item in silver_bar_items:
                sb_f+=item.get('fine',0.0); sb_w+=item.get('wage',0.0); sb_g+=item.get('gross',0.0); sb_p+=item.get('poly',0.0)
                output.append(format_line(sno,item.get('fine',0.0),item.get('wage',0.0),item.get('gross',0.0),item.get('poly',0.0),item.get('item_name',''),item.get('purity',0.0),0,0)); sno+=1
            output.append(sep_dash); output.append(format_totals_line(sb_f,sb_w,sb_g,sb_p)); output.append(sep_eq) # Use equals after totals

        if return_goods:
            # output.append(" "); # REMOVED Blank line
            rg_title="* * Return Goods * *"; pad=(TOTAL_WIDTH-len(rg_title))//2; output.append(" "*pad+rg_title); output.append(sep_dash); output.append(header_line[:TOTAL_WIDTH]); output.append(sep_dash)
            sno=1;
            for item in return_goods:
                ret_gf+=item.get('fine',0.0); ret_gw+=item.get('wage',0.0); ret_gg+=item.get('gross',0.0); ret_gp+=item.get('poly',0.0)
                output.append(format_line(sno,item.get('fine',0.0),item.get('wage',0.0),item.get('gross',0.0),item.get('poly',0.0),item.get('item_name',''),item.get('purity',0.0),item.get('pieces',0),item.get('wage_rate',0.0))); sno+=1
            output.append(sep_dash); output.append(format_totals_line(ret_gf,ret_gw,ret_gg,ret_gp)); output.append(sep_eq) # Use equals after totals

        if return_silver_bars:
            # output.append(" "); # REMOVED Blank line
            rsb_title="* * Return Silver Bar * *"; pad=(TOTAL_WIDTH-len(rsb_title))//2; output.append(" "*pad+rsb_title); output.append(sep_dash); output.append(header_line[:TOTAL_WIDTH]); output.append(sep_dash)
            sno=1;
            for item in return_silver_bars:
                ret_sf+=item.get('fine',0.0); ret_sw+=item.get('wage',0.0); ret_sg+=item.get('gross',0.0); ret_sp+=item.get('poly',0.0)
                output.append(format_line(sno,item.get('fine',0.0),item.get('wage',0.0),item.get('gross',0.0),item.get('poly',0.0),item.get('item_name',''),item.get('purity',0.0),0,0)); sno+=1
            output.append(sep_dash); output.append(format_totals_line(ret_sf,ret_sw,ret_sg,ret_sp)); output.append(sep_eq) # Use equals after totals
        
        # Get last balance values if they exist
        last_balance_silver = header.get('last_balance_silver', 0.0)
        last_balance_amount = header.get('last_balance_amount', 0.0)
        
        # Add last balance section if it exists (before final section)
        if last_balance_silver > 0 or last_balance_amount > 0:
            # output.append(" ") # REMOVED Blank line
            lb_title = "* * Last Balance * *"
            lb_pad = (TOTAL_WIDTH - len(lb_title)) // 2
            output.append(" " * lb_pad + lb_title)
            output.append(sep_dash)
            
            # Format last balance values on a single line
            lb_str = f"Silver: {last_balance_silver:.3f} g   Amount: {self._format_currency_locale(last_balance_amount)}"
            lb_pad = (TOTAL_WIDTH - len(lb_str)) // 2
            output.append(" " * lb_pad + lb_str)
            output.append(sep_dash)

        # output.append(" "); # REMOVED Blank line
        final_title="Final Silver & Amount"; pad=(TOTAL_WIDTH-len(final_title))//2; output.append(" "*pad+final_title); output.append(sep_eq)
        # Calculate net values
        net_fine = reg_f - sb_f - ret_gf - ret_sf
        
        # Add last balance silver to net fine if it exists
        if last_balance_silver > 0:
            net_fine_display = net_fine + last_balance_silver
        else:
            net_fine_display = net_fine
            
        # Calculate net wage and add last balance amount to it
        net_wage = reg_w - sb_w - ret_gw - ret_sw
        if last_balance_amount > 0:
            net_wage_display = net_wage + last_balance_amount
        else:
            net_wage_display = net_wage
        
        # Calculate costs with last balance included
        silver_cost = net_fine_display * silver_rate
        total_cost = net_wage_display + silver_cost
            
        # Round values for display
        net_wage_r = int(round(net_wage_display))
        silver_cost_r = int(round(silver_cost))
        total_cost_r = int(round(total_cost))

        fine_str=f"{net_fine_display:{W_FINE}.3f}"
        wage_str=f"{net_wage_r:{W_LBR}.0f}"
        scost_label="S.Cost : "
        scost_value_formatted = self._format_currency_locale(silver_cost_r)
        scost_display = scost_label + scost_value_formatted
        total_label="Total: "
        total_value_formatted = self._format_currency_locale(total_cost_r)
        total_display = total_label + total_value_formatted

        tfw = 18; scfw = 22
        total_pad = total_display.rjust(tfw)
        scost_pad = scost_display.rjust(scfw)

        # Construct the final line conditionally based on silver_rate
        if silver_rate > 0:
            part1_len=W_SNO+S+W_FINE+S+W_LBR
            space_before=TOTAL_WIDTH - part1_len - len(scost_pad) - len(total_pad) - 2
            pad_after_labour=max(1, space_before - 1); pad_between=1
            final_line = f"{' '*(W_SNO+S)}{fine_str} {wage_str}" + (" "*pad_after_labour) + scost_pad + (" "*pad_between) + total_pad
        else:
            # If silver rate is 0, only show Fine and Labour, omit S.Cost and Total
            part1_len=W_SNO+S+W_FINE+S+W_LBR
            remaining_space = TOTAL_WIDTH - part1_len
            final_line = f"{' '*(W_SNO+S)}{fine_str} {wage_str}" + (" " * remaining_space)

        output.append(final_line[:TOTAL_WIDTH])
        output.append(sep_eq); # output.append(" ") # REMOVED Blank line
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
                    body {{ margin: 0; }}
                    </style></head><body><pre>{html_content}</pre></body></html>"""
        return html

    def _generate_estimate_new_format(self, estimate_data):
        """Generate the new layout variant for estimates."""
        header = estimate_data['header']
        items = estimate_data['items']
        voucher_no = header['voucher_no']
        silver_rate = header['silver_rate']

        regular_items, silver_bar_items, return_goods, return_silver_bars = [], [], [], []
        for item in items:
            is_return = item.get('is_return', 0) == 1
            is_silver_bar = item.get('is_silver_bar', 0) == 1

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
            W_SNO + S + W_NAME + S + W_GROSS + S + W_POLY + S + W_NET + S + W_SPER +
            S + W_WRATE + S + W_PCS + S + W_FINE + S + W_LBR
        )

        def fmt_num(value, width):
            if value is None:
                return " " * width
            try:
                return f"{float(value):<{width}.2f}"[:width].ljust(width)
            except Exception:
                return " " * width

        def format_line(sno, name, gross, poly, net, sper, wrate, pcs, fine, labour_amt):
            try:
                sno_str = "" if sno in (None, "") else str(sno)
                sno_part = sno_str[:W_SNO].ljust(W_SNO)
                name_part = (str(name or "")[:W_NAME]).ljust(W_NAME)
                gross_part = fmt_num(gross, W_GROSS)
                poly_part = fmt_num(poly, W_POLY)
                net_part = fmt_num(net, W_NET)
                sper_part = fmt_num(sper, W_SPER)
                wrate_part = fmt_num(wrate, W_WRATE)
                pcs_part = fmt_num(pcs, W_PCS) if pcs not in (None, "") else " " * W_PCS
                fine_part = fmt_num(fine, W_FINE)
                labour_part = fmt_num(labour_amt, W_LBR)

                line_parts = [
                    sno_part,
                    name_part,
                    gross_part,
                    poly_part,
                    net_part,
                    sper_part,
                    wrate_part,
                    pcs_part,
                    fine_part,
                    labour_part,
                ]
                line = ' '.join(line_parts)
                return f"{line:<{TOTAL_WIDTH}}"[:TOTAL_WIDTH]
            except Exception as err:
                import logging
                logging.getLogger(__name__).error(
                    f"Error formatting new layout line: {err}, Data: {(sno, name, gross, poly, net, sper, wrate, pcs, fine, labour_amt)}"
                )
                return " " * TOTAL_WIDTH


        output = []

        note = header.get('note', '')
        title = "* * ESTIMATE SLIP ONLY * *"

        if note:
            title_len = len(title)
            note_len = len(note)
            title_pad = (TOTAL_WIDTH - title_len) // 2
            title_end_pos = title_pad + title_len
            space_after_title = TOTAL_WIDTH - title_end_pos - 5
            if note_len > space_after_title:
                note = note[:space_after_title-3] + "..."
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

        header_parts = [
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
        header_line = ' '.join(header_parts)
        output.append(f"{header_line:<{TOTAL_WIDTH}}"[:TOTAL_WIDTH])
        output.append(sep_eq)

        reg_f = reg_w = reg_g = reg_p = reg_n = 0.0
        sb_f = sb_w = sb_g = sb_p = sb_n = 0.0
        ret_gf = ret_gw = ret_gg = ret_gp = ret_gn = 0.0
        ret_sf = ret_sw = ret_sg = ret_sp = ret_sn = 0.0

        if regular_items:
            sno = 1
            for item in regular_items:
                gross = item.get('gross', 0.0) or 0.0
                poly = item.get('poly', 0.0) or 0.0
                net = item.get('net_wt', None)
                if net is None:
                    net = gross - poly
                purity = item.get('purity', 0.0)
                wage_rate = item.get('wage_rate', 0.0)
                pieces = item.get('pieces', 0)
                fine = item.get('fine', 0.0) or 0.0
                wage = item.get('wage', 0.0) or 0.0

                reg_f += fine
                reg_w += wage
                reg_g += gross
                reg_p += poly
                reg_n += net

                output.append(format_line(
                    sno,
                    item.get('item_name', ''),
                    gross,
                    poly,
                    net,
                    purity,
                    wage_rate,
                    pieces,
                    fine,
                    wage,
                ))
                sno += 1
            output.append(sep_dash)
            output.append(format_line('', 'TOTAL', reg_g, reg_p, reg_n, None, None, None, reg_f, reg_w))
            output.append(sep_eq)
            if silver_bar_items or return_goods or return_silver_bars:
                output.append('')

        if silver_bar_items:
            sb_title = "* * Silver Bars * *"
            pad = (TOTAL_WIDTH - len(sb_title)) // 2
            output.append(" " * pad + sb_title)
            output.append(sep_dash)
            output.append(header_line[:TOTAL_WIDTH])
            output.append(sep_dash)
            sno = 1
            for item in silver_bar_items:
                gross = item.get('gross', 0.0) or 0.0
                poly = item.get('poly', 0.0) or 0.0
                net = item.get('net_wt', None)
                if net is None:
                    net = gross - poly
                purity = item.get('purity', 0.0)
                fine = item.get('fine', 0.0) or 0.0
                wage = item.get('wage', 0.0) or 0.0

                sb_f += fine
                sb_w += wage
                sb_g += gross
                sb_p += poly
                sb_n += net

                output.append(format_line(
                    sno,
                    item.get('item_name', ''),
                    gross,
                    poly,
                    net,
                    purity,
                    None,
                    None,
                    fine,
                    wage,
                ))
                sno += 1
            output.append(sep_dash)
            output.append(format_line('', 'TOTAL', sb_g, sb_p, sb_n, None, None, None, sb_f, sb_w))
            output.append(sep_eq)
            if return_goods or return_silver_bars:
                output.append('')

        if return_goods:
            rg_title = "* * Return Goods * *"
            pad = (TOTAL_WIDTH - len(rg_title)) // 2
            output.append(" " * pad + rg_title)
            output.append(sep_dash)
            output.append(header_line[:TOTAL_WIDTH])
            output.append(sep_dash)
            sno = 1
            for item in return_goods:
                gross = item.get('gross', 0.0) or 0.0
                poly = item.get('poly', 0.0) or 0.0
                net = item.get('net_wt', None)
                if net is None:
                    net = gross - poly
                purity = item.get('purity', 0.0)
                wage_rate = item.get('wage_rate', 0.0)
                pieces = item.get('pieces', 0)
                fine = item.get('fine', 0.0) or 0.0
                wage = item.get('wage', 0.0) or 0.0

                ret_gf += fine
                ret_gw += wage
                ret_gg += gross
                ret_gp += poly
                ret_gn += net

                output.append(format_line(
                    sno,
                    item.get('item_name', ''),
                    gross,
                    poly,
                    net,
                    purity,
                    wage_rate,
                    pieces,
                    fine,
                    wage,
                ))
                sno += 1
            output.append(sep_dash)
            output.append(format_line('', 'TOTAL', ret_gg, ret_gp, ret_gn, None, None, None, ret_gf, ret_gw))
            output.append(sep_eq)
            if return_silver_bars:
                output.append('')

        if return_silver_bars:
            rsb_title = "* * Return Silver Bar * *"
            pad = (TOTAL_WIDTH - len(rsb_title)) // 2
            output.append(" " * pad + rsb_title)
            output.append(sep_dash)
            output.append(header_line[:TOTAL_WIDTH])
            output.append(sep_dash)
            sno = 1
            for item in return_silver_bars:
                gross = item.get('gross', 0.0) or 0.0
                poly = item.get('poly', 0.0) or 0.0
                net = item.get('net_wt', None)
                if net is None:
                    net = gross - poly
                purity = item.get('purity', 0.0)
                fine = item.get('fine', 0.0) or 0.0
                wage = item.get('wage', 0.0) or 0.0

                ret_sf += fine
                ret_sw += wage
                ret_sg += gross
                ret_sp += poly
                ret_sn += net

                output.append(format_line(
                    sno,
                    item.get('item_name', ''),
                    gross,
                    poly,
                    net,
                    purity,
                    None,
                    None,
                    fine,
                    wage,
                ))
                sno += 1
            output.append(sep_dash)
            output.append(format_line('', 'TOTAL', ret_sg, ret_sp, ret_sn, None, None, None, ret_sf, ret_sw))
            output.append(sep_eq)

        last_balance_silver = header.get('last_balance_silver', 0.0)
        last_balance_amount = header.get('last_balance_amount', 0.0)

        if last_balance_silver > 0 or last_balance_amount > 0:
            lb_title = "* * Last Balance * *"
            lb_pad = (TOTAL_WIDTH - len(lb_title)) // 2
            output.append(" " * lb_pad + lb_title)
            output.append(sep_dash)
            lb_str = f"Silver: {last_balance_silver:.2f} g   Amount: {self._format_currency_locale(last_balance_amount)}"
            lb_pad = (TOTAL_WIDTH - len(lb_str)) // 2
            output.append(" " * lb_pad + lb_str)
            output.append(sep_dash)

        final_title = "Final Silver & Amount"
        pad = (TOTAL_WIDTH - len(final_title)) // 2
        output.append(" " * pad + final_title)
        output.append(sep_eq)

        net_fine = reg_f - sb_f - ret_gf - ret_sf
        net_fine_display = net_fine + last_balance_silver if last_balance_silver > 0 else net_fine
        net_wage = reg_w - sb_w - ret_gw - ret_sw
        net_wage_display = net_wage + last_balance_amount if last_balance_amount > 0 else net_wage

        silver_cost = net_fine_display * silver_rate
        total_cost = net_wage_display + silver_cost

        net_wage_r = int(round(net_wage_display))
        silver_cost_r = int(round(silver_cost))
        total_cost_r = int(round(total_cost))

        fine_str = f"{net_fine_display:{W_FINE}.2f}"
        wage_str = f"{net_wage_r:{W_LBR}.0f}"
        scost_label = "S.Cost : "
        scost_value_formatted = self._format_currency_locale(silver_cost_r)
        scost_display = scost_label + scost_value_formatted
        total_label = "Total: "
        total_value_formatted = self._format_currency_locale(total_cost_r)
        total_display = total_label + total_value_formatted

        tfw = 18
        scfw = 22
        total_pad = total_display.rjust(tfw)
        scost_pad = scost_display.rjust(scfw)

        if silver_rate > 0:
            part1_len = W_SNO + S + W_FINE + S + W_LBR
            space_before = TOTAL_WIDTH - part1_len - len(scost_pad) - len(total_pad) - 2
            pad_after_labour = max(1, space_before - 1)
            pad_between = 1
            final_line = (
                f"{' ' * (W_SNO + S)}{fine_str} {wage_str}" +
                (" " * pad_after_labour) + scost_pad + (" " * pad_between) + total_pad
            )
        else:
            part1_len = W_SNO + S + W_FINE + S + W_LBR
            remaining_space = TOTAL_WIDTH - part1_len
            final_line = f"{' ' * (W_SNO + S)}{fine_str} {wage_str}" + (" " * remaining_space)

        output.append(final_line[:TOTAL_WIDTH])
        output.append(sep_eq)
        note_line = "Note :-  G O O D S   N O T   R E T U R N"
        pad = (TOTAL_WIDTH - len(note_line)) // 2
        output.append(" " * pad + note_line)
        output.append(" \f")

        html_content = "\n".join(output)
        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
                    pre {{
                        line-height: 1.0;
                        white-space: pre;
                        margin: 0;
                        padding: 0;
                        page-break-inside: avoid;
                    }}
                    body {{ margin: 0; }}
                    </style></head><body><pre>{html_content}</pre></body></html>"""
        return html


    def _generate_estimate_thermal_format(self, estimate_data):
        """Generate thermal slip layout sized for ~80mm paper."""
        header = estimate_data['header']
        items = estimate_data['items']
        voucher_no = header['voucher_no']
        silver_rate = header['silver_rate']

        regular_items, silver_bar_items, return_goods, return_silver_bars = [], [], [], []
        for item in items:
            is_return = item.get('is_return', 0) == 1
            is_silver_bar = item.get('is_silver_bar', 0) == 1

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

        TOTAL_WIDTH = 48
        W_SNO = 2
        W_NAME = TOTAL_WIDTH - W_SNO - 1  # space between sno and name
        W_GROSS = 10
        W_POLY = 10
        W_NET = 10
        W_SPER = 8
        W_FINE = 10
        W_PCS = 6
        W_LBR = 10

        def fmt_num(label, value, width):
            if value is None:
                return ' ' * width
            try:
                body = f"{float(value):.2f}"
            except Exception:
                body = str(value)
            cell = f"{label}:{body}"
            return cell[:width].ljust(width)

        def fmt_text(label, value, width):
            if value in (None, ''):
                return ' ' * width
            cell = f"{label}:{value}"
            return cell[:width].ljust(width)

        def append_item(lines, sno, name, gross, poly, net, sper, wrate, pcs, fine, labour, wage_type):
            sno_str = '' if sno in (None, '') else str(sno)
            name_line = f"{sno_str:>2} {str(name or '')[:W_NAME]}"
            lines.append(name_line[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))

            metrics_line1 = ' '.join([
                fmt_num('G', gross, W_GROSS),
                fmt_num('P', poly, W_POLY),
                fmt_num('N', net, W_NET),
            ])
            lines.append(metrics_line1[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))

            pcs_display = pcs
            if pcs_display is None:
                pcs_display = ''
            elif isinstance(pcs_display, float) and pcs_display.is_integer():
                pcs_display = int(pcs_display)

            labour_present = abs(labour or 0.0) > 1e-6
            labour_unit_code = (wage_type or '').strip().upper()
            unit_map = {'PC': '/pc', 'WT': '/gm'}
            labour_unit = unit_map.get(labour_unit_code, '') if (labour_present or abs(wrate or 0.0) > 1e-6) else ''

            row2_parts = [
                fmt_num('S%', sper, W_SPER),
                fmt_num('Fi', fine, W_FINE),
                fmt_text('Pc', pcs_display, W_PCS),
            ]
            lines.append(' '.join(row2_parts)[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))

            if labour_present:
                labour_amount = fmt_num('Lb', labour, W_LBR)
                lines.append(labour_amount[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))

            if labour_unit:
                labour_unit_line = fmt_text('Lbr', labour_unit, W_LBR)
                lines.append(labour_unit_line[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))

        output = []

        note = header.get('note', '')
        title = "* ESTIMATE SLIP *"
        pad = max(0, (TOTAL_WIDTH - len(title)) // 2)
        output.append((" " * pad + title)[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
        if note:
            output.append(str(note)[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))

        voucher_str = str(voucher_no)
        rate_str = f"Rate:{silver_rate:0.2f}"
        spacer = max(1, TOTAL_WIDTH - len(voucher_str) - len(rate_str))
        output.append(f"{voucher_str}{' ' * spacer}{rate_str}"[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
        sep = '-' * TOTAL_WIDTH
        output.append(sep)

        reg_f = reg_w = reg_g = reg_p = reg_n = 0.0
        sb_f = sb_w = sb_g = sb_p = sb_n = 0.0
        ret_gf = ret_gw = ret_gg = ret_gp = ret_gn = 0.0
        ret_sf = ret_sw = ret_sg = ret_sp = ret_sn = 0.0

        if regular_items:
            sno = 1
            for item in regular_items:
                gross = item.get('gross', 0.0) or 0.0
                poly = item.get('poly', 0.0) or 0.0
                net = item.get('net_wt', gross - poly)
                purity = item.get('purity', 0.0)
                wage_rate = item.get('wage_rate', 0.0)
                wage_type = item.get('wage_type', '')
                pcs = item.get('pieces', 0)
                fine = item.get('fine', 0.0) or 0.0
                wage = item.get('wage', 0.0) or 0.0

                reg_f += fine
                reg_w += wage
                reg_g += gross
                reg_p += poly
                reg_n += net

                append_item(output, sno, item.get('item_name', ''), gross, poly, net, purity, wage_rate, pcs, fine, wage, wage_type)
                sno += 1
            output.append(sep)
            output.append(f"TOTAL G:{reg_g:9.2f} P:{reg_p:9.2f} N:{reg_n:9.2f}"[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
            line = f"      Fi:{reg_f:9.2f}"
            if abs(reg_w) > 1e-6:
                line += f" Lb:{reg_w:9.2f}"
            output.append(line[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
            output.append(sep)

        if silver_bar_items:
            sb_title = "* Bars *"
            pad = max(0, (TOTAL_WIDTH - len(sb_title)) // 2)
            output.append((" " * pad + sb_title)[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
            output.append(sep)
            sno = 1
            for item in silver_bar_items:
                gross = item.get('gross', 0.0) or 0.0
                poly = item.get('poly', 0.0) or 0.0
                net = item.get('net_wt', gross - poly)
                purity = item.get('purity', 0.0)
                fine = item.get('fine', 0.0) or 0.0
                wage = item.get('wage', 0.0) or 0.0

                sb_f += fine
                sb_w += wage
                sb_g += gross
                sb_p += poly
                sb_n += net

                append_item(output, sno, item.get('item_name', ''), gross, poly, net, purity, None, None, fine, wage, None)
                sno += 1
            output.append(sep)
            output.append(f"TOTAL G:{sb_g:9.2f} P:{sb_p:9.2f} N:{sb_n:9.2f}"[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
            line = f"      Fi:{sb_f:9.2f}"
            if abs(sb_w) > 1e-6:
                line += f" Lb:{sb_w:9.2f}"
            output.append(line[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
            output.append(sep)

        if return_goods:
            rg_title = "* Returns *"
            pad = max(0, (TOTAL_WIDTH - len(rg_title)) // 2)
            output.append((" " * pad + rg_title)[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
            output.append(sep)
            sno = 1
            for item in return_goods:
                gross = item.get('gross', 0.0) or 0.0
                poly = item.get('poly', 0.0) or 0.0
                net = item.get('net_wt', gross - poly)
                purity = item.get('purity', 0.0)
                wage_rate = item.get('wage_rate', 0.0)
                wage_type = item.get('wage_type', '')
                pcs = item.get('pieces', 0)
                fine = item.get('fine', 0.0) or 0.0
                wage = item.get('wage', 0.0) or 0.0

                ret_gf += fine
                ret_gw += wage
                ret_gg += gross
                ret_gp += poly
                ret_gn += net

                append_item(output, sno, item.get('item_name', ''), gross, poly, net, purity, wage_rate, pcs, fine, wage, wage_type)
                sno += 1
            output.append(sep)
            output.append(f"TOTAL G:{ret_gg:9.2f} P:{ret_gp:9.2f} N:{ret_gn:9.2f}"[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
            line = f"      Fi:{ret_gf:9.2f}"
            if abs(ret_gw) > 1e-6:
                line += f" Lb:{ret_gw:9.2f}"
            output.append(line[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
            output.append(sep)

        if return_silver_bars:
            rsb_title = "* Ret Bars *"
            pad = max(0, (TOTAL_WIDTH - len(rsb_title)) // 2)
            output.append((" " * pad + rsb_title)[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
            output.append(sep)
            sno = 1
            for item in return_silver_bars:
                gross = item.get('gross', 0.0) or 0.0
                poly = item.get('poly', 0.0) or 0.0
                net = item.get('net_wt', gross - poly)
                purity = item.get('purity', 0.0)
                fine = item.get('fine', 0.0) or 0.0
                wage = item.get('wage', 0.0) or 0.0

                ret_sf += fine
                ret_sw += wage
                ret_sg += gross
                ret_sp += poly
                ret_sn += net

                append_item(output, sno, item.get('item_name', ''), gross, poly, net, purity, None, None, fine, wage, None)
                sno += 1
            output.append(sep)
            output.append(f"TOTAL G:{ret_sg:9.2f} P:{ret_sp:9.2f} N:{ret_sn:9.2f}"[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
            line = f"      Fi:{ret_sf:9.2f}"
            if abs(ret_sw) > 1e-6:
                line += f" Lb:{ret_sw:9.2f}"
            output.append(line[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
            output.append(sep)

        last_balance_silver = header.get('last_balance_silver', 0.0)
        last_balance_amount = header.get('last_balance_amount', 0.0)

        if last_balance_silver > 0 or last_balance_amount > 0:
            lb_title = "Last Balance"
            pad = max(0, (TOTAL_WIDTH - len(lb_title)) // 2)
            output.append((" " * pad + lb_title)[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
            output.append(sep)
            lb_str = f"Ag:{last_balance_silver:.2f} Amt:{self._format_currency_locale(last_balance_amount)}"
            output.append(lb_str[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
            output.append(sep)

        output.append("Final Silver & Amount"[:TOTAL_WIDTH].center(TOTAL_WIDTH))
        output.append(sep)

        net_fine = reg_f - sb_f - ret_gf - ret_sf
        net_fine_display = net_fine + last_balance_silver if last_balance_silver > 0 else net_fine
        net_wage = reg_w - sb_w - ret_gw - ret_sw
        net_wage_display = net_wage + last_balance_amount if last_balance_amount > 0 else net_wage

        silver_cost = net_fine_display * silver_rate
        total_cost = net_wage_display + silver_cost

        output.append(f"Fine:{net_fine_display:9.2f} Wage:{net_wage_display:9.2f}"[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
        output.append(f"S.Cost:{silver_cost:8.2f} Total:{total_cost:9.2f}"[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
        output.append(sep)
        note_line = "Note: Goods Not Return"
        output.append(note_line[:TOTAL_WIDTH].ljust(TOTAL_WIDTH))
        output.append(" \f")

        html_content = "\n".join(output)
        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
                    pre {{
                        line-height: 1.05;
                        white-space: pre;
                        margin: 0;
                        padding: 0;
                        page-break-inside: avoid;
                    }}
                    body {{ margin: 0; }}
                    </style></head><body><pre>{html_content}</pre></body></html>"""
        return html


    def _generate_silver_bars_html_table(self, bars, status_filter=None):
        """Generates HTML table for the general INVENTORY report."""
        status_text = f" - {status_filter}" if status_filter else " - All"; current_date = QDate.currentDate().toString("yyyy-MM-dd")
        html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Silver Bar Inventory</title><style>
                   body{{font-family:Arial,sans-serif;font-size:8pt;margin:0;}} /* Increased font size */
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
                   body{{font-family:Arial,sans-serif;font-size:8pt;margin:0}}table{{border-collapse:collapse;width:100%;margin-top:15px;page-break-inside:auto}}
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
                bw = bar['weight'] if 'weight' in bar.keys() and bar['weight'] is not None else 0.0
                bfw = bar['fine_weight'] if 'fine_weight' in bar.keys() and bar['fine_weight'] is not None else 0.0
                bp = bar['purity'] if 'purity' in bar.keys() and bar['purity'] is not None else 0.0
                # Note: bar_no and status are no longer primary fields in this context

                bc += 1
                tw += bw
                tf += bfw
                html += f"""<tr>
                               <td>{idx+1}</td>
                               <td class="right">{bw:.3f}</td>
                               <td class="right">{bp:.2f}</td>
                               <td class="right">{bfw:.3f}</td>
                           </tr>"""
        else:
            # Adjust colspan for the new number of columns
            html += '<tr><td colspan="4" style="text-align:center;padding:10px 0;">-- No bars assigned --</td></tr>'

        html += f"""</tbody></table>
                   <div class="totals">TOTAL Bars: {bc} | TOTAL Weight: {tw:,.3f} g | TOTAL Fine Wt: {tf:,.3f} g</div>
                   </body></html>"""
        return html

    # ---------------------- Preview Enhancements ----------------------
    def _open_preview_with_enhancements(self, html_content, parent_widget, title, table_mode=False):
        """Open QPrintPreviewDialog with custom toolbar actions and persistent zoom."""
        import logging
        # Create preview dialog
        preview = QPrintPreviewDialog(self.printer, parent_widget)
        preview.setWindowTitle(title)
        preview.paintRequested.connect(lambda printer: self._print_html(printer, html_content, table_mode=table_mode))

        # Set initial zoom from settings
        preview_widget = None
        try:
            preview_widget = preview.findChild(QPrintPreviewWidget)
            if preview_widget:
                settings = get_app_settings()
                default_zoom = 1.25
                zoom_factor = settings.value("print/preview_zoom", defaultValue=default_zoom, type=float)
                zoom_factor = max(0.1, min(zoom_factor, 5.0))
                logging.getLogger(__name__).debug(f"Applying zoom factor: {zoom_factor}")
                # Ensure custom zoom mode before applying factor
                try:
                    preview_widget.setZoomMode(QPrintPreviewWidget.CustomZoom)
                except Exception:
                    pass
                preview_widget.setZoomFactor(zoom_factor)
            else:
                logging.getLogger(__name__).warning("Could not find QPrintPreviewWidget to set zoom.")
        except Exception as zoom_err:
            logging.getLogger(__name__).warning(f"Error setting initial zoom: {zoom_err}")

        # Enhance toolbar
        try:
            self._augment_preview_toolbar(preview, preview_widget, html_content, table_mode, parent_widget)
        except Exception as tb_err:
            logging.getLogger(__name__).warning(f"Could not augment preview toolbar: {tb_err}")

        preview.showMaximized()

        # Execute dialog; after close, persist zoom
        preview.exec_()
        try:
            if preview_widget:
                z = float(preview_widget.zoomFactor())
                settings = get_app_settings()
                settings.setValue("print/preview_zoom", z)
                logging.getLogger(__name__).debug(f"Saved preview zoom: {z}")
        except Exception as save_err:
            logging.getLogger(__name__).warning(f"Could not save preview zoom: {save_err}")

    def _augment_preview_toolbar(self, preview, preview_widget, html_content, table_mode, parent_widget):
        """Add useful actions to the existing QPrintPreviewDialog toolbar."""
        toolbars = preview.findChildren(QToolBar)
        toolbar = toolbars[0] if toolbars else None
        if not toolbar:
            return

        # Separator helper
        def sep():
            toolbar.addSeparator()

        # Save as PDF
        act_pdf = QAction("Save PDF", preview)
        act_pdf.setToolTip("Export to PDF file (Ctrl+S)")
        act_pdf.setShortcut("Ctrl+S")
        act_pdf.triggered.connect(lambda: self._export_pdf_via_dialog(html_content, table_mode, parent_widget))
        toolbar.addAction(act_pdf)

        # Page Setup
        act_page = QAction("Page Setup", preview)
        act_page.setToolTip("Choose page size, margins, orientation")
        act_page.triggered.connect(lambda: self._page_setup_and_refresh(preview, html_content, table_mode))
        toolbar.addAction(act_page)

        sep()

        # Zoom controls (in addition to built-ins)
        if preview_widget:
            act_zi = QAction("Zoom +", preview)
            act_zi.setShortcut("+")
            def _zoom_in():
                try:
                    preview_widget.setZoomMode(QPrintPreviewWidget.CustomZoom)
                except Exception:
                    pass
                try:
                    z = float(preview_widget.zoomFactor())
                except Exception:
                    z = 1.0
                z = min(5.0, z * 1.10)
                preview_widget.setZoomFactor(z)
            act_zi.triggered.connect(_zoom_in)
            toolbar.addAction(act_zi)

            act_zo = QAction("Zoom -", preview)
            act_zo.setShortcut("-")
            def _zoom_out():
                try:
                    preview_widget.setZoomMode(QPrintPreviewWidget.CustomZoom)
                except Exception:
                    pass
                try:
                    z = float(preview_widget.zoomFactor())
                except Exception:
                    z = 1.0
                z = max(0.1, z / 1.10)
                preview_widget.setZoomFactor(z)
            act_zo.triggered.connect(_zoom_out)
            toolbar.addAction(act_zo)

            act_fitw = QAction("Fit Width", preview)
            act_fitw.setShortcut("Ctrl+W")
            def _fit_width():
                try:
                    preview_widget.fitToWidth()
                except Exception:
                    pass
            act_fitw.triggered.connect(_fit_width)
            toolbar.addAction(act_fitw)

            act_fitp = QAction("Fit Page", preview)
            act_fitp.setShortcut("Ctrl+F")
            def _fit_page():
                try:
                    preview_widget.fitInView()
                except Exception:
                    pass
            act_fitp.triggered.connect(_fit_page)
            toolbar.addAction(act_fitp)

        sep()

        # Orientation toggle
        act_orient = QAction("Toggle Portrait/Landscape", preview)
        act_orient.setToolTip("Switch orientation and refresh preview")
        act_orient.triggered.connect(lambda: self._toggle_orientation_and_refresh(preview, html_content, table_mode))
        toolbar.addAction(act_orient)

        sep()

        # Page navigation and page info
        if preview_widget:
            act_first = QAction("First", preview)
            act_first.setToolTip("Go to first page (Home)")
            act_first.setShortcut("Home")
            act_first.triggered.connect(lambda: preview_widget.setCurrentPage(1))
            toolbar.addAction(act_first)

            act_prev = QAction("Prev", preview)
            act_prev.setShortcut("PgUp")
            act_prev.triggered.connect(lambda: preview_widget.setCurrentPage(max(1, preview_widget.currentPage() - 1)))
            toolbar.addAction(act_prev)

            act_next = QAction("Next", preview)
            act_next.setShortcut("PgDown")
            def _safe_next():
                try:
                    pc = preview_widget.pageCount()
                except Exception:
                    pc = preview_widget.currentPage() + 1
                preview_widget.setCurrentPage(min(pc, preview_widget.currentPage() + 1))
            act_next.triggered.connect(_safe_next)
            toolbar.addAction(act_next)

            act_last = QAction("Last", preview)
            act_last.setToolTip("Go to last page (End)")
            act_last.setShortcut("End")
            def _safe_last():
                try:
                    preview_widget.setCurrentPage(preview_widget.pageCount())
                except Exception:
                    pass
            act_last.triggered.connect(_safe_last)
            toolbar.addAction(act_last)

            # Page info label
            page_info = QLabel("")
            page_info_action = QWidgetAction(preview)
            page_info_action.setDefaultWidget(page_info)
            toolbar.addAction(page_info_action)

            def _update_page_info():
                try:
                    page_info.setText(f"  Page {preview_widget.currentPage()} / {preview_widget.pageCount()}  ")
                except Exception:
                    pass

            try:
                # previewChanged is emitted when the preview is repainted
                preview_widget.previewChanged.connect(_update_page_info)
            except Exception:
                pass
            # Initialize
            _update_page_info()

        sep()

        # Quick Print (bypass dialog) with distinct shortcut
        act_qprint = QAction("Quick Print", preview)
        act_qprint.setToolTip("Send directly to current/default printer (Ctrl+Shift+P)")
        act_qprint.setShortcut("Ctrl+Shift+P")
        act_qprint.triggered.connect(lambda: self._quick_print_current(preview, html_content, table_mode, parent_widget))
        toolbar.addAction(act_qprint)

        # Select Printer (updates current printer without printing)
        act_sel_prn = QAction("Select Printer", preview)
        act_sel_prn.setToolTip("Choose a printer and keep it for this session")
        def _choose_printer():
            dlg = QPrintDialog(self.printer, preview)
            if dlg.exec_() == QDialog.Accepted:
                try:
                    # Persist selected printer name
                    prn_name = self.printer.printerName()
                    s = get_app_settings()
                    s.setValue("print/default_printer", prn_name)
                except Exception:
                    pass
                # Refresh preview in case device metrics differ
                w = preview.findChild(QPrintPreviewWidget)
                if w:
                    w.updatePreview()
        act_sel_prn.triggered.connect(_choose_printer)
        toolbar.addAction(act_sel_prn)

    def _export_pdf_via_dialog(self, html_content, table_mode, parent_widget):
        """Prompt for a PDF path and export current content as PDF."""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(parent_widget, "Save as PDF", "estimate.pdf", "PDF Files (*.pdf)", options=options)
        if not file_path:
            return
        try:
            # Use a temporary printer configured for PDF output
            pdf_printer = QPrinter(QPrinter.HighResolution)
            pdf_printer.setOutputFormat(QPrinter.PdfFormat)
            if not file_path.lower().endswith('.pdf'):
                file_path = f"{file_path}.pdf"
            pdf_printer.setOutputFileName(file_path)
            # Preserve page size and orientation from current printer
            pdf_printer.setPageSize(self.printer.pageSize())
            pdf_printer.setOrientation(self.printer.orientation())
            # Apply current margins from settings (kept consistent across previews)
            settings = get_app_settings()
            margins_str = settings.value("print/margins", defaultValue="10,5,10,5", type=str)
            try:
                margins = [int(m.strip()) for m in margins_str.split(',')]
                if len(margins) != 4:
                    margins = [10, 5, 10, 5]
            except Exception:
                margins = [10, 5, 10, 5]
            pdf_printer.setPageMargins(margins[0], margins[1], margins[2], margins[3], QPrinter.Millimeter)
            # Render
            self._print_html(pdf_printer, html_content, table_mode=table_mode)
            QMessageBox.information(parent_widget, "Saved", f"PDF saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(parent_widget, "Export Failed", f"Could not export PDF:\n{str(e)}")

    def _page_setup_and_refresh(self, preview, html_content, table_mode):
        """Open page setup dialog and refresh preview if accepted."""
        dlg = QPageSetupDialog(self.printer, preview)
        if dlg.exec_() == QDialog.Accepted:
            # Refresh preview via inner QPrintPreviewWidget
            widget = preview.findChild(QPrintPreviewWidget)
            if widget:
                widget.updatePreview()
            else:
                preview.repaint()

    # Note: Rely on QPrintPreviewDialog's built-in Print action (Ctrl+P)

    def _toggle_orientation_and_refresh(self, preview, html_content, table_mode):
        """Toggle between portrait and landscape and refresh preview."""
        current = self.printer.orientation()
        self.printer.setOrientation(QPrinter.Landscape if current == QPrinter.Portrait else QPrinter.Portrait)
        widget = preview.findChild(QPrintPreviewWidget)
        if widget:
            widget.updatePreview()
        else:
            preview.repaint()

    def _quick_print_current(self, preview, html_content, table_mode, parent_widget):
        """Send the document directly to the currently configured/default printer."""
        try:
            self._print_html(self.printer, html_content, table_mode=table_mode)
            # Optional toast: keep it non-intrusive
            QMessageBox.information(parent_widget or preview, "Printing", "Document sent to printer.")
        except Exception as e:
            QMessageBox.critical(parent_widget or preview, "Print Failed", f"Could not print document:\n{str(e)}")


