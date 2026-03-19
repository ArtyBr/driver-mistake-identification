"""Load trips, labels, analysis results, and GPS data."""

import json
import os
import pickle
import re
import subprocess
from pathlib import Path

import pandas as pd

from config import VIDEO_BASE, GPS_CACHE_PATH


# ── Trip discovery ─────────────────────────────────────────────────────────

# Pattern: DD_MM_YY_descriptor_time_of_day
_TRIP_RE = re.compile(
    r"^(\d{2})_(\d{2})_(\d{2})_(.+?)_(day|night|rainy_day)$"
)


def discover_trips(video_base=None):
    """
    Walk *video_base* and return a list of trip dicts.

    Each dict:
        name, path, date, driver, route, condition,
        video_pairs (list of (road, face) tuples),
        has_labels (bool), has_results (bool)
    """
    base = Path(video_base) if video_base else VIDEO_BASE
    trips = []
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        m = _TRIP_RE.match(entry.name)
        if not m:
            continue
        day, month, year, descriptor, condition = m.groups()
        # Parse driver from descriptor (first word before _to_ or _from_)
        driver = descriptor.split("_")[0]
        route = descriptor

        # Find F/I video pairs
        pairs = _find_video_pairs(entry)

        trips.append({
            "name": entry.name,
            "path": entry,
            "date": f"20{year}-{month}-{day}",
            "driver": driver,
            "route": route,
            "condition": condition,
            "video_pairs": pairs,
            "has_labels": (entry / "event_labels.json").exists(),
            "has_results": any((entry / "results").exists() for _ in [1]),  # placeholder
        })
    return trips


def _find_video_pairs(trip_dir):
    """Find matching road (F) / face (I) video pairs in a trip folder."""
    files = {f.name: f for f in trip_dir.iterdir() if f.suffix.upper() == ".MP4"}

    road_files = sorted(
        [f for name, f in files.items() if name.endswith(("F.MP4", "F.mp4"))],
        key=lambda p: p.name,
    )

    pairs = []
    for road in road_files:
        face = find_face_video(road)
        if face and face.exists():
            pairs.append((road, face))
    return pairs


def find_face_video(road_path):
    """
    Given a road video like 2025_0901_210641_004610F.MP4,
    find the corresponding face video 2025_0901_210641_004611I.MP4.

    The face video has the same timestamp prefix but sequence number +1 and suffix I.
    """
    road_path = Path(road_path)
    name = road_path.stem  # e.g. 2025_0901_210641_004610F
    # Match: timestamp_seqF
    m = re.match(r"^(.+_)(\d+)F$", name, re.IGNORECASE)
    if not m:
        return None
    prefix, seq_str = m.groups()
    face_seq = str(int(seq_str) + 1).zfill(len(seq_str))
    face_name = f"{prefix}{face_seq}I{road_path.suffix}"
    face_path = road_path.parent / face_name
    # Also try uppercase/lowercase variants
    if not face_path.exists():
        for variant in [face_name.upper(), face_name]:
            candidate = road_path.parent / variant
            if candidate.exists():
                return candidate
    return face_path


# ── Ground truth labels ────────────────────────────────────────────────────

def load_ground_truth(label_path):
    """
    Load event_labels.json (may have trailing commas).

    Returns dict: {video_id: [(time_seconds, event_type), ...]}
    """
    text = Path(label_path).read_text()
    # Strip trailing commas before } or ]
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    raw = json.loads(text)

    labels = {}
    for video_id, events in raw.items():
        parsed = []
        for time_str, event_type in events.items():
            seconds = _mmss_to_seconds(time_str)
            parsed.append((seconds, event_type))
        parsed.sort(key=lambda x: x[0])
        labels[video_id] = parsed
    return labels


def _mmss_to_seconds(mmss):
    """Convert 'MM:SS' string to float seconds."""
    parts = mmss.split(":")
    return int(parts[0]) * 60 + int(parts[1])


# ── Analysis results ───────────────────────────────────────────────────────

def load_results(results_path):
    """Load a results.json file."""
    with open(results_path) as f:
        return json.load(f)


# ── GPS extraction ─────────────────────────────────────────────────────────

def extract_gps(video_path, cache=None):
    """
    Extract GPS track from a video file using exiftool.

    Returns a DataFrame with columns: datetime, lat, lon, speed_kmh, track.
    Uses cache dict (keyed by path string) if provided.
    """
    key = str(video_path)
    if cache is not None and key in cache:
        return cache[key]

    try:
        result = subprocess.run(
            [
                "exiftool", "-ee", "-n", "-p",
                "$GPSDateTime,$GPSLatitude,$GPSLongitude,$GPSSpeed,$GPSTrack",
                str(video_path),
            ],
            capture_output=True, text=True, timeout=60,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return pd.DataFrame()

    rows = []
    for line in result.stdout.strip().split("\n"):
        parts = line.split(",")
        if len(parts) >= 4:
            try:
                rows.append({
                    "datetime": parts[0].strip(),
                    "lat": float(parts[1]),
                    "lon": float(parts[2]),
                    "speed_kmh": float(parts[3]) if parts[3].strip() else 0.0,
                    "track": float(parts[4]) if len(parts) > 4 and parts[4].strip() else 0.0,
                })
            except (ValueError, IndexError):
                continue

    df = pd.DataFrame(rows)
    if cache is not None:
        cache[key] = df
    return df


def extract_trip_gps(trip, cache=None):
    """Concatenate GPS from all road (F) videos in a trip."""
    frames = []
    for road, _face in trip["video_pairs"]:
        df = extract_gps(road, cache=cache)
        if not df.empty:
            df["video"] = road.stem
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def load_gps_cache():
    """Load pickled GPS cache from disk."""
    if GPS_CACHE_PATH.exists():
        with open(GPS_CACHE_PATH, "rb") as f:
            return pickle.load(f)
    return {}


def save_gps_cache(cache):
    """Persist GPS cache to disk."""
    GPS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GPS_CACHE_PATH, "wb") as f:
        pickle.dump(cache, f)
