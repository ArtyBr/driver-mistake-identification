# Visual Odometry Module

This module implements a **Monocular Visual Odometry (VO)** system that estimates a vehicle's 3D trajectory from a single dashcam video. It combines classical computer vision (optical flow, essential matrix decomposition) with a Kalman filter for smoothing and a Mask R-CNN neural network for dynamic object rejection. The module also detects turning events (left/right) based on accumulated yaw changes.

## Prerequisites

```bash
pip install opencv-python numpy torch torchvision matplotlib
```

- **GPU recommended**: Mask R-CNN runs on CUDA if available, otherwise falls back to CPU (significantly slower).

## Directory Structure

```
visual_odometry/
├── vo_main.py       # All implementation code
├── __init__.py      # Package init
└── README.md        # This file
```

## Usage

### Standalone (console-only, no visualization)

```bash
python3 vo_main.py /path/to/dashcam_video.MP4
```

This prints per-frame logs (status, flow, inlier ratio, position, turn events) to stdout but opens no windows.

### Standalone with live visualization

```bash
python3 vo_main.py /path/to/dashcam_video.MP4 --show
```

The `--show` flag opens a matplotlib window with two panels:
- **Left panel**: The cropped camera frame with dynamic objects highlighted in red and tracked features drawn as green dots.
- **Right panel**: A 3D trajectory plot updated in real time, with cyan stars for left turns and magenta stars for right turns.

Press **Q** in the matplotlib window to stop early. When the video ends (or Q is pressed), a top-down X-Z trajectory plot is saved as a PNG alongside the input video.

### Additional options

```bash
python3 vo_main.py /path/to/video.MP4 --start 30.5 --show
```

`--start` seeks to the given time in seconds before processing begins.

### As an imported module

```python
from visual_odometry.vo_main import VisualOdometry

vo = VisualOdometry(video_path="/path/to/video.mp4", start_seconds=10, fps=30.0)

while True:
    success, frame_raw, frame_cropped, turn_event, dynamic_mask = vo.process_frame()
    if not success:
        break
    if turn_event:
        print(turn_event)  # "TURN_LEFT" or "TURN_RIGHT"
```

You can also feed frames externally (e.g., from another pipeline) by passing `external_frame` to `process_frame()` instead of providing a `video_path` at construction time.

### Tunable Constants

| Constant | Location | Default | Purpose |
|---|---|---|---|
| `maxCorners` | `feature_params` (line 185) | 2000 | Max features to detect globally |
| `qualityLevel` | `feature_params` (line 185) | 0.05 | Minimum feature quality (Shi-Tomasi) |
| `minDistance` | `feature_params` (line 185) | 30 | Min pixel distance between features |
| `winSize` | `lk_params` (line 186) | (21,21) | Lucas-Kanade optical flow window |
| `maxLevel` | `lk_params` (line 186) | 3 | Pyramid levels for optical flow |
| `angle_threshold_degrees` | `TurnDetector` (line 241) | 30.0 | Accumulated yaw before a turn is triggered |
| `cooldown_frames` | `TurnDetector` (line 241) | 60 | Frames to wait after a turn before detecting another |
| `ignore_classes` | `__init__` (line 237) | [1,2,3,4,6,8] | COCO class IDs to mask out (person, bicycle, car, motorcycle, bus, truck) |

---

## How It Works: End-to-End Pipeline

Each call to `process_frame()` executes the following stages:

### 1. Frame Acquisition and Cropping (lines 320-346)

The raw frame is cropped to the center 75% in both dimensions. This removes barrel distortion artefacts at the edges and the dashcam's timestamp/UI overlays. On the first frame, the intrinsic matrix `K` is adjusted by shifting the principal point (`cx`, `cy`) to account for the crop offset (lines 343-346). This adjustment happens only once (`k_adjusted` flag).

### 2. Dynamic Object Masking via Mask R-CNN (lines 252-281, 348-360)

**Purpose:** Features on moving objects (cars, pedestrians, cyclists) would corrupt the ego-motion estimate because they move independently of the camera. Mask R-CNN segments these objects so their pixels can be excluded from feature detection and tracking.

**Why Mask R-CNN:** We need per-pixel instance segmentation, not just bounding boxes, because features near the edge of a bounding box could still be on static background. Mask R-CNN (He et al., 2017, "Mask R-CNN", ICCV) provides instance-level masks out of the box. The specific variant used is **Mask R-CNN with a ResNet50-FPN-V2 backbone** (Lin et al., 2017, "Feature Pyramid Networks for Object Detection", CVPR), which balances accuracy and speed.

