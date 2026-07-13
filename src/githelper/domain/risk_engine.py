"""Risk Engine.

Pure decision logic: given a ChangeStateSummary, determines whether accumulated
changes represent meaningful work worth protecting / reminding about.

Zero dependencies on Git, OS, UI, or Qt. Receives data, returns a judgment.
Implements structural, Git-observable signals only (ADR-007):
  - Number of files changed
  - Lines added/removed
  - File extensions/types touched
  - Whether source-code files are involved

Threshold tables are organized by ReminderSensitivity preset (Doc 06 Â§6.4):
Relaxed, Balanced, Frequent.
"""

from __future__ import annotations

from dataclasses import dataclass

from githelper.domain.models import (
    ChangeStateSummary,
    ReminderSensitivity,
    RiskAssessment,
    RiskLevel,
)


# ---------------------------------------------------------------------------
# Threshold Configuration
# ---------------------------------------------------------------------------

# Source-code file extensions that receive higher weight in risk scoring.
# Kept conservative â€” only common, hand-written source types.
SOURCE_CODE_EXTENSIONS: frozenset[str] = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".java", ".kt", ".scala",
    ".go", ".rs", ".c", ".cpp", ".h", ".hpp", ".cs",
    ".rb", ".swift", ".m", ".mm",
    ".sql", ".sh", ".bash", ".ps1",
    ".html", ".css", ".scss", ".less",
    ".vue", ".svelte",
})


@dataclass(frozen=True)
class RiskThresholds:
    """Per-preset threshold values for risk scoring.

    These are the internal tuning knobs behind the three human-readable presets.
    Users never see these numbers directly (Doc 06 Â§6.4 â€” no raw numeric sliders).
    """

    files_low: int        # Files changed threshold for LOW risk.
    files_high: int       # Files changed threshold for HIGH risk.
    lines_low: int        # Lines changed threshold for LOW risk.
    lines_high: int       # Lines changed threshold for HIGH risk.
    source_code_weight: float  # Multiplier when source-code files are involved.


# Threshold tables per sensitivity preset.
_THRESHOLDS: dict[ReminderSensitivity, RiskThresholds] = {
    ReminderSensitivity.RELAXED: RiskThresholds(
        files_low=8,
        files_high=15,
        lines_low=100,
        lines_high=300,
        source_code_weight=1.3,
    ),
    ReminderSensitivity.BALANCED: RiskThresholds(
        files_low=5,
        files_high=10,
        lines_low=50,
        lines_high=150,
        source_code_weight=1.5,
    ),
    ReminderSensitivity.FREQUENT: RiskThresholds(
        files_low=2,
        files_high=5,
        lines_low=20,
        lines_high=60,
        source_code_weight=1.8,
    ),
}


def get_thresholds(sensitivity: ReminderSensitivity) -> RiskThresholds:
    """Return the threshold configuration for the given sensitivity preset."""
    return _THRESHOLDS[sensitivity]


# ---------------------------------------------------------------------------
# Risk Scoring
# ---------------------------------------------------------------------------


def evaluate(
    change_state: ChangeStateSummary,
    sensitivity: ReminderSensitivity = ReminderSensitivity.BALANCED,
) -> RiskAssessment:
    """Evaluate the risk level of a repository's current uncommitted state.

    This is a pure function: same inputs always produce the same output.
    No I/O, no side effects, no wall-clock dependency.

    Args:
        change_state: Current uncommitted changes summary from the monitor.
        sensitivity: User's chosen reminder sensitivity preset.

    Returns:
        A RiskAssessment with the computed risk level, normalized score,
        contributing factors, and whether a reminder is warranted.
    """
    if change_state.is_clean:
        return RiskAssessment(
            level=RiskLevel.NONE,
            score=0.0,
            contributing_factors=(),
            is_reminder_worthy=False,
        )

    thresholds = get_thresholds(sensitivity)
    factors: list[str] = []

    # --- File count scoring ---
    file_score = _score_dimension(
        value=change_state.files_changed,
        low_threshold=thresholds.files_low,
        high_threshold=thresholds.files_high,
    )
    if change_state.files_changed >= thresholds.files_low:
        factors.append(f"{change_state.files_changed} files changed")

    # --- Line count scoring ---
    total_lines = change_state.lines_added + change_state.lines_removed
    line_score = _score_dimension(
        value=total_lines,
        low_threshold=thresholds.lines_low,
        high_threshold=thresholds.lines_high,
    )
    if total_lines >= thresholds.lines_low:
        factors.append(f"~{total_lines} lines changed")

    # --- Combine scores ---
    # Weighted average: files and lines contribute equally to the base score.
    base_score = (file_score * 0.5) + (line_score * 0.5)

    # --- Source-code weight boost ---
    if change_state.has_source_code:
        base_score = min(1.0, base_score * thresholds.source_code_weight)
        factors.append("source code files modified")

    # --- Determine risk level ---
    if base_score >= 0.7:
        level = RiskLevel.HIGH
    elif base_score >= 0.35:
        level = RiskLevel.MEDIUM
    elif base_score > 0.0:
        level = RiskLevel.LOW
    else:
        level = RiskLevel.NONE

    # A reminder is warranted when risk is HIGH.
    is_reminder_worthy = level == RiskLevel.HIGH

    return RiskAssessment(
        level=level,
        score=round(base_score, 4),
        contributing_factors=tuple(factors),
        is_reminder_worthy=is_reminder_worthy,
    )


def _score_dimension(value: int, low_threshold: int, high_threshold: int) -> float:
    """Score a single dimension (e.g., file count) on a 0.0â€“1.0 scale.

    Returns:
        0.0 if value is 0.
        Linear interpolation between 0.0 and 1.0 as value goes from 0 to high_threshold.
        Clamped at 1.0 above high_threshold.
    """
    if value <= 0:
        return 0.0
    if value >= high_threshold:
        return 1.0
    return value / high_threshold
