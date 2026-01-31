# Visual Odometry Implementation Plan

## Goal
Create a Python module (`vo_main.py`) within `visual_odometry/` to perform Monocular Visual Odometry (VO) on a video file. The system will track the vehicle's trajectory in 3D space using the provided camera intrinsic parameters.

## 1. Prerequisites & Dependencies
- **Python 3.x**
- **OpenCV (`cv2`)**: For image processing, feature tracking, and geometric calculations.
- **NumPy (`numpy`)**: For matrix operations.
- **Matplotlib (`matplotlib`)**: For real-time 3D trajectory visualization.

## 2. Configuration & Calibration
Embed or load the specific intrinsic parameters from `@camera_calibration/calibration_3.txt`.

**Intrinsic Matrix ($K$):**
```python
K = np.array([
    [993.6305137521725, 0.0, 954.7271539229214],
    [0.0, 1144.329008082279, 539.4773780846734],
    [0.0, 0.0, 1.0]
])
```

**Distortion Coefficients ($D$):**
```python
D = np.array([0.09120135029599218, 0.03431960504192815, -0.027375346575880814, -0.017942890066237845, -0.6799011067187613])
```

## 3. Class Structure: `VisualOdometry`

### 3.1 Initialization (`__init__`)
- Store $K$ and $D$.
- Initialize trajectory variables:
  - Current Rotation ($R_{curr}$): $3 \times 3$ Identity matrix.
  - Current Translation ($t_{curr}$): $3 \times 1$ Zero vector.
- Initialize previous frame storage and keypoints.

### 3.2 Image Preprocessing (`_process_frame`)
- Convert frame to grayscale.
- **Undistortion:** Apply `cv2.undistort` using $K$ and $D$ to remove lens distortion before calculating geometry. This is critical for accurate linear tracking.

### 3.3 Feature Detection & Tracking
We will use a standard Optical Flow approach:
1.  **Initialization:** For the very first frame, detect features using **FAST** or **Shi-Tomasi** (via `cv2.goodFeaturesToTrack`).
2.  **Tracking:** Use **Lucas-Kanade Optical Flow** (`cv2.calcOpticalFlowPyrLK`) to track features from `frame_{i-1}` to `frame_{i}`.
3.  **Maintenance:** If the number of tracked points drops below a threshold (e.g., < 2000), re-detect new features to maintain a robust track.

### 3.4 Pose Estimation
1.  **Essential Matrix ($E$):** Compute $E$ using `cv2.findEssentialMat` with the matched points from the optical flow and the camera focal length/principal point.
    - Method: `cv2.RANSAC` to reject outliers.
2.  **Recover Pose:** Extract relative rotation ($R$) and translation ($t$) from $E$ using `cv2.recoverPose`.
3.  **Scale Handling (Monocular Limitation):**
    - Monocular VO cannot determine absolute scale (speed).
    - **Strategy:** Since we lack CAN bus speed data in this isolated module, we will simply normalize the translation vector ($t$) or assume a constant scale factor of `1.0`.
    - *Note:* In a production car system, we would multiply $t$ by the vehicle's current speed * time_delta.

### 3.5 Trajectory Update
Accumulate the global pose:
$$t_{curr} = t_{curr} + scale \times (R_{curr} \times t)$$
$$R_{curr} = R \times R_{curr}$$
(Note: Matrix multiplication order depends on whether coordinates are world-centric or camera-centric. We will follow standard OpenCV convention).

## 4. Visualization (Real-time 3D Graph)
- Use `matplotlib.pyplot` with `projection='3d'`.
- Maintain lists of X, Y, Z coordinates.
- In the main loop, after processing a frame:
  1.  Append new $t_{curr}$ coordinates to the lists.
  2.  Clear the previous plot (or update data efficiently).
  3.  Plot the full trajectory.
  4.  Draw the "car" (current point) with a distinct marker.
  5.  `plt.pause(0.001)` to render the update.

## 5. Main Execution Flow (`main`)
1.  Parse arguments (path to video file).
2.  Open video capture (`cv2.VideoCapture`).
3.  Instantiate `VisualOdometry` class.
4.  Loop through video frames:
    - Read frame.
    - Pass to VO object to get estimated translation `(x, y, z)`.
    - Update 3D visualization.
    - Display the camera view with tracked features overlaid (for debugging).
    - Exit on 'q' key or end of video.

## 6. Directory Structure
```
visual_odometry/
├── visual_odometry_plan.md  <-- This file
├── vo_main.py               <-- The implementation
└── README.md                <-- Instructions for running
```
