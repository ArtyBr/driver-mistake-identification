import cv2
import numpy as np
import sys
import os
import torch
import torchvision
from torchvision import transforms
import math

# python3 vo_main.py /media/arty/3A30-14F9/Videos/02_09_25_me_to_gym_day/2025_0902_152436_004637F.MP4

def rotationMatrixToEulerAngles(R):
    sy = math.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])
    singular = sy < 1e-6
    if not singular:
        x = math.atan2(R[2, 1], R[2, 2])
        y = math.atan2(-R[2, 0], sy)
        z = math.atan2(R[1, 0], R[0, 0])
    else:
        x = math.atan2(-R[1, 2], R[1, 1])
        y = math.atan2(-R[2, 0], sy)
        z = 0
    return np.array([x, y, z])

def eulerAnglesToRotationMatrix(theta):
    R_x = np.array([[1, 0, 0],
                    [0, math.cos(theta[0]), -math.sin(theta[0])],
                    [0, math.sin(theta[0]), math.cos(theta[0])]])
    R_y = np.array([[math.cos(theta[1]), 0, math.sin(theta[1])],
                    [0, 1, 0],
                    [-math.sin(theta[1]), 0, math.cos(theta[1])]])
    R_z = np.array([[math.cos(theta[2]), -math.sin(theta[2]), 0],
                    [math.sin(theta[2]), math.cos(theta[2]), 0],
                    [0, 0, 1]])
    R = np.dot(R_z, np.dot(R_y, R_x))
    return R

class PoseKalmanFilter:
    def __init__(self, fps=30.0):
        self.dt = 1.0 / fps
        
        # State: [x, y, z, roll, pitch, yaw, vx, vy, vz, v_roll, v_pitch, v_yaw] (12x1)
        self.kalman = cv2.KalmanFilter(12, 6, 0)
        
        # Transition Matrix (F)
        # x_k = x_{k-1} + v_{k-1} * dt
        self.kalman.transitionMatrix = np.eye(12, dtype=np.float32)
        for i in range(6):
            self.kalman.transitionMatrix[i, i+6] = self.dt
            
        # Measurement Matrix (H)
        # We measure [x, y, z, roll, pitch, yaw]
        self.kalman.measurementMatrix = np.eye(6, 12, dtype=np.float32)
        
        # Process Noise Covariance (Q)
        # Model uncertainty (assume constant velocity is mostly true)
        self.kalman.processNoiseCov = np.eye(12, dtype=np.float32) * 1e-4
        
        # Measurement Noise Covariance (R)
        # Sensor noise (VO uncertainty)
        # We can tune this dynamically
        self.kalman.measurementNoiseCov = np.eye(6, dtype=np.float32) * 1e-2
        
        # Error Covariance (P)
        self.kalman.errorCovPost = np.eye(12, dtype=np.float32)

    def predict(self):
        return self.kalman.predict()

    def correct(self, measurement, confidence_scale=1.0):
        # confidence_scale: Higher means LESS confident in measurement (higher R)
        
        # Update R based on confidence
        base_R = 1e-2
        self.kalman.measurementNoiseCov = np.eye(6, dtype=np.float32) * base_R * confidence_scale
        
        return self.kalman.correct(measurement)

