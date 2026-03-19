import cv2
import numpy as np
import config
import json
from tqdm import tqdm
from pathlib import Path
from utils import setup_video_paths, scale_lane_coeffs
from visualization import VideoVisualizer
from safety_monitor import ManeuverValidator
import gc
import torch
import sys

# Ensure Visual Odometry is importable
# Assuming project structure: combined_analysis/src/video_processor.py -> root -> visual_odometry
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

try:
    from visual_odometry.vo_main import VisualOdometry
except ImportError:
    print("Warning: Could not import VisualOdometry. Ensure 'visual_odometry' module is in path.")
    VisualOdometry = None

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, (np.int32, np.int64)):
            return int(obj)
        return super().default(obj)

class VideoProcessor:
    def __init__(self, lane_wrapper, face_analyzer, args):
        self.lane_wrapper = lane_wrapper
        self.face_analyzer = face_analyzer
        self.args = args
        self.visualizer = VideoVisualizer()
        self.safety_monitor = ManeuverValidator()
        
        self.state_history = []
        self.last_state = None
        self.all_events = []
        
        # Initialize VO
        self.vo = None
        if VisualOdometry:
            # We don't provide a video path because we will feed frames manually
            # Assuming 30 FPS default, will be updated in run() if possible
            self.vo = VisualOdometry(video_path=None, fps=30.0)

    def run(self, export_json=False, output_json_path=None, custom_video_paths=None, metadata=None):
        # 1. Setup Video Capture
        if custom_video_paths:
             cap_road, cap_face, start_frame, end_frame, fps = self._setup_custom_video_capture(custom_video_paths)
        else:
             cap_road, cap_face, start_frame, end_frame, fps = self._setup_video_capture()

        if not cap_road: return
        
        # Update VO FPS
        if self.vo:
            self.vo.fps = fps
            self.vo.kf.dt = 1.0 / fps # Update KF delta time

        # 2. Setup Video Writer
        out_writer = None
        w, h = 0, 0
        if not export_json and self.args.savedir:
             out_writer, w, h = self._setup_video_writer(cap_road, fps)

        # Setup Face Video Writer (Always, even in headless)
        face_out_writer = None
        face_fps = cap_face.get(cv2.CAP_PROP_FPS)
        # Use a default if cap_face doesn't provide it
        if not (1 < face_fps <= 120): face_fps = 30.0

        num_frames = end_frame - start_frame
        print(f"Processing frames {start_frame} to {end_frame} ({num_frames} frames) @ {fps} FPS...")

        # Face video may have a different frame rate (e.g. 60 fps phone vs 30 fps dashcam).
        # Track its position so we can advance it in lock-step with road time rather than
        # reading one face frame per road frame.
        last_good_face_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        face_exhausted = False
        face_current_time = -1.0  # sentinel: no face frame read yet

        # Data collection containers
        timeline_events = []
        frame_data = []

        try:
            for i in tqdm(range(num_frames), mininterval=2.0):
                # 3. Read road frame
                ret_r, frame_road = cap_road.read()
                if not ret_r: break

                current_time = cap_road.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

                # Advance face video to road time, handling FPS mismatches.
                if not face_exhausted:
                    while face_current_time < current_time:
                        ret_f, candidate = cap_face.read()
                        if not ret_f:
                            face_exhausted = True
                            break
                        face_current_time = cap_face.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                        
                        # Apply face blurring to the face frame *before* analysis and writing
                        candidate_blurred, _ = self.face_analyzer.process_frame(candidate)
                        last_good_face_frame = candidate_blurred

                        # Initialize face_out_writer on first frame read
                        if face_out_writer is None and self.args.savedir:
                            face_out_writer = self._setup_face_video_writer(last_good_face_frame, face_fps)
                        
                        # Write the blurred frame to the face-only video
                        if face_out_writer:
                            face_out_writer.write(last_good_face_frame)

                frame_face = last_good_face_frame

                if export_json:
                    # Headless processing
                    # Use a modified version of headless processing that doesn't re-blur
                    frame_info = self._process_single_frame_headless_no_blur(frame_road, frame_face, current_time)
                    frame_data.append(frame_info)
                else:
                    # 4. Process Frame (Visual)
                    # Use a modified version that doesn't re-blur
                    vis_road = self._process_single_frame_no_blur(frame_road, frame_face, current_time, frame_idx=i)

                    # 5. Display & Write
                    if self.args.show:
                        cv2.imshow('Combined Analysis', vis_road)
                        if cv2.waitKey(1) & 0xFF == ord('q'): break

                    if out_writer and out_writer.isOpened():
                        out_writer.write(cv2.resize(vis_road, (w, h)))
            
            # --- End of Run Visualization ---
            if not export_json and self.vo:
                self._show_summary_plot()

            if export_json:
                # Compile final JSON
                final_events = []
                for event in self.all_events:
                    final_events.append({
                        "timestamp": event['timestamp'],
                        "type": event['type'],
                        "severity": event['severity'],
                        "message": event['message'],
                        "vo_x": event.get('vo_x'),
                        "vo_z": event.get('vo_z'),
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
                        json.dump(result, f, cls=NumpyEncoder)
                return result

        except KeyboardInterrupt:
            print("\nInterrupted by user")
            if not export_json and self.vo:
                self._show_summary_plot()
        except Exception as e:
            print(f"\nError in VideoProcessor.run: {e}")
            import traceback; traceback.print_exc()
            raise e
        finally:
            cap_road.release()
            cap_face.release()
            if out_writer: out_writer.release()
            if face_out_writer: face_out_writer.release()

            # Post-processing: Replace original face.mp4 with blurred one and generate quality variants
            if self.args.savedir:
                blurred_path = Path(self.args.savedir) / "face_blurred.mp4"
                final_face_path = Path(self.args.savedir) / "face.mp4"
                
                if blurred_path.exists():
                    print(f"Finalizing blurred face video variants for {final_face_path}...")
                    # Generate all quality variants including the 'original' one (as face.mp4)
                    # using web-compatible settings
                    self._generate_all_face_variants(blurred_path, final_face_path)
                    
                    # Cleanup temporary blurred file
                    try:
                        blurred_path.unlink()
                    except:
                        pass

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

    def _setup_face_video_writer(self, frame, fps):
        if not self.args.savedir:
            return None

        h, w = frame.shape[:2]
        # Ensure divisible by 2
        w, h = (w // 2) * 2, (h // 2) * 2

        Path(self.args.savedir).mkdir(parents=True, exist_ok=True)
        # We use 'face_blurred.mp4' as a temporary name during processing
        out_path = str(Path(self.args.savedir) / "face_blurred.mp4")
        
        face_out_writer = None
        for codec in ['mp4v', 'avc1', 'XVID']:
            face_out_writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*codec), fps, (w, h))
            if face_out_writer.isOpened():
                print(f"Recording blurred face to {out_path} using {codec}")
                break
        
        return face_out_writer

    def _process_single_frame(self, frame_road, frame_face, current_time, frame_idx=0):
        # We now pre-blur in run(), so this is kept for legacy but we add a no-blur variant
        return self._process_single_frame_no_blur(frame_road, frame_face, current_time, frame_idx)

    def _process_single_frame_no_blur(self, frame_road, frame_face, current_time, frame_idx=0):
        # Debug logging for first frame
        debug = frame_idx == 0
        
        if debug: print("[Debug] Processing Lane Detection...", flush=True)
        # Lane Processing
        vis_road, lane_data, cross_events = self.lane_wrapper.process_frame(frame_road)

        # VO Processing
        turn_event = None
        vo_pos = {'x': None, 'z': None}
        if self.vo:
            if debug: print("[Debug] Processing Visual Odometry...", flush=True)
            _, _, _, turn_event, _ = self.vo.process_frame(external_frame=frame_road)
            vo_pos['x'] = float(self.vo.cur_t[0][0])
            vo_pos['z'] = float(self.vo.cur_t[2][0])
            
            if turn_event:
                result = self.safety_monitor.validate_turn(turn_event, current_time, self.state_history)
                if result:
                    self.safety_monitor.active_alerts.append(result)
                    self.all_events.append({
                        'timestamp': current_time,
                        'type': 'turn_event',
                        'message': result.message,
                        'severity': result.severity,
                        'vo_x': vo_pos['x'],
                        'vo_z': vo_pos['z']
                    })
                    print(f"[{current_time:.2f}s] {result.message}")

        if debug: print("[Debug] Processing Face Analysis...", flush=True)
        # Face Processing (Assume frame_face is already blurred)
        # We still need the analysis data (pose, label)
        _, face_info = self.face_analyzer.process_frame(frame_face)
        
        # Draw analysis on the face frame
        vis_face = self.visualizer.visualize_face_analysis(frame_face.copy(), face_info)

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
                        self.all_events.append({
                            'timestamp': current_time,
                            'type': 'safety_alert',
                            'message': result.message,
                            'severity': result.severity,
                            'vo_x': vo_pos['x'],
                            'vo_z': vo_pos['z']
                        })
                        print(f"[{current_time:.2f}s] {result.message}")

        if debug: print("[Debug] Visualizing...", flush=True)
        self.visualizer.draw_face_overlay(vis_road, vis_face)
        self.visualizer.draw_status_panel(vis_road, face_info)
        self.visualizer.draw_history_panel(vis_road, self.state_history, current_time)
        self.visualizer.draw_safety_alerts(vis_road, self.safety_monitor.active_alerts)
        
        return vis_road

    def _process_single_frame_headless_no_blur(self, frame_road, frame_face, current_time):
        # Lane Processing
        vis_road, lane_data, cross_events = self.lane_wrapper.process_frame(frame_road)

        # VO Processing Headless
        turn_event = None
        vo_pos = {'x': None, 'z': None}
        if self.vo:
            _, _, _, turn_event, _ = self.vo.process_frame(external_frame=frame_road)
            vo_pos['x'] = float(self.vo.cur_t[0][0])
            vo_pos['z'] = float(self.vo.cur_t[2][0])
            
            if turn_event:
                result = self.safety_monitor.validate_turn(turn_event, current_time, self.state_history)
                if result:
                    self.safety_monitor.active_alerts.append(result)
                    self.all_events.append({
                        'timestamp': current_time,
                        'type': 'turn_event',
                        'message': result.message,
                        'severity': result.severity,
                        'vo_x': vo_pos['x'],
                        'vo_z': vo_pos['z']
                    })

        # Face Processing (Assume frame_face is already blurred)
        _, face_info = self.face_analyzer.process_frame(frame_face)
        
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
                        self.all_events.append({
                            'timestamp': current_time,
                            'type': 'safety_alert',
                            'message': result.message,
                            'severity': result.severity,
                            'vo_x': vo_pos['x'],
                            'vo_z': vo_pos['z']
                        })
        
        # Serialize Lane Data
        serialized_lanes = []
        if lane_data:
            scaled_lanes = scale_lane_coeffs(
                lane_data, 
                src_w=config.MODEL_WIDTH, src_h=config.MODEL_HEIGHT,
                dst_w=config.TARGET_WIDTH, dst_h=config.TARGET_HEIGHT
            )
            for track in scaled_lanes:
                coeffs, t_id, conf, age, events = track
                serialized_lanes.append([round(float(x), 6) for x in coeffs])

        # Serialize Face Info
        serialized_face = {}
        if face_info:
            serialized_face = {
                'yaw': round(float(face_info.get('yaw', 0)), 2),
                'pitch': round(float(face_info.get('pitch', 0)), 2),
                'roll': round(float(face_info.get('roll', 0)), 2),
                'label': face_info.get('label', 'N/A'),
                'nose_2d': [int(x) for x in face_info.get('nose_2d')] if face_info.get('nose_2d') else None
            }

        frame_result = {
            "time": round(float(current_time), 3),
            "lane_lines": serialized_lanes,
            "face_info": serialized_face,
            "current_state": self.last_state
        }
        if vo_pos['x'] is not None:
            frame_result["vo_x"] = round(vo_pos['x'], 3)
            frame_result["vo_z"] = round(vo_pos['z'], 3)
        return frame_result

    def _generate_all_face_variants(self, temp_blurred_path: Path, final_face_path: Path):
        """
        Transcodes the temporary blurred video into web-compatible face.mp4 (original res),
        face_720p.mp4 and face_480p.mp4.  Skips variants that would upscale.
        """
        # 1. Generate main face.mp4 (Full resolution, web-compatible)
        print(f"Transcoding main blurred video: {final_face_path}")
        self._ffmpeg_transcode(temp_blurred_path, final_face_path)

        # 2. Determine source height to avoid upscaling
        orig_height = self._get_video_height(temp_blurred_path)

        # 3. Generate quality variants (skip upscaling)
        targets = [720, 480]
        for target in targets:
            if orig_height > 0 and orig_height <= target:
                print(f"Skipping face_{target}p.mp4 (source is {orig_height}p, no upscale)")
                continue
            out_path = final_face_path.parent / f"face_{target}p.mp4"
            print(f"Generating quality variant: {out_path}")
            self._ffmpeg_transcode(temp_blurred_path, out_path, height=target)

    @staticmethod
    def _get_video_height(video_path: Path) -> int:
        """Returns the height of the first video stream using ffprobe. Returns 0 on failure."""
        import os, subprocess
        try:
            env = os.environ.copy()
            env.pop("LD_LIBRARY_PATH", None)
            res = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=height",
                 "-of", "default=noprint_wrappers=1:nokey=1",
                 str(video_path)],
                capture_output=True, text=True, env=env,
            )
            if res.returncode == 0 and res.stdout.strip():
                return int(res.stdout.strip())
        except Exception:
            pass
        return 0

    def _ffmpeg_transcode(self, input_path: Path, output_path: Path, height: int = None):
        """Helper to run ffmpeg with web-compatible settings, optionally scaling."""
        import os
        import subprocess
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            print("Warning: imageio_ffmpeg not installed, falling back to system ffmpeg")
            ffmpeg_exe = "ffmpeg"

        cmd = [ffmpeg_exe, "-i", str(input_path)]
        
        if height:
            cmd += ["-vf", f"scale=-2:{height}"]
        
        # Web-compatible H.264 using imageio-ffmpeg's reliable binary
        cmd += [
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "copy",
            str(output_path),
            "-y"
        ]
        
        env = os.environ.copy()
        if "LD_LIBRARY_PATH" in env:
            del env["LD_LIBRARY_PATH"]

        try:
            subprocess.run(cmd, capture_output=True, text=True, env=env, check=True)
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error for {output_path}: {e.stderr}")
        except Exception as e:
            print(f"FFmpeg exception for {output_path}: {e}")

    def _generate_quality_variants(self, input_path: Path):
        # This is now handled by _generate_all_face_variants
        pass

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

        # VO Processing Headless
        turn_event = None
        vo_pos = {'x': None, 'z': None}
        if self.vo:
            _, _, _, turn_event, _ = self.vo.process_frame(external_frame=frame_road)
            vo_pos['x'] = float(self.vo.cur_t[0][0])
            vo_pos['z'] = float(self.vo.cur_t[2][0])
            
            if turn_event:
                # Validate turn safety
                result = self.safety_monitor.validate_turn(turn_event, current_time, self.state_history)
                if result:
                    self.safety_monitor.active_alerts.append(result)
                    self.all_events.append({
                        'timestamp': current_time,
                        'type': 'turn_event',
                        'message': result.message,
                        'severity': result.severity,
                        'vo_x': vo_pos['x'],
                        'vo_z': vo_pos['z']
                    })

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
                        self.all_events.append({
                            'timestamp': current_time,
                            'type': 'safety_alert',
                            'message': result.message,
                            'severity': result.severity,
                            'vo_x': vo_pos['x'],
                            'vo_z': vo_pos['z']
                        })
        
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

        frame_result = {
            "time": round(float(current_time), 3),
            "lane_lines": serialized_lanes,
            "face_info": serialized_face,
            "current_state": self.last_state
        }
        if vo_pos['x'] is not None:
            frame_result["vo_x"] = round(vo_pos['x'], 3)
            frame_result["vo_z"] = round(vo_pos['z'], 3)
        return frame_result

    def _show_summary_plot(self):
        """Generates and shows the 3D trajectory plot with event markers."""
        if not self.vo:
            return

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("Warning: matplotlib not installed. Skipping summary plot.")
            return

        traj_x = self.vo.traj_x
        traj_z = self.vo.traj_z
        
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111)
        
        # Plot Path
        ax.plot(traj_x, traj_z, label='Vehicle Trajectory', color='blue', linewidth=2)
        ax.scatter(traj_x[-1], traj_z[-1], color='red', marker='o', label='End Point')
        ax.scatter(traj_x[0], traj_z[0], color='green', marker='o', label='Start Point')
        
        # Plot Events
        turn_x, turn_z = [], []
        alert_x, alert_z = [], []
        
        for evt in self.all_events:
            if evt.get('vo_x') is not None and evt.get('vo_z') is not None:
                if evt['type'] == 'turn_event':
                    turn_x.append(evt['vo_x'])
                    turn_z.append(evt['vo_z'])
                elif evt['type'] == 'safety_alert':
                    alert_x.append(evt['vo_x'])
                    alert_z.append(evt['vo_z'])
        
        if turn_x:
            ax.scatter(turn_x, turn_z, color='orange', marker='*', s=150, label='Turns', zorder=5)
        if alert_x:
            ax.scatter(alert_x, alert_z, color='red', marker='X', s=100, label='Safety Alerts', zorder=5)
        
        ax.set_title("Trip Summary: Trajectory & Events")
        ax.set_xlabel("X Position (meters relative)")
        ax.set_ylabel("Z Position (meters relative)")
        ax.legend()
        ax.grid(True)
        ax.axis('equal')
        
        print("\n" + "="*50)
        print("                TRIP EVENT LOG")
        print("="*50)
        for evt in self.all_events:
            print(f"Time: {evt['timestamp']:6.2f}s | {evt['type'].upper():12} | {evt['message']}")
        print("="*50 + "\n")
        
        plt.show()