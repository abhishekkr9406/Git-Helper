"""Domain data contracts.

Shared data shapes used across the whole system. These are the domain's vocabulary â€”
they describe what a change, a risk, or a decision means to GitHelper.

Adapters (Git integration, persistence, UI) translate their own external formats
into these models. The models themselves belong to the domain that defines their meaning.

This module has zero dependencies on any other githelper package or any external library.
It depends only on the Python standard library.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RepoStatus(enum.Enum):
    """Observable status of a watched repository.

    Maps directly to the Repository Monitoring Machine states (Doc 07 Â§3.1)
    and to the tray icon status indicators (Doc 06 Â§3.2).
    """

    IDLE = "idle"               # Working tree clean â€” no uncommitted content.
    MONITORING = "monitoring"   # Uncommitted content exists, not yet reminder-worthy.
    RISK_DETECTED = "risk_detected"  # Engines agreed â€” popup not yet shown.
    REMINDER = "reminder"       # Commit Popup is visible for this repo.
    COMMIT = "commit"           # Commit operation in progress.
    PUSH = "push"               # Push operation in progress.
    RECOVERY = "recovery"       # Startup: recovery snapshot awaiting user decision.


class RiskLevel(enum.Enum):
    """Qualitative risk level produced by the Risk Engine."""

    NONE = "none"       # No meaningful uncommitted work detected.
    LOW = "low"         # Some changes, below reminder threshold.
    MEDIUM = "medium"   # Approaching reminder threshold.
    HIGH = "high"       # At or above reminder threshold â€” meaningful work at risk.


class ReminderSensitivity(enum.Enum):
    """User-facing reminder sensitivity presets (Doc 06 Â§6.4).

    Three human-readable presets â€” no raw numeric threshold sliders.
    The underlying tuning values live in the Risk and Time Engines.
    """

    RELAXED = "relaxed"
    BALANCED = "balanced"
    FREQUENT = "frequent"


class FileChangeType(enum.Enum):
    """Type of change for a single file in a diff summary."""

    MODIFIED = "M"
    ADDED = "A"
    DELETED = "D"
    RENAMED = "R"
    COPIED = "C"
    UNTRACKED = "?"


class PopupPosition(enum.Enum):
    """Screen corner for popup placement (Doc 06 Â§4.6)."""

    TOP_RIGHT = "top_right"
    BOTTOM_RIGHT = "bottom_right"


# ---------------------------------------------------------------------------
# Data Contracts â€” Change Detection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChangeStateSummary:
    """Summary of a repository's current uncommitted state.

    Produced by the Repository Monitor, consumed by the Risk Engine.
    Frozen because it is a snapshot of a point-in-time state and must not
    be mutated after creation.
    """

    files_changed: int = 0
    files_staged: int = 0
    files_unstaged: int = 0
    files_untracked: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    file_extensions: frozenset[str] = field(default_factory=frozenset)
    has_source_code: bool = False
    is_clean: bool = True


# ---------------------------------------------------------------------------
# Data Contracts â€” Risk & Time Engine Output
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RiskAssessment:
    """Output of the Risk Engine for a single evaluation.

    Contains both the qualitative level and the contributing factors
    so the UI can generate the human-readable 'why now' reason line
    (Doc 06 Â§4.4).
    """

    level: RiskLevel
    score: float  # 0.0 â€“ 1.0 normalized score for internal use.
    contributing_factors: tuple[str, ...] = ()
    is_reminder_worthy: bool = False


@dataclass(frozen=True)
class TimeDecision:
    """Output of the Time Engine for a single evaluation.

    Determines whether now is an appropriate moment to interrupt the user,
    independent of risk level.
    """

    should_remind: bool = False
    cooldown_remaining_seconds: float = 0.0
    minutes_since_last_commit: float = 0.0
    reason: str = ""
    in_quiet_hours: bool = False


@dataclass(frozen=True)
class ReminderDecision:
    """Combined output of Risk Engine + Time Engine.

    Both engines must agree for `should_show` to be True (Doc 01 Â§3, Doc 07 Â§3.2 #8).
    The `reason_text` is the human-readable one-liner shown in the Commit Popup.
    """

    should_show: bool = False
    reason_text: str = ""
    risk_assessment: RiskAssessment | None = None
    time_decision: TimeDecision | None = None


# ---------------------------------------------------------------------------
# Data Contracts â€” Repository
# ---------------------------------------------------------------------------


@dataclass
class RepositoryRecord:
    """A registered, watched repository.

    Mutable because status changes over time as the monitoring machine transitions.
    """

    path: Path
    display_name: str
    status: RepoStatus = RepoStatus.IDLE
    push_pending: bool = False  # Non-blocking flag per Doc 07 Â§3.2 transition #19.
    last_commit_hash: str = ""
    last_commit_time: datetime | None = None
    last_reminder_time: datetime | None = None
    snooze_until: datetime | None = None
    stable_marker: StableMarker | None = None


# ---------------------------------------------------------------------------
# Data Contracts â€” Stable Version
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StableMarker:
    """A Stable version marker (Doc 09 ADR-008).

    GitHelper-local metadata â€” not a Git tag, branch, or note.
    Stored in GitHelper's own persistence store per repository.
    """

    commit_hash: str
    label: str = ""
    marked_at: datetime | None = None
    repo_path: Path | None = None


# ---------------------------------------------------------------------------
# Data Contracts â€” Recovery Snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SnapshotFileEntry:
    """A single file entry within a recovery snapshot manifest."""

    relative_path: str
    change_type: FileChangeType
    size_bytes: int = 0


@dataclass(frozen=True)
class SnapshotMetadata:
    """Metadata describing a recovery snapshot (Doc 03 Â§4.4).

    The snapshot itself (actual file contents) is managed by snapshot_storage.py.
    This metadata is what gets persisted in the state store and shown to the user.
    """

    repo_path: Path
    captured_at: datetime
    files: tuple[SnapshotFileEntry, ...] = ()
    files_changed: int = 0
    files_new: int = 0
    snapshot_id: str = ""
    clean_shutdown: bool = False


# ---------------------------------------------------------------------------
# Data Contracts â€” Diff / Compare
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileDiffEntry:
    """A single file's diff summary in a Compare-to-Stable view (Doc 06 Â§8)."""

    relative_path: str
    change_type: FileChangeType
    lines_added: int = 0
    lines_removed: int = 0


@dataclass(frozen=True)
class CompareResult:
    """Result of comparing current working state to a Stable commit (Doc 06 Â§8.2)."""

    baseline_commit: str
    baseline_label: str = ""
    total_files_changed: int = 0
    total_lines_changed: int = 0
    files: tuple[FileDiffEntry, ...] = ()


# ---------------------------------------------------------------------------
# Data Contracts â€” Git Log
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommitRecord:
    """A single commit entry from the Git log (Doc 06 Â§7.2)."""

    hash: str
    short_hash: str
    message: str
    author: str = ""
    timestamp: datetime | None = None
    is_stable: bool = False  # Set by UI/Orchestrator based on StableMarker comparison.


# ---------------------------------------------------------------------------
# Data Contracts â€” Application Settings
# ---------------------------------------------------------------------------


@dataclass
class AppSettings:
    """All user-configurable settings (Doc 06 Â§6).

    Mutable because the user changes settings at runtime.
    Defaults match the 'Balanced' preset.
    """

    # General tab (Doc 06 Â§6.2)
    start_at_login: bool = True
    show_tray_status_dot: bool = True
    popup_position: PopupPosition = PopupPosition.BOTTOM_RIGHT
    show_metrics_in_popup: bool = True

    # Reminders tab (Doc 06 Â§6.4)
    reminder_sensitivity: ReminderSensitivity = ReminderSensitivity.BALANCED
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "20:00"  # 24h format HH:MM.
    quiet_hours_end: str = "08:00"
    pause_in_fullscreen: bool = True

    # Recovery tab (Doc 06 Â§6.5)
    snapshot_retention_days: int = 7
    snapshot_storage_path: str = ""  # Empty = default location.

    # Runtime state (not user-configured, but persisted)
    monitoring_paused: bool = False
