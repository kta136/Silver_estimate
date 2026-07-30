from __future__ import annotations

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


def test_quick_print_validation_failure_is_explicit(qt_app) -> None:
    del qt_app
    render_calls = []
    service = PrintOutputService(
        printer=QPrinter(),
        render_document=lambda *args: render_calls.append(args),
        printer_validator=lambda _printer: (False, "No printer is available."),
    )

    outcome = service.quick_print(_payload())

    assert outcome.status is PrintOutputStatus.VALIDATION_FAILED
    assert outcome.message == "No printer is available."
    assert render_calls == []


def test_quick_print_success_returns_typed_outcome(qt_app) -> None:
    del qt_app
    render_calls = []
    service = PrintOutputService(
        printer=QPrinter(),
        render_document=lambda *args: render_calls.append(args),
        printer_validator=lambda _printer: (True, ""),
    )

    outcome = service.quick_print(_payload())

    assert outcome.status is PrintOutputStatus.SUCCESS
    assert outcome.succeeded
    assert len(render_calls) == 1
