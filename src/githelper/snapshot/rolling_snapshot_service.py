"""Rolling snapshot service.

Background-timer-driven service that periodically creates recovery snapshots
when uncommitted work exists. The load-bearing mechanism for the REC-002 recovery guarantee.
"""

import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from githelper.common.constants import SNAPSHOT_INTERVAL_SECONDS
from githelper.diagnostics.logger import get_logger
from githelper.domain.models import ChangeStateSummary, SnapshotMetadata

logger = get_logger(__name__)


class RollingSnapshotService:
    """Periodically creates snapshots for repositories with uncommitted work."""

    def __init__(
        self,
        get_repo_state: Callable[[Path], ChangeStateSummary | None],
        create_snapshot_func: Callable[[Path, str], Path],
        on_snapshot_created: Callable[[SnapshotMetadata], None]
    ):
        """
        Args:
            get_repo_state: Callback to get the current state of a repo.
            create_snapshot_func: Callback to actually create the ZIP file.
            on_snapshot_created: Callback to persist metadata when a snapshot is made.
        """
        self.get_repo_state = get_repo_state
        self.create_snapshot_func = create_snapshot_func
        self.on_snapshot_created = on_snapshot_created
        
        self._interval = SNAPSHOT_INTERVAL_SECONDS
        self._monitored_repos: set[Path] = set()
        self._lock = threading.Lock()
        
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the background rolling snapshot thread."""
        if self._thread is not None and self._thread.is_alive():
            return
            
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="RollingSnapshot", daemon=True)
        self._thread.start()
        logger.info("RollingSnapshotService started.")

    def stop(self) -> None:
        """Stop the background thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("RollingSnapshotService stopped.")

    def update_repositories(self, repos: list[Path]) -> None:
        """Update the list of repositories to snapshot."""
        with self._lock:
            self._monitored_repos = set(repos)

    def _run_loop(self) -> None:
        """Main loop for the snapshot thread."""
        while not self._stop_event.is_set():
            # Wait for interval
            if self._stop_event.wait(timeout=self._interval):
                break
                
            with self._lock:
                repos_to_check = list(self._monitored_repos)
                
            for repo in repos_to_check:
                self._evaluate_and_snapshot(repo)

    def _evaluate_and_snapshot(self, repo_path: Path) -> None:
        """Create a snapshot if the repo has uncommitted work."""
        try:
            state = self.get_repo_state(repo_path)
            if state is None or state.is_clean:
                return
                
            snapshot_id = str(uuid.uuid4())
            zip_path = self.create_snapshot_func(repo_path, snapshot_id)
            
            metadata = SnapshotMetadata(
                snapshot_id=snapshot_id,
                repo_path=repo_path,
                captured_at=datetime.now(timezone.utc),
                files_changed=state.files_changed
            )
            
            # Notify manager to save metadata
            self.on_snapshot_created(metadata)
            logger.info(f"Created rolling snapshot for {repo_path}")
            
        except Exception as e:
            logger.error(f"Failed to create rolling snapshot for {repo_path}: {e}")
