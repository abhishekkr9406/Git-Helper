"""State store.

The only module permitted to perform direct I/O against GitHelper's local state store
(Architecture DR-009). Provides a narrow read/write interface using SQLite with WAL mode.
Thread-safe via internal write serialization.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from githelper.domain.models import (
    AppSettings,
    PopupPosition,
    ReminderSensitivity,
    RepoStatus,
    RepositoryRecord,
    StableMarker,
)
from githelper.persistence.schema import initialize_schema


class StateStore:
    """Thread-safe SQLite wrapper for GitHelper state persistence.

    Uses WAL mode for crash-safety and concurrent reads (REL-001/REL-006).
    Write operations are serialized internally via a lock, avoiding SQLITE_BUSY.
    """

    def __init__(self, db_path: Path | str):
        """Initialize the store and ensure schema is created."""
        self._db_path = str(db_path)
        self._write_lock = threading.Lock()
        
        # Initialize schema immediately.
        with self._get_connection() as conn:
            # Enable WAL mode for crash safety and concurrent reads.
            conn.execute("PRAGMA journal_mode = WAL;")
            initialize_schema(conn)

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Provide a connection with proper row factory and timezone handling."""
        # Detect types ensures datetime columns are parsed correctly.
        conn = sqlite3.connect(
            self._db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            isolation_level=None  # We manage transactions explicitly.
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # ---------------------------------------------------------------------------
    # Repositories CRUD
    # ---------------------------------------------------------------------------

    def load_repositories(self) -> list[RepositoryRecord]:
        """Load all watched repositories."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM repositories
            """)
            repos = []
            for row in cursor:
                repos.append(
                    RepositoryRecord(
                        path=Path(row["path"]),
                        display_name=row["display_name"],
                        status=RepoStatus(row["status"]),
                        push_pending=bool(row["push_pending"]),
                        last_commit_hash=row["last_commit_hash"] or "",
                        last_commit_time=self._ensure_utc(row["last_commit_time"]),
                        last_reminder_time=self._ensure_utc(row["last_reminder_time"]),
                        snooze_until=self._ensure_utc(row["snooze_until"]),
                        stable_marker=None  # Loaded separately if needed
                    )
                )
            
            # Attach stable markers
            for repo in repos:
                repo.stable_marker = self.get_stable_marker(repo.path)
                
            return repos

    def save_repository(self, repo: RepositoryRecord) -> None:
        """Insert or update a repository record."""
        with self._write_lock:
            with self._get_connection() as conn:
                with conn:
                    conn.execute("""
                        INSERT INTO repositories (
                            path, display_name, status, push_pending,
                            last_commit_hash, last_commit_time,
                            last_reminder_time, snooze_until
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(path) DO UPDATE SET
                            display_name=excluded.display_name,
                            status=excluded.status,
                            push_pending=excluded.push_pending,
                            last_commit_hash=excluded.last_commit_hash,
                            last_commit_time=excluded.last_commit_time,
                            last_reminder_time=excluded.last_reminder_time,
                            snooze_until=excluded.snooze_until
                    """, (
                        str(repo.path),
                        repo.display_name,
                        repo.status.value,
                        int(repo.push_pending),
                        repo.last_commit_hash or None,
                        repo.last_commit_time,
                        repo.last_reminder_time,
                        repo.snooze_until
                    ))

    def delete_repository(self, path: Path) -> None:
        """Remove a watched repository and its cascades (markers/snapshots)."""
        with self._write_lock:
            with self._get_connection() as conn:
                with conn:
                    conn.execute("DELETE FROM repositories WHERE path = ?", (str(path),))

    # ---------------------------------------------------------------------------
    # Stable Markers CRUD
    # ---------------------------------------------------------------------------

    def get_stable_marker(self, repo_path: Path) -> StableMarker | None:
        """Get the stable marker for a repository, if one exists."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT commit_hash, label, marked_at
                FROM stable_markers
                WHERE repo_path = ?
            """, (str(repo_path),))
            row = cursor.fetchone()
            if row:
                return StableMarker(
                    commit_hash=row["commit_hash"],
                    label=row["label"],
                    marked_at=self._ensure_utc(row["marked_at"]),
                    repo_path=repo_path
                )
            return None

    def save_stable_marker(self, marker: StableMarker) -> None:
        """Insert or update a stable marker."""
        if not marker.repo_path:
            raise ValueError("StableMarker must have a repo_path to be saved.")
            
        with self._write_lock:
            with self._get_connection() as conn:
                with conn:
                    conn.execute("""
                        INSERT INTO stable_markers (repo_path, commit_hash, label, marked_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(repo_path) DO UPDATE SET
                            commit_hash=excluded.commit_hash,
                            label=excluded.label,
                            marked_at=excluded.marked_at
                    """, (
                        str(marker.repo_path),
                        marker.commit_hash,
                        marker.label,
                        marker.marked_at or datetime.now(timezone.utc)
                    ))

    # ---------------------------------------------------------------------------
    # Settings CRUD
    # ---------------------------------------------------------------------------

    def load_settings(self) -> AppSettings:
        """Load all application settings, falling back to defaults."""
        settings = AppSettings()
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT key, value FROM app_settings")
            rows = {row["key"]: row["value"] for row in cursor}

        # General
        if "start_at_login" in rows:
            settings.start_at_login = rows["start_at_login"] == "1"
        if "show_tray_status_dot" in rows:
            settings.show_tray_status_dot = rows["show_tray_status_dot"] == "1"
        if "popup_position" in rows:
            try:
                settings.popup_position = PopupPosition(rows["popup_position"])
            except ValueError:
                pass
        if "show_metrics_in_popup" in rows:
            settings.show_metrics_in_popup = rows["show_metrics_in_popup"] == "1"

        # Reminders
        if "reminder_sensitivity" in rows:
            try:
                settings.reminder_sensitivity = ReminderSensitivity(rows["reminder_sensitivity"])
            except ValueError:
                pass
        if "quiet_hours_enabled" in rows:
            settings.quiet_hours_enabled = rows["quiet_hours_enabled"] == "1"
        if "quiet_hours_start" in rows:
            settings.quiet_hours_start = rows["quiet_hours_start"]
        if "quiet_hours_end" in rows:
            settings.quiet_hours_end = rows["quiet_hours_end"]
        if "pause_in_fullscreen" in rows:
            settings.pause_in_fullscreen = rows["pause_in_fullscreen"] == "1"

        # Recovery
        if "snapshot_retention_days" in rows:
            try:
                settings.snapshot_retention_days = int(rows["snapshot_retention_days"])
            except ValueError:
                pass
        if "snapshot_storage_path" in rows:
            settings.snapshot_storage_path = rows["snapshot_storage_path"]
            
        # Runtime State
        if "monitoring_paused" in rows:
            settings.monitoring_paused = rows["monitoring_paused"] == "1"

        return settings

    def save_settings(self, settings: AppSettings) -> None:
        """Save application settings."""
        # Convert to key/value strings
        kvs = [
            ("start_at_login", "1" if settings.start_at_login else "0"),
            ("show_tray_status_dot", "1" if settings.show_tray_status_dot else "0"),
            ("popup_position", settings.popup_position.value),
            ("show_metrics_in_popup", "1" if settings.show_metrics_in_popup else "0"),
            ("reminder_sensitivity", settings.reminder_sensitivity.value),
            ("quiet_hours_enabled", "1" if settings.quiet_hours_enabled else "0"),
            ("quiet_hours_start", settings.quiet_hours_start),
            ("quiet_hours_end", settings.quiet_hours_end),
            ("pause_in_fullscreen", "1" if settings.pause_in_fullscreen else "0"),
            ("snapshot_retention_days", str(settings.snapshot_retention_days)),
            ("snapshot_storage_path", settings.snapshot_storage_path),
            ("monitoring_paused", "1" if settings.monitoring_paused else "0"),
        ]
        
        with self._write_lock:
            with self._get_connection() as conn:
                with conn:
                    for key, value in kvs:
                        conn.execute("""
                            INSERT INTO app_settings (key, value)
                            VALUES (?, ?)
                            ON CONFLICT(key) DO UPDATE SET value=excluded.value
                        """, (key, value))

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    def _ensure_utc(self, dt: datetime | None) -> datetime | None:
        """Ensure a parsed datetime is marked as UTC.
        
        SQLite datetime adapter sometimes returns naive datetimes even when
        we pass timezone-aware ones in.
        """
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

# sqlite3 adapters for Python datetime
sqlite3.register_adapter(datetime, lambda d: d.astimezone(timezone.utc).isoformat(sep=" "))
sqlite3.register_converter(
    "TIMESTAMP", 
    lambda s: datetime.fromisoformat(s.decode("utf-8")).replace(tzinfo=timezone.utc)
)
