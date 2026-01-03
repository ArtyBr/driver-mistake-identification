import cv2
import numpy as np
import config
import json
from tqdm import tqdm
from pathlib import Path
from utils import setup_video_paths, scale_lane_coeffs
from visualization import VideoVisualizer
from safety_monitor import ManeuverValidator
from vehicle_detector import VehicleDetector
import gc
import torch

class VideoProcessor:
    def __init__(self, lane_wrapper, face_analyzer, args):
        self.lane_wrapper = lane_wrapper
        self.face_analyzer = face_analyzer
        self.args = args
        self.visualizer = VideoVisualizer()
        self.safety_monitor = ManeuverValidator()
        self.vehicle_detector = VehicleDetector()
        
        self.state_history = []
        self.last_state = None
        self.all_events = []
        
        # Optimization: Frame Skipping
        self.frame_count = 0
        self.skip_rate = 3
        self.last_vehicles = []
        self.last_lane_vis = None
        self.last_lane_data = []
        self.last_cross_events = []

    def run(self, export_json=False, output_json_path=None, custom_video_paths=None, metadata=None):
        # 1. Setup Video Capture
        if custom_video_paths:
             cap_road, cap_face, start_frame, end_frame, fps = self._setup_custom_video_capture(custom_video_paths)
        else:
             cap_road, cap_face, start_frame, end_frame, fps = self._setup_video_capture()

        if not cap_road: return

        # 2. Setup Video Writer (only if not exporting JSON or if we want both)
        out_writer = None
        w, h = 0, 0
        if not export_json and self.args.savedir:
             out_writer, w, h = self._setup_video_writer(cap_road, fps)

        num_frames = end_frame - start_frame
        print(f"Processing frames {start_frame} to {end_frame} ({num_frames} frames) @ {fps} FPS...")

        # Data collection containers
        timeline_events = []
        frame_data = []

        try:
            for _ in tqdm(range(num_frames), mininterval=2.0):
                # 3. Read Frames
                ret_r, frame_road = cap_road.read()
                ret_f, frame_face = cap_face.read()

                if not ret_r: break
                if not ret_f: frame_face = np.zeros((480, 640, 3), dtype=np.uint8)

                current_time = cap_road.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

                if export_json:
                    # Headless processing
                    frame_info = self._process_single_frame_headless(frame_road, frame_face, current_time)
                    frame_data.append(frame_info)
                else:
                    # 4. Process Frame (Visual)
                    vis_road = self._process_single_frame(frame_road, frame_face, current_time)

                    # 5. Display & Write
                    if self.args.show:
                        cv2.imshow('Combined Analysis', vis_road)
                        if cv2.waitKey(1) & 0xFF == ord('q'): break

                    if out_writer and out_writer.isOpened():
                        out_writer.write(cv2.resize(vis_road, (w, h)))
            
            if export_json:
                # Compile final JSON
                final_events = []
                for alert in self.all_events:
                    final_events.append({
                        "timestamp": alert.timestamp,
                        "type": "safety_alert",
                        "severity": alert.severity,
                        "message": alert.message,
                        "duration": 2.0
                    })
                
                result = {
                    "meta": {
                        "duration": num_frames / fps,
                        "fps": fps,
                        "road_file": Path(custom_video_paths.get('road')).name if custom_video_paths else "unknown",
                        "face_file": Path(custom_video_paths.get('face')).name if custom_video_paths else "unknown",
                        "road_metadata": metadata.get('road') if metadata else None,
                        "face_metadata": metadata.get('face') if metadata else None
                    },
                    "timeline_events": final_events,
                    "frame_data": frame_data
                }
                
                if output_json_path:
                    with open(output_json_path, 'w') as f:
                        json.dump(result, f)
                return result

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

    def _setup_video_capture(self):
        path_road, path_face = setup_video_paths(self.args.video_base)
        if not Path(path_road).exists() or not Path(path_face).exists():
            print(f"Error: Files not found.\n{path_road}\n{path_face}")
            return None, None, 0, 0, 0

        cap_road = cv2.VideoCapture(path_road)
        cap_face = cv2.VideoCapture(path_face)
        
        if not cap_road.isOpened():
            raise Exception(f"Cannot open road video: {path_road}")
        
        fps = cap_road.get(cv2.CAP_PROP_FPS)
        fps = 30.0 if not (1 < fps <= 120) else fps
        total_frames = int(cap_road.get(cv2.CAP_PROP_FRAME_COUNT))

        start_frame = max(0, int(self.args.start_seconds * fps))
        if self.args.end_seconds is not None:
            end_frame = min(total_frames, int(self.args.end_seconds * fps))
        else:
            end_frame = total_frames

        if start_frame >= end_frame:
            print(f"Error: Start time ({self.args.start_seconds}s) is after or at end time ({self.args.end_seconds}s).")
            cap_road.release()
            cap_face.release()
            return None, None, 0, 0, 0

        cap_road.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        cap_face.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        return cap_road, cap_face, start_frame, end_frame, fps

    def _setup_video_writer(self, cap_road, fps):
        if not self.args.savedir:
            return None, 0, 0

        # Determine output size based on config or frame size
        # Assuming TARGET_WIDTH/HEIGHT from config if available, else standard
        w = config.TARGET_WIDTH if hasattr(config, 'TARGET_WIDTH') else 1920
        h = config.TARGET_HEIGHT if hasattr(config, 'TARGET_HEIGHT') else 1080
        
        # Ensure divisible by 2 for some codecs
        w, h = (w // 2) * 2, (h // 2) * 2

        Path(self.args.savedir).mkdir(parents=True, exist_ok=True)
        out_path = str(Path(self.args.savedir) / (Path(self.args.video_base).name + "_combined.mp4"))
        
        out_writer = None
        for codec in ['mp4v', 'avc1', 'XVID']:
            out_writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*codec), fps, (w, h))
            if out_writer.isOpened():
                print(f"Recording to {out_path} using {codec}")
                break
        
        return out_writer, w, h

    def _process_single_frame(self, frame_road, frame_face, current_time):
        # Lane Processing (Run every frame for smooth tracking)
        vis_road, lane_data, cross_events = self.lane_wrapper.process_frame(frame_road)

        # Vehicle Detection (Run every N frames)
        if self.frame_count % self.skip_rate == 0:
            vehicles = self.vehicle_detector.detect(frame_road)
            self.last_vehicles = vehicles
        else:
            vehicles = self.last_vehicles

        self.visualizer.draw_vehicle_distance(vis_road, vehicles)
        
        # Increment counter
        self.frame_count += 1

        # Face Processing
        frame_face, face_info = self.face_analyzer.process_frame(frame_face)
        
        # Draw analysis on the face frame
        vis_face = self.visualizer.visualize_face_analysis(frame_face.copy(), face_info)

        # Update History
        self._update_history(face_info, current_time)

        # --- SAFETY CHECKS ---
        # 1. Prune old alerts
        self.safety_monitor.prune_alerts(current_time)
        
        # 2. Check for new events
        if cross_events:
            for event in cross_events:
                # event is a dict: {'track_id': ..., 'direction': ..., 'age': ..., 'confidence': ...}
                direction = event.get('direction')
                if direction:
                    result = self.safety_monitor.validate_lane_change(direction, current_time, self.state_history)
                    if result:
                        self.safety_monitor.active_alerts.append(result)
                        self.all_events.append(result)
                        print(f"[{current_time:.2f}s] {result.message}")

        # Visualization Composition
        # 1. Overlay Face Video
        self.visualizer.draw_face_overlay(vis_road, vis_face)
        
        # 2. Draw Status Panel
        self.visualizer.draw_status_panel(vis_road, face_info)
        
        # 3. Draw History Panel
        self.visualizer.draw_history_panel(vis_road, self.state_history, current_time)
        
        # 4. Draw Safety Alerts
        self.visualizer.draw_safety_alerts(vis_road, self.safety_monitor.active_alerts)

        return vis_road

    def _update_history(self, face_info, current_time):
        if face_info and face_info['label'] not in ["N/A", "Unknown"]:
            curr = face_info['label']
            if curr != self.last_state:
                self.state_history.append({'state': curr, 'timestamp': current_time})
                self.last_state = curr
            elif self.state_history:
                self.state_history[-1]['timestamp'] = current_time 
        
        # Prune
        self.state_history = [s for s in self.state_history if (current_time - s['timestamp']) <= config.HISTORY_DURATION]
        if not self.state_history: self.last_state = None

    def _setup_custom_video_capture(self, custom_video_paths):
        path_road = custom_video_paths.get('road')
        path_face = custom_video_paths.get('face')
        
        cap_road = cv2.VideoCapture(path_road)
        cap_face = cv2.VideoCapture(path_face)
        
        if not cap_road.isOpened():
            raise Exception(f"Cannot open road video: {path_road}")
        
        fps = cap_road.get(cv2.CAP_PROP_FPS)
        fps = 30.0 if not (1 < fps <= 120) else fps
        total_frames = int(cap_road.get(cv2.CAP_PROP_FRAME_COUNT))

        start_frame = max(0, int(self.args.start_seconds * fps))
        if self.args.end_seconds is not None:
            end_frame = min(total_frames, int(self.args.end_seconds * fps))
        else:
            end_frame = total_frames

        cap_road.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        cap_face.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        return cap_road, cap_face, start_frame, end_frame, fps

    def _process_single_frame_headless(self, frame_road, frame_face, current_time):
        # Lane Processing
        vis_road, lane_data, cross_events = self.lane_wrapper.process_frame(frame_road)

        # Vehicle Detection (Run every N frames)
        if self.frame_count % self.skip_rate == 0:
            vehicles = self.vehicle_detector.detect(frame_road)
            self.last_vehicles = vehicles
        else:
            vehicles = self.last_vehicles
            
        self.frame_count += 1

        # Face Processing
        frame_face, face_info = self.face_analyzer.process_frame(frame_face)
        
        # Update History
        self._update_history(face_info, current_time)

        # --- SAFETY CHECKS ---
        self.safety_monitor.prune_alerts(current_time)
        
        if cross_events:
            for event in cross_events:
                direction = event.get('direction')
                if direction:
                    result = self.safety_monitor.validate_lane_change(direction, current_time, self.state_history)
                    if result:
                        self.safety_monitor.active_alerts.append(result)
                        self.all_events.append(result)
        
        # Serialize Lane Data (Coefficients only)
        serialized_lanes = []
        if lane_data:
            # Scale to target resolution
            scaled_lanes = scale_lane_coeffs(
                lane_data, 
                src_w=config.MODEL_WIDTH, src_h=config.MODEL_HEIGHT,
                dst_w=config.TARGET_WIDTH, dst_h=config.TARGET_HEIGHT
            )
            
            for track in scaled_lanes:
                coeffs, t_id, conf, age, events = track
                # Store coefficients [a, b, c] rounded to 6 decimal places
                serialized_lanes.append([round(float(x), 6) for x in coeffs])

        # Serialize Face Info (Essential fields only)
        serialized_face = {}
        if face_info:
            serialized_face = {
                'yaw': round(float(face_info.get('yaw', 0)), 2),
                'pitch': round(float(face_info.get('pitch', 0)), 2),
                'roll': round(float(face_info.get('roll', 0)), 2),
                'label': face_info.get('label', 'N/A'),
                'nose_2d': [int(x) for x in face_info.get('nose_2d')] if face_info.get('nose_2d') else None
            }
        
        # Serialize Vehicles
        serialized_vehicles = []
        for v in vehicles:
            serialized_vehicles.append({
                'label': v['label'],
                'score': round(v['score'], 2),
                'distance': round(v['distance'], 1),
                'bbox': v['bbox']
            })

        return {
            "time": round(float(current_time), 3),
            "lane_lines": serialized_lanes,
            "face_info": serialized_face,
            "vehicles": serialized_vehicles,
            "current_state": self.last_state
        }