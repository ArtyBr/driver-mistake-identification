import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add paths
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

from lane_detector import LaneDetectorWrapper
from utils import fix_anchor_path
from lane_detection.lanedet.lanedet.utils.config import Config

def test_load():
    config_path = project_root / "lane_detection/lanedet/configs/laneatt/resnet18_culane.py"
    weights_path = project_root / "lane_detection/lanedet/weights/laneatt_r18_culane.pth"
    lanedet_dir = project_root / "lane_detection/lanedet"
    
    cfg = Config.fromfile(str(config_path))
    cfg.load_from = str(weights_path)
    cfg.show = False
    cfg.savedir = None
    
    if hasattr(cfg, 'heads'): fix_anchor_path(cfg.heads, lanedet_dir)
    if hasattr(cfg, 'net') and hasattr(cfg.net, 'heads'): fix_anchor_path(cfg.net.heads, lanedet_dir)

    logger.info("Initializing LaneDetectorWrapper...")
    lane_wrapper = LaneDetectorWrapper(cfg)
    logger.info("Done.")

if __name__ == "__main__":
    test_load()
