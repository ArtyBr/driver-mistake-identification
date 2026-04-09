# Combined Analysis Pipeline

The core analysis engine for the SafeDrive system. Processes dual video streams (road-facing + driver-facing) frame-by-frame, detecting lane changes via LaneAtt and classifying driver gaze via InsightFace + PCA/SVM. A safety monitor correlates lane change events with a 5-second gaze history buffer to flag unsafe manoeuvres (e.g., merging without checking mirrors).

This pipeline powers the web application at https://safedrive.dcs.warwick.ac.uk/.

## Usage

### Interactive mode (with visualisation)

```bash
python3 main.py <config> \
    --road <road.mp4> \
    --face <face.mp4> \
    --load_from <weights> \
    --savedir <output_dir> \
    --show \
    --start_seconds 0 \
    --end_seconds 60
```

| Argument | Default | Description |
|----------|---------|-------------|
| `config` | *(required)* | Path to LaneAtt config (e.g., `../lane_detection/lanedet/configs/laneatt/resnet18_culane.py`) |
| `--road` | *(required)* | Path to road-facing video |
| `--face` | *(required)* | Path to driver-facing video |
| `--load_from` | `best.pth` | Path to lane detection model weights |
| `--savedir` | `data/output` | Output directory for results |
| `--show` | off | Display real-time visualisation window |
| `--start_seconds` | 0.0 | Start processing at this timestamp |
| `--end_seconds` | None | Stop processing at this timestamp |

### Headless mode (batch processing, used by web app)

```bash
python3 run_headless.py \
    --road <road.mp4> \
    --face <face.mp4> \
    --output <results.json> \
    [--flip_face] \
    [--models_dir <custom_models>] \
    [--road_meta <json>] \
    [--face_meta <json>]
```

### Recalibration (re-classify gaze with new PCA+SVM models)

```bash
python3 recalibrate_headless.py \
    --results_path <results.json> \
    --models_dir <models_directory> \
    [--output <output.json>]
```

No GPU or video I/O required -- re-classifies stored head pose angles and replays safety logic in seconds.

## Files

| File | Description |
|------|-------------|
| `main.py` | Entry point for interactive analysis with visualisation |
| `run_headless.py` | Entry point for headless batch processing (invoked by web backend) |
| `recalibrate_headless.py` | Lightweight re-analysis with alternative gaze models |
| `src/` | Core modules (see [`src/README.md`](src/README.md)) |
| `tests/` | Unit tests |
| `data/` | Input/output data directory (gitignored) |

## Dependencies

```bash
pip install torch torchvision opencv-python insightface scikit-learn numpy scipy tqdm
```

Requires the `lane_detection/lanedet` package to be installed (see [`../lane_detection/README.md`](../lane_detection/README.md)).
