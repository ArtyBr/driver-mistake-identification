# Source Code Documentation

This directory contains the core modules for the Unified Driver Analysis System. The system is designed following modular principles to separate video processing, computer vision analysis, visualization, and safety logic.

## Module Overview

### 1. `main.py` (Project Root)
The entry point of the application. It handles:
- Environment and path setup (injecting `src/` and `lane_detection/` into `sys.path`).
- Argument parsing.
- Orchestrating the initialization of all major components.

### 2. `video_processor.py`
The heart of the system. It contains the `VideoProcessor` class which:
- Manages synchronized video capture for both Road and Face cameras.
- Orchestrates the main processing loop.
- Delegates analysis to `LaneDetectorWrapper` and `FaceAnalyzer`.
- Maintains the driver's state history (e.g., gaze direction over time).
- Calls the `SafetyMonitor` to validate driving maneuvers.
- Uses `VideoVisualizer` to compose the final output frame.

### 3. `lane_detector.py`
A wrapper around the external LaneAtt library and the internal `LaneTracker`.
- **Input:** Raw road video frame.
- **Output:** Visualized frame with lane overlays, raw polynomial coefficients, and instantaneous "lane cross" events.

### 4. `lane_tracking.py`
Contains the Kalman Filter logic for stabilizing lane detections over time.
- **`LaneTrack`**: Represents a single lane line, its history, and its state.
- **`LaneTracker`**: Manages multiple tracks, performs data association between frames, and detects when a vehicle crosses a lane boundary.

### 5. `face_analyzer.py`
Utilizes InsightFace and custom SVM/PCA models to analyze the driver.
- Performs face detection.
- Estimates head pose (Yaw, Pitch, Roll).
- Classifies direction into "Looking Ahead", "Left Mirror", or "Right Mirror".
- Returns raw analytical data without drawing on the frame (SRP compliance).

### 6. `safety_monitor.py`
The "brain" that combines environment data with driver behavior.
- **`ManeuverValidator`**: Checks if driving maneuvers are safe.
- **Lane Change Validation**: When a lane change is detected, it queries the last 5 seconds of `FaceAnalyzer` history to ensure the appropriate mirror check was performed.
- Returns `SafetyEvent` objects which contain severity levels and descriptive messages.

### 7. `visualization.py`
Handles all UI and HUD elements.
- Draws the "Driver Feed" overlay.
- Draws the "Driver Status" and "Event Log" panels.
- Renders safety alerts (Safe/Unsafe) prominently on the screen.
- Provides utility functions for styled text and semi-transparent HUD panels.

### 8. `config.py` & `utils.py`
- **`config.py`**: Centralized constants (resolutions, class names, history durations).
- **`utils.py`**: Low-level helpers for path manipulation, coordinate scaling, and configuration patching.

## Data Flow

1. **Capture**: `VideoProcessor` reads frames from Road and Face videos.
2. **Vision Analysis**:
   - Road frame -> `LaneDetector` -> Lane Tracks + Cross Events.
   - Face frame -> `FaceAnalyzer` -> Gaze Direction.
3. **Logic**:
   - `VideoProcessor` updates `state_history` with the latest gaze direction.
   - If a `cross_event` occurs, `SafetyMonitor` scans `state_history` for a valid mirror check.
4. **Composition**:
   - `VideoVisualizer` takes all analysis results and draws them onto the Road frame.
5. **Output**: Result is displayed to screen and/or written to an MP4 file.

## Extension Guide

- **Adding new maneuvers**: Add a validation method in `ManeuverValidator` and trigger it in `VideoProcessor` when the corresponding environment event is detected.
- **Adding new face states**: Update `CLASS_NAMES` in `config.py` and ensure the SVM model in `face_analysis/models/` is trained for the new classes.

to run:
`python3 ./combined_analysis/main.py ./lane_detection/lanedet/configs/condlane/resnet101_culane.py     --video_base /media/arty/3A30-14F9/Videos/13_09_25_me_to_cov_day/2025_0913_103653_007442      --load_from ./lane_detection/lanedet/weights/condlane_r101_culane.pth   --show --show_dets`
