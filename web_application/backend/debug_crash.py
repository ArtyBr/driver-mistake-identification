import sys
import os
import logging
import traceback
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

logger.info(f"Sys Path setup complete.")

def test_full_load():
    try:
        logger.info("Importing modules...")
        
        # Simulate lazy imports
        # from video_processor import VideoProcessor
        from lane_detector import LaneDetectorWrapper
        # from face_analyzer import FaceAnalyzer
        from utils import fix_anchor_path
        from lane_detection.lanedet.lanedet.utils.config import Config
        import config as config

        logger.info("Modules imported.")

        # Configuration
        config_path = project_root / "lane_detection/lanedet/configs/laneatt/resnet18_culane.py"
        weights_path = project_root / "lane_detection/lanedet/weights/laneatt_r18_culane.pth"
        lanedet_dir = project_root / "lane_detection/lanedet"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config not found: {config_path}")

        logger.info("Loading Config...")
        cfg = Config.fromfile(str(config_path))
        cfg.load_from = str(weights_path)
        cfg.show = False
        cfg.savedir = None
        
        if hasattr(cfg, 'heads'): fix_anchor_path(cfg.heads, lanedet_dir)
        if hasattr(cfg, 'net') and hasattr(cfg.net, 'heads'): fix_anchor_path(cfg.net.heads, lanedet_dir)

        # logger.info("Initializing FaceAnalyzer...")
        # face_model_path = project_root / 'face_analysis' / 'models'
        # face_analyzer = FaceAnalyzer(str(face_model_path))
        
        logger.info("Initializing LaneDetectorWrapper...")
        lane_wrapper = LaneDetectorWrapper(cfg)
        
        logger.info("Success! All models loaded and initialized.")

    except Exception as e:
        logger.error(f"Crash detected: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_full_load()
