import sys
from pathlib import Path
import os

current_dir = Path(__file__).resolve().parent
web_app_dir = current_dir.parent
project_root = web_app_dir.parent

print(f"Project Root: {project_root}")
print(f"Exists: {project_root.exists()}")

sys.path.append(str(project_root))

try:
    import lane_detection
    print("Success: import lane_detection")
except ImportError as e:
    print(f"Fail: import lane_detection: {e}")

try:
    import lane_detection.lanedet.tools.detect
    print("Success: import lane_detection.lanedet.tools.detect")
except ImportError as e:
    print(f"Fail: import lane_detection.lanedet.tools.detect: {e}")

sys.path.append(str(project_root / "lane_detection"))
try:
    import lanedet
    print("Success: import lanedet")
except ImportError as e:
    print(f"Fail: import lanedet: {e}")