**Alternatives considered:**
- **Semantic segmentation** (e.g., DeepLabV3): Provides per-pixel class labels but not instance separation. Would work for masking but is less standard for object-level filtering and doesn't provide confidence scores per detection.
- **YOLO + bounding box masking**: Much faster, but rectangular masks would aggressively exclude static background pixels around vehicles, reducing the number of usable features unnecessarily.
- **Optical flow magnitude thresholding**: A classical approach where pixels with flow inconsistent with the dominant motion are rejected. Cheaper than a neural network but unreliable when the camera is stationary (all flow is near zero) or when a vehicle ahead is moving at the same speed as the ego vehicle (flow looks static).

**`get_segmentation_mask(frame)`** (line 252):
- Converts the frame to a tensor and runs it through the pretrained Mask R-CNN (loaded at line 221).
- Iterates over all detections. For each detection with confidence > 0.3 whose class label is in `ignore_classes` (person, bicycle, car, motorcycle, bus, truck -- COCO dataset IDs), it extracts the instance segmentation mask, binarizes it at threshold 0.5, and OR-combines it into a single `combined_mask`.
- Returns a binary mask where 255 = dynamic object pixel.

**Back in `process_frame()`** (lines 348-360):
- The dynamic mask is **dilated** with a 31x31 kernel (2 iterations) to generously cover object edges and motion blur halos.
- A `static_mask` is computed as the bitwise NOT (255 = safe-to-track pixel).
- If less than 5% of the frame is static (`is_blind`), the system enters a degraded mode where it trusts the Kalman filter's prediction instead of VO measurements.

### 3. Feature Detection with Grid Bucketing (lines 283-318)

**`detect_features(image, mask)`** (line 283):

Rather than calling `cv2.goodFeaturesToTrack` on the whole image (which would cluster features in high-texture regions like trees), the image is divided into a **4x6 grid** (24 cells). Each cell independently detects up to `maxCorners / 24` features using **Shi-Tomasi corner detection** (Shi & Tomasi, 1994, "Good Features to Track", CVPR). Features are only detected on pixels where `static_mask > 0`. Coordinates are translated from cell-local back to image-global before returning.

This grid-bucketing strategy ensures features are spatially distributed across the frame, which is critical for robust essential matrix estimation (especially for rotation). Without bucketing, all features might concentrate on a single textured region like foliage, giving poor geometric constraints for the rest of the scene.

**Why Shi-Tomasi corners:** Shi-Tomasi (`goodFeaturesToTrack`) finds corners by computing the minimum eigenvalue of the structure tensor at each pixel. It is the standard choice for Lucas-Kanade tracking because LK was specifically designed to track patches with strong gradients in two directions -- exactly what Shi-Tomasi selects for.

**Alternatives considered:**
- **FAST** (Rosten & Drummond, 2006): Much faster detection but produces less uniformly high-quality corners. Better suited for real-time SLAM systems that need thousands of features per frame at minimal cost.
- **ORB** (Rublee et al., 2011): Provides binary descriptors for matching, but we use optical flow rather than descriptor matching, so ORB's descriptors would go unused. Its keypoint detector (oriented FAST) is also noisier than Shi-Tomasi.
- **SIFT/SURF**: High-quality features with scale/rotation invariance, but significantly slower and unnecessary since frame-to-frame motion is small enough that LK tracking handles scale/rotation implicitly.

### 4. Optical Flow Tracking with Forward-Backward Validation (lines 373-401)

Features from the previous frame are tracked to the current frame using **Lucas-Kanade pyramidal optical flow** (Lucas & Kanade, 1981, "An Iterative Image Registration Technique"; Bouguet, 2001, "Pyramidal Implementation of the Lucas Kanade Feature Tracker") via `cv2.calcOpticalFlowPyrLK` (line 380).

A **forward-backward consistency check** is then performed (lines 382-396), a technique popularized by Kalal et al. (2010) in the TLD (Tracking-Learning-Detection) tracker:
1. Track points forward: `prev_frame -> curr_frame` yielding `p1`.
2. Track points backward: `curr_frame -> prev_frame` yielding `p0_back`.
3. Compute the forward-backward error: the Euclidean distance between original positions and back-tracked positions.
4. A point is accepted only if:
   - Forward tracking succeeded (`st[i] == 1`)
   - Backward tracking succeeded (`st_back[i] == 1`)
   - Forward-backward error < 0.5 pixels (`fb_err[i] < 0.5`)
   - The point lands on a static pixel in the current frame's mask

This eliminates most tracking failures and points that drifted onto moving objects between frames. A minimum of 10 surviving points is required to proceed (`tracking_success`).

