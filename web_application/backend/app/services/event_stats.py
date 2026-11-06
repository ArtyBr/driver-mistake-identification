"""
Shared utilities for parsing and aggregating safety event data from results.json.

Event message formats (from safety_monitor.py):
  Lane changes: "SAFE: Right Mirror checked before lane change (left-to-right)."
                "UNSAFE: No Left Mirror check before lane change (right-to-left)!"
  Turns:        "SAFE: Left Mirror checked before LEFT TURN."
                "UNSAFE: No Right Mirror check before RIGHT TURN!"
"""
import re
import json
from pathlib import Path
from typing import Optional, Dict, Any


def _extract_direction(message: str, event_type: str) -> Optional[str]:
    """Return 'left' or 'right' for a safety event based on its message text."""
    msg = message.lower()
    if event_type == 'safety_alert':
        if 'left-to-right' in msg:
            return 'right'   # car moved right
        if 'right-to-left' in msg:
            return 'left'    # car moved left
    elif event_type == 'turn_event':
        # direction string is after "before " in the message
        m = re.search(r'before (.+?)[.!]', msg)
        if m:
            label = m.group(1)
            if 'left' in label:
                return 'left'
            if 'right' in label:
                return 'right'
    return None


def _dir_bucket() -> Dict:
    return {'total': 0, 'safe': 0, 'unsafe': 0, 'pct_safe': None}


def _tally_type(events: list, event_type: str) -> Dict:
    """Build rich stats for one event type (turn_event or safety_alert)."""
    subset = [e for e in events if e.get('type') == event_type]
    result: Dict[str, Any] = {
        'total': len(subset),
        'safe': 0,
        'unsafe': 0,
        'pct_safe': None,
        'left': _dir_bucket(),
        'right': _dir_bucket(),
    }
    for e in subset:
        is_safe = e.get('severity') != 'CRITICAL'
        if is_safe:
            result['safe'] += 1
        else:
            result['unsafe'] += 1
        d = _extract_direction(e.get('message', ''), event_type)
        if d in ('left', 'right'):
            result[d]['total'] += 1
            if is_safe:
                result[d]['safe'] += 1
            else:
                result[d]['unsafe'] += 1

    if result['total'] > 0:
        result['pct_safe'] = round(result['safe'] / result['total'] * 100, 1)
    for d in ('left', 'right'):
        if result[d]['total'] > 0:
            result[d]['pct_safe'] = round(result[d]['safe'] / result[d]['total'] * 100, 1)
    return result


def compute_event_stats(timeline_events: list) -> Dict[str, Any]:
    """Convert a raw timeline_events list into rich structured stats."""
    return {
        'total_events': len(timeline_events),
        'turns': _tally_type(timeline_events, 'turn_event'),
        'lane_changes': _tally_type(timeline_events, 'safety_alert'),
    }


def read_event_stats(results_json_path: Path) -> Optional[Dict[str, Any]]:
    """Read results.json at the given path and return event stats, or None on error."""
    try:
        with open(results_json_path) as f:
            data = json.load(f)
        return compute_event_stats(data.get('timeline_events', []))
    except Exception:
        return None
