import argparse
import gc
import os
import pickle
import re
import sys
import warnings
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import torch
from tqdm import tqdm

# Filter specific warnings
warnings.filterwarnings("ignore", category=FutureWarning, message="`rcond` parameter")

# --- PATH SETUP ---
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
LANE_DET_PATH = PROJECT_ROOT / 'lane_detection'

sys.path.extend([str(PROJECT_ROOT), str(LANE_DET_PATH)])

# --- MODULE IMPORTS ---
try:
    from insightface.app import FaceAnalysis
    from lane_detection.lanedet.tools.detect import Detect, visualize_tracked_lanes
    from lane_detection.lanedet.lanedet.utils.config import Config
    from helper_classes import LaneTracker
except ImportError as e:
    sys.exit(f"Error importing modules: {e}\nEnsure 'lane_detection' is in the python path.")

# --- CONSTANTS ---
CLASS_NAMES = {0: 'Left Mirror', 1: 'Right Mirror', 2: 'Looking Ahead'}
HISTORY_DURATION = 5.0  # Seconds
OVERLAY_SCALE = 0.35
FONT = cv2.FONT_HERSHEY_SIMPLEX

# --- RESIZING CONSTANTS ---
MODEL_WIDTH = 1640
MODEL_HEIGHT = 590
TARGET_WIDTH = 1920
TARGET_HEIGHT = 1080


class FaceAnalyzer:
    def __init__(self, models_dir: Path):
        self.app = FaceAnalysis(providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
        self.app.prepare(ctx_id=0, det_size=(640, 640))
        
        print("Loading Face Analysis Models...")
        self.svm = self._load_model(models_dir / 'svm_head_pose_model.pkl')
        self.pca = self._load_model(models_dir / 'pca_head_pose_model.pkl')

    @staticmethod
    def _load_model(path: Path):
        if path.exists():
            with open(path, 'rb') as f:
                return pickle.load(f)
        print(f"Warning: Model not found at {path}")
        return None

    def process_frame(self, frame):
        faces = self.app.get(frame)
        if not faces:
            return frame, None

        face = faces[0]
        pitch, yaw, roll = face.pose if hasattr(face, 'pose') and face.pose is not None else (0.0, 0.0, 0.0)
        
        # Keypoints processing
        kps = face.kps.astype(int)
        if len(kps) >= 3:
            nose_2d = tuple(kps[2])
        else:
            bbox = face.bbox.astype(int)
            nose_2d = ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)

        # Classification
        svm_label, svm_conf = "N/A", 0.0
        if self.svm and self.pca:
            input_data = pd.DataFrame([[yaw, pitch, roll]], columns=['yaw', 'pitch', 'roll'])
            pca_input = self.pca.transform(input_data)
            svm_pred_idx = self.svm.predict(pca_input)[0]
            svm_probs = self.svm.predict_proba(pca_input)[0]
            svm_conf = svm_probs[svm_pred_idx]
            svm_label = CLASS_NAMES.get(svm_pred_idx, "Unknown")

        analysis_data = {
            'yaw': int(yaw), 'pitch': int(pitch), 'roll': int(roll),
            'label': svm_label, 'conf': svm_conf
        }

        # Visualization
        bbox = face.bbox.astype(int)
        cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)
        for kp in kps:
            cv2.circle(frame, tuple(kp), 2, (0, 255, 0), -1)
        
        p2 = (int(nose_2d[0] + yaw * 10), int(nose_2d[1] - pitch * 10))
        cv2.line(frame, nose_2d, p2, (255, 0, 0), 3)

        return frame, analysis_data


def draw_fading_text(img, text, pos, font_scale, color, thickness, alpha):
    x, y = pos
    (w, h), _ = cv2.getTextSize(text, FONT, font_scale, thickness)
    
    # Boundary checks
    if y - h - 5 < 0 or y + 5 > img.shape[0] or x + w > img.shape[1] or x < 0:
        return

    roi = img[y-h-5:y+5, x:x+w]
    overlay = roi.copy()
    cv2.putText(overlay, text, (0, h), FONT, font_scale, color, thickness)
    cv2.addWeighted(overlay, alpha, roi, 1 - alpha, 0, roi)
    img[y-h-5:y+5, x:x+w] = roi


def setup_video_paths(base_path_str):
    """Determines the paths for road (F) and face (I) videos."""
    path_road = base_path_str + "F.mp4"
    
    # Logic to increment trailing number for the face video
    match = re.search(r'(\d+)$', base_path_str)
    if match:
        num_str = match.group(1)
        new_num_str = str(int(num_str) + 1).zfill(len(num_str))
        path_face = base_path_str[:-len(num_str)] + new_num_str + "I.mp4"
    else:
        path_face = base_path_str + "I.mp4"
        
    return path_road, path_face


