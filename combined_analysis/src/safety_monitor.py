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
        # 1. Determine required check based on direction
        # direction comes from LaneTracker: "left-to-right" or "right-to-left"
        required_check = None
        maneuver_desc = "Lane Change"
        
        if direction == "left-to-right":
            required_check = "Right Mirror"
            maneuver_desc = "Right Lane Change"
        elif direction == "right-to-left":
            required_check = "Left Mirror"
            maneuver_desc = "Left Lane Change"
        
        if not required_check:
            return SafetyEvent(current_time, f"Unknown Lane Change: {direction}", False, "lane_change", "INFO")

        # 2. Check history
        # We look for the specific mirror check within the last HISTORY_DURATION (or specifically 5s as requested)
        # config.HISTORY_DURATION is 5.0
        
        found_check = False
        last_check_time = 0.0
        
        for state in reversed(state_history):
            # state is {'state': str, 'timestamp': float}
            # The history is already pruned to 5s in VideoProcessor, but let's be safe
            if (current_time - state['timestamp']) > 5.0:
                continue
            
            if state['state'] == required_check:
                found_check = True
                last_check_time = state['timestamp']
                break
        
        # 3. Formulate Result
        if found_check:
            return SafetyEvent(
                timestamp=current_time,
                message=f"SAFE: {required_check} checked before {maneuver_desc}.",
                is_safe=True,
                maneuver_type="lane_change",
                severity="INFO"
            )
        else:
            return SafetyEvent(
                timestamp=current_time,
                message=f"UNSAFE: No {required_check} check detected during {maneuver_desc}!",
                is_safe=False,
                maneuver_type="lane_change",
                severity="CRITICAL"
            )

    def prune_alerts(self, current_time: float, duration: float = 3.0):
        """Removes alerts older than 'duration' seconds."""
        self.active_alerts = [a for a in self.active_alerts if (current_time - a.timestamp) < duration]
