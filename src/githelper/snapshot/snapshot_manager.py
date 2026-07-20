"""Snapshot Manager coordinator.

Handles startup recovery detection, restore, and discard. Surfaces snapshot
availability to the Application Layer.
"""

from pathlib import Path
from typing import Callable

from githelper.diagnostics.logger import get_logger
from githelper.domain.models import ChangeStateSummary, SnapshotMetadata
from githelper.persistence.state_store import StateStore
from githelper.snapshot.rolling_snapshot_service import RollingSnapshotService
from githelper.snapshot.snapshot_storage import SnapshotStorage

logger = get_logger(__name__)


class SnapshotManager:
    """Coordinates snapshot creation, retrieval, restoration, and cleanup."""

    def __init__(
        self,
        state_store: StateStore,
        get_repo_state: Callable[[Path], ChangeStateSummary | None],
        on_recovery_needed: Callable[[SnapshotMetadata], None]
    ):
        """
        Args:
            state_store: The persistence store.
            get_repo_state: Callback to get current repo state for rolling snapshots.
            on_recovery_needed: Callback invoked during startup if a valid snapshot is found
                                after an unclean shutdown.
        """
        self._store = state_store
        self.on_recovery_needed = on_recovery_needed
        
        self._storage = SnapshotStorage()
        self._rolling_service = RollingSnapshotService(
            get_repo_state=get_repo_state,
            create_snapshot_func=self._storage.create_snapshot,
            on_snapshot_created=self._on_snapshot_created
        )
        self._is_running = False

    def start(self) -> None:
        """Start the snapshot manager."""
        if self._is_running:
            return
            
        self._rolling_service.start()
        self._is_running = True
        logger.info("SnapshotManager started.")

    def stop(self) -> None:
        """Stop the snapshot manager."""
        if self._is_running:
            self._rolling_service.stop()
            self._is_running = False
            logger.info("SnapshotManager stopped.")

    def update_repositories(self, repos: list[Path]) -> None:
        """Update the list of repositories being managed."""
        self._rolling_service.update_repositories(repos)

    def perform_startup_check(self) -> None:
        """Check if we need to recover snapshots due to an unclean shutdown.
        
        Per Architecture (DR-001): If clean_shutdown was False, and snapshots exist,
        we prompt the user for recovery.
        """
        was_clean = self._store.get_clean_shutdown_flag()
        
        # Reset the flag immediately since we are now running
        self._store.set_clean_shutdown_flag(False)
        
        if was_clean:
            # Clean shutdown means we can safely discard old snapshots
            self._cleanup_all_snapshots()
            return
            
        # Unclean shutdown: check for snapshots
        snapshots = self._store.load_all_snapshot_metadata()
        if not snapshots:
            logger.info("Unclean shutdown detected, but no snapshots available.")
            return
            
        logger.warning(f"Unclean shutdown detected. Found {len(snapshots)} snapshots.")
        
        # For each snapshot, ask the UI to prompt the user
        for meta in snapshots:
            zip_path = self._storage.storage_dir / f"{meta.snapshot_id}.zip"
            if zip_path.exists():
                self.on_recovery_needed(meta)
            else:
                logger.warning(f"Snapshot file missing for {meta.repo_path}: {zip_path}")
                self._store.delete_snapshot_metadata(meta.snapshot_id)

    def restore_snapshot(self, snapshot_id: str) -> None:
        """Restore a snapshot and delete it afterwards."""
        meta = self._store.get_snapshot_metadata(snapshot_id)
        if not meta:
            logger.error(f"Cannot restore: Snapshot metadata not found for {snapshot_id}")
            return
            
        try:
            zip_path = self._storage.storage_dir / f"{snapshot_id}.zip"
            self._storage.restore_snapshot(zip_path, meta.repo_path)
            self.discard_snapshot(snapshot_id)
            logger.info(f"Successfully restored snapshot {snapshot_id}")
        except Exception as e:
            logger.error(f"Failed to restore snapshot {snapshot_id}: {e}")

    def discard_snapshot(self, snapshot_id: str) -> None:
        """Discard a specific snapshot."""
        meta = self._store.get_snapshot_metadata(snapshot_id)
        if meta:
            zip_path = self._storage.storage_dir / f"{snapshot_id}.zip"
            self._storage.delete_snapshot(zip_path)
            self._store.delete_snapshot_metadata(snapshot_id)
            
    def mark_clean_shutdown(self) -> None:
        """Mark the shutdown as clean and discard all snapshots."""
        self._cleanup_all_snapshots()
        self._store.set_clean_shutdown_flag(True)

    def _cleanup_all_snapshots(self) -> None:
        """Discard all snapshots and their metadata."""
        snapshots = self._store.load_all_snapshot_metadata()
        for meta in snapshots:
            zip_path = self._storage.storage_dir / f"{meta.snapshot_id}.zip"
            self._storage.delete_snapshot(zip_path)
            self._store.delete_snapshot_metadata(meta.snapshot_id)
            
        # Cleanup any orphaned zip files just in case
        self._storage.cleanup_old_snapshots(set())

    def _on_snapshot_created(self, metadata: SnapshotMetadata) -> None:
        """Callback from RollingSnapshotService when a new snapshot is made."""
        # Check if we already have a snapshot for this repo, if so, delete the old one.
        existing_snaps = self._store.load_all_snapshot_metadata()
        for snap in existing_snaps:
            if snap.repo_path == metadata.repo_path:
                self.discard_snapshot(snap.snapshot_id)
                
        self._store.save_snapshot_metadata(metadata)
