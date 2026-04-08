"""
Benchmark KMeans vs SVM gaze classification models against ground truth labels.

Reads ground truth JSON (from label_ground_truth.py), runs InsightFace head pose
extraction on each labelled frame, classifies with both PCA+KMeans and PCA+SVM,
and produces:
  - Per-model accuracy, precision, recall, F1 (macro & per-class)
  - Confusion matrices (printed + saved as PNG)
  - Side-by-side comparison table
"""

import json
import pickle
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from insightface.app import FaceAnalysis
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay,
)
from scipy.optimize import linear_sum_assignment
import matplotlib.pyplot as plt


CLASS_NAMES = {0: 'Left Mirror', 1: 'Right Mirror', 2: 'Looking Ahead', 3: 'Rear Mirror'}
LABEL_TO_IDX = {v: k for k, v in CLASS_NAMES.items()}
CLASS_LIST = [CLASS_NAMES[i] for i in range(4)]


def load_models(models_dir, kmeans_path=None):
    models_dir = Path(models_dir)
    with open(models_dir / 'pca_head_pose_model.pkl', 'rb') as f:
        pca = pickle.load(f)
    with open(models_dir / 'svm_head_pose_model.pkl', 'rb') as f:
        svm = pickle.load(f)
    km_file = Path(kmeans_path) if kmeans_path else models_dir / 'kmeans_model.pkl'
    with open(km_file, 'rb') as f:
        kmeans = pickle.load(f)
    print(f"  KMeans model: {km_file}")
    return pca, svm, kmeans


def find_driver_face(faces, frame_shape):
    """Identify the driver face (same logic as FaceAnalyzer)."""
    if not faces:
        return None
    h, w = frame_shape[:2]
    is_landscape = w > h

    def face_area(f):
        bbox = f.bbox
        return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])

    if is_landscape:
        left_faces = [f for f in faces if (f.bbox[0] + f.bbox[2]) / 2 < w / 2]
        if left_faces:
            return max(left_faces, key=face_area)
    return max(faces, key=face_area)


