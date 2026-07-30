"""Preview zoom, view-mode, and page-navigation ownership."""

from __future__ import annotations

import logging
from typing import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtPrintSupport import QPrintPreviewWidget
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QToolBar,
    QWidget,
)

from .icons import get_icon
from .print_preview_dialog import PrintPreviewDialog
from .themed_controls import ThemedSpinBox

LOGGER = logging.getLogger(__name__)

AddToolbarAction = Callable[[QToolBar, QAction], None]


class _PreviewWheelZoomFilter(QObject):
    """Translate Ctrl+wheel into preview zoom actions."""

    def __init__(
        self,
        *,
        zoom_in: Callable[[], None],
        zoom_out: Callable[[], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._zoom_in = zoom_in
        self._zoom_out = zoom_out

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API
        if event.type() != QEvent.Type.Wheel:
            return super().eventFilter(watched, event)
        if not bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            return super().eventFilter(watched, event)

        try:
            delta = int(event.angleDelta().y())
        except Exception:
            delta = 0
        if delta > 0:
            self._zoom_in()
        elif delta < 0:
            self._zoom_out()
        else:
            return super().eventFilter(watched, event)
        return True


class PrintPreviewNavigationController:
    """Own zoom, view mode, keyboard navigation, and page indicators."""

    def __init__(self) -> None:
        self._wheel_zoom_filters: dict[int, _PreviewWheelZoomFilter] = {}

    def install_ctrl_wheel_zoom(
        self,
        preview: PrintPreviewDialog,
        preview_widget: QPrintPreviewWidget | None,
    ) -> None:
        if not preview_widget:
            return
        filter_obj = _PreviewWheelZoomFilter(
            zoom_in=lambda: self.zoom_in(preview_widget),
            zoom_out=lambda: self.zoom_out(preview_widget),
            parent=preview,
        )
        preview_widget.installEventFilter(filter_obj)
        viewport = getattr(preview_widget, "viewport", lambda: None)()
        if viewport is not None:
            viewport.installEventFilter(filter_obj)
        preview_key = id(preview)
        self._wheel_zoom_filters[preview_key] = filter_obj
        preview.destroyed.connect(
            lambda _obj=None, key=preview_key: self._wheel_zoom_filters.pop(key, None)
        )

    def add_view_mode_actions(
        self,
        target: QToolBar | QMenu,
        preview_widget: QPrintPreviewWidget,
        preview: PrintPreviewDialog,
    ) -> None:
        group = QActionGroup(preview)
        group.setExclusive(True)
        view_actions = self._create_view_actions(
            target,
            preview_widget,
            preview,
            group,
        )

        def sync_view_actions() -> None:
            try:
                current_mode = preview_widget.viewMode()
            except Exception:
                current_mode = QPrintPreviewWidget.ViewMode.SinglePageView
            for action, mode in view_actions:
                action.blockSignals(True)
                action.setChecked(mode == current_mode)
                action.blockSignals(False)

        sync_view_actions()
        try:
            preview_widget.previewChanged.connect(sync_view_actions)
        except Exception as exc:
            LOGGER.debug("Failed to sync preview view mode actions: %s", exc)

    def add_zoom_actions(
        self,
        toolbar: QToolBar,
        preview: PrintPreviewDialog,
        preview_widget: QPrintPreviewWidget,
        add_action: AddToolbarAction,
    ) -> None:
        actions = (
            ("fit_width", "Fit Width", "Ctrl+W", self.fit_width),
            ("fit_page", "Fit Page", "Ctrl+F", self.fit_page),
            ("zoom_out", "Zoom Out", "Ctrl+-", self.zoom_out),
            ("zoom_in", "Zoom In", "Ctrl++", self.zoom_in),
        )
        for icon_name, text, shortcut, callback in actions:
            action = QAction(get_icon(icon_name, widget=preview), text, preview)
            action.setShortcut(shortcut)
            action.setToolTip(f"{text.lower().capitalize()} ({shortcut})")
            action.setPriority(
                QAction.Priority.NormalPriority
                if text in {"Fit Width", "Fit Page"}
                else QAction.Priority.LowPriority
            )
            action.triggered.connect(
                lambda checked=False, handler=callback: handler(preview_widget)
            )
            add_action(toolbar, action)

    def add_page_navigation(
        self,
        toolbar: QToolBar,
        more_menu: QMenu,
        preview: PrintPreviewDialog,
        preview_widget: QPrintPreviewWidget,
    ) -> None:
        first = self._page_action(
            preview,
            icon_name="page_first",
            text="First",
            shortcut="Home",
            callback=lambda: preview_widget.setCurrentPage(1),
        )
        previous = self._page_action(
            preview,
            icon_name="page_previous",
            text="Prev",
            shortcut="PgUp",
            callback=lambda: preview_widget.setCurrentPage(
                max(1, preview_widget.currentPage() - 1)
            ),
        )
        next_page = self._page_action(
            preview,
            icon_name="page_next",
            text="Next",
            shortcut="PgDown",
            callback=lambda: self.go_next_page(preview_widget),
        )
        last = self._page_action(
            preview,
            icon_name="page_last",
            text="Last",
            shortcut="End",
            callback=lambda: self.go_last_page(preview_widget),
        )

        preview.addActions([first, previous, next_page, last])
        more_menu.addSeparator()
        more_menu.addActions([first, previous, next_page, last])
        page_spin, total_label = self._build_page_navigation_widget(
            preview,
            preview_widget,
        )
        container = page_spin.parentWidget()
        if container is None:
            raise RuntimeError("Page navigation controls have no container.")
        toolbar.addWidget(container)
        self._bind_page_info(preview_widget, page_spin, total_label)

    def zoom_in(self, preview_widget: QPrintPreviewWidget) -> None:
        self._set_custom_zoom(preview_widget)
        try:
            zoom_factor = float(preview_widget.zoomFactor())
        except Exception:
            zoom_factor = 1.0
        preview_widget.setZoomFactor(min(5.0, zoom_factor * 1.10))

    def zoom_out(self, preview_widget: QPrintPreviewWidget) -> None:
        self._set_custom_zoom(preview_widget)
        try:
            zoom_factor = float(preview_widget.zoomFactor())
        except Exception:
            zoom_factor = 1.0
        preview_widget.setZoomFactor(max(0.1, zoom_factor / 1.10))

    @staticmethod
    def fit_width(preview_widget: QPrintPreviewWidget) -> None:
        try:
            preview_widget.fitToWidth()
        except Exception as exc:
            LOGGER.debug("Failed to fit preview to width: %s", exc)

    @staticmethod
    def fit_page(preview_widget: QPrintPreviewWidget) -> None:
        try:
            preview_widget.fitInView()
        except Exception as exc:
            LOGGER.debug("Failed to fit preview to page: %s", exc)

    @staticmethod
    def set_view_mode(
        preview_widget: QPrintPreviewWidget,
        view_mode: QPrintPreviewWidget.ViewMode,
    ) -> None:
        try:
            preview_widget.setViewMode(view_mode)
        except Exception as exc:
            LOGGER.debug("Failed to set preview view mode: %s", exc)

    @staticmethod
    def go_next_page(preview_widget: QPrintPreviewWidget) -> None:
        try:
            page_count = preview_widget.pageCount()
        except Exception:
            page_count = preview_widget.currentPage() + 1
        preview_widget.setCurrentPage(min(page_count, preview_widget.currentPage() + 1))

    @staticmethod
    def go_last_page(preview_widget: QPrintPreviewWidget) -> None:
        try:
            preview_widget.setCurrentPage(preview_widget.pageCount())
        except Exception as exc:
            LOGGER.debug("Failed to navigate preview to last page: %s", exc)

    def _create_view_actions(
        self,
        target: QToolBar | QMenu,
        preview_widget: QPrintPreviewWidget,
        preview: PrintPreviewDialog,
        group: QActionGroup,
    ) -> list[tuple[QAction, QPrintPreviewWidget.ViewMode]]:
        view_actions: list[tuple[QAction, QPrintPreviewWidget.ViewMode]] = []
        for icon_name, text, mode in (
            (
                "view_single_page",
                "Single Page",
                QPrintPreviewWidget.ViewMode.SinglePageView,
            ),
            (
                "view_facing_pages",
                "Facing Pages",
                QPrintPreviewWidget.ViewMode.FacingPagesView,
            ),
            (
                "view_overview",
                "All Pages",
                QPrintPreviewWidget.ViewMode.AllPagesView,
            ),
        ):
            action = QAction(get_icon(icon_name, widget=preview), text, preview)
            action.setCheckable(True)
            action.setPriority(QAction.Priority.LowPriority)
            action.setToolTip(text)
            action.triggered.connect(
                lambda checked=False, view_mode=mode: self.set_view_mode(
                    preview_widget,
                    view_mode,
                )
            )
            group.addAction(action)
            target.addAction(action)
            view_actions.append((action, mode))
        return view_actions

    @staticmethod
    def _build_page_navigation_widget(
        preview: PrintPreviewDialog,
        preview_widget: QPrintPreviewWidget,
    ) -> tuple[ThemedSpinBox, QLabel]:
        container = QWidget(preview)
        container.setObjectName("PreviewPageNavigator")
        container.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        spin = ThemedSpinBox(container)
        spin.setObjectName("PreviewPageSpin")
        spin.setRange(1, 1)
        spin.setMinimumWidth(52)
        spin.setMaximumWidth(60)
        spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        spin.setAlignment(Qt.AlignmentFlag.AlignRight)
        spin.setAccessibleName("Page number")
        spin.setToolTip("Jump directly to a page number")
        spin.valueChanged.connect(lambda value: preview_widget.setCurrentPage(value))

        total_label = QLabel("/ 1", container)
        layout.addWidget(spin)
        layout.addWidget(total_label)
        return spin, total_label

    @staticmethod
    def _bind_page_info(
        preview_widget: QPrintPreviewWidget,
        page_spin: ThemedSpinBox,
        total_label: QLabel,
    ) -> None:
        def update_page_info() -> None:
            try:
                page_count = max(1, int(preview_widget.pageCount()))
            except Exception:
                page_count = 1
            try:
                current_page = int(preview_widget.currentPage())
            except Exception:
                current_page = 1
            current_page = min(max(1, current_page), page_count)
            page_spin.blockSignals(True)
            page_spin.setMaximum(page_count)
            page_spin.setValue(current_page)
            page_spin.blockSignals(False)
            total_label.setText(f"/ {page_count}")

        try:
            preview_widget.previewChanged.connect(update_page_info)
        except Exception as exc:
            LOGGER.debug("Failed to hook previewChanged signal: %s", exc)
        update_page_info()

    @staticmethod
    def _page_action(
        preview: PrintPreviewDialog,
        *,
        icon_name: str,
        text: str,
        shortcut: str,
        callback: Callable[[], None],
    ) -> QAction:
        action = QAction(get_icon(icon_name, widget=preview), text, preview)
        page_name = "previous" if text == "Prev" else text.lower()
        action.setToolTip(f"Go to {page_name} page ({shortcut})")
        action.setShortcut(shortcut)
        action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        action.setPriority(QAction.Priority.LowPriority)
        action.triggered.connect(callback)
        return action

    @staticmethod
    def _set_custom_zoom(preview_widget: QPrintPreviewWidget) -> None:
        try:
            preview_widget.setZoomMode(QPrintPreviewWidget.ZoomMode.CustomZoom)
        except Exception as exc:
            LOGGER.debug("Failed to switch preview widget to custom zoom: %s", exc)


__all__ = ["PrintPreviewNavigationController"]
