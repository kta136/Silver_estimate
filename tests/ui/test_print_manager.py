from PyQt5.QtGui import QFont

from silverestimate.ui.print_manager import PrintManager


class _DbStub:
    pass


def test_generate_silver_bars_html_escapes_dynamic_text(qt_app, settings_stub):
    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))
    bars = [
        {
            "bar_id": 1,
            "estimate_voucher_no": "V1<script>alert(1)</script>",
            "weight": 12.345,
            "purity": 99.99,
            "fine_weight": 12.343,
            "date_added": "2026-02-13 <today>",
            "status": "In <Stock>",
        }
    ]

    rendered = manager._generate_silver_bars_html_table(bars, status_filter="<all>")

    assert "<script>alert(1)</script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "In &lt;Stock&gt;" in rendered
    assert "2026-02-13 &lt;today&gt;" in rendered
    assert "SILVER BARS INVENTORY - &lt;all&gt;" in rendered


def test_generate_estimate_thermal_escapes_note_html(qt_app, settings_stub):
    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))
    estimate_data = {
        "header": {
            "voucher_no": "V-001",
            "date": "2026-02-13",
            "silver_rate": 0.0,
            "note": "<b>unsafe-note</b>",
            "last_balance_silver": 0.0,
            "last_balance_amount": 0.0,
        },
        "items": [],
    }

    rendered = manager._generate_estimate_thermal_format(estimate_data)

    assert "<b>unsafe-note</b>" not in rendered
    assert "&lt;b&gt;unsafe-note&lt;/b&gt;" in rendered
