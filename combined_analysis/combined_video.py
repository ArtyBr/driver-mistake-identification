import cv2
import numpy as np
import argparse
import os
import sys
import pickle
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import re
import torch

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
lane_det_path = os.path.join(project_root, 'lane_detection')

sys.path.append(project_root)
sys.path.append(lane_det_path)

# --- IMPORTS FROM OTHER MODULES ---
try:
    from insightface.app import FaceAnalysis
    from lane_detection.lanedet.tools.detect import Detect, visualize_tracked_lanes
    from helper_classes import LaneTracker
    from lane_detection.lanedet.lanedet.utils.config import Config
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please ensure your 'lane_detection' folder is in the python path.")
    sys.exit(1)

# --- CONFIGURATION ---
CLASS_NAMES = {0: 'Left Mirror', 1: 'Right Mirror', 2: 'Looking Ahead'}

class FaceAnalyzer:
    def __init__(self, models_dir):
        # Initialize InsightFace
        self.app = FaceAnalysis(providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
        self.app.prepare(ctx_id=0, det_size=(640, 640))
        
        # Load Models
        print("Loading Face Analysis Models...")
        self.svm = self._load_model(os.path.join(models_dir, 'svm_head_pose_model.pkl'))
        self.pca = self._load_model(os.path.join(models_dir, 'pca_head_pose_model.pkl'))

    def _load_model(self, path):
        if os.path.exists(path):
            return pickle.load(open(path, 'rb'))
        else:
            print(f"Warning: Model not found at {path}. Face analysis might fail.")
            return None

    def process_frame(self, frame):
        faces = self.app.get(frame)
        analysis_data = None 

        if faces:
            face = faces[0]
            
            if hasattr(face, 'pose') and face.pose is not None:
                pitch, yaw, roll = face.pose
            else:
                pitch, yaw, roll = 0.0, 0.0, 0.0
            
            kps = face.kps.astype(int)
            if len(kps) >= 3:
                nose_2d = tuple(kps[2])
            else:
                bbox = face.bbox.astype(int)
                nose_2d = (int((bbox[0] + bbox[2]) / 2), int((bbox[1] + bbox[3]) / 2))

            svm_label = "N/A"
            svm_conf = 0.0

            if self.svm and self.pca:
                input_data = pd.DataFrame([[yaw, pitch, roll]], columns=['yaw', 'pitch', 'roll'])
                pca_input = self.pca.transform(input_data)
                
                svm_pred_idx = self.svm.predict(pca_input)[0]
                svm_probs = self.svm.predict_proba(pca_input)[0]
                svm_conf = svm_probs[svm_pred_idx]
                svm_label = CLASS_NAMES.get(svm_pred_idx, "Unknown")

            analysis_data = {
                'yaw': int(yaw),
                'pitch': int(pitch),
                'roll': int(roll),
                'label': svm_label,
                'conf': svm_conf
            }

            bbox = face.bbox.astype(int)
            cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)
            
            for kp in kps:
                cv2.circle(frame, tuple(kp), 2, (0, 255, 0), -1)
            
            p1 = nose_2d
            p2 = (int(nose_2d[0] + yaw * 10), int(nose_2d[1] - pitch * 10))
            cv2.line(frame, p1, p2, (255, 0, 0), 3)

        return frame, analysis_data