def extract_poses(video_path, frame_indices):
    """Extract head pose (yaw, pitch, roll) for each frame index using InsightFace."""
    print("Initializing InsightFace...")
    app = FaceAnalysis(providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
    app.prepare(ctx_id=0, det_size=(640, 640))

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        sys.exit(1)

    poses = {}
    sorted_indices = sorted(frame_indices)

    for i, fidx in enumerate(sorted_indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES, fidx)
        ret, frame = cap.read()
        if not ret:
            print(f"  Warning: Could not read frame {fidx}")
            continue

        faces = app.get(frame)
        driver = find_driver_face(faces, frame.shape)
        if driver is None:
            print(f"  Warning: No face detected in frame {fidx}")
            continue

        pitch, yaw, roll = driver.pose if hasattr(driver, 'pose') and driver.pose is not None else (0, 0, 0)
        poses[fidx] = {'yaw': float(yaw), 'pitch': float(pitch), 'roll': float(roll)}

        if (i + 1) % 20 == 0 or i == len(sorted_indices) - 1:
            print(f"  Processed {i + 1}/{len(sorted_indices)} frames")

    cap.release()
    return poses


def find_best_cluster_mapping(gt_labels, km_predictions, n_classes=4):
    """
    Find the optimal mapping from KMeans cluster IDs to class labels
    using the Hungarian algorithm on a cost matrix.
    """
    cost_matrix = np.zeros((n_classes, n_classes))
    for gt, pred in zip(gt_labels, km_predictions):
        cost_matrix[pred, gt] += 1

    # Hungarian algorithm minimizes cost, so negate (we want max matches)
    row_ind, col_ind = linear_sum_assignment(-cost_matrix)
    mapping = {row: col for row, col in zip(row_ind, col_ind)}
    return mapping


def run_benchmark(gt_path, models_dir, output_dir, kmeans_path=None):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load ground truth
    with open(gt_path) as f:
        gt_data = json.load(f)

    video_path = gt_data['video_path']
    labels = gt_data['labels']  # {frame_idx_str: class_name}
    print(f"Loaded {len(labels)} ground truth labels from {gt_path}")

    frame_indices = [int(k) for k in labels.keys()]
    gt_class_indices = [LABEL_TO_IDX[labels[k]] for k in labels.keys()]

    # Extract poses
    poses = extract_poses(video_path, frame_indices)

    # Filter to frames where face was detected
    valid_frames = [k for k in labels.keys() if int(k) in poses]
    if len(valid_frames) < len(labels):
        print(f"  Face detected in {len(valid_frames)}/{len(labels)} labelled frames")

    gt_indices = [LABEL_TO_IDX[labels[k]] for k in valid_frames]
    pose_data = [poses[int(k)] for k in valid_frames]

    # Build input matrix
    df = pd.DataFrame(pose_data, columns=['yaw', 'pitch', 'roll'])

    # Load models
    pca, svm, kmeans = load_models(models_dir, kmeans_path)

    # PCA transform
    pca_transformed = pca.transform(df)

    # SVM predictions
    svm_preds = svm.predict(pca_transformed).tolist()

    # KMeans predictions (raw cluster IDs)
    km_raw_preds = kmeans.predict(pca_transformed).tolist()

    # Find best cluster→class mapping
    km_mapping = find_best_cluster_mapping(gt_indices, km_raw_preds)
    km_preds = [km_mapping[p] for p in km_raw_preds]

    print(f"\nKMeans cluster → class mapping (via Hungarian algorithm):")
    for cluster_id, class_id in sorted(km_mapping.items()):
        print(f"  Cluster {cluster_id} → {CLASS_NAMES[class_id]}")

    # Convert to label strings for reporting
    gt_labels = [CLASS_NAMES[i] for i in gt_indices]
    svm_labels = [CLASS_NAMES[i] for i in svm_preds]
    km_labels = [CLASS_NAMES[i] for i in km_preds]

    # --- Metrics ---
    print("\n" + "=" * 70)
    print("SVM CLASSIFICATION REPORT")
    print("=" * 70)
    svm_report = classification_report(gt_labels, svm_labels, labels=CLASS_LIST, zero_division=0)
    print(svm_report)

    print("=" * 70)
    print("KMEANS CLASSIFICATION REPORT")
    print("=" * 70)
    km_report = classification_report(gt_labels, km_labels, labels=CLASS_LIST, zero_division=0)
    print(km_report)

    # --- Summary comparison ---
    svm_acc = accuracy_score(gt_labels, svm_labels)
    km_acc = accuracy_score(gt_labels, km_labels)
    svm_f1 = f1_score(gt_labels, svm_labels, labels=CLASS_LIST, average='macro', zero_division=0)
    km_f1 = f1_score(gt_labels, km_labels, labels=CLASS_LIST, average='macro', zero_division=0)
    svm_prec = precision_score(gt_labels, svm_labels, labels=CLASS_LIST, average='macro', zero_division=0)
    km_prec = precision_score(gt_labels, km_labels, labels=CLASS_LIST, average='macro', zero_division=0)
    svm_rec = recall_score(gt_labels, svm_labels, labels=CLASS_LIST, average='macro', zero_division=0)
    km_rec = recall_score(gt_labels, km_labels, labels=CLASS_LIST, average='macro', zero_division=0)

    print("=" * 70)
    print("SUMMARY COMPARISON")
    print("=" * 70)
    summary = pd.DataFrame({
        'Metric': ['Accuracy', 'Precision (macro)', 'Recall (macro)', 'F1 (macro)'],
        'SVM': [f"{svm_acc:.3f}", f"{svm_prec:.3f}", f"{svm_rec:.3f}", f"{svm_f1:.3f}"],
        'KMeans': [f"{km_acc:.3f}", f"{km_prec:.3f}", f"{km_rec:.3f}", f"{km_f1:.3f}"],
    })
    print(summary.to_string(index=False))

    # --- Confusion matrices ---
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    svm_cm = confusion_matrix(gt_labels, svm_labels, labels=CLASS_LIST)
    ConfusionMatrixDisplay(svm_cm, display_labels=CLASS_LIST).plot(
        ax=axes[0], cmap='Blues', values_format='d', xticks_rotation=45
    )
    axes[0].set_title('SVM Confusion Matrix')

    km_cm = confusion_matrix(gt_labels, km_labels, labels=CLASS_LIST)
    ConfusionMatrixDisplay(km_cm, display_labels=CLASS_LIST).plot(
        ax=axes[1], cmap='Oranges', values_format='d', xticks_rotation=45
    )
    axes[1].set_title('KMeans Confusion Matrix')

    plt.tight_layout()
    cm_path = output_dir / 'confusion_matrices.png'
    plt.savefig(cm_path, dpi=150, bbox_inches='tight')
    print(f"\nConfusion matrices saved to {cm_path}")
    plt.close()

    # --- Save metrics to JSON ---
    metrics = {
        'n_frames': len(valid_frames),
        'svm': {
            'accuracy': svm_acc,
            'precision_macro': svm_prec,
            'recall_macro': svm_rec,
            'f1_macro': svm_f1,
            'confusion_matrix': svm_cm.tolist(),
        },
        'kmeans': {
            'accuracy': km_acc,
            'precision_macro': km_prec,
            'recall_macro': km_rec,
            'f1_macro': km_f1,
            'cluster_mapping': {str(k): CLASS_NAMES[v] for k, v in km_mapping.items()},
            'confusion_matrix': km_cm.tolist(),
        },
        'class_names': CLASS_LIST,
    }
    metrics_path = output_dir / 'benchmark_metrics.json'
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"Metrics saved to {metrics_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark KMeans vs SVM gaze models")
    parser.add_argument("--gt", type=str, default="ground_truth_labels.json",
                        help="Path to ground truth JSON from label_ground_truth.py")
    parser.add_argument("--models-dir", type=str, default="models",
                        help="Directory containing PCA, SVM, and KMeans .pkl files")
    parser.add_argument("--output-dir", type=str, default="benchmark_output",
                        help="Directory to save results")
    parser.add_argument("--kmeans-model", type=str, default=None,
                        help="Path to a specific KMeans .pkl file (overrides models-dir default)")
    args = parser.parse_args()

    run_benchmark(args.gt, args.models_dir, args.output_dir, args.kmeans_model)
