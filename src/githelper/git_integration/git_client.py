"""Git client.

Wraps the system git binary via subprocess. Provides a narrow set of operations:
status, commit, push, log, diff-against-commit. Uses porcelain/machine-readable
output formats. No other module may invoke git directly (Architecture DR-007).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from githelper.domain.models import (
    ChangeStateSummary,
    CommitRecord,
    CompareResult,
    FileChangeType,
    FileDiffEntry,
)
from githelper.git_integration.errors import (
    GitAuthError,
    GitCommandFailedError,
    GitConflictError,
    GitNotFoundError,
    GitRepositoryError,
)

# Optional timeout for standard git commands to prevent hanging processes.
_DEFAULT_TIMEOUT = 10.0
# Push can take longer over network.
_PUSH_TIMEOUT = 60.0


def _get_git_path() -> str:
    """Find the git executable on PATH."""
    git_path = shutil.which("git")
    if not git_path:
        raise GitNotFoundError("git executable not found on PATH. Is Git installed?")
    return git_path


def _run_git(
    repo_path: Path,
    args: list[str],
    timeout: float = _DEFAULT_TIMEOUT,
    check_repo: bool = True
) -> subprocess.CompletedProcess[str]:
    """Execute a git command in the given repository path."""
    if check_repo and not is_git_repository(repo_path):
        raise GitRepositoryError(f"Not a git repository: {repo_path}")

    git_exe = _get_git_path()
    cmd = [git_exe] + args

    # Use a custom environment to force English output for predictable parsing,
    # and to disable interactive credential prompts if possible, though we
    # rely on the user's credential manager ultimately.
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env["GIT_TERMINAL_PROMPT"] = "0"

    try:
        result = subprocess.run(
            cmd,
            cwd=str(repo_path),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        # Wrap timeout in a standard GitCommandFailedError
        raise GitCommandFailedError(
            command=" ".join(cmd),
            exit_code=-1,
            stdout=str(e.stdout) if e.stdout else "",
            stderr=f"Command timed out after {timeout} seconds",
        ) from e
    except Exception as e:
        raise GitCommandFailedError(
            command=" ".join(cmd),
            exit_code=-2,
            stdout="",
            stderr=str(e),
        ) from e

    return result


def _handle_git_error(result: subprocess.CompletedProcess[str], cmd_str: str) -> None:
    """Translate non-zero exit codes into specific GitErrors."""
    if result.returncode == 0:
        return

    stderr_lower = result.stderr.lower()
    
    if "conflict" in stderr_lower or "unmerged" in stderr_lower:
        raise GitConflictError(f"Merge conflict detected: {result.stderr}")
        
    if "authentication failed" in stderr_lower or "could not read username" in stderr_lower or "permission denied" in stderr_lower:
        raise GitAuthError(f"Git authentication failed: {result.stderr}")

    raise GitCommandFailedError(
        command=cmd_str,
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


# ---------------------------------------------------------------------------
# Public Operations
# ---------------------------------------------------------------------------


def is_git_repository(path: Path) -> bool:
    """Check if the given path is a valid git repository root."""
    if not path.is_dir():
        return False
        
    try:
        result = _run_git(
            repo_path=path,
            args=["rev-parse", "--show-toplevel"],
            check_repo=False
        )
        if result.returncode != 0:
            return False
            
        top_level = Path(result.stdout.strip()).resolve()
        return top_level == path.resolve()
    except GitError:
        return False


def get_status(repo_path: Path) -> ChangeStateSummary:
    """Get the current uncommitted state of the repository."""
    # Use porcelain v1 for broad compatibility and easy parsing.
    result = _run_git(repo_path, ["status", "--porcelain", "-z"])
    _handle_git_error(result, "git status")

    if not result.stdout:
        return ChangeStateSummary(is_clean=True)

    # -z uses NUL characters to separate entries.
    entries = result.stdout.split('\0')
    
    staged = 0
    unstaged = 0
    untracked = 0
    extensions: set[str] = set()

    # With -z, a rename is "XY old_path\0new_path\0".
    # We iterate manually to handle the two-path entries.
    i = 0
    while i < len(entries):
        entry = entries[i]
        if not entry:
            i += 1
            continue
            
        status_code = entry[:2]
        filepath = entry[3:]
        
        # Track file extension
        ext = Path(filepath).suffix.lower()
        if ext:
            extensions.add(ext)

        # Count categories
        # status_code[0] is index, status_code[1] is working tree
        x, y = status_code[0], status_code[1]
        
        if x == '?' and y == '?':
            untracked += 1
        else:
            if x != ' ':
                staged += 1
            if y != ' ':
                unstaged += 1
                
        # If it's a rename (R or C in index), the next entry is the old path.
        if x in ('R', 'C'):
            i += 1
            
        i += 1

    # Lines added/removed requires diff. We do one for tracked files.
    lines_added = 0
    lines_removed = 0
    
    # We use numstat for tracked files (staged and unstaged).
    diff_result = _run_git(repo_path, ["diff", "HEAD", "--numstat"])
    if diff_result.returncode == 0 and diff_result.stdout:
        for line in diff_result.stdout.strip().split('\n'):
            parts = line.split('\t')
            if len(parts) >= 2:
                try:
                    added = int(parts[0]) if parts[0] != '-' else 0
                    removed = int(parts[1]) if parts[1] != '-' else 0
                    lines_added += added
                    lines_removed += removed
                except ValueError:
                    pass

    files_changed = staged + unstaged + untracked
    
    # Has source code? (Risk engine logic injected via models, but we check extensions here)
    # The actual source code logic is in the Risk Engine, but we populate the summary.
    from githelper.domain.risk_engine import SOURCE_CODE_EXTENSIONS
    has_source_code = not extensions.isdisjoint(SOURCE_CODE_EXTENSIONS)

    return ChangeStateSummary(
        files_changed=files_changed,
        files_staged=staged,
        files_unstaged=unstaged,
        files_untracked=untracked,
        lines_added=lines_added,
        lines_removed=lines_removed,
        file_extensions=frozenset(extensions),
        has_source_code=has_source_code,
        is_clean=files_changed == 0
    )


def get_log(repo_path: Path, max_count: int = 50) -> list[CommitRecord]:
    """Retrieve recent commit history."""
    # Format: %H (hash)|%h (short)|%an (author)|%aI (iso strict)|%s (subject)
    fmt = "%H|%h|%an|%aI|%s"
    result = _run_git(
        repo_path, 
        ["log", f"-n{max_count}", f"--format={fmt}", "--no-patch"]
    )
    _handle_git_error(result, "git log")
    
    commits = []
    if not result.stdout.strip():
        return commits
        
    for line in result.stdout.strip().split('\n'):
        parts = line.split('|', 4)
        if len(parts) == 5:
            dt = None
            try:
                dt = datetime.fromisoformat(parts[3]).astimezone(timezone.utc)
            except ValueError:
                pass
                
            commits.append(CommitRecord(
                hash=parts[0],
                short_hash=parts[1],
                author=parts[2],
                timestamp=dt,
                message=parts[4].strip()
            ))
            
    return commits


def commit(repo_path: Path, message: str, push_after: bool = False) -> str:
    """Commit all current changes (tracked and untracked).

    Returns the new commit hash.
    """
    # 1. Add all changes (including untracked)
    add_result = _run_git(repo_path, ["add", "-A"])
    _handle_git_error(add_result, "git add")

    # 2. Commit
    commit_result = _run_git(repo_path, ["commit", "-m", message])
    _handle_git_error(commit_result, "git commit")

    # 3. Get the new hash
    hash_result = _run_git(repo_path, ["rev-parse", "HEAD"])
    _handle_git_error(hash_result, "git rev-parse")
    
    new_hash = hash_result.stdout.strip()
    
    # 4. Push if requested
    if push_after:
        push(repo_path)
        
    return new_hash


def push(repo_path: Path) -> None:
    """Push the current branch to its configured upstream."""
    # Push can take a while over the network, so we use a longer timeout.
    result = _run_git(repo_path, ["push"], timeout=_PUSH_TIMEOUT)
    _handle_git_error(result, "git push")


def diff_stat(repo_path: Path, from_commit: str) -> CompareResult:
    """Generate a file-level difference summary between current state and a commit."""
    # We use --name-status to get the change type, and --numstat to get lines.
    # It's easier to run them separately and combine.
    
    # Get status mapping (M, A, D, etc.)
    status_result = _run_git(repo_path, ["diff", "--name-status", from_commit])
    _handle_git_error(status_result, "git diff --name-status")
    
    status_map = {}
    for line in status_result.stdout.strip().split('\n'):
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) >= 2:
            change_char = parts[0][0] # Could be 'M', 'A', 'D', 'R100', etc.
            status_map[parts[-1]] = change_char
            
    # Get line counts
    numstat_result = _run_git(repo_path, ["diff", "--numstat", from_commit])
    _handle_git_error(numstat_result, "git diff --numstat")
    
    entries = []
    total_added = 0
    total_removed = 0
    
    for line in numstat_result.stdout.strip().split('\n'):
        if not line:
            continue
        parts = line.split('\t')
        if len(parts) >= 3:
            try:
                added = int(parts[0]) if parts[0] != '-' else 0
                removed = int(parts[1]) if parts[1] != '-' else 0
            except ValueError:
                added = 0
                removed = 0
                
            filepath = parts[2]
            status_char = status_map.get(filepath, 'M')
            
            # Map git status char to our enum
            ctype = FileChangeType.MODIFIED
            if status_char == 'A': ctype = FileChangeType.ADDED
            elif status_char == 'D': ctype = FileChangeType.DELETED
            elif status_char == 'R': ctype = FileChangeType.RENAMED
            elif status_char == 'C': ctype = FileChangeType.COPIED
            
            entries.append(FileDiffEntry(
                relative_path=filepath,
                change_type=ctype,
                lines_added=added,
                lines_removed=removed
            ))
            
            total_added += added
            total_removed += removed
            
    return CompareResult(
        baseline_commit=from_commit,
        total_files_changed=len(entries),
        total_lines_changed=total_added + total_removed,
        files=tuple(entries)
    )
