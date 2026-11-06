# Lane Detection

Wrapper around the third-party [lanedet](https://github.com/Turoad/lanedet) library for lane detection from dashcam video. The combined analysis pipeline calls into lanedet programmatically via `combined_analysis/src/lane_detector.py`.

## Setup

```bash
cd lane_detection/lanedet
conda env create -f environment.yml
conda activate lanedet
pip install -e .
```

## Model Weights

Download from https://github.com/Turoad/lanedet/releases/tag/1.0 and place in `lanedet/weights/`.

The primary model used in this project is **LaneAtt with ResNet-18** (`laneatt_r18_culane.pth`), trained on the CULane dataset.

## Usage

### Training

```bash
python3 lanedet/main.py <config> --gpus 0 [--load_from <checkpoint>] [--validate]
```

### Inference

```bash
python3 lanedet/tools/detect.py <config> \
    --img <image_dir> OR --vid <video_dir> \
    --load_from <weights> \
    --savedir <output_dir>
```

### Example

```bash
python3 lanedet/tools/detect.py \
    lanedet/configs/laneatt/resnet18_culane.py \
    --vid /path/to/videos \
    --load_from lanedet/weights/laneatt_r18_culane.pth \
    --savedir ./vis
```

## Files

| File/Directory | Description |
|----------------|-------------|
| `lanedet/` | Third-party lanedet library (configs, models, tools) |
| `lanedet/configs/` | Model architecture configs (LaneAtt, RESA, CondLane, SCNN, UFLD) |
| `lanedet/weights/` | Model weight files (gitignored, download separately) |
| `lanedet/tools/detect.py` | Standalone inference script |

## Dependencies

See `lanedet/environment.yml` for the full conda environment specification.
