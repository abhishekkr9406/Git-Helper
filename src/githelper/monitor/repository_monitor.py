"""Repository Monitor coordinator.

Combines filesystem watcher and reconciliation poller signals into change-state
summaries emitted to the Application Layer.
"""

from pathlib import Path
from typing import Callable

from githelper.domain.models import ChangeStateSummary
from githelper.git_integration import git_client
from githelper.git_integration.errors import GitError
from githelper.monitor.filesystem_watcher import FilesystemWatcher
from githelper.monitor.reconciliation_poller import ReconciliationPoller
from githelper.diagnostics.logger import get_logger

logger = get_logger(__name__)


class RepositoryMonitor:
    """Coordinates filesystem watching and polling for a set of repositories."""
    
    def __init__(self, on_state_changed: Callable[[Path, ChangeStateSummary], None]):
        """
        Args:
            on_state_changed: Callback invoked when a repository's state changes.
                              Takes the repo path and its new ChangeStateSummary.
        """
        self.on_state_changed = on_state_changed
        
        self._watcher = FilesystemWatcher(on_repo_changed=self._handle_repo_event)
        self._poller = ReconciliationPoller(on_poll=self._handle_poll_event)
        
        self._monitored_repos: set[Path] = set()
        self._is_running = False

    def start(self) -> None:
        """Start the monitor services."""
        if not self._is_running:
            self._watcher.start()
            self._poller.start()
            self._is_running = True
            logger.info("RepositoryMonitor started.")

    def stop(self) -> None:
        """Stop the monitor services."""
        if self._is_running:
            self._watcher.stop()
            self._poller.stop()
            self._is_running = False
            logger.info("RepositoryMonitor stopped.")

    def update_repositories(self, repos: list[Path]) -> None:
        """Update the set of monitored repositories.
        
        Adds new repositories to the watcher and removes removed ones.
        """
        new_set = set(repos)
        
        # Remove old
        for repo in self._monitored_repos - new_set:
            self._watcher.unwatch_repository(repo)
            
        # Add new
        for repo in new_set - self._monitored_repos:
            self._watcher.watch_repository(repo)
            
        self._monitored_repos = new_set
        self._poller.update_repositories(repos)
        
        # Trigger an initial check for all new repos to get baseline state
        for repo in new_set:
            self._evaluate_repo(repo)

    def force_check(self, repo_path: Path) -> None:
        """Force an immediate evaluation of a repository."""
        if repo_path in self._monitored_repos:
            self._evaluate_repo(repo_path)

    def _handle_repo_event(self, repo_path: Path) -> None:
        """Called by the FilesystemWatcher when a file changes."""
        self._evaluate_repo(repo_path)

    def _handle_poll_event(self, repos: list[Path]) -> None:
        """Called by the ReconciliationPoller periodically."""
        for repo in repos:
            self._evaluate_repo(repo)

    def _evaluate_repo(self, repo_path: Path) -> None:
        """Evaluate the git status of a repo and emit the event."""
        try:
            summary = git_client.get_status(repo_path)
            self.on_state_changed(repo_path, summary)
        except GitError as e:
            logger.error(f"Failed to get status for {repo_path}: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error evaluating repo {repo_path}: {e}")