def fix_anchor_path(heads_cfg, lanedet_dir):
    """Corrects relative paths in the lane detection config."""
    if hasattr(heads_cfg, 'anchors_freq_path') and heads_cfg.anchors_freq_path:
        if not os.path.isabs(heads_cfg.anchors_freq_path):
            potential = os.path.join(lanedet_dir, heads_cfg.anchors_freq_path)
            if os.path.exists(potential):
                heads_cfg.anchors_freq_path = potential


def scale_lane_coeffs(tracks, src_w, src_h, dst_w, dst_h):
    """
    Scales polynomial coefficients from source resolution to destination resolution.
    Equation: x = ay^2 + by + c
    """
    sx = dst_w / src_w
    sy = dst_h / src_h
    
    scaled_tracks = []
    
    for track in tracks:
        # Unpack the tuple from LaneTracker.update
        # (t.coeffs, t.id, t.confidence, t.age, t.lane_change_events)
        coeffs, t_id, conf, age, events = track
        a, b, c = coeffs

        # Mathematical Derivation for scaling:
        # x' = x * sx
        # y' = y * sy  => y = y' / sy
        # x' = sx * (a * (y'/sy)^2 + b * (y'/sy) + c)
        # x' = (a * sx / sy^2) * y'^2 + (b * sx / sy) * y' + (c * sx)

        new_a = a * sx / (sy ** 2)
        new_b = b * sx / sy
        new_c = c * sx
        
        scaled_coeffs = np.array([new_a, new_b, new_c])
        scaled_tracks.append((scaled_coeffs, t_id, conf, age, events))
        
    return scaled_tracks


