"""Application-wide constants.

Default timeout values, thresholds, shared numeric limits referenced by more
than one layer. Paths should generally be resolved dynamically, but fallback
constants can live here.
"""

from typing import Final


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

APP_NAME: Final[str] = "GitHelper"
APP_AUTHOR: Final[str] = "GitHelper"

# ---------------------------------------------------------------------------
# Timing & Delays
# ---------------------------------------------------------------------------

# How often the Rolling Snapshot Service checks for work (seconds).
# Per Doc 04, a 5-minute interval balances safety and battery.
SNAPSHOT_INTERVAL_SECONDS: Final[int] = 300

# How often the Reconciliation Poller runs (seconds).
# This is a slow backstop to catch anything the filesystem watcher missed.
# 10 minutes is appropriate since the watcher handles immediate feedback.
RECONCILIATION_INTERVAL_SECONDS: Final[int] = 600

# How long the Commit Popup stays visible before auto-collapsing to tray (seconds).
# Per Doc 06, non-intrusive auto-collapse.
POPUP_AUTO_COLLAPSE_SECONDS: Final[int] = 120

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

# Maximum characters to show for a commit hash in the UI.
SHORT_HASH_LENGTH: Final[int] = 7

# Maximum repositories to monitor concurrently (sanity limit).
MAX_MONITORED_REPOS: Final[int] = 50
