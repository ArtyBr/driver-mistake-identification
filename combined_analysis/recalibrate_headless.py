#!/usr/bin/env python3
"""recalibrate_headless.py — Lightweight re-analysis using stored head-pose data.

Re-classifies stored (yaw, pitch, roll) values with the user's PCA+SVM model,
then replays safety monitor logic against the new gaze labels.
No GPU, no video I/O — runs in seconds.
"""

import argparse
import json
import pickle
from pathlib import Path

CLASS_NAMES = {0: 'Left Mirror', 1: 'Right Mirror', 2: 'Looking Ahead', 3: 'Rear Mirror'}
HISTORY_DURATION = 5.0


def _load_model(models_dir: str):
    """Loads PCA and SVM pkl files from models_dir."""
    d = Path(models_dir)
    with open(d / "pca_head_pose_model.pkl", "rb") as f:
        pca = pickle.load(f)
    with open(d / "svm_head_pose_model.pkl", "rb") as f:
        svm = pickle.load(f)
    return pca, svm


def reclassify_frames(frame_data: list, svm, pca) -> None:
    """
    Batch-classifies all frames with valid pose data.
    Updates frame['face_info']['label'] and frame['current_state'] in-place.
    """
    import numpy as np

    indices = []
    poses = []
    for i, frame in enumerate(frame_data):
        fi = frame.get("face_info")
        if fi and fi.get("yaw") is not None:
            indices.append(i)
            poses.append([fi["yaw"], fi["pitch"], fi["roll"]])

    if not indices:
        return

    X = np.array(poses, dtype=float)
    X_pca = pca.transform(X)
    predictions = svm.predict(X_pca)

    for idx, pred in zip(indices, predictions):
        label = CLASS_NAMES[int(pred)]
        frame_data[idx]["face_info"]["label"] = label
        frame_data[idx]["current_state"] = label


def parse_required_mirror(message: str) -> str:
    """
    Extracts required_check from a safety_alert message.
    Checks Left Mirror before Right Mirror to handle "Rear and Left Mirror" correctly.
    """
    if "Left Mirror" in message:
        return "Left Mirror"
    if "Right Mirror" in message:
        return "Right Mirror"
    if "Rear Mirror" in message:
        return "Rear Mirror"
    return "Left Mirror"  # fallback


def parse_maneuver_label(message: str) -> str:
    """Extracts maneuver label from a safety_alert message."""
    # Format: "... before {maneuver_label}." or "... before {maneuver_label}!..."
    if "before " not in message:
        return "maneuver"
    after_before = message.split("before ", 1)[1]
    # Trim at "." or "!" (whichever comes first)
    end = len(after_before)
    for ch in ".!":
        idx = after_before.find(ch)
        if idx != -1 and idx < end:
            end = idx
    return after_before[:end].strip()


def replay_safety(timeline_events: list, frame_data: list) -> None:
    """
    Re-evaluates safety_alert events using updated gaze labels.
    Modifies timeline_events in-place.
    """
    # Build sorted [(time, label)] from frame_data (only frames with face data)
    frame_labels = sorted(
        [
            (frame["time"], frame["face_info"]["label"])
            for frame in frame_data
            if frame.get("face_info") and frame["face_info"].get("label")
        ],
        key=lambda x: x[0],
    )

    for event in timeline_events:
        if event.get("type") not in ("safety_alert", "turn_event"):
            continue

        T = float(event["timestamp"])
        required_check = parse_required_mirror(event["message"])

        # Scan labels in [T - HISTORY_DURATION, T]
        found_side = False
        found_rear = False
        for t, label in frame_labels:
            if t > T:
                break
            if (T - t) <= HISTORY_DURATION:
                if label == required_check:
                    found_side = True
                if label == "Rear Mirror":
                    found_rear = True

        maneuver_label = parse_maneuver_label(event["message"])

        if found_side:
            mirror_msg = required_check
            if found_rear:
                mirror_msg = f"Rear and {required_check}"
            event["message"] = f"SAFE: {mirror_msg} checked before {maneuver_label}."
            event["severity"] = "INFO"
            event["is_safe"] = True
        else:
            rear_note = " (Rear mirror look was detected)" if found_rear else ""
            event["message"] = f"UNSAFE: No {required_check} check before {maneuver_label}!{rear_note}"
            event["severity"] = "CRITICAL"
            event["is_safe"] = False


def main():
    parser = argparse.ArgumentParser(description="Recalibrate results.json with user's PCA+SVM model.")
    parser.add_argument("--results_path", required=True, help="Path to source results.json")
    parser.add_argument("--models_dir", required=True, help="Directory containing pca_head_pose_model.pkl and svm_head_pose_model.pkl")
    parser.add_argument("--output", default=None, help="Output path for updated results.json (defaults to overwrite source)")
    args = parser.parse_args()

    results_path = Path(args.results_path)
    output_path = Path(args.output) if args.output else results_path

    print(f"Loading results from: {results_path}")
    with open(results_path, "r") as f:
        results = json.load(f)

    print(f"Loading models from: {args.models_dir}")
    pca, svm = _load_model(args.models_dir)

    frame_data = results.get("frame_data", [])
    timeline_events = results.get("timeline_events", [])

    print(f"Reclassifying {len(frame_data)} frames...")
    reclassify_frames(frame_data, svm, pca)

    print(f"Replaying safety monitor for {len(timeline_events)} events...")
    replay_safety(timeline_events, frame_data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f)

    print(f"Done. Results written to: {output_path}")


if __name__ == "__main__":
    main()
