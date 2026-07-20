"""Integration tests for the Git client.

Tests run against real temporary Git repositories.
"""

import subprocess
from pathlib import Path

import pytest
from githelper.domain.models import FileChangeType
from githelper.git_integration import git_client
from githelper.git_integration.errors import (
    GitCommandFailedError,
    GitConflictError,
    GitRepositoryError,
)


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    """Fixture to create and return a temporary git repository."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    # Initialize repo
    subprocess.run(["git", "init"], cwd=str(repo_dir), check=True, capture_output=True)
    
    # Configure dummy user for commits
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo_dir), check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), check=True)
    
    return repo_dir


class TestGitClient:
    """Tests for the Git client."""

    def test_is_git_repository(self, temp_repo: Path, tmp_path: Path) -> None:
        """Verify repository detection."""
        assert git_client.is_git_repository(temp_repo) is True
        
        # tmp_path itself is not a git repo
        assert git_client.is_git_repository(tmp_path) is False
        
        # Non-existent path
        assert git_client.is_git_repository(tmp_path / "does_not_exist") is False

    def test_get_status_clean(self, temp_repo: Path) -> None:
        """Verify status on a clean repository."""
        status = git_client.get_status(temp_repo)
        assert status.is_clean is True
        assert status.files_changed == 0

    def test_get_status_untracked(self, temp_repo: Path) -> None:
        """Verify status detects untracked files."""
        # Create a new file
        (temp_repo / "new_file.txt").write_text("hello")
        
        status = git_client.get_status(temp_repo)
        assert status.is_clean is False
        assert status.files_changed == 1
        assert status.files_untracked == 1
        assert status.files_staged == 0
        assert status.has_source_code is False

    def test_get_status_source_code(self, temp_repo: Path) -> None:
        """Verify status detects source code files."""
        # Create a Python file
        (temp_repo / "main.py").write_text("print('hello')")
        
        status = git_client.get_status(temp_repo)
        assert status.has_source_code is True

    def test_commit_and_log(self, temp_repo: Path) -> None:
        """Verify committing changes and reading the log."""
        (temp_repo / "file.txt").write_text("initial")
        
        # Commit
        hash1 = git_client.commit(temp_repo, "Initial commit")
        assert len(hash1) == 40
        
        # Check log
        log = git_client.get_log(temp_repo)
        assert len(log) == 1
        assert log[0].hash == hash1
        assert log[0].message == "Initial commit"
        assert log[0].author == "Test User"
        
        # Make another commit
        (temp_repo / "file.txt").write_text("updated")
        hash2 = git_client.commit(temp_repo, "Update file")
        
        log2 = git_client.get_log(temp_repo)
        assert len(log2) == 2
        assert log2[0].hash == hash2
        assert log2[1].hash == hash1

    def test_diff_stat(self, temp_repo: Path) -> None:
        """Verify diff stat generation against a baseline commit."""
        # Baseline
        f1 = temp_repo / "file1.txt"
        f1.write_text("line 1\nline 2\n")
        baseline_hash = git_client.commit(temp_repo, "Baseline")
        
        # Changes: modify f1, add f2, remove f1 (wait, if we remove f1 it's deleted)
        # Modify f1 (remove a line, add a line)
        f1.write_text("line 1\nnew line 2\n")
        # Add f2
        f2 = temp_repo / "file2.txt"
        f2.write_text("line 1\n")
        
        # We don't need to commit to see diff_stat against baseline!
        # Because diff_stat compares current working tree to the given commit.
        # But wait, diff stat in git_client uses `git diff HEAD` for uncommitted changes? 
        # No, `diff_stat` uses `git diff --numstat from_commit`, which compares working tree 
        # (including unstaged and staged) to `from_commit` if not specified differently.
        # Oh, `git diff <commit>` compares working tree to <commit>, BUT it does NOT include untracked files!
        # Let's check: git diff <commit> includes tracked modified files, but not untracked.
        # So we should git add the untracked file so it's in the index, or `git diff` won't see it.
        subprocess.run(["git", "add", "file2.txt"], cwd=str(temp_repo))
        
        result = git_client.diff_stat(temp_repo, baseline_hash)
        
        assert result.baseline_commit == baseline_hash
        assert result.total_files_changed == 2
        
        # Find entries
        f1_entry = next(f for f in result.files if f.relative_path == "file1.txt")
        assert f1_entry.change_type == FileChangeType.MODIFIED
        assert f1_entry.lines_added == 1
        assert f1_entry.lines_removed == 1
        
        f2_entry = next(f for f in result.files if f.relative_path == "file2.txt")
        assert f2_entry.change_type == FileChangeType.ADDED
        assert f2_entry.lines_added == 1
        assert f2_entry.lines_removed == 0

    def test_not_a_repository_error(self, tmp_path: Path) -> None:
        """Verify operations fail on non-repositories."""
        with pytest.raises(GitRepositoryError):
            git_client.get_status(tmp_path)
            
    def test_conflict_error_parsing(self, temp_repo: Path) -> None:
        """Verify merge conflicts are detected and raise GitConflictError."""
        # Create baseline
        (temp_repo / "file.txt").write_text("base")
        git_client.commit(temp_repo, "Base")
        
        # Create branch 'feature'
        subprocess.run(["git", "checkout", "-b", "feature"], cwd=str(temp_repo))
        (temp_repo / "file.txt").write_text("feature")
        git_client.commit(temp_repo, "Feature")
        
        # Back to master
        subprocess.run(["git", "checkout", "master"], cwd=str(temp_repo))
        (temp_repo / "file.txt").write_text("master")
        git_client.commit(temp_repo, "Master")
        
        # Merge feature into master (will conflict)
        result = subprocess.run(["git", "merge", "feature"], cwd=str(temp_repo), capture_output=True)
        assert result.returncode != 0
        
        # Now try to commit via GitHelper, which does git add -A, then commit.
        # Wait, git add -A will stage the conflict markers!
        # If we try to commit now, git will commit the conflict markers if we aren't careful,
        # but if we try to `git push` during a conflict state it might fail, or `git merge` itself failed.
        # Let's test the error parser directly.
        
        # Let's run a raw git command that we know fails with unmerged paths
        # Actually `git commit` fails if there are unmerged paths and we didn't add them.
        # We can just simulate the error result processing.
        class FakeResult:
            returncode = 1
            stderr = "error: Merging is not possible because you have unmerged files."
            stdout = ""
            
        with pytest.raises(GitConflictError):
            git_client._handle_git_error(FakeResult(), "git commit")