class TurnDetector:
    def __init__(self, angle_threshold_degrees=30.0, cooldown_frames=45):
        self.angle_threshold = math.radians(angle_threshold_degrees)
        self.cooldown_frames = cooldown_frames
        self.cooldown_counter = 0
        
        self.accumulated_yaw = 0.0
        self.prev_yaw = None
        self.max_delta_seen = 0.0
        self.straight_frames = 0
        
    def update(self, current_yaw, frame_count):
        if self.cooldown_counter > 0:
            self.cooldown_counter -= 1
            self.prev_yaw = current_yaw
            self.accumulated_yaw = 0.0
            self.max_delta_seen = 0.0
            return None

        if self.prev_yaw is None:
            self.prev_yaw = current_yaw
            return None

        # Calculate delta with wrap-around handling
        delta = current_yaw - self.prev_yaw
        while delta > math.pi: delta -= 2 * math.pi
        while delta < -math.pi: delta += 2 * math.pi
        
        # --- Robustness Logic ---
        
        # 1. Accumulate raw movement
        self.accumulated_yaw += delta
        self.max_delta_seen = max(self.max_delta_seen, abs(delta))
        
        # 2. Straightness check (to reset accumulator)
        # If rotation is very low for ~1 second, we assume the turn attempt is over
        if abs(delta) < math.radians(0.1):
            self.straight_frames += 1
        else:
            self.straight_frames = 0
            
        if self.straight_frames > 30: 
            self.accumulated_yaw = 0.0
            self.max_delta_seen = 0.0

        # 3. Trigger Logic
        detected = None
        
        # Check if the turn has any "sharp" component (intersection turns vs smooth curves)
        # Lowered to 0.6 degrees per frame (~18 deg/sec) to catch tighter/slower turns
        is_sharp = self.max_delta_seen > math.radians(0.6)
        # Check for extremely sudden maneuvers
        is_sudden = abs(delta) > math.radians(8.0)
        
        # Trigger if:
        # A) Normal threshold reached (30 deg) AND it was somewhat sharp
        # B) Extreme rotation reached (80 deg) even if smooth (very long curve/roundabout)
        # C) Sudden high-rotation frame AND we already turned at least 15 degrees
        if (abs(self.accumulated_yaw) >= self.angle_threshold and is_sharp) or \
           (abs(self.accumulated_yaw) >= math.radians(80.0)) or \
           (abs(self.accumulated_yaw) >= math.radians(15.0) and is_sudden):
            
            direction_str = "RIGHT" if self.accumulated_yaw > 0 else "LEFT"
            detected = f"TURN_{direction_str}"
            self.cooldown_counter = self.cooldown_frames
            self.accumulated_yaw = 0.0
            self.max_delta_seen = 0.0
            self.straight_frames = 0

        self.prev_yaw = current_yaw
        return detected

