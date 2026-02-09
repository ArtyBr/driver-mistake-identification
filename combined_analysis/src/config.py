from pathlib import Path
import cv2

# --- PATH SETUP ---
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
LANE_DET_PATH = PROJECT_ROOT / 'lane_detection'

# --- CONSTANTS ---
CLASS_NAMES = {0: 'Left Mirror', 1: 'Right Mirror', 2: 'Looking Ahead', 3: 'Rear Mirror'}
HISTORY_DURATION = 5.0  # Seconds
OVERLAY_SCALE = 0.35
FONT = cv2.FONT_HERSHEY_SIMPLEX

# --- RESIZING CONSTANTS ---
MODEL_WIDTH = 1640
MODEL_HEIGHT = 590
TARGET_WIDTH = 1920
TARGET_HEIGHT = 1080
