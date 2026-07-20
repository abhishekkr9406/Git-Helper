"""Reconciliation poller.

Low-frequency correctness backstop that periodically verifies repository state
via git, catching any events the filesystem watcher may have missed.
"""

import threading
import time
from pathlib import Path
from typing import Callable

from githelper.common.constants import RECONCILIATION_INTERVAL_SECONDS
from githelper.diagnostics.logger import get_logger

logger = get_logger(__name__)


class ReconciliationPoller:
    """Periodically triggers re-evaluation of repository state."""
    
    def __init__(self, on_poll: Callable[[list[Path]], None]):
        self.on_poll = on_poll
        self._interval = RECONCILIATION_INTERVAL_SECONDS
        self._repositories: set[Path] = set()
        self._lock = threading.Lock()
        
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the background polling thread."""
        if self._thread is not None and self._thread.is_alive():
            return
            
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="ReconciliationPoller", daemon=True)
        self._thread.start()
        logger.info("ReconciliationPoller started.")

    def stop(self) -> None:
        """Stop the background polling thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("ReconciliationPoller stopped.")

    def update_repositories(self, repos: list[Path]) -> None:
        """Update the list of repositories to poll."""
        with self._lock:
            self._repositories = set(repos)

    def _run_loop(self) -> None:
        """Main loop for the poller thread."""
        while not self._stop_event.is_set():
            # Wait for interval, but check stop event frequently
            if self._stop_event.wait(timeout=self._interval):
                break
                
            with self._lock:
                repos_to_poll = list(self._repositories)
                
            if repos_to_poll:
                logger.debug(f"Running reconciliation poll for {len(repos_to_poll)} repos")
                try:
                    self.on_poll(repos_to_poll)
                except Exception as e:
                    logger.error(f"Error during reconciliation poll: {e}")
