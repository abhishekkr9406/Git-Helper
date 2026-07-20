"""Tests for the Repository Monitor."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from githelper.domain.models import ChangeStateSummary
from githelper.monitor.repository_monitor import RepositoryMonitor


def test_repository_monitor_coordinates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that the monitor coordinates watcher and poller properly."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    
    mock_get_status = MagicMock()
    mock_get_status.return_value = ChangeStateSummary(is_clean=True)
    
    # Patch git_client to avoid actual git calls
    monkeypatch.setattr("githelper.monitor.repository_monitor.git_client.get_status", mock_get_status)
    
    callbacks = []
    def on_state_changed(path: Path, state: ChangeStateSummary) -> None:
        callbacks.append((path, state))
        
    monitor = RepositoryMonitor(on_state_changed=on_state_changed)
    
    # We patch watcher/poller so we don't start real threads
    monitor._watcher = MagicMock()
    monitor._poller = MagicMock()
    
    monitor.start()
    
    assert monitor._watcher.start.called
    assert monitor._poller.start.called
    
    # Update repos
    monitor.update_repositories([repo_path])
    
    assert monitor._watcher.watch_repository.called
    assert monitor._poller.update_repositories.called
    
    # Initial check should have been triggered
    assert mock_get_status.called
    assert len(callbacks) == 1
    assert callbacks[0][0] == repo_path
    assert callbacks[0][1].is_clean is True
    
    # Test force check
    monitor.force_check(repo_path)
    assert len(callbacks) == 2
    
    monitor.stop()
    assert monitor._watcher.stop.called
    assert monitor._poller.stop.called