**Why Lucas-Kanade optical flow:** For monocular VO with frame-to-frame tracking, sparse LK flow is the standard approach (used in VISO2, LIBVISO2, and early ORB-SLAM). It directly gives sub-pixel point correspondences without needing descriptor extraction or matching. The pyramidal variant handles larger displacements by tracking at multiple image scales.

**Alternatives considered:**
- **Dense optical flow** (Farneback, Horn-Schunck): Computes flow for every pixel. Far more expensive and unnecessary since we only need correspondences at feature points.
- **Descriptor matching** (ORB, SIFT + brute-force/FLANN): More robust to large displacements and appearance changes, but slower per frame and less precise for small motions. Better suited for loop closure or wide-baseline stereo than consecutive frame tracking.
- **Direct methods** (DSO, LSD-SLAM): Operate on pixel intensities directly rather than features. More accurate in texture-poor environments but significantly more complex to implement and computationally heavier.

### 5. Relative Pose Estimation (lines 403-431)

If tracking succeeded:

1. **Average flow** is computed (line 413). If < 1.0 pixel, the camera is essentially stationary and no pose is estimated.
2. **Essential Matrix** `E` is computed via `cv2.findEssentialMat` with RANSAC (Fischler & Bolles, 1981, "Random Sample Consensus") at line 416. Parameters: `prob=0.999` (high confidence), `threshold=0.5` pixels.
3. **Inlier filtering**: The pose is only trusted if there are > 5 inliers AND the inlier ratio > 40% (line 420).
4. **`cv2.recoverPose`** decomposes `E` into a relative rotation `R_cand` and unit translation `t_cand` (line 421), implementing the cheirality check from Nister (2004, "An Efficient Solution to the Five-Point Relative Pose Problem", IEEE TPAMI) to select the geometrically valid decomposition.
5. **Rotation sanity check** (lines 422-430): The rotation angle is computed from the trace of `R_cand` using Rodrigues' rotation formula. If the angle exceeds 0.5 radians (~28 degrees per frame), the frame is skipped as a likely error (a vehicle cannot physically rotate that fast between consecutive frames). Otherwise, the raw pose accumulators are updated:
   ```
   raw_t = raw_t + raw_R @ t_rel
   raw_R = raw_R @ R_rel
   ```
   And the per-frame yaw is integrated into `yaw_integrated` (line 438) by decomposing the small-angle `R_rel` into Euler angles and accumulating the Y-rotation. This avoids the sign-flip issues that arise when decomposing the large accumulated `raw_R` matrix directly in long videos.

**Why the Essential Matrix:** The essential matrix encodes the epipolar geometry between two calibrated views. Since we have the camera intrinsics `K`, we can use `E` rather than the fundamental matrix `F`, which gives a cleaner decomposition into rotation and translation. The five-point algorithm (Nister, 2004) embedded in `findEssentialMat` is the standard for calibrated monocular VO.

**Alternatives considered:**
- **Fundamental matrix** (`findFundamentalMat`): Works without knowing `K` but produces projective (not metric) reconstruction. Since we have calibration, using `E` is strictly better.
- **Homography** (`findHomography`): Only correct when all points lie on a plane. Would work for flat roads with no 3D structure, but fails in general scenes with buildings, signs, etc.
- **PnP** (`solvePnP`): Requires 3D-2D correspondences, meaning we'd need a 3D map. This is what full SLAM systems use, but we're doing pure VO without map maintenance.

**Monocular scale limitation:** `t_rel` from `recoverPose` is a unit vector (magnitude = 1). Without external speed data (GPS, CAN bus), the trajectory shows the correct shape but not the correct scale. Every frame of motion advances by exactly 1 unit.

### 6. Kalman Filter Smoothing (lines 440-464)

**`PoseKalmanFilter`** (lines 38-77) wraps an OpenCV Kalman filter (based on the standard linear Kalman filter from Kalman, 1960, "A New Approach to Linear Filtering and Prediction Problems") with a 12-dimensional state:

```
State = [x, y, z, roll, pitch, yaw, vx, vy, vz, v_roll, v_pitch, v_yaw]
```

- **Transition model** (lines 47-49): Constant-velocity model. Each position/angle is predicted as `value + velocity * dt` where `dt = 1/fps`.
- **Measurement model** (line 53): Only the first 6 state variables (position + orientation) are directly measured from VO.
- **Process noise** `Q` (line 57): `1e-4 * I` -- assumes the constant-velocity model is mostly correct.
- **Measurement noise** `R` (line 62): `1e-2 * I` baseline, dynamically scaled.

