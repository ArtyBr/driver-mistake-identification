# Unified Driver Analysis System

This system combines Lane Detection (using LaneAtt) and Face Analysis (using InsightFace) to monitor driver behavior and environment.

## Architecture

The project has been refactored into a modular structure:

- **`main.py`**: The entry point. Handles argument parsing and system initialization.
- **`video_processor.py`**: core processing loop, handling video I/O, synchronization, and visualization.
- **`lane_detector.py`**: Wrapper around the lane detection library and tracking logic.
- **`lane_tracking.py`**: Kalman filter-based lane tracking (formerly `helper_classes.py`).
- **`face_analyzer.py`**: Face detection and head pose estimation.
- **`config.py`**: Shared constants and configuration.
- **`utils.py`**: Helper functions.

## Usage

To run the analysis:

```bash
python3 main.py <path_to_lane_config> \
    --video_base <path_to_video_base> \
    --load_from <path_to_weights> \
    --savedir <output_directory> \
    [--show] [--start_seconds S] [--end_seconds E]
```

### Example

```bash
python3 main.py ./lane_detection/lanedet/configs/laneatt/resnet18_culane.py \
    --video_base /media/arty/3A30-14F9/Videos/01_09_25_me_to_wp_night/2025_0901_211242_004616 \
    --load_from ./lane_detection/lanedet/weights/laneatt_r18_culane.pth \
    --savedir ./combined_analysis/data/output/ \
    --show
```

Note: `video_base` should be the path to the video files *without* the `F.mp4` or `I.mp4` suffix.