def draw_fading_text(img, text, pos, font_scale, color, thickness, alpha):
    """
    Draws text with a specific alpha (opacity) onto an image.
    """
    x, y = pos
    (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
    
    # Boundary checks
    if y - h - 5 < 0 or y + 5 > img.shape[0] or x + w > img.shape[1] or x < 0:
        return

    roi = img[y-h-5:y+5, x:x+w]
    text_overlay = roi.copy()
    
    cv2.putText(text_overlay, text, (0, h), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
    cv2.addWeighted(text_overlay, alpha, roi, 1 - alpha, 0, roi)
    img[y-h-5:y+5, x:x+w] = roi

def run_combined_analysis(args, lane_cfg):
    # 1. Setup File Paths
    base_path = args.video_base
    path_road = base_path + "F.mp4"

    # Increment the trailing number for face video
    match = re.search(r'(\d+)$', base_path)
    if match:
        num_str = match.group(1)                # Extract "004616"
        length = len(num_str)                   # Remember the length (6) for padding
        new_num = int(num_str) + 1              # Convert to int and add 1 -> 4617
        new_num_str = str(new_num).zfill(length)# Convert back to string and pad -> "004617"
        
        # Slice off the old number, add the new number, then add the extension
        path_face = base_path[:-length] + new_num_str + "I.mp4"
    else:
        # Fallback if no number is found at the end
        path_face = base_path + "I.mp4"

    if not os.path.exists(path_face) or not os.path.exists(path_road):
        print(f"Error: Could not find both files:\n{path_face}\n{path_road}")
        return

    # 2. Initialize Analyzers
    print("Initializing Lane Detector...")
    lane_detector = Detect(lane_cfg)
    lane_tracker = LaneTracker()

    print("Initializing Face Analyzer...")
    models_path = os.path.join(project_root, 'face_analysis', 'models')
    face_analyzer = FaceAnalyzer(models_path)

    # 3. Open Video Streams
    cap_face = cv2.VideoCapture(path_face)
    cap_road = cv2.VideoCapture(path_road)

    fps = cap_road.get(cv2.CAP_PROP_FPS)
    width = int(cap_road.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap_road.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap_road.get(cv2.CAP_PROP_FRAME_COUNT))

    if args.savedir:
        os.makedirs(args.savedir, exist_ok=True)
        filename = os.path.basename(base_path) + "_combined.mp4"
        out_path = os.path.join(args.savedir, filename)
        
        # CHANGE 1: Use 'avc1' (H.264) instead of 'mp4v' for better compatibility
        # If 'avc1' fails on your specific OS, fall back to 'mp4v'
        try:
            fourcc = cv2.VideoWriter_fourcc(*'avc1')
        except:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            
        out_writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
        print(f"Saving output to: {out_path}")
    else:
        out_writer = None

    # --- STATE HISTORY VARIABLES ---
    state_history = []  # List of dicts: {'state': str, 'timestamp': float}
    last_recorded_state = None
    HISTORY_DURATION = 5.0 # Seconds

    print(f"Processing {total_frames} frames...")
    
    overlay_scale = 0.35
    
    for _ in tqdm(range(total_frames)):
        ret_r, frame_road = cap_road.read()
        ret_f, frame_face = cap_face.read()

        if not ret_r:
            break
        
        if not ret_f:
            frame_face = np.zeros((480, 640, 3), dtype=np.uint8)

        # Get current timestamp in seconds
        current_time = cap_road.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

        # --- PROCESS ROAD ---
        detected_coeffs, ori_road_img = lane_detector.get_lane_detections(frame_road)
        filtered_lane_coeffs = lane_tracker.update(detected_coeffs)
        vis_road = visualize_tracked_lanes(ori_road_img, filtered_lane_coeffs, show=False)

        # --- PROCESS FACE ---
        vis_face, face_info = face_analyzer.process_frame(frame_face)

        # --- UPDATE STATE HISTORY ---
        if face_info and face_info['label'] not in ["N/A", "Unknown"]:
            current_label = face_info['label']
            
            # Logic: 
            # 1. If same as last state, UPDATE the timestamp (keep it alive/fresh)
            # 2. If different, APPEND new state
            if current_label == last_recorded_state and len(state_history) > 0:
                state_history[-1]['timestamp'] = current_time
            elif current_label != last_recorded_state:
                state_history.append({
                    'state': current_label,
                    'timestamp': current_time
                })
                last_recorded_state = current_label
        
        # Prune old states (> 3 seconds)
        state_history = [
            item for item in state_history 
            if (current_time - item['timestamp']) <= HISTORY_DURATION
        ]
        
        # Reset last_state if list becomes empty so we can capture the same state again cleanly if it reappears
        if len(state_history) == 0:
            last_recorded_state = None

        # --- COMBINE FRAMES (Overlay) ---
        h_r, w_r = vis_road.shape[:2]
        h_f, w_f = vis_face.shape[:2]
        
        new_w_f = int(w_r * overlay_scale)
        new_h_f = int(new_w_f * (h_f / w_f))
        
        vis_face_resized = cv2.resize(vis_face, (new_w_f, new_h_f))
        
        margin = 20
        y_offset = margin
        x_offset = w_r - new_w_f - margin
        
        cv2.rectangle(vis_road, (x_offset-2, y_offset-2), 
                      (x_offset+new_w_f+2, y_offset+new_h_f+2), (0,0,0), 2)
        
        vis_road[y_offset:y_offset+new_h_f, x_offset:x_offset+new_w_f] = vis_face_resized

        # --- DRAW TEXT ON MAIN ROAD FRAME ---
        
        # 1. Current real-time info (Top Left)
        if face_info:
            yaw = face_info['yaw']
            pitch = face_info['pitch']
            label = face_info['label']
            roll = face_info['roll']
            conf = face_info['conf']
            color_svm = (0, 255, 0) if conf > 0.7 else (0, 165, 255)

            cv2.putText(vis_road, f"Head Pose: Y:{yaw} P:{pitch} R:{roll}", (30, 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 1)
            cv2.putText(vis_road, f"Current: {label} ({conf:.2f})", (30, 100), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, color_svm, 2)

        # 2. Historical List (Top Middle - Centered)
        history_start_y = 40 # Starting higher up
        
        # Draw Title
        title_text = "State history (last 5s):"
        (t_w, t_h), _ = cv2.getTextSize(title_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        title_x = (w_r // 2) - (t_w // 2) # Center X
        cv2.putText(vis_road, title_text, (title_x, history_start_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        # Draw List items
        # States higher up on list = older (History list is Old -> New)
        # So we draw index 0 at the top, index 1 below it, etc.
        for i, item in enumerate(state_history):
            age = current_time - item['timestamp']
            
            # Alpha calculation
            alpha = max(0, 1.0 - (age / HISTORY_DURATION))
            
            # Display the state and the age
            display_text = f"- {item['state']} ({age:.1f}s ago)"
            
            # Calculate Center position for this specific text
            (txt_w, txt_h), _ = cv2.getTextSize(display_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
            txt_x = (w_r // 2) - (txt_w // 2)
            txt_y = history_start_y + 30 + (i * 30)
            
            draw_fading_text(vis_road, display_text, (txt_x, txt_y), 
                             0.7, (0, 255, 255), 2, alpha)

        # --- OUTPUT ---
        if args.show:
            cv2.imshow('Combined Analysis', vis_road)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        if out_writer:
            out_writer.write(vis_road)

    cap_road.release()
    cap_face.release()
    if out_writer:
        if vis_road.shape[1] != width or vis_road.shape[0] != height:
            vis_road = cv2.resize(vis_road, (width, height))
        
        out_writer.write(vis_road)
    cv2.destroyAllWindows()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Combined Lane and Face Analysis")
    parser.add_argument('config', help='Path to the Lane Detection config file (py file)')
    parser.add_argument('--video_base', required=True, 
                        help='Base path for videos (excluding I.mp4/F.mp4 suffix).')
    parser.add_argument('--savedir', default='./results', help='Directory to save results')
    parser.add_argument('--show', action='store_true', help='Show window during processing')
    parser.add_argument('--load_from', default='best.pth', help='Path to lane model weights')

    args = parser.parse_args()

    cfg = Config.fromfile(args.config)
    cfg.load_from = args.load_from
    cfg.show = False 
    cfg.savedir = None 

    lanedet_dir = os.path.join(project_root, 'lane_detection', 'lanedet')
    
    def fix_anchor_path(heads_cfg):
        if hasattr(heads_cfg, 'anchors_freq_path') and heads_cfg.anchors_freq_path is not None:
            if not os.path.isabs(heads_cfg.anchors_freq_path):
                potential_path = os.path.join(lanedet_dir, heads_cfg.anchors_freq_path)
                if os.path.exists(potential_path):
                    print(f"Redirecting anchor path to: {potential_path}")
                    heads_cfg.anchors_freq_path = potential_path
                else:
                    print(f"Warning: Anchor file not found at {potential_path}")

    if hasattr(cfg, 'heads'):
        fix_anchor_path(cfg.heads)
    if hasattr(cfg, 'net') and hasattr(cfg.net, 'heads'):
        fix_anchor_path(cfg.net.heads)

    run_combined_analysis(args, cfg)