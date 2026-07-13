"""Tests for the Reminder Scheduler."""

import pytest
from githelper.domain.models import (
    ReminderSensitivity,
    RiskAssessment,
    RiskLevel,
    TimeDecision,
)
from githelper.domain import reminder_scheduler


class TestReminderScheduler:
    """Tests for the Reminder Scheduler logic."""

    def test_evaluate_shows_when_both_engines_agree(self) -> None:
        """Verify a reminder is triggered when both risk and time are met."""
        risk = RiskAssessment(
            level=RiskLevel.HIGH,
            score=0.8,
            contributing_factors=("5 files changed", "~120 lines changed"),
            is_reminder_worthy=True
        )
        time_dec = TimeDecision(
            should_remind=True,
            cooldown_remaining_seconds=0.0,
            minutes_since_last_commit=60.0,
            reason="~60 min of work since last commit"
        )
        
        decision = reminder_scheduler.evaluate(risk, time_dec)
        
        assert decision.should_show
        assert "5 files changed" in decision.reason_text
        assert "~120 lines changed" in decision.reason_text
        assert "~60 min of work" in decision.reason_text

    def test_evaluate_suppresses_when_risk_low(self) -> None:
        """Verify a reminder is suppressed if Risk Engine says no, even if time elapsed."""
        risk = RiskAssessment(
            level=RiskLevel.LOW,
            score=0.2,
            contributing_factors=("1 file changed",),
            is_reminder_worthy=False
        )
        time_dec = TimeDecision(
            should_remind=True,
            cooldown_remaining_seconds=0.0,
            minutes_since_last_commit=120.0,
            reason="~2 hrs of work since last commit"
        )
        
        decision = reminder_scheduler.evaluate(risk, time_dec)
        
        assert not decision.should_show
        assert decision.reason_text == "Risk too low (LOW)."

    def test_evaluate_suppresses_when_time_cooldown_active(self) -> None:
        """Verify a reminder is suppressed if Time Engine says no, even if risk is HIGH."""
        risk = RiskAssessment(
            level=RiskLevel.HIGH,
            score=0.9,
            contributing_factors=("20 files changed",),
            is_reminder_worthy=True
        )
        time_dec = TimeDecision(
            should_remind=False,
            cooldown_remaining_seconds=600.0,
            minutes_since_last_commit=120.0,
            reason="Snoozed"
        )
        
        decision = reminder_scheduler.evaluate(risk, time_dec)
        
        assert not decision.should_show
        assert decision.reason_text == "Time gate blocked: Snoozed."

    def test_evaluate_clean_state(self) -> None:
        """Verify clean state is handled correctly."""
        risk = RiskAssessment(
            level=RiskLevel.NONE,
            score=0.0,
            contributing_factors=(),
            is_reminder_worthy=False
        )
        time_dec = TimeDecision(
            should_remind=False,
            cooldown_remaining_seconds=0.0,
            minutes_since_last_commit=10.0,
            reason="Too soon after last commit"
        )
        
        decision = reminder_scheduler.evaluate(risk, time_dec)
        
        assert not decision.should_show
        assert decision.reason_text == "No meaningful uncommitted work."
