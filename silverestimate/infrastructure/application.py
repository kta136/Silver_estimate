"""Application bootstrap utilities for SilverEstimate."""

from __future__ import annotations

import logging
import sys
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple, cast

import PyQt5.QtCore as QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget

from silverestimate.infrastructure.app_constants import APP_TITLE
from silverestimate.infrastructure.logger import (
    LogCleanupScheduler,
    get_log_config,
    qt_message_handler,
    setup_logging,
)
from silverestimate.infrastructure.paths import get_asset_path
from silverestimate.infrastructure.windows_integration import set_app_user_model_id

if TYPE_CHECKING:
    from PyQt5.QtWidgets import QMainWindow

    from silverestimate.persistence.database_manager import DatabaseManager

    MainWindowFactory = Callable[..., QMainWindow]
else:
    MainWindowFactory = Callable[..., Any]


class StartupError(RuntimeError):
    """Raised when the main window cannot complete initialization."""


@dataclass
class ApplicationContext:
    """Aggregate of resources created during application bootstrap."""

    app: Optional[QApplication] = None
    logger: Optional[logging.Logger] = None
    cleanup_scheduler: Optional[LogCleanupScheduler] = None
    db_manager: Optional["DatabaseManager"] = None
    main_window: Optional["QMainWindow"] = None
    dialog_parent: Optional[QWidget] = None
    startup_t0_perf: float = 0.0
    startup_t0_unix: float = 0.0

    def shutdown(self) -> None:
        """Release resources created during startup."""
        if self.cleanup_scheduler:
            try:
                self.cleanup_scheduler.stop()
            except Exception as exc:
                if self.logger:
                    self.logger.debug("Failed to stop cleanup scheduler: %s", exc)
        main_window_db = getattr(self.main_window, "db", None)
        if self.main_window and main_window_db:
            try:
                main_window_db.close()
            except Exception as exc:
                if self.logger:
                    self.logger.debug("Failed to close database on exit: %s", exc)
        elif self.db_manager:
            try:
                self.db_manager.close()
            except Exception as exc:
                if self.logger:
                    self.logger.debug("Failed to close database on exit: %s", exc)


