"""Database schema definition and migration logic.

Defines the on-disk representation of persisted records (Doc 05 Â§4.8).
Separate from domain models to allow independent evolution (e.g., schema versioning)
without forcing changes on the domain layer.

This module defines the SQLite tables and initialization logic.
"""

from __future__ import annotations

import sqlite3
from typing import Final


# Current schema version. Increment this when making schema changes that require migration.
SCHEMA_VERSION: Final[int] = 1


# ---------------------------------------------------------------------------
# Schema Definitions
# ---------------------------------------------------------------------------

_TABLE_REPOSITORIES = """
CREATE TABLE IF NOT EXISTS repositories (
    path TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL,
    push_pending INTEGER NOT NULL DEFAULT 0,
    last_commit_hash TEXT,
    last_commit_time TIMESTAMP,
    last_reminder_time TIMESTAMP,
    snooze_until TIMESTAMP
);
"""

_TABLE_STABLE_MARKERS = """
CREATE TABLE IF NOT EXISTS stable_markers (
    repo_path TEXT PRIMARY KEY,
    commit_hash TEXT NOT NULL,
    label TEXT NOT NULL,
    marked_at TIMESTAMP NOT NULL,
    FOREIGN KEY(repo_path) REFERENCES repositories(path) ON DELETE CASCADE
);
"""

_TABLE_SNAPSHOT_METADATA = """
CREATE TABLE IF NOT EXISTS snapshot_metadata (
    snapshot_id TEXT PRIMARY KEY,
    repo_path TEXT NOT NULL,
    captured_at TIMESTAMP NOT NULL,
    files_changed INTEGER NOT NULL,
    files_new INTEGER NOT NULL,
    clean_shutdown INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(repo_path) REFERENCES repositories(path) ON DELETE CASCADE
);
"""

# JSON string representation of the SnapshotFileEntry manifest.
# We don't need to normalize this into a files table because we only read/write
# the manifest as a complete document when a snapshot is viewed.
_TABLE_SNAPSHOT_FILES = """
CREATE TABLE IF NOT EXISTS snapshot_files (
    snapshot_id TEXT PRIMARY KEY,
    manifest_json TEXT NOT NULL,
    FOREIGN KEY(snapshot_id) REFERENCES snapshot_metadata(snapshot_id) ON DELETE CASCADE
);
"""

_TABLE_SETTINGS = """
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_TABLE_SCHEMA_VERSION = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
"""

# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def initialize_schema(conn: sqlite3.Connection) -> None:
    """Initialize the database schema if it does not exist, and run migrations.

    Args:
        conn: An open SQLite connection.
    """
    # SQLite foreign keys are disabled by default.
    conn.execute("PRAGMA foreign_keys = ON;")

    with conn:
        # Create tables
        conn.execute(_TABLE_REPOSITORIES)
        conn.execute(_TABLE_STABLE_MARKERS)
        conn.execute(_TABLE_SNAPSHOT_METADATA)
        conn.execute(_TABLE_SNAPSHOT_FILES)
        conn.execute(_TABLE_SETTINGS)
        conn.execute(_TABLE_SCHEMA_VERSION)

        # Check version and migrate
        cursor = conn.execute("SELECT version FROM schema_version LIMIT 1")
        row = cursor.fetchone()
        
        if row is None:
            # Fresh database
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        else:
            current_version = row[0]
            if current_version < SCHEMA_VERSION:
                _run_migrations(conn, current_version)


def _run_migrations(conn: sqlite3.Connection, current_version: int) -> None:
    """Run schema migrations from current_version to SCHEMA_VERSION."""
    # Add migration steps here as schema evolves in the future.
    # e.g. if current_version == 1: ...
    
    with conn:
        conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
