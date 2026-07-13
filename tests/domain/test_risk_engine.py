"""Tests for the Risk Engine."""

import pytest
from githelper.domain.models import ChangeStateSummary, ReminderSensitivity, RiskLevel
from githelper.domain import risk_engine


class TestRiskEngine:
    """Tests for the Risk Engine logic."""

    def test_clean_state_is_none_risk(self) -> None:
        """Verify that a clean state always returns NONE risk."""
        state = ChangeStateSummary(is_clean=True)
        assessment = risk_engine.evaluate(state, ReminderSensitivity.BALANCED)
        assert assessment.level == RiskLevel.NONE
        assert assessment.score == 0.0
        assert not assessment.is_reminder_worthy

    def test_relaxed_sensitivity_high_thresholds(self) -> None:
        """Verify Relaxed sensitivity requires more changes to reach HIGH risk."""
        state = ChangeStateSummary(
            files_changed=9,
            lines_added=150,
            has_source_code=False,
            is_clean=False
        )
        assessment = risk_engine.evaluate(state, ReminderSensitivity.RELAXED)
        assert assessment.level in (RiskLevel.MEDIUM, RiskLevel.LOW)
        assert not assessment.is_reminder_worthy

        # Push it over the Relaxed threshold
        high_state = ChangeStateSummary(
            files_changed=16,
            lines_added=350,
            has_source_code=False,
            is_clean=False
        )
        high_assessment = risk_engine.evaluate(high_state, ReminderSensitivity.RELAXED)
        assert high_assessment.level == RiskLevel.HIGH
        assert high_assessment.is_reminder_worthy

    def test_balanced_sensitivity(self) -> None:
        """Verify Balanced sensitivity thresholds."""
        state = ChangeStateSummary(
            files_changed=6,
            lines_added=60,
            has_source_code=False,
            is_clean=False
        )
        assessment = risk_engine.evaluate(state, ReminderSensitivity.BALANCED)
        # 6 files > 5 (low), 60 lines > 50 (low), but neither hit high (10, 150).
        # Score should be > 0.0 and <= 0.7
        assert assessment.level in (RiskLevel.LOW, RiskLevel.MEDIUM)
        
        high_state = ChangeStateSummary(
            files_changed=11,
            lines_added=160,
            has_source_code=False,
            is_clean=False
        )
        high_assessment = risk_engine.evaluate(high_state, ReminderSensitivity.BALANCED)
        assert high_assessment.level == RiskLevel.HIGH

    def test_frequent_sensitivity_low_thresholds(self) -> None:
        """Verify Frequent sensitivity triggers HIGH risk quickly."""
        state = ChangeStateSummary(
            files_changed=5,
            lines_added=65,
            has_source_code=False,
            is_clean=False
        )
        assessment = risk_engine.evaluate(state, ReminderSensitivity.FREQUENT)
        assert assessment.level == RiskLevel.HIGH
        assert assessment.is_reminder_worthy

    def test_source_code_weight_boost(self) -> None:
        """Verify that source code presence boosts the risk score."""
        state = ChangeStateSummary(
            files_changed=5,
            lines_added=50,
            has_source_code=False,
            is_clean=False
        )
        assessment_no_code = risk_engine.evaluate(state, ReminderSensitivity.BALANCED)
        
        state_with_code = ChangeStateSummary(
            files_changed=5,
            lines_added=50,
            has_source_code=True,
            is_clean=False
        )
        assessment_with_code = risk_engine.evaluate(state_with_code, ReminderSensitivity.BALANCED)
        
        assert assessment_with_code.score > assessment_no_code.score
        assert "source code files modified" in assessment_with_code.contributing_factors

    def test_contributing_factors_generated(self) -> None:
        """Verify human-readable contributing factors are included."""
        state = ChangeStateSummary(
            files_changed=12,
            lines_added=200,
            has_source_code=True,
            is_clean=False
        )
        assessment = risk_engine.evaluate(state, ReminderSensitivity.BALANCED)
        assert "12 files changed" in assessment.contributing_factors
        assert "~200 lines changed" in assessment.contributing_factors
        assert "source code files modified" in assessment.contributing_factors
