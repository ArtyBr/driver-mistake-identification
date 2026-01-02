import sys
from pathlib import Path
import logging

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("core.config")

# Path Configuration
# backend/app/core/config.py -> backend/app/core -> backend/app -> backend
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
WEB_APP_DIR = BACKEND_DIR.parent
PROJECT_ROOT = WEB_APP_DIR.parent
UPLOAD_DIR = WEB_APP_DIR / "uploads"
DB_PATH = BACKEND_DIR / "jobs.db"

# Create necessary directories
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Add project paths to sys.path for external module imports
# This is necessary because the analysis scripts are in sibling directories
# and rely on their own internal imports.
PATHS_TO_ADD = [
    str(PROJECT_ROOT),
    str(PROJECT_ROOT / "combined_analysis"),
    str(PROJECT_ROOT / "combined_analysis" / "src"),
    str(PROJECT_ROOT / "lane_detection"), 
    str(PROJECT_ROOT / "lane_detection" / "lanedet"),
]

for p in PATHS_TO_ADD:
    if p not in sys.path:
        sys.path.append(p)
        logger.debug(f"Added path to sys.path: {p}")

# Constants
API_PREFIX = ""
PROJECT_NAME = "Driver Mistake Identification API"
VERSION = "1.0.0"
