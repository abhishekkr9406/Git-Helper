"""Tests for the State Store."""

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from githelper.domain.models import (
    AppSettings,
    PopupPosition,
    ReminderSensitivity,
    RepoStatus,
    RepositoryRecord,
    StableMarker,
)
from githelper.persistence.state_store import StateStore


@pytest.fixture
def store(tmp_path: Path) -> StateStore:
    """Fixture providing an empty StateStore backed by a temporary file."""
    db_file = tmp_path / "test_state.db"
    return StateStore(db_file)


class TestStateStore:
    """Tests for StateStore CRUD operations."""

    def test_initialization_creates_schema(self, store: StateStore, tmp_path: Path) -> None:
        """Verify that initializing the store creates the necessary tables."""
        db_file = tmp_path / "test_state.db"
        assert db_file.exists()
        
        with sqlite3.connect(db_file) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor}
            
        assert "repositories" in tables
        assert "app_settings" in tables
        assert "stable_markers" in tables
        assert "snapshot_metadata" in tables

    def test_repository_crud(self, store: StateStore) -> None:
        """Verify save, load, and delete for repositories."""
        now = datetime.now(timezone.utc).replace(microsecond=0)
        repo = RepositoryRecord(
            path=Path("C:/test/repo"),
            display_name="test_repo",
            status=RepoStatus.MONITORING,
            push_pending=True,
            last_commit_hash="abc1234",
            last_commit_time=now,
            last_reminder_time=now,
            snooze_until=now + timedelta(hours=1)
        )
        
        # Save
        store.save_repository(repo)
        
        # Load
        repos = store.load_repositories()
        assert len(repos) == 1
        loaded = repos[0]
        assert loaded.path == repo.path
        assert loaded.display_name == repo.display_name
        assert loaded.status == repo.status
        assert loaded.push_pending == repo.push_pending
        assert loaded.last_commit_hash == repo.last_commit_hash
        assert loaded.last_commit_time == repo.last_commit_time
        assert loaded.last_reminder_time == repo.last_reminder_time
        assert loaded.snooze_until == repo.snooze_until
        
        # Delete
        store.delete_repository(repo.path)
        assert len(store.load_repositories()) == 0

    def test_repository_update(self, store: StateStore) -> None:
        """Verify updating an existing repository record."""
        repo = RepositoryRecord(
            path=Path("C:/test/repo"),
            display_name="test_repo",
            status=RepoStatus.IDLE
        )
        store.save_repository(repo)
        
        repo.status = RepoStatus.RISK_DETECTED
        repo.push_pending = True
        store.save_repository(repo)
        
        repos = store.load_repositories()
        assert len(repos) == 1
        assert repos[0].status == RepoStatus.RISK_DETECTED
        assert repos[0].push_pending is True

    def test_stable_marker_crud(self, store: StateStore) -> None:
        """Verify save and load for stable markers."""
        repo_path = Path("C:/test/repo")
        repo = RepositoryRecord(path=repo_path, display_name="test_repo")
        store.save_repository(repo)
        
        now = datetime.now(timezone.utc).replace(microsecond=0)
        marker = StableMarker(
            commit_hash="def5678",
            label="v1.0",
            marked_at=now,
            repo_path=repo_path
        )
        
        # Save
        store.save_stable_marker(marker)
        
        # Load directly
        loaded = store.get_stable_marker(repo_path)
        assert loaded is not None
        assert loaded.commit_hash == "def5678"
        assert loaded.label == "v1.0"
        assert loaded.marked_at == now
        
        # Load via repository
        repos = store.load_repositories()
        assert repos[0].stable_marker is not None
        assert repos[0].stable_marker.commit_hash == "def5678"

    def test_settings_crud(self, store: StateStore) -> None:
        """Verify save and load for app settings."""
        # Load defaults
        default_settings = store.load_settings()
        assert default_settings.start_at_login is True
        assert default_settings.reminder_sensitivity == ReminderSensitivity.BALANCED
        
        # Change and save
        settings = AppSettings(
            start_at_login=False,
            popup_position=PopupPosition.TOP_RIGHT,
            reminder_sensitivity=ReminderSensitivity.RELAXED,
            quiet_hours_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="06:00",
            snapshot_retention_days=14,
            monitoring_paused=True
        )
        store.save_settings(settings)
        
        # Load and verify
        loaded = store.load_settings()
        assert loaded.start_at_login is False
        assert loaded.popup_position == PopupPosition.TOP_RIGHT
        assert loaded.reminder_sensitivity == ReminderSensitivity.RELAXED
        assert loaded.quiet_hours_enabled is True
        assert loaded.quiet_hours_start == "22:00"
        assert loaded.quiet_hours_end == "06:00"
        assert loaded.snapshot_retention_days == 14
        assert loaded.monitoring_paused is True
