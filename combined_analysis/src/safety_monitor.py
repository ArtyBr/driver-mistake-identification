from dataclasses import dataclass
import time
from typing import List, Dict, Optional
import config

@dataclass
class SafetyEvent:
    timestamp: float
    message: str
    is_safe: bool
    maneuver_type: str
    severity: str  # "INFO", "WARNING", "CRITICAL"

class ManeuverValidator:
    def __init__(self):
        self.active_alerts = []
        # Debounce/Cooldown logic could go here if needed
        
    def validate_lane_change(self, direction: str, current_time: float, state_history: List[Dict]) -> SafetyEvent:
        """
        Validates a lane change against the driver's gaze history.
        """
        required_check = "Right Mirror" if direction == "left-to-right" else "Left Mirror"
        return self._validate_maneuver(required_check, f"lane change ({direction})", "lane_change", current_time, state_history)

    def validate_turn(self, direction: str, current_time: float, state_history: List[Dict]) -> SafetyEvent:
        """
        Validates a turn (from VO) against the driver's gaze history.
        """
        required_check = "Left Mirror" if "LEFT" in direction else "Right Mirror"
        return self._validate_maneuver(required_check, direction, "turn", current_time, state_history)

    def _validate_maneuver(self, required_check: str, maneuver_label: str, maneuver_type: str, current_time: float, state_history: List[Dict]) -> SafetyEvent:
        found_side = False
        found_rear = False
        for state in reversed(state_history):
            if (current_time - state['timestamp']) > 5.0:
                continue
            if state['state'] == required_check:
                found_side = True
            if state['state'] == "Rear Mirror":
                found_rear = True
        
        if found_side:
            mirror_msg = f"{required_check}"
            if found_rear: mirror_msg = f"Rear and {required_check}"
            return SafetyEvent(
                timestamp=current_time,
                message=f"SAFE: {mirror_msg} checked before {maneuver_label}.",
                is_safe=True,
                maneuver_type=maneuver_type,
                severity="INFO"
            )
        else:
            rear_note = " (Rear mirror look was detected)" if found_rear else ""
            return SafetyEvent(
                timestamp=current_time,
                message=f"UNSAFE: No {required_check} check before {maneuver_label}!{rear_note}",
                is_safe=False,
                maneuver_type=maneuver_type,
                severity="CRITICAL"
            )

    def prune_alerts(self, current_time: float, duration: float = 3.0):
        """Removes alerts older than 'duration' seconds."""
        self.active_alerts = [a for a in self.active_alerts if (current_time - a.timestamp) < duration]
