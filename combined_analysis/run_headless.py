import sys
import os
import argparse
import json
import logging
import traceback
import warnings
from pathlib import Path

# Fix onnxruntime threading errors (must be set before importing insightface/onnxruntime)
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["ORT_THREAD_AFFINITY_POLICY"] = "0"

# Suppress warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=RuntimeWarning, message='.*tarfile.*')

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HeadlessRunner")

# Setup Paths
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
src_dir = current_dir / "src"
lane_det_dir = project_root / "lane_detection"
lanedet_pkg_dir = lane_det_dir / "lanedet"

sys.path.extend([
    str(project_root),
    str(current_dir),
    str(src_dir),
    str(lane_det_dir),
    str(lanedet_pkg_dir)
])

# Import modules
try:
    from src.video_processor import VideoProcessor
    from src.lane_detector import LaneDetectorWrapper
    from src.face_analyzer import FaceAnalyzer
    from src.utils import fix_anchor_path
    from lane_detection.lanedet.lanedet.utils.config import Config
    import src.config as config
except ImportError:
    # Try alternate structure if src is in path directly
    from video_processor import VideoProcessor
    from lane_detector import LaneDetectorWrapper
    from face_analyzer import FaceAnalyzer
    from utils import fix_anchor_path
    from lane_detection.lanedet.lanedet.utils.config import Config
    import config as config

class DummyArgs:
    def __init__(self, savedir, show=False, video_base=None):
        self.savedir = savedir
        self.show = show
        self.video_base = video_base
        self.start_seconds = 0
        self.end_seconds = None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--road", required=True)
    parser.add_argument("--face", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--road_meta", type=str, help="JSON string of road video metadata")
    parser.add_argument("--face_meta", type=str, help="JSON string of face video metadata")
    parser.add_argument("--models_dir", type=str, default=None, help="Path to custom gaze model directory (user calibration)")
    parser.add_argument("--flip_face", action="store_true", help="Horizontally flip the face video (for mirrored selfie cameras)")
    args_cli = parser.parse_args()

    try:
        road_meta = json.loads(args_cli.road_meta) if args_cli.road_meta else None
        face_meta = json.loads(args_cli.face_meta) if args_cli.face_meta else None

        logger.info(f"Starting analysis for:\nRoad: {args_cli.road}\nFace: {args_cli.face}")

        # Config Setup
        config_path = lanedet_pkg_dir / "configs/laneatt/resnet18_culane.py"
        weights_path = lanedet_pkg_dir / "weights/laneatt_r18_culane.pth"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config not found: {config_path}")
        if not weights_path.exists():
            raise FileNotFoundError(f"Weights not found: {weights_path}")

        # Load Config
        cfg = Config.fromfile(str(config_path))
        cfg.load_from = str(weights_path)
        cfg.show = False
        cfg.savedir = None
        
        if hasattr(cfg, 'heads'): fix_anchor_path(cfg.heads, lanedet_pkg_dir)
        if hasattr(cfg, 'net') and hasattr(cfg.net, 'heads'): fix_anchor_path(cfg.net.heads, lanedet_pkg_dir)

        # Initialize Models
        logger.info("Initializing FaceAnalyzer...")
        if args_cli.models_dir:
            face_model_path = Path(args_cli.models_dir)
            logger.info(f"Using custom calibration models from: {face_model_path}")
        else:
            face_model_path = project_root / 'face_analysis' / 'models'
        face_analyzer = FaceAnalyzer(str(face_model_path))
        
        logger.info("Initializing LaneDetectorWrapper...")
        lane_wrapper = LaneDetectorWrapper(cfg)
        
        # Initialize Processor
        output_dir = Path(args_cli.output).parent
        dummy_args = DummyArgs(savedir=str(output_dir), video_base=args_cli.road)
        
        processor = VideoProcessor(lane_wrapper, face_analyzer, dummy_args, flip_face=args_cli.flip_face)
        
        # Run
        custom_paths = {"road": args_cli.road, "face": args_cli.face}
        logger.info("Running processing loop...")
        processor.run(
            export_json=True, 
            output_json_path=args_cli.output, 
            custom_video_paths=custom_paths,
            metadata={"road": road_meta, "face": face_meta}
        )
        
        logger.info("Analysis completed successfully.")

    except Exception as e:
        logger.info(f"Analysis Failed: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
