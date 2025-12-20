import cv2
import numpy as np
import config
from tqdm import tqdm
from pathlib import Path
from utils import setup_video_paths, draw_fading_text
import gc
import torch

class VideoProcessor:
    def __init__(self, lane_wrapper, face_analyzer, args):
        self.lane_wrapper = lane_wrapper
        self.face_analyzer = face_analyzer
        self.args = args
        self.state_history = []
        self.last_state = None

    def run(self):
        # 1. Setup
        path_road, path_face = setup_video_paths(self.args.video_base)
        if not Path(path_road).exists() or not Path(path_face).exists():
            print(f"Error: Files not found.\n{path_road}\n{path_face}")
            return

        cap_road = cv2.VideoCapture(path_road)
        cap_face = cv2.VideoCapture(path_face)
        
        if not cap_road.isOpened():
            raise Exception(f"Cannot open road video: {path_road}")
        
        fps = cap_road.get(cv2.CAP_PROP_FPS)
        fps = 30.0 if not (1 < fps <= 120) else fps
        total_frames = int(cap_road.get(cv2.CAP_PROP_FRAME_COUNT))

        # --- START/END TIME LOGIC ---
        start_frame = max(0, int(self.args.start_seconds * fps))
        if self.args.end_seconds is not None:
            end_frame = min(total_frames, int(self.args.end_seconds * fps))
        else:
            end_frame = total_frames

        if start_frame >= end_frame:
            print(f"Error: Start time ({self.args.start_seconds}s) is after or at end time ({self.args.end_seconds}s).")
            cap_road.release()
            cap_face.release()
            return

        # Seek both videos to the start frame
        cap_road.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        cap_face.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        num_frames_to_process = end_frame - start_frame
        
        out_writer = None

        print(f"Processing frames {start_frame} to {end_frame} ({num_frames_to_process} frames) @ {fps} FPS...")

        try:
            for _ in tqdm(range(num_frames_to_process)):
                ret_r, frame_road = cap_road.read()
                ret_f, frame_face = cap_face.read()

                if not ret_r: 
                    break
                if not ret_f: 
                    frame_face = np.zeros((480, 640, 3), dtype=np.uint8)

                current_time = cap_road.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

                # Lane Processing
                vis_road, lane_data = self.lane_wrapper.process_frame(frame_road)

                # Face Processing
                vis_face, face_info = self.face_analyzer.process_frame(frame_face)

                # --- STATE HISTORY ---
                if face_info and face_info['label'] not in ["N/A", "Unknown"]:
                    curr = face_info['label']
                    if curr != self.last_state:
                        self.state_history.append({'state': curr, 'timestamp': current_time})
                        self.last_state = curr
                    elif self.state_history:
                        self.state_history[-1]['timestamp'] = current_time # Update timestamp for duration

                # Prune old history
                self.state_history = [s for s in self.state_history if (current_time - s['timestamp']) <= config.HISTORY_DURATION]
                if not self.state_history: self.last_state = None

                # --- OVERLAY FACE ON ROAD ---
                h_r, w_r = vis_road.shape[:2]
                h_f, w_f = vis_face.shape[:2]
                
                new_w_f = int(w_r * config.OVERLAY_SCALE)
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
                    
                    cv2.putText(vis_road, stats, (30, 60), config.FONT, 0.8, (255, 255, 255), 1)
                    cv2.putText(vis_road, label_txt, (30, 100), config.FONT, 1, color, 2)

                # Draw History
                hist_y = 40
                cv2.putText(vis_road, "State history (last 5s):", ((w_r//2)-100, hist_y), config.FONT, 0.6, (200,200,200), 1)
                
                for i, item in enumerate(self.state_history):
                    age = current_time - item['timestamp']
                    alpha = max(0, 1.0 - (age / config.HISTORY_DURATION))
                    txt = f"- {item['state']} ({age:.1f}s ago)"
                    
                    (tw, th), _ = cv2.getTextSize(txt, config.FONT, 0.7, 2)
                    draw_fading_text(vis_road, txt, ((w_r//2)-(tw//2), hist_y + 30 + (i * 30)), 0.7, (0, 255, 255), 2, alpha)

                if self.args.show:
                    cv2.imshow('Combined Analysis', vis_road)
                    if cv2.waitKey(1) & 0xFF == ord('q'): break

                # --- VIDEO WRITING ---
                if out_writer is None and self.args.savedir:
                    h, w = vis_road.shape[:2]
                    h, w = (h // 2) * 2, (w // 2) * 2
                    
                    Path(self.args.savedir).mkdir(parents=True, exist_ok=True)
                    out_path = str(Path(self.args.savedir) / (Path(self.args.video_base).name + "_combined.mp4"))
                    
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