class VisualOdometry:
    def __init__(self, video_path=None, start_seconds=0, fps=30.0,
                 use_kalman=True, use_masking=True, use_bucketing=True, use_fb_validation=True):
        self.video_path = video_path
        self.fps = fps
        self.cap = None

        # Feature toggle flags
        self.use_kalman = use_kalman
        self.use_masking = use_masking
        self.use_bucketing = use_bucketing
        self.use_fb_validation = use_fb_validation

        if video_path:
            self.cap = cv2.VideoCapture(video_path)
            if not self.cap.isOpened():
                raise IOError(f"Cannot open video file: {video_path}")

            # Seek to start time if specified
            if start_seconds > 0:
                print(f"Seeking to {start_seconds} seconds...")
                self.cap.set(cv2.CAP_PROP_POS_MSEC, start_seconds * 1000)

            # Update FPS from video
            vid_fps = self.cap.get(cv2.CAP_PROP_FPS)
            if vid_fps > 0 and not np.isnan(vid_fps):
                self.fps = vid_fps

        # Intrinsic Matrix (K) from calibration_3.txt
        self.K_orig = np.array([
            [993.6305137521725, 0.0, 954.7271539229214],
            [0.0, 1144.329008082279, 539.4773780846734],
            [0.0, 0.0, 1.0]
        ])

        self.K = self.K_orig.copy()
        self.k_adjusted = False

        self.D = np.array([0.09120135029599218, 0.03431960504192815, -0.027375346575880814, -0.017942890066237845, -0.6799011067187613])

        # Feature Detection Parameters
        self.feature_params = dict(maxCorners=2000, qualityLevel=0.05, minDistance=30, blockSize=7)
        self.lk_params = dict(winSize=(21, 21), maxLevel=3,
                              criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))

        # Initialization
        self.cur_R = np.eye(3)
        self.cur_t = np.zeros((3, 1))
        # Raw pose accumulator for KF input
        self.raw_R = np.eye(3)
        self.raw_t = np.zeros((3, 1))

        self.prev_image = None
        self.prev_keypoints = None

        self.traj_x = [0.0]
        self.traj_y = [0.0]
        self.traj_z = [0.0]
        self.frame_count = 0

        # Per-frame metrics for benchmarking
        self.frame_stats = []

        # Kalman Filter Init (skip if disabled)
        self.kf = None
        if self.use_kalman:
            print(f"Initializing Kalman Filter (FPS: {self.fps})")
            self.kf = PoseKalmanFilter(fps=self.fps)
            init_meas = np.zeros((6, 1), dtype=np.float32)
            self.kf.kalman.statePost[:6] = init_meas

        # --- Mask R-CNN Setup (skip if masking disabled) ---
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.seg_model = None
        if self.use_masking:
            print("Initializing Mask R-CNN (ResNet50 FPN V2)...")
            try:
                weights = torchvision.models.detection.MaskRCNN_ResNet50_FPN_V2_Weights.DEFAULT
                self.seg_model = torchvision.models.detection.maskrcnn_resnet50_fpn_v2(weights=weights)
                self.seg_model.to(self.device)
                self.seg_model.eval()
                print("Mask R-CNN initialized successfully.")
            except Exception as e:
                print(f"Warning: Failed to initialize Mask R-CNN. Running without dynamic masking. Error: {e}")
                self.seg_model = None

        # Transform for Mask R-CNN (It expects 0-1 float tensors)
        self.seg_transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.ToTensor(),
        ])

        # COCO classes to ignore (dynamic objects)
        # 1: person, 2: bicycle, 3: car, 4: motorcycle, 6: bus, 8: truck
        self.ignore_classes = [1, 2, 3, 4, 6, 8]

        # Turn Detector
        # threshold 30 deg, moderate sharpness (0.6 deg/frame)
        self.turn_detector = TurnDetector(angle_threshold_degrees=30.0, cooldown_frames=60)
        # Yaw integrated from per-frame R_rel (avoids euler decomposition sign-flip
        # on large accumulated raw_R in long videos)
        self.yaw_integrated = 0.0
        self.turn_pts_left_x = []
        self.turn_pts_left_y = []
        self.turn_pts_left_z = []
        self.turn_pts_right_x = []
        self.turn_pts_right_y = []
        self.turn_pts_right_z = []

    def get_segmentation_mask(self, frame):
        h, w = frame.shape[:2]
        
        if self.seg_model is None:
            return np.zeros((h, w), dtype=np.uint8)

        # Prepare input
        input_tensor = self.seg_transform(frame).to(self.device)
        
        with torch.no_grad():
            predictions = self.seg_model([input_tensor])[0]
            
        # Initialize empty mask (0=static)
        combined_mask = np.zeros((h, w), dtype=np.uint8)
        
        # Iterate through detections
        for i in range(len(predictions['scores'])):
            score = predictions['scores'][i].item()
            label = predictions['labels'][i].item()
            
            # Confidence threshold and class check
            if score > 0.3 and label in self.ignore_classes:
                # Extract mask (soft mask > 0.5 becomes binary)
                mask = predictions['masks'][i, 0].cpu().numpy()
                mask_binary = (mask > 0.5).astype(np.uint8) * 255
                
                # Combine with main mask using logical OR
                combined_mask = cv2.bitwise_or(combined_mask, mask_binary)
                
        return combined_mask

    def detect_features(self, image, mask=None):
        """Detect features, using grid bucketing if enabled for even distribution."""
        if not self.use_bucketing:
            return cv2.goodFeaturesToTrack(image, mask=mask, **self.feature_params)

        grid_rows, grid_cols = 4, 6
        h, w = image.shape[:2]
        cell_h, cell_w = h // grid_rows, w // grid_cols

        all_kps = []
        # Target features per cell
        target_per_cell = self.feature_params['maxCorners'] // (grid_rows * grid_cols)

        # Local copy of params to modify maxCorners for each cell
        local_params = self.feature_params.copy()
        local_params['maxCorners'] = target_per_cell

        for r in range(grid_rows):
            for c in range(grid_cols):
                y0, y1 = r * cell_h, (r + 1) * cell_h
                x0, x1 = c * cell_w, (c + 1) * cell_w

                cell_img = image[y0:y1, x0:x1]
                cell_mask = None
                if mask is not None:
                    cell_mask = mask[y0:y1, x0:x1]
                    if cv2.countNonZero(cell_mask) < 10: # Skip if cell is mostly masked
                        continue

                kps = cv2.goodFeaturesToTrack(cell_img, mask=cell_mask, **local_params)
                if kps is not None:
                    # Adjust coordinates to global image
                    kps[:, 0, 0] += x0
                    kps[:, 0, 1] += y0
                    all_kps.append(kps)

        if len(all_kps) > 0:
            return np.vstack(all_kps)
        return None

    def process_frame(self, external_frame=None):
        if external_frame is not None:
            ret = True
            frame_raw = external_frame
        elif self.cap is not None:
            ret, frame_raw = self.cap.read()
        else:
            return False, None, None, None, None

        if not ret:
            return False, None, None, None, None
            
        self.frame_count += 1

        # Crop to center 3/4ths
        h, w = frame_raw.shape[:2]
        h_crop = int(h * 0.75)
        w_crop = int(w * 0.75)
        y_start = (h - h_crop) // 2
        x_start = (w - w_crop) // 2
        frame_cropped = frame_raw[y_start:y_start+h_crop, x_start:x_start+w_crop].copy()

        # Adjust K for the crop
        if not self.k_adjusted:
            self.K[0, 2] = self.K_orig[0, 2] - x_start
            self.K[1, 2] = self.K_orig[1, 2] - y_start
            self.k_adjusted = True

        # Generate Mask using Mask R-CNN (skip if masking disabled)
        if self.use_masking:
            dynamic_mask = self.get_segmentation_mask(frame_cropped)
            kernel = np.ones((31, 31), np.uint8)
            dynamic_mask = cv2.dilate(dynamic_mask, kernel, iterations=2)
            static_mask = cv2.bitwise_not(dynamic_mask)
            static_area_ratio = np.sum(static_mask == 255) / (h_crop * w_crop)
            is_blind = static_area_ratio < 0.05
        else:
            dynamic_mask = np.zeros((h_crop, w_crop), dtype=np.uint8)
            static_mask = np.full((h_crop, w_crop), 255, dtype=np.uint8)
            static_area_ratio = 1.0
            is_blind = False

        # Convert to grayscale
        curr_gray = cv2.cvtColor(frame_cropped, cv2.COLOR_BGR2GRAY)

        if self.prev_image is None or self.prev_keypoints is None:
            # Initialization
            if not is_blind:
                self.prev_keypoints = self.detect_features(curr_gray, mask=static_mask)
            self.prev_image = curr_gray
            print(f"Initialized features. Static area: {static_area_ratio*100:.1f}%", flush=True)
            return True, frame_raw, frame_cropped, None, dynamic_mask

        # --- Feature Tracking ---
        good_new = []
        good_old = []
        tracking_success = False
        
        if not is_blind and self.prev_keypoints is not None and len(self.prev_keypoints) > 0:
            # Track features (Forward)
            p1, st, err = cv2.calcOpticalFlowPyrLK(self.prev_image, curr_gray, self.prev_keypoints, None, **self.lk_params)

            if p1 is not None:
                if self.use_fb_validation:
                    # Track features (Backward) for consistency check
                    p0_back, st_back, err_back = cv2.calcOpticalFlowPyrLK(curr_gray, self.prev_image, p1, None, **self.lk_params)

                    if p0_back is not None:
                        fb_err = np.linalg.norm((self.prev_keypoints - p0_back).reshape(-1, 2), axis=1)

                        for i, (new, old) in enumerate(zip(p1, self.prev_keypoints)):
                            if st[i] == 1 and st_back[i] == 1 and fb_err[i] < 0.5:
                                x, y = new.ravel()
                                if 0 <= int(y) < h_crop and 0 <= int(x) < w_crop:
                                    if static_mask[int(y), int(x)] > 0:
                                        good_new.append(new)
                                        good_old.append(old)
                else:
                    # No forward-backward validation: accept features with forward status only
                    for i, (new, old) in enumerate(zip(p1, self.prev_keypoints)):
                        if st[i] == 1:
                            x, y = new.ravel()
                            if 0 <= int(y) < h_crop and 0 <= int(x) < w_crop:
                                if static_mask[int(y), int(x)] > 0:
                                    good_new.append(new)
                                    good_old.append(old)

            good_new = np.array(good_new)
            good_old = np.array(good_old)
            if len(good_new) > 10:
                tracking_success = True

        # --- Pose Estimation & KF ---
        R_rel = np.eye(3)
        t_rel = np.zeros((3, 1))
        is_moving = False
        inlier_ratio = 0.0
        avg_flow = 0.0
        
        if tracking_success:
            # Calculate average feature displacement
            flow_vectors = good_new - good_old
            avg_flow = np.mean(np.linalg.norm(flow_vectors, axis=1))
            
            if avg_flow > 1.0:
                E, mask = cv2.findEssentialMat(good_new, good_old, self.K, method=cv2.RANSAC, prob=0.999, threshold=0.5)
                if E is not None:
                    inliers = np.sum(mask)
                    inlier_ratio = inliers / len(good_new)
                    if inliers > 5 and inlier_ratio > 0.4:
                        _, R_cand, t_cand, mask = cv2.recoverPose(E, good_new, good_old, self.K, mask=mask)
                        rot_trace = np.trace(R_cand)
                        rot_angle = math.acos(np.clip((rot_trace - 1) / 2, -1, 1))
                        
                        if rot_angle < 0.5: # Increased limit to ~28 degrees per frame to catch sharp turns
                            R_rel = R_cand
                            t_rel = t_cand
                            is_moving = True
                        else:
                             print(f"Skipping frame {self.frame_count}: High rotation ({math.degrees(rot_angle):.1f} deg)")

        # Update Raw Accumulator (only if valid motion)
        if is_moving:
            self.raw_t = self.raw_t + self.raw_R.dot(t_rel)
            self.raw_R = self.raw_R.dot(R_rel)
            # Integrate per-frame yaw directly from R_rel (index 1 = Y-rotation in ZYX convention)
            # R_rel is always a small rotation so euler decomposition is well-behaved here
            self.yaw_integrated += rotationMatrixToEulerAngles(R_rel)[1]

        # Kalman Filter Step (skip if disabled)
        if self.use_kalman and self.kf is not None:
            self.kf.predict()

            meas_pos = self.raw_t.flatten()
            meas_euler = rotationMatrixToEulerAngles(self.raw_R)
            measurement = np.concatenate((meas_pos, meas_euler)).reshape(6, 1).astype(np.float32)

            if is_moving:
                conf_scale = 1.0
            elif is_blind:
                conf_scale = 0.01
            else:
                conf_scale = 0.1

            est_state = self.kf.correct(measurement, confidence_scale=conf_scale)

            self.cur_t = est_state[:3].reshape(3, 1)
            self.cur_R = eulerAnglesToRotationMatrix(est_state[3:6].flatten())
        else:
            # No Kalman filter: use raw pose directly
            self.cur_t = self.raw_t.copy()
            self.cur_R = self.raw_R.copy()

        self.traj_x.append(self.cur_t[0][0])
        self.traj_y.append(self.cur_t[1][0])
        self.traj_z.append(self.cur_t[2][0])
        
        # Status Logging
        if is_blind: status = "BLIND/MASKED"
        elif is_moving: status = "MOVING"
        else: status = "STATIONARY"
        
        # Turn Detection
        # Use yaw_integrated (sum of per-frame R_rel Y-rotations) rather than est_state[4]
        # (euler decomposition of accumulated raw_R). For long videos, raw_R can have a
        # large accumulated rotation where atan2 can flip sign, causing LEFT/RIGHT confusion.
        turn_event = self.turn_detector.update(self.yaw_integrated, self.frame_count)
        
        log_msg = f"Frame {self.frame_count} | {status} | Flow: {avg_flow:.2f}px | Inlier: {inlier_ratio:.2f} | Pos: ({self.cur_t[0][0]:.2f}, {self.cur_t[1][0]:.2f}, {self.cur_t[2][0]:.2f})"
        
        if turn_event:
            log_msg += f" | >>> {turn_event} DETECTED <<<"
            if "LEFT" in turn_event:
                self.turn_pts_left_x.append(self.cur_t[0][0])
                self.turn_pts_left_y.append(self.cur_t[1][0])
                self.turn_pts_left_z.append(self.cur_t[2][0])
            else:
                self.turn_pts_right_x.append(self.cur_t[0][0])
                self.turn_pts_right_y.append(self.cur_t[1][0])
                self.turn_pts_right_z.append(self.cur_t[2][0])
            
        print(log_msg, flush=True)

        # --- Feature Maintenance ---
        if tracking_success and len(good_new) > 0:
            if len(good_new) < 1000 and not is_blind:
                # Detect new features in grid to fill gaps
                new_kps = self.detect_features(curr_gray, mask=static_mask)
                if new_kps is not None:
                    self.prev_keypoints = np.vstack((good_new.reshape(-1, 1, 2), new_kps))
                else:
                    self.prev_keypoints = good_new.reshape(-1, 1, 2)
            else:
                self.prev_keypoints = good_new.reshape(-1, 1, 2)
        else:
            # Lost tracking or blind: Try to rediscover if possible
            if not is_blind:
                self.prev_keypoints = self.detect_features(curr_gray, mask=static_mask)
            else:
                self.prev_keypoints = None

        # Collect per-frame stats for benchmarking
        self.frame_stats.append({
            'frame': self.frame_count,
            'avg_flow': avg_flow,
            'inlier_ratio': inlier_ratio,
            'feature_count': len(good_new) if tracking_success else 0,
            'is_moving': is_moving,
            'is_blind': is_blind,
            'pos_x': self.cur_t[0][0],
            'pos_y': self.cur_t[1][0],
            'pos_z': self.cur_t[2][0],
            'turn_event': turn_event,
        })

        self.prev_image = curr_gray
        return True, frame_raw, frame_cropped, turn_event, dynamic_mask

    def on_key(self, event):
        if event.key == 'q':
            self.stop_requested = True

    def run(self):
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

        plt.ion()
        fig = plt.figure(figsize=(14, 7))
        self.stop_requested = False
        fig.canvas.mpl_connect('key_press_event', self.on_key)

        ax_masked = fig.add_subplot(121)
        ax_traj = fig.add_subplot(122, projection='3d')

        ax_masked.set_title("Mask R-CNN Overlay (Red=Dynamic)")
        ax_masked.axis('off')

        ax_traj.set_title("3D Trajectory")
        ax_traj.set_xlabel('X')
        ax_traj.set_ylabel('Z')
        ax_traj.set_zlabel('Y')
        ax_traj.view_init(elev=-20, azim=-90)

        line_traj, = ax_traj.plot(self.traj_x, self.traj_z, [-y for y in self.traj_y], color='blue', label='Trajectory')
        point_curr, = ax_traj.plot([0], [0], [0], 'ro', label='Current')
        turns_left_plot, = ax_traj.plot([], [], [], 'c*', markersize=12, label='Turn Left')
        turns_right_plot, = ax_traj.plot([], [], [], 'm*', markersize=12, label='Turn Right')
        ax_traj.legend()

        img_plot_masked = None

        print("Starting Visual Odometry (Mask R-CNN)... Press Q to quit.")
        while not self.stop_requested:
            ret, frame_raw, frame_crop, turn_event, mask_dyn = self.process_frame()
            if not ret:
                break

            # Blend red overlay on dynamic objects
            vis_masked = frame_crop.copy()
            red_img = np.zeros_like(vis_masked)
            red_img[:, :, 2] = 255
            blended = cv2.addWeighted(vis_masked, 0.6, red_img, 0.4, 0)
            vis_masked[mask_dyn == 255] = blended[mask_dyn == 255]

            # Draw tracked features
            if self.prev_keypoints is not None:
                for new in self.prev_keypoints:
                    a, b = new.ravel()
                    cv2.circle(vis_masked, (int(a), int(b)), 3, (0, 255, 0), -1)

            masked_rgb = cv2.cvtColor(vis_masked, cv2.COLOR_BGR2RGB)
            if img_plot_masked is None:
                img_plot_masked = ax_masked.imshow(masked_rgb)
            else:
                img_plot_masked.set_data(masked_rgb)

            # Update trajectory plot
            p_x = self.traj_x
            p_y = self.traj_z
            p_z = [-y for y in self.traj_y]

            line_traj.set_data(p_x, p_y)
            line_traj.set_3d_properties(p_z)
            point_curr.set_data([p_x[-1]], [p_y[-1]])
            point_curr.set_3d_properties([p_z[-1]])

            if len(self.turn_pts_left_x) > 0:
                turns_left_plot.set_data(self.turn_pts_left_x, self.turn_pts_left_z)
                turns_left_plot.set_3d_properties([-y for y in self.turn_pts_left_y])
            if len(self.turn_pts_right_x) > 0:
                turns_right_plot.set_data(self.turn_pts_right_x, self.turn_pts_right_z)
                turns_right_plot.set_3d_properties([-y for y in self.turn_pts_right_y])

            if len(p_x) > 1:
                mx = (max(p_x) + min(p_x)) / 2
                my = (max(p_y) + min(p_y)) / 2
                mz = (max(p_z) + min(p_z)) / 2
                r = max(max(p_x) - min(p_x), max(p_y) - min(p_y), max(p_z) - min(p_z)) / 2.0 or 1.0
                ax_traj.set_xlim(mx - r, mx + r)
                ax_traj.set_ylim(my - r, my + r)
                ax_traj.set_zlim(mz - r, mz + r)

            plt.draw()
            plt.pause(0.001)

        print("Finished.")
        plt.ioff()

        # Save X-Z trajectory plot to the same directory as the video
        if self.video_path and len(self.traj_x) > 1:
            video_dir = os.path.dirname(os.path.abspath(self.video_path))
            video_stem = os.path.splitext(os.path.basename(self.video_path))[0]
            save_path = os.path.join(video_dir, f"{video_stem}_trajectory_xz.png")

            fig_save, ax_save = plt.subplots(figsize=(10, 8))
            ax_save.plot(self.traj_x, self.traj_z, color='blue', label='Trajectory')
            if len(self.turn_pts_left_x) > 0:
                ax_save.plot(self.turn_pts_left_x, self.turn_pts_left_z, 'c*', markersize=12, label='Turn Left')
            if len(self.turn_pts_right_x) > 0:
                ax_save.plot(self.turn_pts_right_x, self.turn_pts_right_z, 'm*', markersize=12, label='Turn Right')
            ax_save.set_title("X-Z Trajectory (Top-Down View)")
            ax_save.set_xlabel("X")
            ax_save.set_ylabel("Z")
            ax_save.legend()
            ax_save.set_aspect('equal', adjustable='datalim')
            ax_save.grid(True)
            fig_save.tight_layout()
            fig_save.savefig(save_path, dpi=150)
            plt.close(fig_save)
            print(f"Trajectory plot saved to: {save_path}")

        if not self.stop_requested:
            plt.show(block=True)
        else:
            plt.close()
        self.cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Monocular Visual Odometry")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--start", type=float, default=0.0, help="Start time in seconds")
    parser.add_argument("--show", action="store_true", help="Show live visualisation (trajectory + mask overlay)")
    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"Error: File '{args.video}' not found.")
        sys.exit(1)

    vo = VisualOdometry(args.video, start_seconds=args.start)

    if args.show:
        vo.run()
    else:
        # Console-only mode: just print per-frame logs
        while True:
            ret, _, _, _, _ = vo.process_frame()
            if not ret:
                break
        print("Finished.")
        if vo.cap:
            vo.cap.release()
