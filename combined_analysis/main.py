import sys
from pathlib import Path
import warnings

# Filter specific warnings
warnings.filterwarnings("ignore", category=FutureWarning, message="`rcond` parameter")

# --- PATH SETUP ---
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
LANE_DET_PATH = PROJECT_ROOT / 'lane_detection'
SRC_DIR = CURRENT_DIR / 'src'

# Extend path to include project root, lane_detection submodule, and src
sys.path.extend([str(PROJECT_ROOT), str(LANE_DET_PATH), str(SRC_DIR)])

import torch  # Import torch early to avoid libc10.so/shared library issues
import argparse
import config
from utils import fix_anchor_path
import traceback

# Delayed imports to ensure sys.path is ready
try:
    from lane_detection.lanedet.lanedet.utils.config import Config
    from lane_detector import LaneDetectorWrapper
    from face_analyzer import FaceAnalyzer
    from video_processor import VideoProcessor
except ImportError as e:
    traceback.print_exc()
    sys.exit(f"Error importing modules: {e}\nEnsure 'lane_detection' is in the python path and dependencies are installed.")

def main():
    parser = argparse.ArgumentParser(description="Combined Lane and Face Analysis (Modular)")
    parser.add_argument('config', help='Path to Lane Detection config')
    parser.add_argument('--video_base', required=True, help='Base video path (no I.mp4/F.mp4 suffix)')
    parser.add_argument('--savedir', default=str(CURRENT_DIR / 'data' / 'output'), help='Output directory')
    parser.add_argument('--show', action='store_true', help='Show visualization')
    parser.add_argument('--load_from', default='best.pth', help='Model weights')
    
    parser.add_argument('--start_seconds', type=float, default=0.0,
                         help='Start processing time in seconds (default: 0.0)')
    parser.add_argument('--end_seconds', type=float, default=None,
                         help='End processing time in seconds (default: None = end of video)')
    
    args = parser.parse_args()

    # Load and patch Config
    cfg = Config.fromfile(args.config)
    cfg.load_from = args.load_from
    cfg.show = False 
    cfg.savedir = None 

    lanedet_dir = LANE_DET_PATH / 'lanedet'
    if hasattr(cfg, 'heads'): fix_anchor_path(cfg.heads, lanedet_dir)
    if hasattr(cfg, 'net') and hasattr(cfg.net, 'heads'): fix_anchor_path(cfg.net.heads, lanedet_dir)

    # Initialize Modules
    # We pass the models directory to FaceAnalyzer. 
    # In original code: PROJECT_ROOT / 'face_analysis' / 'models'
    face_analyzer = FaceAnalyzer(PROJECT_ROOT / 'face_analysis' / 'models')
    
    lane_wrapper = LaneDetectorWrapper(cfg)

    # Run Processor
    processor = VideoProcessor(lane_wrapper, face_analyzer, args)
    processor.run()

if __name__ == '__main__':
    main()
