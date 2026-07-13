"""Time Engine.

Pure decision logic: given elapsed time since last commit and last reminder,
determines whether now is an appropriate moment to interrupt the user.

Zero dependencies on Git, OS, UI, or Qt. Wall-clock time is injected as a
parameter â€” never read internally â€” so this module is fully testable without
mocking time.

Implements:
  - Minimum time before first reminder after a commit.
  - Cooldown after dismiss/snooze/"not now".
  - Quiet hours support (Doc 06 Â§6.4).
  - Sensitivity-based interval tuning (Relaxed / Balanced / Frequent).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

from githelper.domain.models import (
    ReminderSensitivity,
    TimeDecision,
)


# ---------------------------------------------------------------------------
# Time Threshold Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TimeThresholds:
    """Per-preset time intervals for the Time Engine.

    All values in minutes.
    """

    min_time_before_first_reminder: float   # Minutes after last commit before first reminder.
    cooldown_after_dismiss: float            # Cooldown after user clicks "Not now".
    cooldown_after_snooze_15: float          # After 15-min snooze selection.
    cooldown_after_snooze_60: float          # After 1-hour snooze selection.
    cooldown_after_snooze_until_launch: float  # Effectively infinite until restart.


_THRESHOLDS: dict[ReminderSensitivity, TimeThresholds] = {
    ReminderSensitivity.RELAXED: TimeThresholds(
        min_time_before_first_reminder=90.0,
        cooldown_after_dismiss=45.0,
        cooldown_after_snooze_15=15.0,
        cooldown_after_snooze_60=60.0,
        cooldown_after_snooze_until_launch=float("inf"),
    ),
    ReminderSensitivity.BALANCED: TimeThresholds(
        min_time_before_first_reminder=45.0,
        cooldown_after_dismiss=20.0,
        cooldown_after_snooze_15=15.0,
        cooldown_after_snooze_60=60.0,
        cooldown_after_snooze_until_launch=float("inf"),
    ),
    ReminderSensitivity.FREQUENT: TimeThresholds(
        min_time_before_first_reminder=20.0,
        cooldown_after_dismiss=10.0,
        cooldown_after_snooze_15=15.0,
        cooldown_after_snooze_60=60.0,
        cooldown_after_snooze_until_launch=float("inf"),
    ),
}


def get_thresholds(sensitivity: ReminderSensitivity) -> TimeThresholds:
    """Return the threshold configuration for the given sensitivity preset."""
    return _THRESHOLDS[sensitivity]


# ---------------------------------------------------------------------------
# Time Evaluation
# ---------------------------------------------------------------------------


def evaluate(
    now: datetime,
    last_commit_time: datetime | None,
    last_reminder_time: datetime | None,
    snooze_until: datetime | None,
    sensitivity: ReminderSensitivity = ReminderSensitivity.BALANCED,
    quiet_hours_enabled: bool = False,
    quiet_hours_start: str = "20:00",
    quiet_hours_end: str = "08:00",
) -> TimeDecision:
    """Evaluate whether now is an appropriate time to show a reminder.

    This is a pure function: same inputs always produce the same output.
    `now` is injected, never read from the system clock.

    Args:
        now: The current time (injected for testability â€” Doc 08 Â§4 rule 4).
        last_commit_time: When the last commit was made in this repo.
            None if no commits during this session.
        last_reminder_time: When the last reminder was shown/dismissed/snoozed.
            None if no reminders have been shown.
        snooze_until: If set, reminders are suppressed until this time.
            None if no active snooze.
        sensitivity: User's chosen reminder sensitivity preset.
        quiet_hours_enabled: Whether quiet hours are active.
        quiet_hours_start: Start of quiet hours in "HH:MM" format.
        quiet_hours_end: End of quiet hours in "HH:MM" format.

    Returns:
        A TimeDecision indicating whether a reminder should be shown,
        with cooldown and context information.
    """
    thresholds = get_thresholds(sensitivity)

    # --- Check quiet hours ---
    if quiet_hours_enabled and _in_quiet_hours(now, quiet_hours_start, quiet_hours_end):
        return TimeDecision(
            should_remind=False,
            cooldown_remaining_seconds=0.0,
            minutes_since_last_commit=_minutes_since(now, last_commit_time),
            reason="Quiet hours active",
            in_quiet_hours=True,
        )

    # --- Check active snooze ---
    if snooze_until is not None and now < snooze_until:
        remaining = (snooze_until - now).total_seconds()
        return TimeDecision(
            should_remind=False,
            cooldown_remaining_seconds=remaining,
            minutes_since_last_commit=_minutes_since(now, last_commit_time),
            reason="Snoozed",
            in_quiet_hours=False,
        )

    # --- Check minimum time since last commit ---
    minutes_since_commit = _minutes_since(now, last_commit_time)
    if minutes_since_commit < thresholds.min_time_before_first_reminder:
        remaining = (
            thresholds.min_time_before_first_reminder - minutes_since_commit
        ) * 60.0
        return TimeDecision(
            should_remind=False,
            cooldown_remaining_seconds=max(0.0, remaining),
            minutes_since_last_commit=minutes_since_commit,
            reason="Too soon after last commit",
            in_quiet_hours=False,
        )

    # --- Check cooldown since last reminder ---
    if last_reminder_time is not None:
        minutes_since_reminder = _minutes_since(now, last_reminder_time)
        cooldown = thresholds.cooldown_after_dismiss
        if minutes_since_reminder < cooldown:
            remaining = (cooldown - minutes_since_reminder) * 60.0
            return TimeDecision(
                should_remind=False,
                cooldown_remaining_seconds=max(0.0, remaining),
                minutes_since_last_commit=minutes_since_commit,
                reason="Cooldown after previous reminder",
                in_quiet_hours=False,
            )

    # --- All time gates passed â†’ reminder is appropriate ---
    # Build a human-readable time estimate for the reason line.
    time_desc = _format_duration(minutes_since_commit)

    return TimeDecision(
        should_remind=True,
        cooldown_remaining_seconds=0.0,
        minutes_since_last_commit=minutes_since_commit,
        reason=f"~{time_desc} of work since last commit",
        in_quiet_hours=False,
    )


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------


def _minutes_since(now: datetime, reference: datetime | None) -> float:
    """Calculate minutes elapsed since reference time.

    Returns a very large number if reference is None (treated as 'a long time ago').
    """
    if reference is None:
        return float("inf")
    delta = (now - reference).total_seconds()
    return max(0.0, delta / 60.0)


def _in_quiet_hours(now: datetime, start_str: str, end_str: str) -> bool:
    """Check whether `now` falls within the quiet hours window.

    Handles overnight spans (e.g., 20:00 to 08:00) correctly.
    """
    current_time = now.time()
    start = time.fromisoformat(start_str)
    end = time.fromisoformat(end_str)

    if start <= end:
        # Same-day range (e.g., 09:00 to 17:00)
        return start <= current_time <= end
    else:
        # Overnight range (e.g., 20:00 to 08:00)
        return current_time >= start or current_time <= end


def _format_duration(minutes: float) -> str:
    """Format a duration in minutes into a human-readable string.

    Examples: '25 min', '1.5 hrs', '3 hrs'
    """
    if minutes == float("inf"):
        return "a long time"
    if minutes < 60:
        return f"{int(minutes)} min"
    hours = minutes / 60.0
    if hours == int(hours):
        return f"{int(hours)} hrs" if hours != 1 else "1 hr"
    return f"{hours:.1f} hrs"
