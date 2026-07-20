"""Structured error types for the Git Integration Layer.

Callers only see these errors, never raw subprocess exceptions.
"""

from githelper.common.exceptions import GitHelperError


class GitError(GitHelperError):
    """Base class for all Git-related errors."""
    pass


class GitNotFoundError(GitError):
    """Raised when the git executable cannot be found on PATH."""
    pass


class GitRepositoryError(GitError):
    """Raised when an operation is attempted on a path that is not a git repository."""
    pass


class GitAuthError(GitError):
    """Raised when a git operation fails due to authentication/credentials."""
    pass


class GitConflictError(GitError):
    """Raised when an operation fails due to merge conflicts or unmerged paths."""
    pass


class GitCommandFailedError(GitError):
    """Raised when a git subprocess returns a non-zero exit code unexpectedly.
    
    Contains the stdout, stderr, and exit code for logging/diagnostics,
    but these should generally not be shown to the user directly unless necessary.
    """
    
    def __init__(self, command: str, exit_code: int, stdout: str, stderr: str):
        super().__init__(f"Git command failed (exit code {exit_code}): {command}")
        self.command = command
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
