"""Power listener.

Wraps psutil for cross-platform battery-state polling.
"""

from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class BatteryState:
    """Current battery state."""
    percent: float
    is_plugged: bool
    is_critical: bool


def get_battery_state() -> BatteryState | None:
    """Get the current battery state if a battery is present.
    
    Returns None if the system has no battery (e.g., desktop PC).
    """
    try:
        battery = psutil.sensors_battery()
    except Exception:
        # Fallback if psutil fails on some strange hardware
        return None
        
    if battery is None:
        return None
        
    # We define 'critical' as under 20% and not plugged in (Doc 02 PERF-003).
    is_critical = battery.percent < 20.0 and not battery.power_plugged
    
    return BatteryState(
        percent=battery.percent,
        is_plugged=battery.power_plugged,
        is_critical=is_critical
    )