class ApplicationBuilder:
    """Coordinate logging, Qt bootstrapping, authentication, and window creation."""

    def __init__(
        self,
        *,
        main_window_factory: MainWindowFactory,
        startup_controller_factory: Optional[Callable[..., Any]] = None,
        log_config_getter: Callable[[], dict[str, Any]] = get_log_config,
        logging_setup: Callable[..., logging.Logger] = setup_logging,
        asset_resolver: Callable[..., Path] = get_asset_path,
        icon_factory: Callable[[str], QIcon] = QIcon,
        qt_handler: Callable[..., None] = qt_message_handler,
        qt_attributes: Tuple[int | Qt.ApplicationAttribute, ...] = (
            Qt.AA_EnableHighDpiScaling,
            Qt.AA_UseHighDpiPixmaps,
        ),
        user_model_id: str = "com.silverestimate.app",
        app_name: str = "silver_app",
    ) -> None:
        self._main_window_factory = main_window_factory
        self._startup_controller_factory = startup_controller_factory
        self._log_config_getter = log_config_getter
        self._logging_setup = logging_setup
        self._asset_resolver = asset_resolver
        self._icon_factory = icon_factory
        self._qt_handler = qt_handler
        self._qt_attributes = qt_attributes
        self._user_model_id = user_model_id
        self._app_name = app_name

    def run(self) -> int:
        """Build and execute the application, returning an exit code."""
        context = ApplicationContext()
        try:
            return self._run(context)
        except StartupError as exc:
            logger = context.logger or logging.getLogger(__name__)
            logger.critical("Failed to initialize main window: %s", exc, exc_info=True)
            self._show_message_box(
                "Initialization Error",
                str(exc),
            )
            return 1
        except Exception as exc:
            self._handle_unexpected_exception(context, exc)
            return 1
        finally:
            context.shutdown()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run(self, context: ApplicationContext) -> int:
        """Internal orchestration for startup."""
        context.startup_t0_perf = time.perf_counter()
        context.startup_t0_unix = time.time()
        self._configure_logging(context)
        if context.logger:
            context.logger.debug(
                "[perf] startup.app_bootstrap_start t_unix=%.6f",
                context.startup_t0_unix,
            )
        self._configure_qt(context)
        if context.logger:
            context.logger.debug(
                "[perf] startup.qt_ready_ms=%.2f t_unix=%.6f",
                (time.perf_counter() - context.startup_t0_perf) * 1000.0,
                time.time(),
            )
        db_manager, early_exit = self._authenticate(context)
        if early_exit is not None:
            return early_exit
        context.main_window = self._main_window_factory(
            db_manager=db_manager,
            logger=context.logger,
        )
        return self._enter_event_loop(context)

    def _configure_logging(self, context: ApplicationContext) -> None:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        log_config = self._log_config_getter()
        logger = self._logging_setup(
            app_name=self._app_name,
            log_dir=log_config["log_dir"],
            debug_mode=log_config["debug_mode"],
            enable_info=log_config["enable_info"],
            enable_error=log_config["enable_error"],
            enable_debug=log_config["enable_debug"],
        )
        context.logger = logger
        logger.info("%s starting", APP_TITLE)
        logger.debug("Logging configuration: %s", log_config)

        if log_config.get("auto_cleanup"):
            try:
                cleanup_scheduler = LogCleanupScheduler(
                    log_dir=log_config["log_dir"],
                    cleanup_days=log_config["cleanup_days"],
                )
                cleanup_scheduler.start()
                logger.info(
                    "Log cleanup scheduler initialized with %s days retention",
                    log_config["cleanup_days"],
                )
                context.cleanup_scheduler = cleanup_scheduler
            except Exception as exc:
                logger.error(
                    "Failed to initialize log cleanup scheduler: %s",
                    exc,
                    exc_info=True,
                )

    def _configure_qt(self, context: ApplicationContext) -> None:
        QtCore.qInstallMessageHandler(self._qt_handler)
        if context.logger:
            context.logger.debug("Qt message handler installed")

        for attr in self._qt_attributes:
            try:
                QApplication.setAttribute(cast(Qt.ApplicationAttribute, attr))
            except Exception as exc:
                if context.logger:
                    context.logger.warning(
                        "Failed to set Qt attribute %s: %s", attr, exc
                    )

        if sys.platform == "win32":
            set_app_user_model_id(self._user_model_id)

        existing_app = QApplication.instance()
        app = (
            existing_app
            if isinstance(existing_app, QApplication)
            else QApplication(sys.argv)
        )
        context.app = app
        # Hidden parent widget for dialogs shown before the main window exists.
        # Some tests monkeypatch QApplication with a lightweight stub; skip
        # QWidget creation there to avoid requiring a real Qt app instance.
        if type(app).__module__.startswith("PyQt5."):
            dialog_parent = QWidget()
            dialog_parent.setAttribute(Qt.WA_DontShowOnScreen, True)
            context.dialog_parent = dialog_parent
        else:
            context.dialog_parent = None

        try:
            icon_path = self._asset_resolver("assets", "icons", "silverestimate.ico")
            if icon_path.exists():
                app.setWindowIcon(self._icon_factory(str(icon_path)))
            elif context.logger:
                context.logger.debug("Application icon not found at %s", icon_path)
        except Exception as exc:
            if context.logger:
                context.logger.debug("Failed to set application icon: %s", exc)

    def _authenticate(
        self, context: ApplicationContext
    ) -> Tuple[Optional["DatabaseManager"], Optional[int]]:
        status_enum: Any | None = None
        factory = self._startup_controller_factory
        if factory is None:
            from silverestimate.controllers.startup_controller import (
                StartupController,
                StartupStatus,
            )

            factory = StartupController
            status_enum = StartupStatus
        else:
            try:
                from silverestimate.controllers.startup_controller import (
                    StartupStatus,
                )

                status_enum = StartupStatus
            except Exception:
                status_enum = None

        try:
            controller = factory(
                logger=context.logger,
                parent=context.dialog_parent,
            )
        except TypeError:
            controller = factory(logger=context.logger)
        result = controller.authenticate_and_prepare()

        raw_status = getattr(result, "status", None)
        if hasattr(raw_status, "name"):
            status_name = getattr(raw_status, "name", "")
        elif raw_status is None:
            status_name = ""
        else:
            status_name = str(raw_status)
        cancelled_name = (
            getattr(status_enum.CANCELLED, "name", "CANCELLED")
            if status_enum is not None
            else "CANCELLED"
        )
        wiped_name = (
            getattr(status_enum.WIPED, "name", "WIPED")
            if status_enum is not None
            else "WIPED"
        )
        ok_name = (
            getattr(status_enum.OK, "name", "OK") if status_enum is not None else "OK"
        )

        if status_name == cancelled_name:
            if context.logger:
                context.logger.info("Authentication cancelled by user. Exiting.")
            return None, 0

        if status_name == wiped_name:
            if context.logger and not result.silent_wipe:
                context.logger.info("Data wipe completed. Exiting.")
            return None, 0

        if status_name != ok_name or not result.db:
            if context.logger:
                context.logger.critical(
                    "Startup failed during authentication or database initialization."
                )
            return None, 1

        context.db_manager = result.db
        if context.logger:
            context.logger.info("Authentication successful, initializing main window")
        return result.db, None

    def _enter_event_loop(self, context: ApplicationContext) -> int:
        if not context.app or not context.main_window:
            return 1
        if context.logger:
            context.logger.info("Showing main application window")
            context.logger.debug(
                "[perf] startup.main_window_show_ms=%.2f t_unix=%.6f",
                (time.perf_counter() - context.startup_t0_perf) * 1000.0,
                time.time(),
            )
        context.main_window.show()
        if context.logger:
            context.logger.debug("Entering Qt main event loop")
        exit_code = context.app.exec_()
        if context.logger:
            context.logger.info("Application exiting with code %s", exit_code)
        return exit_code

    def _show_message_box(self, title: str, message: str) -> None:
        try:
            QMessageBox.critical(None, title, message)
        except Exception as exc:
            logging.getLogger(__name__).debug(
                "Failed to display startup error dialog: %s", exc
            )

    def _handle_unexpected_exception(
        self,
        context: ApplicationContext,
        exc: Exception,
    ) -> None:
        logger = context.logger
        if logger:
            logger.critical(
                "Unhandled exception during application startup", exc_info=True
            )
        else:
            print(f"CRITICAL ERROR: {exc}")
            print(traceback.format_exc())

        message = (
            "The application encountered a fatal error and cannot continue.\n\n"
            f"Error: {exc}"
        )
        self._show_message_box("Fatal Error", message)
