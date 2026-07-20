"""Tests for the Filesystem Watcher."""

import time
from pathlib import Path

import pytest
from githelper.monitor.filesystem_watcher import FilesystemWatcher


def test_filesystem_watcher_triggers(tmp_path: Path) -> None:
    """Verify that file changes trigger the callback."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    
    triggers = 0
    
    def on_change(path: Path) -> None:
        nonlocal triggers
        triggers += 1
        assert path == repo_path

    watcher = FilesystemWatcher(on_repo_changed=on_change)
    
    watcher.start()
    watcher.watch_repository(repo_path)
    
    # Give watchdog a tiny bit of time to setup
    time.sleep(0.5)
    
    # Create a file
    (repo_path / "test.txt").write_text("hello")
    
    # Wait for debounce (1.0 seconds) + a bit of padding
    time.sleep(1.5)
    
    assert triggers >= 1
    
    watcher.stop()
