"""
Train a KMeans model on head pose data extracted from a video segment.

Extracts yaw/pitch/roll from every frame using InsightFace, applies PCA,
then fits KMeans on the PCA-transformed data.
"""

import pickle
import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from insightface.app import FaceAnalysis
from sklearn.cluster import KMeans


def find_driver_face(faces, frame_shape):
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


def main():
    parser = argparse.ArgumentParser(description="Train KMeans on head pose from video segment")
    parser.add_argument("--video", type=str, required=True)
    parser.add_argument("--start", type=float, required=True, help="Start time in seconds")
    parser.add_argument("--end", type=float, required=True, help="End time in seconds")
    parser.add_argument("--n-clusters", type=int, default=4)
    parser.add_argument("--pca-model", type=str, default="models/pca_head_pose_model.pkl",
                        help="Path to existing PCA model")
    parser.add_argument("--output", type=str, default="models/kmeans_head_pose_model_v2.pkl",
                        help="Output path for trained KMeans model")
    args = parser.parse_args()

    # Load PCA
    with open(args.pca_model, 'rb') as f:
        pca = pickle.load(f)
    print(f"Loaded PCA model from {args.pca_model}")

    # Init InsightFace
    print("Initializing InsightFace...")
    app = FaceAnalysis(providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
    app.prepare(ctx_id=0, det_size=(640, 640))

    # Open video
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"Error: Could not open video {args.video}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS)
    start_frame = int(args.start * fps)
    end_frame = int(args.end * fps)
    total_frames = end_frame - start_frame
    print(f"Video FPS: {fps}")
    print(f"Extracting poses from frames {start_frame}-{end_frame} ({total_frames} frames)")

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    poses = []
    frame_idx = start_frame
    no_face_count = 0

    while frame_idx < end_frame:
        ret, frame = cap.read()
        if not ret:
            break

        faces = app.get(frame)
        driver = find_driver_face(faces, frame.shape)
        if driver is None:
            no_face_count += 1
            frame_idx += 1
            continue

        pitch, yaw, roll = driver.pose if hasattr(driver, 'pose') and driver.pose is not None else (0, 0, 0)
        poses.append({'yaw': float(yaw), 'pitch': float(pitch), 'roll': float(roll)})

        if (frame_idx - start_frame + 1) % 100 == 0:
            print(f"  Processed {frame_idx - start_frame + 1}/{total_frames} frames")

        frame_idx += 1

    cap.release()
    print(f"  Extracted {len(poses)} poses ({no_face_count} frames with no face detected)")

    # PCA transform
    df = pd.DataFrame(poses, columns=['yaw', 'pitch', 'roll'])
    pca_data = pca.transform(df)

    # Train KMeans
    kmeans = KMeans(n_clusters=args.n_clusters, random_state=42, n_init=10)
    kmeans.fit(pca_data)
    print(f"  KMeans trained with {args.n_clusters} clusters")
    print(f"  Cluster centers:\n{kmeans.cluster_centers_}")

    # Save
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'wb') as f:
        pickle.dump(kmeans, f)
    print(f"  Saved KMeans model to {output_path}")


if __name__ == "__main__":
    main()
