"""Tests for the Time Engine."""

from datetime import datetime, timedelta
import pytest
from githelper.domain.models import ReminderSensitivity
from githelper.domain import time_engine


class TestTimeEngine:
    """Tests for the Time Engine logic."""

    def test_min_time_before_first_reminder(self) -> None:
        """Verify reminder is suppressed if too soon after a commit."""
        now = datetime(2026, 7, 13, 10, 0, 0)
        # Commit was 10 minutes ago
        last_commit = now - timedelta(minutes=10)
        
        decision = time_engine.evaluate(
            now=now,
            last_commit_time=last_commit,
            last_reminder_time=None,
            snooze_until=None,
            sensitivity=ReminderSensitivity.BALANCED
        )
        assert not decision.should_remind
        assert decision.reason == "Too soon after last commit"
        # Balanced min time is 45 mins. So 35 mins (2100 seconds) remaining.
        assert decision.cooldown_remaining_seconds == 35 * 60

    def test_passes_min_time_if_long_enough(self) -> None:
        """Verify reminder is allowed if enough time has passed since last commit."""
        now = datetime(2026, 7, 13, 10, 0, 0)
        # Commit was 50 minutes ago
        last_commit = now - timedelta(minutes=50)
        
        decision = time_engine.evaluate(
            now=now,
            last_commit_time=last_commit,
            last_reminder_time=None,
            snooze_until=None,
            sensitivity=ReminderSensitivity.BALANCED
        )
        assert decision.should_remind
        assert decision.cooldown_remaining_seconds == 0.0
        assert decision.reason == "~50 min of work since last commit"

    def test_snooze_suppression(self) -> None:
        """Verify reminders are suppressed when an active snooze exists."""
        now = datetime(2026, 7, 13, 10, 0, 0)
        last_commit = now - timedelta(minutes=60)
        snooze_until = now + timedelta(minutes=10)
        
        decision = time_engine.evaluate(
            now=now,
            last_commit_time=last_commit,
            last_reminder_time=None,
            snooze_until=snooze_until,
            sensitivity=ReminderSensitivity.BALANCED
        )
        assert not decision.should_remind
        assert decision.reason == "Snoozed"
        assert decision.cooldown_remaining_seconds == 10 * 60

    def test_dismiss_cooldown(self) -> None:
        """Verify 'Not now' dismiss respects the cooldown interval."""
        now = datetime(2026, 7, 13, 10, 0, 0)
        last_commit = now - timedelta(minutes=60)
        # Reminder was dismissed 5 minutes ago
        last_reminder = now - timedelta(minutes=5)
        
        decision = time_engine.evaluate(
            now=now,
            last_commit_time=last_commit,
            last_reminder_time=last_reminder,
            snooze_until=None,
            sensitivity=ReminderSensitivity.BALANCED
        )
        assert not decision.should_remind
        assert decision.reason == "Cooldown after previous reminder"
        # Balanced dismiss cooldown is 20 min. So 15 mins remaining.
        assert decision.cooldown_remaining_seconds == 15 * 60

    def test_quiet_hours_overnight(self) -> None:
        """Verify quiet hours suppress reminders correctly."""
        # 11:00 PM
        now = datetime(2026, 7, 13, 23, 0, 0)
        last_commit = now - timedelta(minutes=120)
        
        decision = time_engine.evaluate(
            now=now,
            last_commit_time=last_commit,
            last_reminder_time=None,
            snooze_until=None,
            sensitivity=ReminderSensitivity.BALANCED,
            quiet_hours_enabled=True,
            quiet_hours_start="20:00",
            quiet_hours_end="08:00"
        )
        assert not decision.should_remind
        assert decision.reason == "Quiet hours active"
        assert decision.in_quiet_hours

    def test_format_duration(self) -> None:
        """Test internal duration formatting utility."""
        assert time_engine._format_duration(45) == "45 min"
        assert time_engine._format_duration(60) == "1 hr"
        assert time_engine._format_duration(90) == "1.5 hrs"
        assert time_engine._format_duration(120) == "2 hrs"
        assert time_engine._format_duration(float("inf")) == "a long time"
