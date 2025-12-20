import sys
from pathlib import Path
import os

current_dir = Path(__file__).resolve().parent
web_app_dir = current_dir.parent
project_root = web_app_dir.parent

sys.path.extend([
    str(project_root),
    str(project_root / "combined_analysis"),
    str(project_root / "combined_analysis" / "src"),
    str(project_root / "lane_detection"), 
    str(project_root / "lane_detection" / "lanedet"),
])

print("Importing FaceAnalyzer...")
from face_analyzer import FaceAnalyzer
print("Success")
