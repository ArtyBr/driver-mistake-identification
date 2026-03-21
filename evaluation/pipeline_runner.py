"""Run analysis pipeline on ±EVENT_WINDOW windows around labeled events."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from config import (
    EVENT_WINDOW, VIDEO_MAX_DURATION, PIPELINE_RESULTS_DIR,
    RUN_HEADLESS_PATH,
)
from data_loader import find_face_video


def compute_windows(events, window=EVENT_WINDOW, max_dur=VIDEO_MAX_DURATION):
    """
    Given a list of (time_seconds, event_type), compute merged ±window ranges.

    Returns list of (start, end) tuples, clamped to [0, max_dur].
    """
    if not events:
        return []

    raw = []
    for t, _ in events:
        s = max(0.0, t - window)
        e = min(max_dur, t + window)
        raw.append((s, e))
    raw.sort()

    merged = [raw[0]]
    for s, e in raw[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def run_pipeline_on_windows(trip_path, video_id, events, force=False,
                            global_progress=None, no_seg=False):
    """
    Run run_headless.py on each merged window for the given video.

    Parameters
    ----------
    trip_path : Path
        Path to the trip folder containing the videos.
    video_id : str
        Road video stem, e.g. "2025_0901_210641_004610F".
    events : list of (time_seconds, event_type)
        Ground truth events for this video.
    force : bool
        If True, re-run even if cached results exist.
    global_progress : dict or None
        If provided, a mutable dict with keys: done, total, elapsed, start_time
        for cross-video progress tracking.

    Returns
    -------
    list of dict
        Each dict: {window_start, window_end, results_path, video_id}
    """
    windows = compute_windows(events)
    if not windows:
        return []

    # Find video files
    road_path = _find_video_file(trip_path, video_id)
    if road_path is None:
        print(f"    WARNING: Road video not found: {video_id} in {trip_path}")
        return []

    face_path = find_face_video(road_path)
    road_only = False
    if face_path is None or not face_path.exists():
        print(f"    NOTE: Face video not found for {video_id} — running road-only (no gaze/safety)")
        face_path = road_path  # Use road video as face; gaze will be noise but lane/turn detection works
        road_only = True
        # Write marker so cached results loader knows this is road-only
        marker = PIPELINE_RESULTS_DIR / video_id / "road_only.marker"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()

    results = []
    for i, (ws, we) in enumerate(windows):
        out_dir = PIPELINE_RESULTS_DIR / video_id / f"window_{ws:.0f}_{we:.0f}"
        out_file = out_dir / "results.json"

        duration = we - ws
        if out_file.exists() and not force and _is_valid_json(out_file) and not _is_truncated(out_file, duration):
            print(f"      window {i+1}/{len(windows)}: {ws:.0f}s–{we:.0f}s — cached")
            results.append({
                "window_start": ws,
                "window_end": we,
                "results_path": out_file,
                "video_id": video_id,
                "road_only": road_only,
            })
            if global_progress:
                global_progress["done"] += 1
            continue

        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            sys.executable, str(RUN_HEADLESS_PATH),
            "--road", str(road_path),
            "--face", str(face_path),
            "--output", str(out_file),
            "--start_seconds", str(ws),
            "--end_seconds", str(we),
        ]
        if no_seg:
            cmd.append("--no-seg")

        # ~5 fps processing → ~6s per video-second, plus overhead; minimum 300s
        timeout = max(300, int(duration * 8) + 120)
        print(f"      window {i+1}/{len(windows)}: {ws:.0f}s–{we:.0f}s ({duration:.0f}s of video) — running ...", end="")
        t0 = time.time()
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
            )
            elapsed = time.time() - t0
            if proc.returncode != 0 and not out_file.exists():
                print(f" FAILED ({elapsed:.1f}s)")
                print(f"        stderr: {proc.stderr[-300:]}")
                continue
            elif proc.returncode != 0:
                # Process crashed during cleanup but results were written (e.g. free(): invalid pointer)
                print(f" done ({elapsed:.1f}s, exit code {proc.returncode} — results saved)")
            else:
                print(f" done ({elapsed:.1f}s)")
        except subprocess.TimeoutExpired:
            print(f" TIMEOUT (>{timeout}s)")
            # Check if results were written before timeout killed the process
            if not out_file.exists():
                continue

        if out_file.exists():
            # Validate that results aren't severely truncated (e.g. crash mid-processing)
            if _is_truncated(out_file, duration):
                print(f"        WARNING: results truncated (crash mid-processing), deleting")
                try:
                    out_file.unlink()
                except OSError:
                    pass
                continue
            results.append({
                "window_start": ws,
                "window_end": we,
                "results_path": out_file,
                "video_id": video_id,
                "road_only": road_only,
            })

        if global_progress:
            global_progress["done"] += 1
            _print_global_progress(global_progress)

    return results


def _is_truncated(results_path, expected_duration, min_ratio=0.7):
    """Check if results.json has far fewer frames than expected (crash mid-processing)."""
    try:
        import json as _json
        with open(results_path) as f:
            data = _json.load(f)
        n_frames = len(data.get("frame_data", []))
        fps = data.get("meta", {}).get("fps", 30)
        expected_frames = expected_duration * fps
        if expected_frames > 0 and n_frames / expected_frames < min_ratio:
            return True
    except Exception:
        return True  # corrupt = truncated
    return False


def _print_global_progress(gp):
    """Print a one-line global progress summary."""
    done = gp["done"]
    total = gp["total"]
    elapsed = time.time() - gp["start_time"]
    pct = done / total * 100 if total > 0 else 0
    if done > 0:
        eta = elapsed / done * (total - done)
        print(f"    ── overall: {done}/{total} windows ({pct:.0f}%), "
              f"elapsed {elapsed:.0f}s, ETA ~{eta:.0f}s ──")


def _is_valid_json(path):
    """Check if a file contains valid JSON."""
    try:
        with open(path) as f:
            json.load(f)
        return True
    except (json.JSONDecodeError, OSError):
        print(f"      WARNING: corrupt results file, will re-run: {path}")
        try:
            os.remove(path)
        except OSError:
            pass
        return False


def _find_video_file(trip_path, video_id):
    """Find the actual video file for a video_id (handles case sensitivity)."""
    try:
        for ext in [".MP4", ".mp4"]:
            candidate = trip_path / f"{video_id}{ext}"
            if candidate.exists():
                return candidate
        # Try case-insensitive search
        for f in trip_path.iterdir():
            if f.stem.upper() == video_id.upper() and f.suffix.upper() == ".MP4":
                return f
    except OSError as e:
        print(f"    WARNING: Cannot access {trip_path}: {e}")
    return None


def run_pipeline_for_trip(trip, labels, force=False, global_progress=None, no_seg=False):
    """
    Run pipeline on all labeled videos in a trip.

    Returns list of window result dicts.
    """
    all_results = []
    video_ids = list(labels.keys())
    for vi, (video_id, events) in enumerate(labels.items()):
        n_windows = len(compute_windows(events))
        print(f"    [{vi+1}/{len(video_ids)}] {video_id} "
              f"({len(events)} events → {n_windows} windows)")
        try:
            window_results = run_pipeline_on_windows(
                trip["path"], video_id, events, force=force,
                global_progress=global_progress, no_seg=no_seg,
            )
            all_results.extend(window_results)
        except OSError as e:
            print(f"    ERROR: I/O error processing {video_id}: {e}")
            print(f"    Skipping remaining videos in this trip.")
            break
    return all_results