def run_combined_analysis(args, lane_cfg):
    # 1. Setup
    path_road, path_face = setup_video_paths(args.video_base)
    if not os.path.exists(path_road) or not os.path.exists(path_face):
        return print(f"Error: Files not found.\n{path_road}\n{path_face}")

    lane_detector = Detect(lane_cfg)
    
    # Initialize tracker with MODEL resolution (this is where detection happens)
    lane_tracker = LaneTracker(img_height=MODEL_HEIGHT, img_width=MODEL_WIDTH)
    
    face_analyzer = FaceAnalyzer(PROJECT_ROOT / 'face_analysis' / 'models')

    cap_road = cv2.VideoCapture(path_road)
    cap_face = cv2.VideoCapture(path_face)
    
    fps = cap_road.get(cv2.CAP_PROP_FPS)
    fps = 30.0 if not (1 < fps <= 120) else fps
    total_frames = int(cap_road.get(cv2.CAP_PROP_FRAME_COUNT))

    out_writer = None
    state_history = []
    last_state = None

    print(f"Processing {total_frames} frames @ {fps} FPS...")

    try:
        for _ in tqdm(range(total_frames)):
            ret_r, frame_road = cap_road.read()
            print(f"Frame shape: {frame_road.shape}")  # Debugging line
            ret_f, frame_face = cap_face.read()

            if not ret_r: 
                break
            if not ret_f: 
                frame_face = np.zeros((480, 640, 3), dtype=np.uint8)

            current_time = cap_road.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

            # --- PROCESS LANE DETECTION (ON MODEL RESOLUTION) ---
            # coeffs are returned in 1640x590 space
            coeffs, _ = lane_detector.get_lane_detections(frame_road)
            
            # Update tracker (tracker runs in 1640x590 space)
            filtered_coeffs = lane_tracker.update(coeffs)

            # --- RESIZE VIDEO ---
            # Resize the base video frame to 1920x1080 *before* overlaying lanes
            vis_road = frame_road

            # --- SCALE TRACKS ---
            # Transform coefficients to match 1920x1080 coordinate system
            scaled_tracks = scale_lane_coeffs(
                filtered_coeffs, 
                src_w=MODEL_WIDTH, src_h=MODEL_HEIGHT, 
                dst_w=TARGET_WIDTH, dst_h=TARGET_HEIGHT
            )

            # --- OVERLAY LANES ---
            # Now apply visualization on the large 1920x1080 image
            vis_road = visualize_tracked_lanes(vis_road, scaled_tracks, show=False)
            
            # Process Face
            vis_face, face_info = face_analyzer.process_frame(frame_face)

            # --- STATE HISTORY ---
            if face_info and face_info['label'] not in ["N/A", "Unknown"]:
                curr = face_info['label']
                if curr != last_state:
                    state_history.append({'state': curr, 'timestamp': current_time})
                    last_state = curr
                elif state_history:
                    state_history[-1]['timestamp'] = current_time # Update timestamp for duration

            # Prune old history
            state_history = [s for s in state_history if (current_time - s['timestamp']) <= HISTORY_DURATION]
            if not state_history: last_state = None

            # --- OVERLAY FACE ON ROAD ---
            h_r, w_r = vis_road.shape[:2] # This is now 1080, 1920
            h_f, w_f = vis_face.shape[:2]
            
            new_w_f = int(w_r * OVERLAY_SCALE)
            new_h_f = int(new_w_f * (h_f / w_f))
            vis_face_resized = cv2.resize(vis_face, (new_w_f, new_h_f))
            
            margin = 20
            x_off = w_r - new_w_f - margin
            y_off = margin
            
            # Border and Overlay
            cv2.rectangle(vis_road, (x_off-2, y_off-2), (x_off+new_w_f+2, y_off+new_h_f+2), (0,0,0), 2)
            vis_road[y_off:y_off+new_h_f, x_off:x_off+new_w_f] = vis_face_resized

            # --- TEXT OVERLAYS ---
            if face_info:
                color = (0, 255, 0) if face_info['conf'] > 0.7 else (0, 165, 255)
                stats = f"Head Pose: Y:{face_info['yaw']} P:{face_info['pitch']} R:{face_info['roll']}"
                label_txt = f"Current: {face_info['label']} ({face_info['conf']:.2f})"
                
                cv2.putText(vis_road, stats, (30, 60), FONT, 0.8, (255, 255, 255), 1)
                cv2.putText(vis_road, label_txt, (30, 100), FONT, 1, color, 2)

            # Draw History
            hist_y = 40
            cv2.putText(vis_road, "State history (last 5s):", ((w_r//2)-100, hist_y), FONT, 0.6, (200,200,200), 1)
            
            for i, item in enumerate(state_history):
                age = current_time - item['timestamp']
                alpha = max(0, 1.0 - (age / HISTORY_DURATION))
                txt = f"- {item['state']} ({age:.1f}s ago)"
                
                (tw, th), _ = cv2.getTextSize(txt, FONT, 0.7, 2)
                draw_fading_text(vis_road, txt, ((w_r//2)-(tw//2), hist_y + 30 + (i * 30)), 0.7, (0, 255, 255), 2, alpha)

            if args.show:
                cv2.imshow('Combined Analysis', vis_road)
                if cv2.waitKey(1) & 0xFF == ord('q'): break

            # --- VIDEO WRITING ---
            if out_writer is None and args.savedir:
                h, w = vis_road.shape[:2]
                # Adjust dimensions to be even for codec compatibility
                h, w = (h // 2) * 2, (w // 2) * 2
                
                Path(args.savedir).mkdir(parents=True, exist_ok=True)
                out_path = str(Path(args.savedir) / (Path(args.video_base).name + "_combined.mp4"))
                
                # Try codecs in order
                for codec in ['mp4v', 'avc1', 'XVID']:
                    out_writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*codec), fps, (w, h))
                    if out_writer.isOpened():
                        print(f"Recording to {out_path} using {codec}")
                        break

            if out_writer and out_writer.isOpened():
                out_writer.write(cv2.resize(vis_road, (w, h)))

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback; traceback.print_exc()
    finally:
        cap_road.release()
        cap_face.release()
        if out_writer: out_writer.release()
        cv2.destroyAllWindows()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Combined Lane and Face Analysis")
    parser.add_argument('config', help='Path to Lane Detection config')
    parser.add_argument('--video_base', required=True, help='Base video path (no I.mp4/F.mp4 suffix)')
    parser.add_argument('--savedir', default='./results', help='Output directory')
    parser.add_argument('--show', action='store_true', help='Show visualization')
    parser.add_argument('--load_from', default='best.pth', help='Model weights')
    
    args = parser.parse_args()

    # Load and patch Config
    cfg = Config.fromfile(args.config)
    cfg.load_from = args.load_from
    cfg.show = False 
    cfg.savedir = None 

    lanedet_dir = LANE_DET_PATH / 'lanedet'
    if hasattr(cfg, 'heads'): fix_anchor_path(cfg.heads, lanedet_dir)
    if hasattr(cfg, 'net') and hasattr(cfg.net, 'heads'): fix_anchor_path(cfg.net.heads, lanedet_dir)

    run_combined_analysis(args, cfg)