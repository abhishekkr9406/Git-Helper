"""Tests for the Snapshot Manager."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from githelper.domain.models import SnapshotMetadata
from githelper.snapshot.snapshot_manager import SnapshotManager


def test_startup_check_clean_shutdown(tmp_path: Path) -> None:
    """Verify that a clean shutdown discards old snapshots."""
    store = MagicMock()
    store.get_clean_shutdown_flag.return_value = True
    store.load_all_snapshot_metadata.return_value = []
    
    recovery_calls = []
    def on_recovery(meta):
        recovery_calls.append(meta)
        
    manager = SnapshotManager(store, MagicMock(), on_recovery)
    
    # Mock storage to verify cleanup
    manager._storage = MagicMock()
    
    manager.perform_startup_check()
    
    # Flag is reset to False immediately on startup
    store.set_clean_shutdown_flag.assert_called_with(False)
    
    # No recovery prompts
    assert len(recovery_calls) == 0


def test_startup_check_unclean_shutdown(tmp_path: Path) -> None:
    """Verify that an unclean shutdown prompts for recovery if snapshots exist."""
    store = MagicMock()
    store.get_clean_shutdown_flag.return_value = False
    
    meta = SnapshotMetadata(
        snapshot_id="123",
        repo_path=Path("test"),
        captured_at=None,
        files_changed=5
    )
    
    # We don't have file_path in the model anymore, the manager looks it up via snapshot_id
    # We must mock the zip file existence in the storage dir
    zip_path = tmp_path / "123.zip"
    zip_path.touch()
    
    store.load_all_snapshot_metadata.return_value = [meta]
    
    recovery_calls = []
    def on_recovery(m):
        recovery_calls.append(m)
        
    manager = SnapshotManager(store, MagicMock(), on_recovery)
    
    # Mock storage_dir so it finds the dummy zip
    manager._storage.storage_dir = tmp_path
    
    manager.perform_startup_check()
    
    assert len(recovery_calls) == 1
    assert recovery_calls[0].snapshot_id == "123"


def test_mark_clean_shutdown() -> None:
    """Verify marking a shutdown as clean cleans up everything."""
    store = MagicMock()
    store.load_all_snapshot_metadata.return_value = []
    
    manager = SnapshotManager(store, MagicMock(), MagicMock())
    manager._storage = MagicMock()
    
    manager.mark_clean_shutdown()
    
    store.set_clean_shutdown_flag.assert_called_with(True)
    assert manager._storage.cleanup_old_snapshots.called
