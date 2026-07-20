"""Session listener.

Platform-agnostic coordinator for shutdown, restart, and sleep signal detection.
Delegates to platform-specific adapters. Emits generic signals to the Orchestrator.
"""

import os
from typing import Callable
from PySide6.QtCore import QCoreApplication


class SessionListener:
    """Listens for OS-level session events (shutdown, sleep, resume)."""

    def __init__(self, app: QCoreApplication):
        self._app = app
        self._filter = None
        self._on_shutdown_callbacks: list[Callable[[], None]] = []
        self._on_sleep_callbacks: list[Callable[[], None]] = []
        self._on_resume_callbacks: list[Callable[[], None]] = []
        
        # In PySide6, aboutToQuit is a reliable backstop if the OS signals fail.
        self._app.aboutToQuit.connect(self._handle_shutdown)

    def start(self) -> None:
        """Start listening to OS signals."""
        if os.name == "nt":
            from githelper.system_state.platform.windows_adapter import install_windows_filter
            self._filter = install_windows_filter(
                self._app,
                on_shutdown=self._handle_shutdown,
                on_sleep=self._handle_sleep,
                on_resume=self._handle_resume
            )
        elif os.name == "posix":
            # macOS/Linux not fully implemented yet, rely on aboutToQuit
            pass

    def stop(self) -> None:
        """Stop listening to OS signals."""
        if self._filter and self._app:
            self._app.removeNativeEventFilter(self._filter)
            self._filter = None

    def register_shutdown_handler(self, callback: Callable[[], None]) -> None:
        """Register a callback for when the OS is shutting down or app is quitting."""
        self._on_shutdown_callbacks.append(callback)

    def register_sleep_handler(self, callback: Callable[[], None]) -> None:
        """Register a callback for when the OS goes to sleep."""
        self._on_sleep_callbacks.append(callback)

    def register_resume_handler(self, callback: Callable[[], None]) -> None:
        """Register a callback for when the OS resumes from sleep."""
        self._on_resume_callbacks.append(callback)

    def _handle_shutdown(self) -> None:
        for cb in self._on_shutdown_callbacks:
            try:
                cb()
            except Exception:
                pass

    def _handle_sleep(self) -> None:
        for cb in self._on_sleep_callbacks:
            try:
                cb()
            except Exception:
                pass

    def _handle_resume(self) -> None:
        for cb in self._on_resume_callbacks:
            try:
                cb()
            except Exception:
                pass
