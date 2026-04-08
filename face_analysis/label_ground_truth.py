"""
Ground truth labelling tool for gaze classification benchmark.

Opens a video segment and displays every Nth frame for manual labelling.
Labels are saved as a JSON file for later use in benchmarking.

Controls (ordered left-to-right as they appear in the video):
    1 = Right Mirror
    2 = Looking Ahead
    3 = Rear Mirror
    4 = Left Mirror
    s = Skip frame (no label)
    q = Quit early
"""

import cv2
import json
import argparse
import sys
from pathlib import Path

CLASS_MAP = {
    ord('1'): 'Right Mirror',
    ord('2'): 'Looking Ahead',
    ord('3'): 'Rear Mirror',
    ord('4'): 'Left Mirror',
}


def label_video(video_path, start_sec, end_sec, every_n, output_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {video_path}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS)
    start_frame = int(start_sec * fps)
    end_frame = int(end_sec * fps)
    total_to_label = (end_frame - start_frame) // every_n

    print(f"Video: {video_path}")
    print(f"FPS: {fps}")
    print(f"Segment: {start_sec}s - {end_sec}s (frames {start_frame}-{end_frame})")
    print(f"Labelling every {every_n} frame(s) → {total_to_label} frames to label")
    print()
    print("Controls (left-to-right as in video):")
    print("  1 = Right Mirror")
    print("  2 = Looking Ahead")
    print("  3 = Rear Mirror")
    print("  4 = Left Mirror")
    print("  s = Skip (no label)")
    print("  q = Quit")
    print()

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    labels = {}
    frame_idx = start_frame
    labelled_count = 0
    skipped_count = 0

    window_name = "Label: 1=Right 2=Ahead 3=Rear 4=Left | s=Skip q=Quit"

    while frame_idx < end_frame:
        ret, frame = cap.read()
        if not ret:
            print("End of video reached.")
            break

        # Only label every Nth frame
        if (frame_idx - start_frame) % every_n != 0:
            frame_idx += 1
            continue

        # Draw info overlay
        display = frame.copy()
        progress = f"Frame {frame_idx} | {labelled_count}/{total_to_label} labelled | {skipped_count} skipped"
        cv2.putText(display, progress, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        time_sec = frame_idx / fps
        cv2.putText(display, f"Time: {time_sec:.2f}s", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow(window_name, display)
        key = cv2.waitKey(0) & 0xFF

        if key == ord('q'):
            print("Quitting early...")
            break
        elif key == ord('s'):
            skipped_count += 1
            print(f"  Frame {frame_idx}: skipped")
        elif key in CLASS_MAP:
            label = CLASS_MAP[key]
            labels[str(frame_idx)] = label
            labelled_count += 1
            print(f"  Frame {frame_idx}: {label}")
        else:
            # Unknown key — show reminder and wait again on same frame
            print(f"  Unknown key. Press 1-4, s, or q.")
            continue

        frame_idx += 1

    cap.release()
    cv2.destroyAllWindows()

    # Save labels
    output = {
        "video_path": video_path,
        "fps": fps,
        "start_sec": start_sec,
        "end_sec": end_sec,
        "every_n": every_n,
        "start_frame": start_frame,
        "end_frame": end_frame,
        "labels": labels,
    }

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved {len(labels)} labels to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Label video frames for gaze ground truth")
    parser.add_argument("--video", type=str,
                        default="/media/arty/3A30-14F9/Videos/blur_test/2026_0221_160806_018912I.MP4")
    parser.add_argument("--start", type=float, default=27.0, help="Start time in seconds")
    parser.add_argument("--end", type=float, default=34.0, help="End time in seconds")
    parser.add_argument("--every-n", type=int, default=2, help="Label every Nth frame")
    parser.add_argument("--output", type=str, default="ground_truth_labels.json",
                        help="Output JSON path")
    args = parser.parse_args()

    label_video(args.video, args.start, args.end, args.every_n, args.output)
