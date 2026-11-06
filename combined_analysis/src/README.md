# Combined Analysis -- Source Modules

Core modules for the dual-stream driver safety analysis pipeline.

## Files

| Module | Description |
|--------|-------------|
| `video_processor.py` | Central controller: manages synchronised video capture, orchestrates analysis, maintains gaze history, triggers safety checks |
| `lane_detector.py` | Wrapper around LaneAtt for lane detection; outputs polynomial coefficients and lane-cross events |
| `lane_tracking.py` | Kalman filter tracker for smoothing lane detections and detecting lane change events |
| `face_analyzer.py` | InsightFace face detection + head pose estimation + PCA/SVM gaze classification |
| `safety_monitor.py` | Rule engine: on lane change trigger, queries 5-second gaze history to validate mirror checks |
| `visualization.py` | OpenCV overlay rendering (lane lines, face boxes, gaze vectors, safety alerts) |
| `config.py` | Centralised constants (class names, history duration, model dimensions) |
| `utils.py` | Path helpers, coordinate scaling, config patching |

## Data Flow

1. `VideoProcessor` reads synchronised frames from road and face videos
2. Road frame passes through `LaneDetectorWrapper` and `LaneTracker` for lane positions and crossing events
3. Face frame passes through `FaceAnalyzer` for gaze direction classification
4. On lane change event, `SafetyMonitor` checks gaze history for the required mirror check
5. `VideoVisualizer` composes the annotated output frame (interactive mode only)
