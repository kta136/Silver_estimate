from __future__ import annotations

import pytest
from PySide6.QtPrintSupport import QPrinter

from silverestimate.ui.print_payload_builder import PrintPreviewPayload
from silverestimate.ui.print_preview_output import (
    PrintOutputService,
    PrintOutputStatus,
)
from silverestimate.ui.silver_bar_print_document import SilverBarListPrintDocument


def _payload() -> PrintPreviewPayload:
    return PrintPreviewPayload(
        document=SilverBarListPrintDocument.from_rows(
            {"list_identifier": "LIST-001", "list_note": "Output"},
            [],
        ),
        title="Print Preview",
        document_kind="silver_bar_list",
        suggested_filename="List.pdf",
    )


def test_pdf_export_cancellation_is_explicit_and_does_not_render(qt_app) -> None:
    del qt_app
    render_calls = []
    service = PrintOutputService(
        printer=QPrinter(),
        render_document=lambda *args: render_calls.append(args),
    )

    outcome = service.export_pdf(_payload(), "")

    assert outcome.status is PrintOutputStatus.CANCELLED
    assert outcome.cancelled
    assert not outcome.succeeded
    assert render_calls == []


@pytest.mark.parametrize(
    "printer_available, expected_status, expected_render_count",
    [
        pytest.param(True, PrintOutputStatus.SUCCESS, 1, id="success"),
        pytest.param(
            False, PrintOutputStatus.VALIDATION_FAILED, 0, id="printer-unavailable"
        ),
    ],
)
def test_quick_print_returns_outcome_and_renders_only_with_valid_printer(
    qt_app, printer_available, expected_status, expected_render_count
) -> None:
    del qt_app
    render_calls = []
    service = PrintOutputService(
        printer=QPrinter(),
        render_document=lambda *args: render_calls.append(args),
        printer_validator=lambda _printer: (
            printer_available,
            "" if printer_available else "No printer is available.",
        ),
    )

    outcome = service.quick_print(_payload())

    assert outcome.status is expected_status
    assert outcome.succeeded is printer_available
    assert len(render_calls) == expected_render_count
    if not printer_available:
        assert outcome.message == "No printer is available."
