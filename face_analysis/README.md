# Face Analysis

Head pose data collection and exploratory analysis for the gaze classification system. This module contains the datasets and notebooks used to develop the PCA+SVM gaze classifier that powers the production pipeline in `combined_analysis/src/face_analyzer.py`.

## Files

| File | Description |
|------|-------------|
| `angle_analysis_unsupervised.ipynb` | Jupyter notebook: unsupervised K-means clustering of head pose angles to discover natural gaze direction clusters |
| `head_pose_data.csv` | Collected head pose measurements (yaw, pitch, roll) with labels |
| `head_pose_data_01.csv` | Additional head pose measurement dataset |
| `head_pose_data_insightface.csv` | Head pose data collected using InsightFace detector |
| `models/` | Pre-trained model files (e.g., MediaPipe face landmarker) |
| `data/` | Labeled frame output from data collection scripts |

## Dependencies

```bash
pip install numpy scikit-learn jupyter matplotlib insightface
```
