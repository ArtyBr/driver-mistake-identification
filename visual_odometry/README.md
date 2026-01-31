# Visual Odometry Module

This module implements a Monocular Visual Odometry (VO) system using OpenCV and Python. It estimates the trajectory of a vehicle from a video feed using feature tracking (optical flow) and geometric pose estimation.

## Prerequisites

Ensure you have the following Python libraries installed. You can install them using pip:

```bash
pip install opencv-python numpy matplotlib
```

## Structure

- `vo_main.py`: The main Python script containing the `VisualOdometry` class and execution logic.
- `visual_odometry_plan.md`: The detailed implementation plan and architectural decisions.
- `README.md`: This file.

## Usage

To run the visual odometry on a video file, use the following command from the root of the project or the `visual_odometry` directory:

```bash
python visual_odometry/vo_main.py <path_to_video_file>
```

### Example

```bash
python3 visual_odometry/vo_main.py /media/arty/3A30-14F9/Videos/02_09_25_me_to_gym_day/2025_0902_152136_004634F.MP4
```

## Configuration

The camera intrinsic parameters (Intrinsic Matrix `K` and Distortion Coefficients `D`) are hardcoded in `vo_main.py` based on the calibration data provided in `@camera_calibration/calibration_3.txt`. If you use a different camera, you must update these matrices in the `__init__` method of the `VisualOdometry` class.

## Controls

- The script opens a 3D Matplotlib window showing the car's trajectory in real-time.
- Press **'q'** in the console or close the window to stop the execution (if video window is enabled).
- The visualization updates every 5 frames for performance.
