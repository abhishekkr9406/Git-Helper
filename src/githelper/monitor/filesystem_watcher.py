"""Filesystem watcher.

Wraps the watchdog library (the only module permitted to import it).
Detects file changes in watched repositories via OS-native filesystem events.
"""

import threading
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from githelper.diagnostics.logger import get_logger

logger = get_logger(__name__)

# Extensions that trigger an immediate re-evaluation of git status.
# Other file changes are ignored to reduce git CPU load.
# This list can be synced with risk_engine or kept broad.
_WATCHED_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".md",
    ".txt", ".csv", ".xml", ".yml", ".yaml", ".ini", ".conf", ".cfg",
    ".sh", ".bat", ".ps1", ".c", ".cpp", ".h", ".hpp", ".cs", ".java",
    ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".sql"
}


class _RepoEventHandler(FileSystemEventHandler):
    """Handles watchdog events for a specific repository."""
    
    def __init__(self, repo_path: Path, on_change: Callable[[Path], None]):
        super().__init__()
        self.repo_path = repo_path
        self.on_change = on_change
        
        # Debounce logic: multiple file events usually happen in a burst.
        # We only want to trigger `on_change` (which runs `git status`) once per burst.
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._debounce_seconds = 1.0

    def _trigger(self) -> None:
        """Called by the timer after the debounce period."""
        with self._lock:
            self._timer = None
        self.on_change(self.repo_path)

    def _schedule_trigger(self) -> None:
        """Schedule or reschedule the trigger."""
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self._debounce_seconds, self._trigger)
            self._timer.start()

    def _is_relevant(self, event: FileSystemEvent) -> bool:
        """Check if the event is relevant to us."""
        if event.is_directory:
            return False
            
        path_str = event.src_path.replace('\\', '/')
        
        # Ignore changes inside .git directory
        if "/.git/" in path_str or path_str.endswith("/.git"):
            return False
            
        # Ignore changes in virtual environments, node_modules, build output
        if any(x in path_str for x in ["/node_modules/", "/.venv/", "/venv/", "/__pycache__/", "/build/", "/dist/"]):
            return False
            
        return True

    def on_any_event(self, event: FileSystemEvent) -> None:
        """Catch-all for any file system event."""
        if self._is_relevant(event):
            self._schedule_trigger()


class FilesystemWatcher:
    """Watches repositories for file changes."""
    
    def __init__(self, on_repo_changed: Callable[[Path], None]):
        """
        Args:
            on_repo_changed: Callback invoked when a watched repo has file changes.
        """
        self.on_repo_changed = on_repo_changed
        self._observer = Observer()
        self._watches: dict[Path, object] = {}
        self._is_running = False

    def start(self) -> None:
        """Start the observer thread."""
        if not self._is_running:
            self._observer.start()
            self._is_running = True
            logger.info("FilesystemWatcher started.")

    def stop(self) -> None:
        """Stop the observer thread and join it."""
        if self._is_running:
            self._observer.stop()
            self._observer.join()
            self._is_running = False
            logger.info("FilesystemWatcher stopped.")

    def watch_repository(self, path: Path) -> None:
        """Start watching a repository."""
        if path in self._watches:
            return
            
        if not path.is_dir():
            logger.warning(f"Cannot watch {path}: Not a directory.")
            return
            
        handler = _RepoEventHandler(path, self.on_repo_changed)
        try:
            # Recursive=True watches the whole tree.
            # watchdog handles the underlying OS limitations (ReadDirectoryChangesW).
            watch = self._observer.schedule(handler, str(path), recursive=True)
            self._watches[path] = watch
            logger.info(f"Started watching repository: {path}")
        except Exception as e:
            logger.error(f"Failed to watch {path}: {e}")

    def unwatch_repository(self, path: Path) -> None:
        """Stop watching a repository."""
        watch = self._watches.pop(path, None)
        if watch:
            try:
                self._observer.unschedule(watch)
                logger.info(f"Stopped watching repository: {path}")
            except Exception as e:
                logger.error(f"Failed to unwatch {path}: {e}")
