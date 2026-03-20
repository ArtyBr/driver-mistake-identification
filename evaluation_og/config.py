"""Evaluation framework configuration — paths, constants, palettes."""

from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVALUATION_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = EVALUATION_DIR / "output"
GPS_CACHE_PATH = OUTPUT_DIR / "gps_cache.pkl"
PIPELINE_RESULTS_DIR = OUTPUT_DIR / "pipeline_results"
COMBINED_ANALYSIS_DIR = PROJECT_ROOT / "combined_analysis"
RUN_HEADLESS_PATH = COMBINED_ANALYSIS_DIR / "run_headless.py"
UPLOADS_DIR = PROJECT_ROOT / "web_application" / "uploads"

# Default video base — override with --video-base
VIDEO_BASE = Path("/media/arty/3A30-14F9/Videos")

# ── Temporal parameters ────────────────────────────────────────────────────
TEMPORAL_TOLERANCE = 5.0   # seconds tolerance for matching GT ↔ detection
EVENT_WINDOW = 30.0        # seconds before/after each GT event to process
VIDEO_MAX_DURATION = 180.0 # each clip is ~3 minutes

# ── Event type constants ───────────────────────────────────────────────────
GT_EVENT_TYPES = ["left turn", "right turn", "left lane change", "right lane change"]

# System maneuver labels → GT event type mapping
SYSTEM_TO_GT = {
    "lane change (left-to-right)": "right lane change",
    "lane change (right-to-left)": "left lane change",
    "LEFT": "left turn",
    "RIGHT": "right turn",
    "TURN_LEFT": "left turn",
    "TURN_RIGHT": "right turn",
}

# Broad category mapping for coarse matching
GT_TO_CATEGORY = {
    "left turn": "turn",
    "right turn": "turn",
    "left lane change": "lane_change",
    "right lane change": "lane_change",
}

# ── Gaze labels ────────────────────────────────────────────────────────────
GAZE_LABELS = ["Looking Ahead", "Left Mirror", "Right Mirror", "Rear Mirror"]

# ── Color palettes ─────────────────────────────────────────────────────────
EVENT_COLORS = {
    "left turn": "#1f77b4",
    "right turn": "#ff7f0e",
    "left lane change": "#2ca02c",
    "right lane change": "#d62728",
}

SAFETY_COLORS = {
    True: "#2ca02c",   # safe — green
    False: "#d62728",  # unsafe — red
}

GAZE_COLORS = {
    "Looking Ahead": "#1f77b4",
    "Left Mirror": "#ff7f0e",
    "Right Mirror": "#2ca02c",
    "Rear Mirror": "#d62728",
    "Radio": "#9467bd",
    "Speedometer": "#8c564b",
    "Unknown": "#7f7f7f",
}

CONDITION_COLORS = {
    "day": "#f4a460",
    "night": "#4169e1",
    "rainy_day": "#708090",
}
