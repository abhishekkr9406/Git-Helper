"""Tests for the Rolling Snapshot Service."""

import time
from pathlib import Path

import pytest
from githelper.domain.models import ChangeStateSummary
from githelper.snapshot.rolling_snapshot_service import RollingSnapshotService


def test_rolling_snapshot_triggers(tmp_path: Path) -> None:
    """Verify that the service creates snapshots for dirty repositories."""
    repo_path = tmp_path / "repo"
    
    # Mock dependencies
    def get_repo_state(path: Path) -> ChangeStateSummary:
        return ChangeStateSummary(is_clean=False, files_changed=3)
        
    created_snaps = []
    def create_snapshot(path: Path, snap_id: str) -> Path:
        zip_path = tmp_path / f"{snap_id}.zip"
        zip_path.touch()
        created_snaps.append((path, snap_id, zip_path))
        return zip_path
        
    saved_meta = []
    def on_snapshot_created(meta) -> None:
        saved_meta.append(meta)

    service = RollingSnapshotService(
        get_repo_state=get_repo_state,
        create_snapshot_func=create_snapshot,
        on_snapshot_created=on_snapshot_created
    )
    
    # Patch interval
    service._interval = 0.1
    
    service.update_repositories([repo_path])
    service.start()
    
    time.sleep(0.3)
    
    service.stop()
    
    assert len(created_snaps) >= 1
    assert created_snaps[0][0] == repo_path
    
    assert len(saved_meta) >= 1
    assert saved_meta[0].repo_path == repo_path
    assert saved_meta[0].files_changed == 3
