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
    def __init__(self, video_path=None, start_seconds=0, fps=30.0):
        self.video_path = video_path
        self.fps = fps
        self.cap = None
        
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
        
        # Kalman Filter Init
        print(f"Initializing Kalman Filter (FPS: {self.fps})")
        self.kf = PoseKalmanFilter(fps=self.fps)
        
        # Initial State for KF
        init_meas = np.zeros((6, 1), dtype=np.float32)
        # We start at 0,0,0 and 0,0,0 rotation
        self.kf.kalman.statePost[:6] = init_meas

        # --- Mask R-CNN Setup ---
        print("Initializing Mask R-CNN (ResNet50 FPN V2)...")
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        self.seg_model = None
        try:
            # Load the model
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
        self.turn_pts_x = []
        self.turn_pts_y = []
        self.turn_pts_z = []

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
        """Detect features using a grid-based approach (bucketing) to ensure even distribution."""
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

        # Generate Mask using Mask R-CNN
        dynamic_mask = self.get_segmentation_mask(frame_cropped)
        
        # Dilate mask slightly to cover edges
        kernel = np.ones((31, 31), np.uint8) 
        dynamic_mask = cv2.dilate(dynamic_mask, kernel, iterations=2)
        
        # Static mask: 255 where static, 0 where dynamic
        static_mask = cv2.bitwise_not(dynamic_mask)
        
        # Safety: If mask covers too much of the screen, we are effectively blind
        static_area_ratio = np.sum(static_mask == 255) / (h_crop * w_crop)
        is_blind = static_area_ratio < 0.05 # Less than 5% static area

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

            # Track features (Backward) for consistency check
            if p1 is not None:
                p0_back, st_back, err_back = cv2.calcOpticalFlowPyrLK(curr_gray, self.prev_image, p1, None, **self.lk_params)

                if p0_back is not None:
                    # Forward-Backward error
                    fb_err = np.linalg.norm((self.prev_keypoints - p0_back).reshape(-1, 2), axis=1)
                    
                    for i, (new, old) in enumerate(zip(p1, self.prev_keypoints)):
                        if st[i] == 1 and st_back[i] == 1 and fb_err[i] < 0.5:
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

        # Kalman Filter Step
        self.kf.predict()
        
        # Prepare measurement (Current Raw Pose)
        meas_pos = self.raw_t.flatten()
        meas_euler = rotationMatrixToEulerAngles(self.raw_R)
        measurement = np.concatenate((meas_pos, meas_euler)).reshape(6, 1).astype(np.float32)
        
        # Confidence logic: Lock position if stationary/blind, trust VO if moving
        if is_moving:
            conf_scale = 1.0
        elif is_blind:
            conf_scale = 0.01 # Extremely high trust in stationary state when masked
        else:
            conf_scale = 0.1 # High trust in stationary state
            
        est_state = self.kf.correct(measurement, confidence_scale=conf_scale)
        
        # Extract Filtered Pose
        self.cur_t = est_state[:3].reshape(3, 1)
        self.cur_R = eulerAnglesToRotationMatrix(est_state[3:6].flatten())
        
        self.traj_x.append(self.cur_t[0][0])
        self.traj_y.append(self.cur_t[1][0])
        self.traj_z.append(self.cur_t[2][0])
        
        # Status Logging
        if is_blind: status = "BLIND/MASKED"
        elif is_moving: status = "MOVING"
        else: status = "STATIONARY"
        
        # Turn Detection
        current_yaw = est_state[4].item() # Pitch(0), Yaw(1), Roll(2) -> Index 4 corresponds to Y-rot (Yaw)
        turn_event = self.turn_detector.update(current_yaw, self.frame_count)
        
        log_msg = f"Frame {self.frame_count} | {status} | Flow: {avg_flow:.2f}px | Inlier: {inlier_ratio:.2f} | Pos: ({self.cur_t[0][0]:.2f}, {self.cur_t[1][0]:.2f}, {self.cur_t[2][0]:.2f})"
        
        if turn_event:
            log_msg += f" | >>> {turn_event} DETECTED <<<"
            self.turn_pts_x.append(self.cur_t[0][0])
            self.turn_pts_y.append(self.cur_t[1][0])
            self.turn_pts_z.append(self.cur_t[2][0])
            
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

        self.prev_image = curr_gray
        return True, frame_raw, frame_cropped, turn_event, dynamic_mask
