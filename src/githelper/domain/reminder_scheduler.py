"""Reminder Scheduler.

Combines Risk Engine and Time Engine output. Both engines must agree
before a reminder is emitted (Doc 01 Â§3, Doc 07 Â§3.2 transition #8).

Zero dependencies on Git, OS, UI, or Qt.
"""

from __future__ import annotations

from githelper.domain.models import (
    ReminderDecision,
    RiskAssessment,
    RiskLevel,
    TimeDecision,
)


def evaluate(risk: RiskAssessment, time_dec: TimeDecision) -> ReminderDecision:
    """Combine Risk and Time engine outputs to make a final reminder decision.

    Args:
        risk: Output from Risk Engine.
        time_dec: Output from Time Engine.

    Returns:
        A ReminderDecision indicating whether to show a popup and why.
    """
    # Both engines must agree (Doc 01 Â§3).
    should_show = risk.is_reminder_worthy and time_dec.should_remind

    # Generate the human-readable 'why now' reason (Doc 06 Â§4.4).
    # "One short, human-readable sentence stating *why now*. Never technical jargon."
    if should_show:
        factors_str = " Â· ".join(risk.contributing_factors)
        time_str = time_dec.reason.replace("~", "").replace(" of work since last commit", "")
        # e.g., "5 files changed Â· ~2.5 hrs"
        reason_text = f"{factors_str} Â· ~{time_str} of work"
    else:
        # If not showing, the reason is just for debugging/logging, not UI.
        if risk.level == RiskLevel.NONE:
            reason_text = "No meaningful uncommitted work."
        elif not risk.is_reminder_worthy:
            reason_text = f"Risk too low ({risk.level.name})."
        elif not time_dec.should_remind:
            reason_text = f"Time gate blocked: {time_dec.reason}."
        else:
            reason_text = "Not showing."

    return ReminderDecision(
        should_show=should_show,
        reason_text=reason_text,
        risk_assessment=risk,
        time_decision=time_dec,
    )
