"""Totals panel component for estimate entry."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

from silverestimate.domain.estimate_models import TotalsResult


class TotalsPanel(QWidget):
    """Panel for displaying estimate totals and calculations.

    This component displays breakdowns by category (Regular, Return, Silver Bar)
    and final calculations (Net Fine Weight, Net Wage, Grand Total).
    """

    def __init__(self, parent=None):
        """Initialize the totals panel.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        self.setObjectName("TotalsContainer")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # Hidden compatibility label so existing logic can continue to update it
        self.mode_indicator_label = QLabel("Mode: Regular")
        self.mode_indicator_label.setVisible(False)

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(12, 6, 18, 10)

        # Helper function to create a form layout for a breakdown section
        def create_breakdown_form(title, labels_attrs):
            form = QFormLayout()
            form.setSpacing(5)
            form.addRow(QLabel(f"<b><u>{title}</u></b>"))
            for label_text, attr_name, default_value in labels_attrs:
                label = QLabel(default_value)
                label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                setattr(self, attr_name, label)
                form.addRow(label_text, label)
            return form

        def create_separator():
            sep = QFrame()
            sep.setFrameShape(QFrame.VLine)
            sep.setFrameShadow(QFrame.Sunken)
            return sep

        # Overall Totals (leftmost): Total Gross and Total Poly
        overall_labels = [
            ("Total Gross Wt:", 'overall_gross_label', "0.0"),
            ("Total Poly Wt:", 'overall_poly_label', "0.0"),
        ]
        main_layout.addLayout(create_breakdown_form("Totals", overall_labels))
        main_layout.addWidget(create_separator())

        # Regular Items
        regular_labels = [
            ("Gross Wt:", 'total_gross_label', "0.0"),
            ("Net Wt:", 'total_net_label', "0.0"),
            ("Fine Wt:", 'total_fine_label', "0.0"),
        ]
        main_layout.addLayout(create_breakdown_form("Regular", regular_labels))
        main_layout.addWidget(create_separator())

        # Return Items
        return_labels = [
            ("Gross Wt:", 'return_gross_label', "0.0"),
            ("Net Wt:", 'return_net_label', "0.0"),
            ("Fine Wt:", 'return_fine_label', "0.0"),
        ]
        main_layout.addLayout(create_breakdown_form("Return", return_labels))
        main_layout.addWidget(create_separator())

        # Silver Bars
        bar_labels = [
            ("Gross Wt:", 'bar_gross_label', "0.0"),
            ("Net Wt:", 'bar_net_label', "0.0"),
            ("Fine Wt:", 'bar_fine_label', "0.0"),
        ]
        main_layout.addLayout(create_breakdown_form("Silver Bar", bar_labels))

        # Add stretch to push Final Calculation to the right
        main_layout.addStretch(1)
        main_layout.addWidget(create_separator())

        # Final Calculation Section
        final_calc_form = QFormLayout()
        final_calc_form.setSpacing(8)
        final_calc_form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        final_calc_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        final_title_label = QLabel("Final Calculation")
        final_title_font = final_title_label.font()
        final_title_font.setPointSize(final_title_font.pointSize() + 1)
        final_title_font.setBold(True)
        final_title_font.setUnderline(True)
        final_title_label.setFont(final_title_font)
        final_calc_form.addRow(final_title_label)

        # Net Fine
        self.net_fine_label = QLabel("0.0")
        self.net_fine_label.setStyleSheet("font-weight: bold;")
        self.net_fine_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.net_fine_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        self.net_fine_label.setMinimumWidth(100)
        net_fine_header = QLabel("Net Fine Wt:")
        net_fine_font = self.net_fine_label.font()
        net_fine_font.setPointSize(net_fine_font.pointSize() + 1)
        self.net_fine_label.setFont(net_fine_font)
        net_fine_header_font = net_fine_header.font()
        net_fine_header_font.setPointSize(net_fine_header_font.pointSize() + 1)
        net_fine_header_font.setBold(True)
        net_fine_header.setFont(net_fine_header_font)
        final_calc_form.addRow(net_fine_header, self.net_fine_label)

        # Net Wage
        self.net_wage_label = QLabel("0")
        self.net_wage_label.setStyleSheet("font-weight: bold;")
        self.net_wage_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.net_wage_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        self.net_wage_label.setMinimumWidth(100)
        net_wage_header = QLabel("Net Wage:")
        net_wage_font = self.net_wage_label.font()
        net_wage_font.setPointSize(net_wage_font.pointSize() + 1)
        self.net_wage_label.setFont(net_wage_font)
        net_wage_header_font = net_wage_header.font()
        net_wage_header_font.setPointSize(net_wage_header_font.pointSize() + 1)
        net_wage_header_font.setBold(True)
        net_wage_header.setFont(net_wage_header_font)
        final_calc_form.addRow(net_wage_header, self.net_wage_label)

        # Separator before Grand Total
        line_before_grand = QFrame()
        line_before_grand.setFrameShape(QFrame.HLine)
        line_before_grand.setFrameShadow(QFrame.Sunken)
        final_calc_form.addRow(line_before_grand)

        # Grand Total
        self.grand_total_label = QLabel("0")
        self.grand_total_label.setStyleSheet("font-weight: bold; color: #059669;")
        self.grand_total_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.grand_total_label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        self.grand_total_label.setMinimumWidth(100)
        grand_total_header = QLabel("Grand Total:")
        grand_total_font = self.grand_total_label.font()
        grand_total_font.setPointSize(grand_total_font.pointSize() + 2)
        self.grand_total_label.setFont(grand_total_font)
        grand_total_header_font = grand_total_header.font()
        grand_total_header_font.setPointSize(grand_total_header_font.pointSize() + 2)
        grand_total_header_font.setBold(True)
        grand_total_header.setFont(grand_total_header_font)
        final_calc_form.addRow(grand_total_header, self.grand_total_label)

        main_layout.addLayout(final_calc_form)

    # Public methods for updating totals

    def set_totals(self, totals: TotalsResult) -> None:
        """Update all totals from a TotalsResult.

        Args:
            totals: The totals result containing all calculations
        """
        # Overall totals
        self.overall_gross_label.setText(f"{totals.overall_gross:.2f}")
        self.overall_poly_label.setText(f"{totals.overall_poly:.2f}")

        # Regular items
        self.total_gross_label.setText(f"{totals.regular.gross:.2f}")
        self.total_net_label.setText(f"{totals.regular.net:.2f}")
        self.total_fine_label.setText(f"{totals.regular.fine:.2f}")

        # Return items
        self.return_gross_label.setText(f"{totals.returns.gross:.2f}")
        self.return_net_label.setText(f"{totals.returns.net:.2f}")
        self.return_fine_label.setText(f"{totals.returns.fine:.2f}")

        # Silver bars
        self.bar_gross_label.setText(f"{totals.silver_bars.gross:.2f}")
        self.bar_net_label.setText(f"{totals.silver_bars.net:.2f}")
        self.bar_fine_label.setText(f"{totals.silver_bars.fine:.2f}")

        # Final calculations
        self.net_fine_label.setText(f"{totals.net_fine:.2f}")
        self.net_wage_label.setText(f"{totals.net_wage:.0f}")
        self.grand_total_label.setText(f"₹ {totals.grand_total:.0f}")

    def clear_totals(self) -> None:
        """Reset all totals to zero."""
        # Overall totals
        self.overall_gross_label.setText("0.0")
        self.overall_poly_label.setText("0.0")

        # Regular items
        self.total_gross_label.setText("0.0")
        self.total_net_label.setText("0.0")
        self.total_fine_label.setText("0.0")

        # Return items
        self.return_gross_label.setText("0.0")
        self.return_net_label.setText("0.0")
        self.return_fine_label.setText("0.0")

        # Silver bars
        self.bar_gross_label.setText("0.0")
        self.bar_net_label.setText("0.0")
        self.bar_fine_label.setText("0.0")

        # Final calculations
        self.net_fine_label.setText("0.0")
        self.net_wage_label.setText("0")
        self.grand_total_label.setText("₹ 0")

    # Font size methods for EstimateLogic compatibility

    def set_breakdown_font_size(self, size: int) -> None:
        """Apply font size to breakdown totals labels.

        Args:
            size: Font point size
        """
        labels = [
            self.overall_gross_label, self.overall_poly_label,
            self.total_gross_label, self.total_net_label, self.total_fine_label,
            self.return_gross_label, self.return_net_label, self.return_fine_label,
            self.bar_gross_label, self.bar_net_label, self.bar_fine_label
        ]
        for label in labels:
            font = label.font()
            font.setPointSize(int(size))
            label.setFont(font)

    def set_final_calc_font_size(self, size: int) -> None:
        """Apply font size to final calculation labels.

        Args:
            size: Font point size
        """
        # Preserve stylesheet while setting font size
        for label in [self.net_fine_label, self.net_wage_label]:
            font = label.font()
            font.setPointSize(int(size))
            label.setFont(font)

        # Grand total - preserve bold and color
        font = self.grand_total_label.font()
        font.setPointSize(int(size))
        self.grand_total_label.setFont(font)
        # Keep color in stylesheet
        self.grand_total_label.setStyleSheet("font-weight: bold; color: #059669;")