**In `process_frame()`:**
1. `kf.predict()` is called every frame (line 441), advancing the state estimate using the constant-velocity model.
2. The raw accumulated pose (`raw_t`, `raw_R`) is converted to a 6D measurement vector `[x, y, z, roll, pitch, yaw]` (lines 444-446). Rotation is converted via `rotationMatrixToEulerAngles()`.
3. `kf.correct()` fuses the measurement with the prediction. The **confidence scale** controls how much the filter trusts the VO measurement vs. its own prediction (lines 448-456):
   - `1.0` when moving: Normal trust in VO.
   - `0.1` when stationary: High trust in "we haven't moved" (low measurement noise = filter snaps to measurement, which is the previous position).
   - `0.01` when blind (masked): Extremely high trust in staying put, since VO has no data.
4. The filtered state is extracted back into `cur_t` (position) and `cur_R` (rotation matrix, via `eulerAnglesToRotationMatrix()`).

**Why a Kalman filter:** The Kalman filter is the optimal linear state estimator for Gaussian noise (Kalman, 1960). It smooths out frame-to-frame jitter in VO estimates while maintaining responsiveness to real motion. The constant-velocity motion model is a good prior for vehicles, which don't teleport or change velocity instantaneously.

**Alternatives considered:**
- **Extended Kalman Filter (EKF)**: Handles nonlinear dynamics. Our state transition is linear (constant velocity), so the standard KF is sufficient and avoids Jacobian computation.
- **Unscented Kalman Filter (UKF)**: Better for highly nonlinear systems. Overkill for our linear motion model.
- **Particle filter**: Handles multi-modal distributions. Unnecessary here since vehicle motion is well-approximated by a single Gaussian.
- **Simple moving average / exponential smoothing**: Would smooth trajectory but cannot model velocity or adapt measurement trust dynamically. The Kalman filter's ability to scale `R` based on tracking confidence is a key advantage.

### 7. Turn Detection (lines 79-149, 471-488)

**`TurnDetector`** monitors the integrated yaw angle to detect turning events.

**`update(current_yaw, frame_count)`** (line 90):
1. **Cooldown**: After a turn is detected, the detector ignores the next `cooldown_frames` frames (default 60 = ~2 seconds at 30fps) to avoid double-triggering on the same turn.
2. **Delta calculation** (lines 103-105): Yaw change between frames, with wrap-around handling for the -pi/+pi boundary.
3. **Accumulation**: The raw yaw delta is accumulated in `accumulated_yaw`, and the maximum single-frame delta is tracked in `max_delta_seen`.
4. **Straightness reset** (lines 115-122): If the per-frame rotation is below 0.1 degrees for 30 consecutive frames (~1 second), the accumulator resets. This prevents slow drift from eventually triggering a false turn.
5. **Trigger conditions** (lines 137-139): A turn is detected if ANY of:
   - **(A)** Accumulated yaw >= 30 degrees AND at least one frame had > 0.6 deg/frame rotation ("sharp" component -- distinguishes intersection turns from highway curves).
   - **(B)** Accumulated yaw >= 80 degrees regardless of sharpness (catches long roundabouts or very gradual turns).
   - **(C)** Accumulated yaw >= 15 degrees AND the current frame has > 8 deg/frame rotation (sudden swerve mid-turn).
6. **Direction**: Positive accumulated yaw = `TURN_RIGHT`, negative = `TURN_LEFT`.
7. Turn positions are stored separately in `turn_pts_left_x/y/z` and `turn_pts_right_x/y/z` for visualization.

**Yaw integration detail** (lines 436-438, 472-475): Rather than extracting yaw from the Kalman-filtered state or from the accumulated `raw_R`, yaw is integrated incrementally by summing the Y-rotation component of each frame's small `R_rel`. This avoids a subtle bug: when `raw_R` accumulates a large rotation over a long video, converting it to Euler angles with `atan2` can produce sign flips at the +/-pi boundary, causing the turn detector to see a false large delta and misclassify turn direction. Since each per-frame `R_rel` is always a small rotation, its Euler decomposition is numerically stable.

### 8. Feature Maintenance (lines 492-508)

