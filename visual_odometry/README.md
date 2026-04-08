# Visual Odometry

Monocular visual odometry system that estimates a vehicle's 3D trajectory from a single dashcam video. Combines Shi-Tomasi feature detection, Lucas-Kanade optical flow tracking, essential matrix decomposition, and Kalman filter smoothing. Uses Mask R-CNN (ResNet50-FPN-V2) to mask out dynamic objects (cars, pedestrians) before feature tracking. Detects turning events based on accumulated yaw changes.

## Usage

### Console-only (no visualisation)

```bash
python3 vo_main.py <video_path> [--start <seconds>] [--stop <seconds>]
```

Prints per-frame logs to stdout. Saves trajectory plot and pose data on completion.

### With live visualisation

```bash
python3 vo_main.py <video_path> --show [--start <seconds>] [--stop <seconds>]
```

Opens a matplotlib window with the camera frame (dynamic objects highlighted) and a 3D trajectory plot.

### Re-plot from saved pose data

```bash
python3 vo_main.py <video_path> --from-pose <pose_file.npz>
```

### All arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `video` | *(required)* | Path to dashcam video file |
| `--start` | 0.0 | Start time in seconds |
| `--stop` | None | Stop time in seconds |
| `--show` | off | Live matplotlib visualisation |
| `--outdir` | video directory | Output directory for plot/pose files |
| `--no-save-plot` | off | Skip saving trajectory PNG |
| `--no-save-pose` | off | Skip saving pose .npz file |
| `--from-pose` | None | Re-create trajectory PNG from a saved .npz file |

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

## Files

| File | Description |
|------|-------------|
| `vo_main.py` | Full implementation: feature detection, optical flow, pose estimation, Kalman filter, turn detection, Mask R-CNN masking, visualisation |
| `__init__.py` | Package init |

## Dependencies

```bash
pip install opencv-python numpy torch torchvision matplotlib scipy
```

GPU recommended for Mask R-CNN inference. Falls back to CPU if CUDA is unavailable.
