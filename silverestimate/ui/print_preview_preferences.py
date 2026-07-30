"""Typed persistence boundary for print-preview preferences."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable

from PySide6.QtPrintSupport import QPrinter, QPrintPreviewWidget

from silverestimate.infrastructure.settings import SettingsKey, get_app_settings

from .print_format_spec import normalize_estimate_format
from .print_page_settings import save_printer_page_settings
from .print_payload_builder import PrintPreviewPayload

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreviewZoomPreference:
    """Normalized preview zoom preference."""

    use_fit_width: bool
    factor: float = 1.25


class PrintPreviewPreferences:
    """Load and persist preview state without owning preview widgets."""

    def __init__(
        self,
        *,
        persist_estimate_format: Callable[[str], None] | None = None,
        persist_tunch_visibility: Callable[[bool], None] | None = None,
    ) -> None:
        self._persist_estimate_format = persist_estimate_format
        self._persist_tunch_visibility = persist_tunch_visibility

    def load_zoom(self) -> PreviewZoomPreference:
        settings = get_app_settings()
        has_saved_zoom = settings.contains(SettingsKey.PRINT_PREVIEW_ZOOM)
        if not has_saved_zoom:
            return PreviewZoomPreference(use_fit_width=True)

        default_zoom = 1.25
        zoom_factor = settings.get_float(
            SettingsKey.PRINT_PREVIEW_ZOOM,
            default_zoom,
            minimum=0.1,
            maximum=5.0,
        )
        return PreviewZoomPreference(
            use_fit_width=False,
            factor=zoom_factor,
        )

    def apply_initial_zoom(
        self,
        preview_widget: QPrintPreviewWidget | None,
    ) -> None:
        if not preview_widget:
            LOGGER.warning("Could not find QPrintPreviewWidget to set zoom.")
            return
        try:
            preference = self.load_zoom()
            if preference.use_fit_width:
                preview_widget.setZoomMode(QPrintPreviewWidget.ZoomMode.FitToWidth)
                return
            preview_widget.setZoomMode(QPrintPreviewWidget.ZoomMode.CustomZoom)
            preview_widget.setZoomFactor(preference.factor)
        except Exception as exc:
            LOGGER.warning("Error setting initial zoom: %s", exc)

    def save_zoom(self, preview_widget: QPrintPreviewWidget | None) -> None:
        if not preview_widget:
            return
        try:
            zoom_factor = float(preview_widget.zoomFactor())
            get_app_settings().set(SettingsKey.PRINT_PREVIEW_ZOOM, zoom_factor)
            LOGGER.debug("Saved preview zoom: %s", zoom_factor)
        except Exception as exc:
            LOGGER.warning("Could not save preview zoom: %s", exc)

    def save_preview_defaults(
        self,
        printer: QPrinter,
        payload: PrintPreviewPayload,
    ) -> None:
        try:
            settings = get_app_settings()
            save_printer_page_settings(settings, printer)
            self._save_payload_defaults(settings, payload)
            settings.sync()
        except Exception as exc:
            LOGGER.warning("Could not persist preview defaults: %s", exc)

    def remember_selected_printer(self, printer: QPrinter) -> None:
        try:
            printer_name = printer.printerName().strip()
            if printer_name:
                get_app_settings().set(
                    SettingsKey.PRINT_DEFAULT_PRINTER,
                    printer_name,
                )
        except Exception as exc:
            LOGGER.debug("Failed to persist selected printer name: %s", exc)

    def default_pdf_path(self, suggested_filename: str) -> str:
        settings = get_app_settings()
        last_export_dir = settings.get_text(
            SettingsKey.PRINT_LAST_EXPORT_DIR,
        )
        if last_export_dir and os.path.isdir(last_export_dir):
            return os.path.join(last_export_dir, suggested_filename)
        return suggested_filename

    def remember_export_directory(self, directory: str) -> None:
        get_app_settings().set(SettingsKey.PRINT_LAST_EXPORT_DIR, directory)

    def _save_payload_defaults(
        self,
        settings,
        payload: PrintPreviewPayload,
    ) -> None:
        if payload.document_kind != "estimate":
            return
        if payload.format_key:
            format_key = normalize_estimate_format(payload.format_key)
            settings.set(SettingsKey.PRINT_ESTIMATE_LAYOUT, format_key)
            if self._persist_estimate_format is not None:
                self._persist_estimate_format(format_key)
        settings.set(SettingsKey.PRINT_SHOW_TUNCH, bool(payload.show_tunch))
        if self._persist_tunch_visibility is not None:
            self._persist_tunch_visibility(bool(payload.show_tunch))


__all__ = ["PreviewZoomPreference", "PrintPreviewPreferences"]
