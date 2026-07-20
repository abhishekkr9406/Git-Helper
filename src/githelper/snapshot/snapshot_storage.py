"""Snapshot storage.

The only module in the codebase permitted to perform snapshot file I/O (Architecture DR-008).
Handles reading, writing, and cleaning up snapshot files. Snapshots are simple ZIP archives
of the repository's working tree, excluding .git and common massive directories.
"""

import os
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from githelper.common.constants import APP_AUTHOR, APP_NAME
from githelper.diagnostics.logger import get_logger

logger = get_logger(__name__)

# Standard exclusions to prevent massive snapshots
_EXCLUSIONS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    "build", "dist", ".idea", ".vscode"
}


def _get_snapshot_dir() -> Path:
    """Get the cross-platform directory for storing snapshots."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
        return Path(base) / APP_AUTHOR / APP_NAME / "snapshots"
    elif os.name == "posix":
        import sys
        if sys.platform == "darwin":
            return Path(os.path.expanduser("~/Library/Application Support")) / APP_NAME / "snapshots"
        else:
            return Path(os.path.expanduser("~/.local/share")) / APP_NAME / "snapshots"
            
    return Path.cwd() / "snapshots"


class SnapshotStorage:
    """Handles snapshot file operations."""
    
    def __init__(self, storage_dir: Path | None = None):
        self.storage_dir = storage_dir or _get_snapshot_dir()
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def create_snapshot(self, repo_path: Path, snapshot_id: str) -> Path:
        """Create a ZIP snapshot of the repository.
        
        Args:
            repo_path: The repository to snapshot.
            snapshot_id: Unique identifier (usually UUID).
            
        Returns:
            The path to the created ZIP file.
        """
        zip_path = self.storage_dir / f"{snapshot_id}.zip"
        
        logger.debug(f"Creating snapshot {zip_path} for {repo_path}")
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(repo_path):
                    # Filter out excluded directories in-place to prevent os.walk from entering them
                    dirs[:] = [d for d in dirs if d not in _EXCLUSIONS]
                    
                    for f in files:
                        file_path = Path(root) / f
                        # Zip path should be relative to the repo root
                        arcname = file_path.relative_to(repo_path)
                        zf.write(file_path, arcname)
                        
            return zip_path
        except Exception as e:
            # Clean up partial zip if it failed
            if zip_path.exists():
                try:
                    zip_path.unlink()
                except Exception:
                    pass
            raise IOError(f"Failed to create snapshot for {repo_path}: {e}") from e

    def restore_snapshot(self, zip_path: Path, target_repo: Path) -> None:
        """Extract a snapshot over the target repository.
        
        Does not delete existing files, only overwrites/adds.
        """
        logger.info(f"Restoring snapshot {zip_path} to {target_repo}")
        if not zip_path.exists():
            raise FileNotFoundError(f"Snapshot not found: {zip_path}")
            
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(target_repo)
        except Exception as e:
            raise IOError(f"Failed to restore snapshot {zip_path}: {e}") from e

    def delete_snapshot(self, zip_path: Path) -> None:
        """Delete a snapshot file."""
        if zip_path.exists():
            try:
                zip_path.unlink()
                logger.debug(f"Deleted snapshot {zip_path}")
            except Exception as e:
                logger.error(f"Failed to delete snapshot {zip_path}: {e}")

    def cleanup_old_snapshots(self, active_snapshot_paths: set[Path]) -> None:
        """Delete any ZIP files in the storage dir that aren't in the active set."""
        for file in self.storage_dir.glob("*.zip"):
            if file not in active_snapshot_paths:
                self.delete_snapshot(file)