After each frame:
- If tracking succeeded but the feature count dropped below 1000 (and the frame isn't blind), new features are detected via grid bucketing and appended to the surviving tracked features.
- If tracking failed entirely and the frame isn't blind, features are re-detected from scratch.
- If the frame is blind, `prev_keypoints` is set to `None` (no features to track).

This adaptive replenishment strategy is standard in VO pipelines (e.g., LIBVISO2, Geiger et al., 2011) to maintain a sufficient feature count without full re-detection every frame.

---

## Utility Functions

### `rotationMatrixToEulerAngles(R)` (lines 12-23)

Converts a 3x3 rotation matrix to Euler angles `[x, y, z]` (roll, pitch, yaw) using the ZYX convention. Handles the gimbal lock singularity case when `sy < 1e-6` (when pitch approaches +/-90 degrees, yaw and roll become indistinguishable).

### `eulerAnglesToRotationMatrix(theta)` (lines 25-36)

Converts Euler angles `[x, y, z]` back to a 3x3 rotation matrix by composing `R_z @ R_y @ R_x` (intrinsic ZYX rotation order).

---

## `run()` Visualization Method (lines 517-631)

The `run()` method (invoked by the `--show` flag) drives the main loop and renders a live matplotlib figure:

- **Left panel** (`ax_masked`): Shows the cropped frame with a red overlay on Mask R-CNN detections and green dots on tracked features.
- **Right panel** (`ax_traj`): A 3D trajectory plot (X vs Z vs -Y) that auto-scales to fit the trajectory. Left turns are marked with cyan stars, right turns with magenta stars.
- **On completion**: A 2D top-down (X-Z) trajectory PNG is saved next to the input video file.

---

## Return Values from `process_frame()`

```python
success, frame_raw, frame_cropped, turn_event, dynamic_mask = vo.process_frame()
```

| Value | Type | Description |
|---|---|---|
| `success` | `bool` | `False` when video ends or no input is available |
| `frame_raw` | `np.ndarray` | Original uncropped frame (BGR) |
| `frame_cropped` | `np.ndarray` | Center-cropped frame used for processing (BGR) |
| `turn_event` | `str` or `None` | `"TURN_LEFT"`, `"TURN_RIGHT"`, or `None` |
| `dynamic_mask` | `np.ndarray` | Binary mask (255 = dynamic object pixel) |

## Accessible State

After each `process_frame()` call, the following instance variables are updated:

| Variable | Type | Description |
|---|---|---|
| `vo.cur_t` | `np.ndarray (3,1)` | Kalman-filtered position `[x, y, z]` |
| `vo.cur_R` | `np.ndarray (3,3)` | Kalman-filtered rotation matrix |
| `vo.traj_x/y/z` | `list[float]` | Full trajectory history |
| `vo.turn_pts_left_x/y/z` | `list[float]` | Positions where left turns were detected |
| `vo.turn_pts_right_x/y/z` | `list[float]` | Positions where right turns were detected |
| `vo.yaw_integrated` | `float` | Cumulative yaw from per-frame integration |
| `vo.frame_count` | `int` | Number of frames processed |

---

## References

1. He, K., Gkioxari, G., Dollar, P., & Girshick, R. (2017). "Mask R-CNN." ICCV.
2. Lin, T.-Y., Dollar, P., Girshick, R., He, K., Hariharan, B., & Belongie, S. (2017). "Feature Pyramid Networks for Object Detection." CVPR.
3. Shi, J., & Tomasi, C. (1994). "Good Features to Track." CVPR.
4. Lucas, B. D., & Kanade, T. (1981). "An Iterative Image Registration Technique with an Application to Stereo Vision." IJCAI.
5. Bouguet, J.-Y. (2001). "Pyramidal Implementation of the Lucas Kanade Feature Tracker." Intel Corporation, Microprocessor Research Labs.
6. Kalal, Z., Mikolajczyk, K., & Matas, J. (2010). "Forward-Backward Error: Automatic Detection of Tracking Failures." ICPR.
7. Fischler, M. A., & Bolles, R. C. (1981). "Random Sample Consensus: A Paradigm for Model Fitting." Communications of the ACM.
8. Nister, D. (2004). "An Efficient Solution to the Five-Point Relative Pose Problem." IEEE TPAMI.
9. Kalman, R. E. (1960). "A New Approach to Linear Filtering and Prediction Problems." Journal of Basic Engineering.
10. Geiger, A., Ziegler, J., & Stiller, C. (2011). "StereoScan: Dense 3D Reconstruction in Real-time." IEEE Intelligent Vehicles Symposium.

## Known Limitations

1. **No absolute scale**: Monocular VO cannot determine real-world distances. Each motion step has unit magnitude. To get metric scale, integrate with GPS or vehicle speed data.
2. **Performance**: Mask R-CNN runs per-frame, which is the bottleneck. On CPU this is very slow; a CUDA GPU is strongly recommended.
3. **Pure rotation**: When the vehicle rotates in place (e.g., a tight parking manoeuvre), the essential matrix becomes degenerate because there is no translational component. The system will report stationary during these moments.
