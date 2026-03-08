#!/usr/bin/env python3
"""
VO Benchmark Testing Suite

Runs the Visual Odometry pipeline with different feature combinations toggled
on/off, producing trajectory plots and evaluation metrics for each configuration.

Usage:
    python visual_odometry/testing/benchmark_vo.py \
        --video <cut_video_path> \
        --labels <turn_labels_json> \
        --gps-video <full_video_path> \
        --gps-start 60 --gps-end 105 \
        --configs baseline fb_only fb_grid fb_grid_mask full
"""

import argparse
import csv
import gc
import json
import math
import os
import re
import subprocess
import sys
import time
from datetime import datetime

import cv2
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, PROJECT_ROOT)

from visual_odometry.vo_main import VisualOdometry

# ---------------------------------------------------------------------------
# Configuration Definitions
# ---------------------------------------------------------------------------

CONFIGS = {
    'baseline': {
        'use_fb_validation': False, 'use_bucketing': False,
        'use_masking': False, 'use_kalman': False,
        'label': 'Baseline (raw VO)',
    },
    'fb_only': {
        'use_fb_validation': True, 'use_bucketing': False,
        'use_masking': False, 'use_kalman': False,
        'label': '+ Forward-Backward',
    },
    'fb_grid': {
        'use_fb_validation': True, 'use_bucketing': True,
        'use_masking': False, 'use_kalman': False,
        'label': '+ Grid Bucketing',
    },
    'fb_grid_mask': {
        'use_fb_validation': True, 'use_bucketing': True,
        'use_masking': True, 'use_kalman': False,
        'label': '+ Mask R-CNN',
    },
    'full': {
        'use_fb_validation': True, 'use_bucketing': True,
        'use_masking': True, 'use_kalman': True,
        'label': 'Full System',
    },
}

CONFIG_ORDER = ['baseline', 'fb_only', 'fb_grid', 'fb_grid_mask', 'full']
CONFIG_COLORS = {
    'baseline': '#e74c3c',
    'fb_only': '#e67e22',
    'fb_grid': '#f1c40f',
    'fb_grid_mask': '#2ecc71',
    'full': '#3498db',
}

# ---------------------------------------------------------------------------
# GPS Extraction & Processing
# ---------------------------------------------------------------------------

def extract_gps_from_video(video_path, start_sec, end_sec):
    """Extract GPS points from a dashcam video using exiftool.
    Returns list of dicts with keys: time_sec, lat, lon, speed, track.
    """
    try:
        result = subprocess.run(
            ['exiftool', '-G1', '-a', '-s', '-ee', '-gps*', video_path],
            capture_output=True, text=True, timeout=120,
        )
    except FileNotFoundError:
        print("WARNING: exiftool not found. GPS comparison will be skipped.")
        return []
    except subprocess.TimeoutExpired:
        print("WARNING: exiftool timed out. GPS comparison will be skipped.")
        return []

    if result.returncode != 0:
        print(f"WARNING: exiftool failed: {result.stderr}")
        return []

    lines = result.stdout.strip().split('\n')

    # Parse into per-sample blocks. Exiftool outputs repeated GPS tags for each
    # embedded sample. We group by GPSDateTime.
    gps_points = []
    current = {}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Format: [GroupName]  TagName   : Value
        m = re.match(r'\[.*?\]\s+(\w+)\s*:\s*(.*)', line)
        if not m:
            continue
        tag, value = m.group(1), m.group(2).strip()

        if tag == 'GPSDateTime':
            # Flush previous point if any
            if current.get('GPSDateTime'):
                gps_points.append(current)
            current = {'GPSDateTime': value}
        elif tag == 'GPSLatitude':
            current['GPSLatitude'] = value
        elif tag == 'GPSLongitude':
            current['GPSLongitude'] = value
        elif tag == 'GPSSpeed':
            current['GPSSpeed'] = value
        elif tag == 'GPSTrack':
            current['GPSTrack'] = value

    # Flush last point
    if current.get('GPSDateTime'):
        gps_points.append(current)

    if not gps_points:
        print("WARNING: No GPS data found in video.")
        return []

    # Parse the first GPS timestamp as reference
    ref_time = _parse_gps_datetime(gps_points[0]['GPSDateTime'])
    if ref_time is None:
        print("WARNING: Could not parse GPS timestamps.")
        return []

    filtered = []
    for pt in gps_points:
        t = _parse_gps_datetime(pt['GPSDateTime'])
        if t is None:
            continue
        elapsed = (t - ref_time).total_seconds()
        if start_sec <= elapsed <= end_sec:
            lat = _parse_dms(pt.get('GPSLatitude', ''))
            lon = _parse_dms(pt.get('GPSLongitude', ''))
            if lat is not None and lon is not None:
                speed = _parse_numeric(pt.get('GPSSpeed', ''))
                track = _parse_numeric(pt.get('GPSTrack', ''))
                filtered.append({
                    'time_sec': elapsed - start_sec,
                    'lat': lat, 'lon': lon,
                    'speed': speed, 'track': track,
                })

    print(f"GPS: extracted {len(filtered)} points in window [{start_sec}s, {end_sec}s]")
    return filtered


def _parse_gps_datetime(s):
    """Parse GPS DateTime string like '2025:09:16 13:47:25Z'."""
    from datetime import datetime as dt
    for fmt in ('%Y:%m:%d %H:%M:%SZ', '%Y:%m:%d %H:%M:%S', '%Y-%m-%dT%H:%M:%SZ'):
        try:
            return dt.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _parse_dms(s):
    """Parse DMS coordinate string like `52 deg 17' 30.12" N` to decimal degrees."""
    if not s:
        return None
    m = re.match(r"""([\d.]+)\s*deg\s*([\d.]+)'\s*([\d.]+)"\s*([NSEW])""", s)
    if not m:
        # Try decimal format
        m2 = re.match(r'([+-]?[\d.]+)', s)
        if m2:
            return float(m2.group(1))
        return None
    d, mins, secs, direction = float(m.group(1)), float(m.group(2)), float(m.group(3)), m.group(4)
    dec = d + mins / 60.0 + secs / 3600.0
    if direction in ('S', 'W'):
        dec = -dec
    return dec


def _parse_numeric(s):
    """Extract first numeric value from a string like '23.5 km/h'."""
    if not s:
        return 0.0
    m = re.match(r'([+-]?[\d.]+)', s)
    return float(m.group(1)) if m else 0.0


def gps_to_local_enu(gps_points):
    """Convert GPS lat/lon to local East-North-Up metric coordinates.
    Uses equirectangular projection from first point as origin.
    Returns Nx2 array of [east, north] in meters.
    """
    if not gps_points:
        return np.empty((0, 2))

    lat0 = math.radians(gps_points[0]['lat'])
    lon0 = gps_points[0]['lon']
    lat0_deg = gps_points[0]['lat']

    coords = []
    for pt in gps_points:
        east = (pt['lon'] - lon0) * math.cos(lat0) * 111320.0
        north = (pt['lat'] - lat0_deg) * 111320.0
        coords.append([east, north])
    return np.array(coords)


# ---------------------------------------------------------------------------
# Procrustes Alignment
# ---------------------------------------------------------------------------

def procrustes_align(vo_points, gps_points):
    """Align VO trajectory to GPS using Procrustes analysis.
    Both inputs are Nx2 arrays. Returns aligned VO points and residual (meters).
    """
    assert len(vo_points) == len(gps_points), \
        f"Point count mismatch: VO={len(vo_points)}, GPS={len(gps_points)}"

    # Center both
    vo_centroid = vo_points.mean(axis=0)
    gps_centroid = gps_points.mean(axis=0)
    vo_c = vo_points - vo_centroid
    gps_c = gps_points - gps_centroid

    # SVD for optimal rotation
    M = gps_c.T @ vo_c  # 2x2
    U, S, Vt = np.linalg.svd(M)

    # Optimal rotation (handle reflection)
    d = np.linalg.det(U @ Vt)
    D = np.diag([1, np.sign(d)])
    R = U @ D @ Vt

    # Optimal scale
    vo_var = np.sum(vo_c ** 2)
    if vo_var < 1e-12:
        return vo_points, float('inf')
    scale = np.sum(S) / vo_var

    # Apply transform
    aligned = scale * (vo_c @ R.T) + gps_centroid

    # Residual
    residual = np.mean(np.linalg.norm(aligned - gps_points, axis=1))
    return aligned, residual


def compute_path_length(points):
    """Compute total path length of Nx2 point array."""
    if len(points) < 2:
        return 0.0
    diffs = np.diff(points, axis=0)
    return float(np.sum(np.linalg.norm(diffs, axis=1)))


# ---------------------------------------------------------------------------
# Ground Truth Turn Labels
# ---------------------------------------------------------------------------

def load_turn_labels(labels_path):
    """Load ground truth turn labels from JSON.
    Format: {"MM:SS": "left turn" | "right turn", ...}
    Returns list of (time_seconds, direction_str).
    """
    with open(labels_path, 'r') as f:
        data = json.load(f)

    labels = []
    for timestamp, direction in data.items():
        parts = timestamp.split(':')
        secs = int(parts[0]) * 60 + int(parts[1])
        dir_str = 'LEFT' if 'left' in direction.lower() else 'RIGHT'
        labels.append((secs, dir_str))
    return sorted(labels, key=lambda x: x[0])


# ---------------------------------------------------------------------------
# Metrics Computation
# ---------------------------------------------------------------------------

def compute_smoothness_metrics(frame_stats, fps):
    """Compute trajectory smoothness metrics from frame stats."""
    positions = np.array([[s['pos_x'], s['pos_z']] for s in frame_stats])
    if len(positions) < 4:
        return {'mean_abs_jerk': 0, 'curvature_variance': 0, 'spike_count': 0}

    # Velocity (1st derivative)
    vel = np.diff(positions, axis=0) * fps
    # Acceleration (2nd derivative)
    acc = np.diff(vel, axis=0) * fps
    # Jerk (3rd derivative)
    jerk = np.diff(acc, axis=0) * fps

    jerk_mag = np.linalg.norm(jerk, axis=1)
    mean_abs_jerk = float(np.mean(jerk_mag))

    # Curvature approximation: |v x a| / |v|^3
    vel_2d = vel[:-1]  # align with acc
    speed = np.linalg.norm(vel_2d, axis=1)
    cross = vel_2d[:, 0] * acc[:, 1] - vel_2d[:, 1] * acc[:, 0]
    # Avoid division by zero
    speed_cubed = np.maximum(speed ** 3, 1e-10)
    curvature = np.abs(cross) / speed_cubed
    curvature_var = float(np.var(curvature[speed > 0.1]))  # Only where moving

    # Position spikes
    displacements = np.linalg.norm(np.diff(positions, axis=0), axis=1)
    mean_d = np.mean(displacements)
    std_d = np.std(displacements)
    spike_count = int(np.sum(displacements > mean_d + 3 * std_d))

    return {
        'mean_abs_jerk': mean_abs_jerk,
        'curvature_variance': curvature_var,
        'spike_count': spike_count,
    }


def compute_tracking_metrics(frame_stats):
    """Compute feature tracking quality metrics."""
    moving_frames = [s for s in frame_stats if s['is_moving']]
    non_blind = [s for s in frame_stats if not s['is_blind']]

    if not moving_frames:
        return {
            'mean_inlier_ratio': 0,
            'mean_feature_count': 0,
            'tracking_loss_rate': 1.0,
        }

    mean_inlier = float(np.mean([s['inlier_ratio'] for s in moving_frames]))
    mean_features = float(np.mean([s['feature_count'] for s in frame_stats]))

    # Tracking loss: non-blind frames with 0 features
    loss_frames = [s for s in non_blind if s['feature_count'] == 0]
    loss_rate = len(loss_frames) / max(len(non_blind), 1)

    return {
        'mean_inlier_ratio': mean_inlier,
        'mean_feature_count': mean_features,
        'tracking_loss_rate': loss_rate,
    }


def compute_turn_metrics(detected_turns, ground_truth, fps, tolerance_sec=3.0):
    """Compute turn detection precision, recall, F1, direction accuracy.
    detected_turns: list of (frame_number, direction_str)
    ground_truth: list of (time_seconds, direction_str)
    """
    if not ground_truth:
        return {
            'precision': 0, 'recall': 0, 'f1': 0,
            'direction_accuracy': 0, 'mean_timing_error': 0,
            'tp': 0, 'fp': 0, 'fn': 0,
        }

    tolerance_frames = tolerance_sec * fps

    # Convert detected turns to seconds
    detected_sec = [(frame / fps, d) for frame, d in detected_turns]

    # Match detections to ground truth (greedy, closest first)
    gt_matched = [False] * len(ground_truth)
    det_matched = [False] * len(detected_sec)
    direction_correct = 0
    timing_errors = []

    for gi, (gt_time, gt_dir) in enumerate(ground_truth):
        best_di = None
        best_err = float('inf')
        for di, (det_time, det_dir) in enumerate(detected_sec):
            if det_matched[di]:
                continue
            err = abs(det_time - gt_time)
            if err <= tolerance_sec and err < best_err:
                best_err = err
                best_di = di
        if best_di is not None:
            gt_matched[gi] = True
            det_matched[best_di] = True
            timing_errors.append(best_err)
            if detected_sec[best_di][1] == gt_dir:
                direction_correct += 1

    tp = sum(gt_matched)
    fp = sum(1 for m in det_matched if not m)
    fn = sum(1 for m in gt_matched if not m)

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-10)
    dir_acc = direction_correct / max(tp, 1)
    mean_timing = float(np.mean(timing_errors)) if timing_errors else 0.0

    return {
        'precision': precision, 'recall': recall, 'f1': f1,
        'direction_accuracy': dir_acc, 'mean_timing_error': mean_timing,
        'tp': tp, 'fp': fp, 'fn': fn,
    }


# ---------------------------------------------------------------------------
# Run a Single Configuration
# ---------------------------------------------------------------------------

def run_config(config_name, config, video_path, output_dir, ground_truth_turns, fps_override=None):
    """Run VO with a specific configuration and return metrics."""
    print(f"\n{'='*60}")
    print(f"Running config: {config_name} ({config['label']})")
    print(f"  FB={config['use_fb_validation']}, Grid={config['use_bucketing']}, "
          f"Mask={config['use_masking']}, KF={config['use_kalman']}")
    print(f"{'='*60}")

    os.makedirs(output_dir, exist_ok=True)

    t_start = time.time()

    vo = VisualOdometry(
        video_path=video_path,
        use_kalman=config['use_kalman'],
        use_masking=config['use_masking'],
        use_bucketing=config['use_bucketing'],
        use_fb_validation=config['use_fb_validation'],
    )

    fps = vo.fps if fps_override is None else fps_override

    # Process all frames
    while True:
        ret, _, _, _, _ = vo.process_frame()
        if not ret:
            break

    t_elapsed = time.time() - t_start

    # Release video
    if vo.cap:
        vo.cap.release()

    # Collect results
    traj_x = np.array(vo.traj_x)
    traj_z = np.array(vo.traj_z)
    frame_stats = vo.frame_stats
    total_frames = vo.frame_count

    # Collect detected turns
    detected_turns = []
    for s in frame_stats:
        if s['turn_event']:
            direction = 'LEFT' if 'LEFT' in s['turn_event'] else 'RIGHT'
            detected_turns.append((s['frame'], direction))

    # --- Save per-config outputs ---

    # 1. Trajectory plot
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.plot(traj_x, traj_z, color=CONFIG_COLORS.get(config_name, 'blue'), linewidth=1.5)
    # Mark turns
    for frame, direction in detected_turns:
        idx = min(frame, len(traj_x) - 1)
        marker = 'c*' if direction == 'LEFT' else 'm*'
        label = f'Turn {direction}'
        ax.plot(traj_x[idx], traj_z[idx], marker, markersize=12)
    ax.set_title(f"Trajectory: {config_name} ({config['label']})")
    ax.set_xlabel('X')
    ax.set_ylabel('Z')
    ax.set_aspect('equal', adjustable='datalim')
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'trajectory_xz.png'), dpi=150)
    plt.close(fig)

    # 2. Frame stats CSV
    if frame_stats:
        csv_path = os.path.join(output_dir, 'frame_stats.csv')
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=frame_stats[0].keys())
            writer.writeheader()
            writer.writerows(frame_stats)

    # 3. Turns detected JSON
    turns_json = [{'frame': f, 'time_sec': f / fps, 'direction': d} for f, d in detected_turns]
    with open(os.path.join(output_dir, 'turns_detected.json'), 'w') as f:
        json.dump(turns_json, f, indent=2)

    # --- Compute metrics ---
    smoothness = compute_smoothness_metrics(frame_stats, fps)
    tracking = compute_tracking_metrics(frame_stats)
    turns = compute_turn_metrics(detected_turns, ground_truth_turns, fps)

    metrics = {
        'config': config_name,
        'label': config['label'],
        'total_frames': total_frames,
        'wall_time_sec': round(t_elapsed, 2),
        'ms_per_frame': round(t_elapsed / max(total_frames, 1) * 1000, 2),
        'fps': fps,
        **{f'smooth_{k}': v for k, v in smoothness.items()},
        **{f'track_{k}': v for k, v in tracking.items()},
        **{f'turn_{k}': v for k, v in turns.items()},
    }

    # Cleanup
    del vo
    gc.collect()
    try:
        import torch
        torch.cuda.empty_cache()
    except Exception:
        pass

    return metrics, traj_x, traj_z, detected_turns, frame_stats


# ---------------------------------------------------------------------------
# GPS Comparison
# ---------------------------------------------------------------------------

def add_gps_metrics(metrics, traj_x, traj_z, gps_enu, fps):
    """Add GPS alignment metrics to a config's metrics dict."""
    if gps_enu is None or len(gps_enu) < 2:
        metrics['gps_procrustes_residual'] = None
        metrics['gps_path_length_ratio'] = None
        return None

    # Subsample VO to 1Hz (every fps-th point)
    step = max(1, int(round(fps)))
    vo_2d = np.column_stack([traj_x, traj_z])
    vo_sub = vo_2d[::step]

    # Match lengths (take the shorter)
    n = min(len(vo_sub), len(gps_enu))
    if n < 3:
        metrics['gps_procrustes_residual'] = None
        metrics['gps_path_length_ratio'] = None
        return None

    vo_sub = vo_sub[:n]
    gps_sub = gps_enu[:n]

    aligned, residual = procrustes_align(vo_sub, gps_sub)

    vo_path_len = compute_path_length(aligned)
    gps_path_len = compute_path_length(gps_sub)
    path_ratio = vo_path_len / max(gps_path_len, 1e-10)

    metrics['gps_procrustes_residual'] = round(residual, 4)
    metrics['gps_path_length_ratio'] = round(path_ratio, 4)

    return aligned


# ---------------------------------------------------------------------------
# Summary Plots
# ---------------------------------------------------------------------------

def generate_summary(all_results, gps_enu, run_dir):
    """Generate comparison plots and summary CSV."""
    summary_dir = os.path.join(run_dir, 'summary')
    os.makedirs(summary_dir, exist_ok=True)

    config_names = [r['metrics']['config'] for r in all_results]
    colors = [CONFIG_COLORS.get(n, 'gray') for n in config_names]

    # --- 1. Comparison Table CSV ---
    csv_path = os.path.join(summary_dir, 'comparison_table.csv')
    if all_results:
        fieldnames = list(all_results[0]['metrics'].keys())
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in all_results:
                writer.writerow(r['metrics'])

    # --- 2. Trajectory Overlay ---
    fig, ax = plt.subplots(figsize=(12, 10))
    for r in all_results:
        name = r['metrics']['config']
        ax.plot(r['traj_x'], r['traj_z'],
                color=CONFIG_COLORS.get(name, 'gray'),
                linewidth=1.5, label=CONFIGS[name]['label'], alpha=0.8)
    ax.set_title('Trajectory Comparison (All Configs)')
    ax.set_xlabel('X')
    ax.set_ylabel('Z')
    ax.set_aspect('equal', adjustable='datalim')
    ax.legend()
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(os.path.join(summary_dir, 'trajectory_overlay.png'), dpi=150)
    plt.close(fig)

    # --- 3. GPS Comparison ---
    if gps_enu is not None and len(gps_enu) >= 2:
        n_configs = len(all_results)
        fig, axes = plt.subplots(1, n_configs, figsize=(5 * n_configs, 5), squeeze=False)
        for i, r in enumerate(all_results):
            ax = axes[0][i]
            ax.plot(gps_enu[:, 0], gps_enu[:, 1], 'b-', linewidth=2.5, alpha=0.7, label='GPS')
            if r.get('aligned_vo') is not None:
                ax.plot(r['aligned_vo'][:, 0], r['aligned_vo'][:, 1],
                        color=CONFIG_COLORS.get(r['metrics']['config'], 'red'),
                        linewidth=1.5, alpha=0.8, label='VO (aligned)')
            residual = r['metrics'].get('gps_procrustes_residual')
            res_str = f"{residual:.2f}m" if residual is not None else "N/A"
            ax.set_title(f"{r['metrics']['config']}\nResidual: {res_str}", fontsize=10)
            ax.set_aspect('equal', adjustable='datalim')
            ax.legend(fontsize=8)
            ax.grid(True)
        fig.suptitle('GPS vs VO Trajectory (Procrustes-aligned)', fontsize=14)
        fig.tight_layout()
        fig.savefig(os.path.join(summary_dir, 'gps_comparison.png'), dpi=150)
        plt.close(fig)

    # --- 4. Smoothness Comparison ---
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    labels = [CONFIGS[n]['label'] for n in config_names]

    jerk_vals = [r['metrics']['smooth_mean_abs_jerk'] for r in all_results]
    axes[0].barh(labels, jerk_vals, color=colors)
    axes[0].set_title('Mean Absolute Jerk (lower=better)')
    axes[0].set_xlabel('Jerk')

    curv_vals = [r['metrics']['smooth_curvature_variance'] for r in all_results]
    axes[1].barh(labels, curv_vals, color=colors)
    axes[1].set_title('Curvature Variance (lower=better)')
    axes[1].set_xlabel('Variance')

    spike_vals = [r['metrics']['smooth_spike_count'] for r in all_results]
    axes[2].barh(labels, spike_vals, color=colors)
    axes[2].set_title('Position Spike Count (lower=better)')
    axes[2].set_xlabel('Spikes')

    fig.suptitle('Trajectory Smoothness Comparison', fontsize=14)
    fig.tight_layout()
    fig.savefig(os.path.join(summary_dir, 'smoothness_comparison.png'), dpi=150)
    plt.close(fig)

    # --- 5. Turn Detection Comparison ---
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    prec_vals = [r['metrics']['turn_precision'] for r in all_results]
    axes[0].barh(labels, prec_vals, color=colors)
    axes[0].set_title('Precision')
    axes[0].set_xlim(0, 1.1)

    rec_vals = [r['metrics']['turn_recall'] for r in all_results]
    axes[1].barh(labels, rec_vals, color=colors)
    axes[1].set_title('Recall')
    axes[1].set_xlim(0, 1.1)

    f1_vals = [r['metrics']['turn_f1'] for r in all_results]
    axes[2].barh(labels, f1_vals, color=colors)
    axes[2].set_title('F1 Score')
    axes[2].set_xlim(0, 1.1)

    fig.suptitle('Turn Detection Comparison', fontsize=14)
    fig.tight_layout()
    fig.savefig(os.path.join(summary_dir, 'turn_detection_comparison.png'), dpi=150)
    plt.close(fig)

    # --- 6. Full metrics JSON ---
    all_metrics = [r['metrics'] for r in all_results]
    with open(os.path.join(summary_dir, 'metrics.json'), 'w') as f:
        json.dump(all_metrics, f, indent=2, default=str)

    print(f"\nSummary outputs saved to: {summary_dir}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='VO Benchmark Testing Suite')
    parser.add_argument('--video', required=True, help='Path to cut video file')
    parser.add_argument('--labels', required=True, help='Path to turn labels JSON')
    parser.add_argument('--gps-video', default=None, help='Path to full (untrimmed) video with GPS')
    parser.add_argument('--gps-start', type=float, default=60, help='GPS window start (seconds into full video)')
    parser.add_argument('--gps-end', type=float, default=105, help='GPS window end (seconds into full video)')
    parser.add_argument('--configs', nargs='*', default=None,
                        help='Subset of configs to run (default: all)',
                        choices=CONFIG_ORDER)
    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(f"Error: Video file not found: {args.video}")
        sys.exit(1)
    if not os.path.exists(args.labels):
        print(f"Error: Labels file not found: {args.labels}")
        sys.exit(1)

    # Determine which configs to run
    configs_to_run = args.configs if args.configs else CONFIG_ORDER

    # Create output directory next to video
    video_dir = os.path.dirname(os.path.abspath(args.video))
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_dir = os.path.join(video_dir, 'benchmark_results', f'run_{timestamp}')
    os.makedirs(run_dir, exist_ok=True)
    print(f"Output directory: {run_dir}")

    # Load ground truth
    ground_truth_turns = load_turn_labels(args.labels)
    print(f"Ground truth: {len(ground_truth_turns)} turns loaded")
    for t, d in ground_truth_turns:
        print(f"  {t}s: {d}")

    # Extract GPS if available
    gps_points = []
    gps_enu = None
    if args.gps_video:
        if os.path.exists(args.gps_video):
            gps_points = extract_gps_from_video(args.gps_video, args.gps_start, args.gps_end)
            if gps_points:
                gps_enu = gps_to_local_enu(gps_points)
                print(f"GPS ENU coordinates: {len(gps_enu)} points")
        else:
            print(f"WARNING: GPS video not found: {args.gps_video}")

    # Run each configuration
    all_results = []
    for config_name in configs_to_run:
        config = CONFIGS[config_name]
        config_dir = os.path.join(run_dir, config_name)

        metrics, traj_x, traj_z, detected_turns, frame_stats = run_config(
            config_name, config, args.video, config_dir, ground_truth_turns,
        )

        # GPS alignment
        aligned_vo = add_gps_metrics(metrics, traj_x, traj_z, gps_enu, metrics['fps'])

        all_results.append({
            'metrics': metrics,
            'traj_x': traj_x,
            'traj_z': traj_z,
            'detected_turns': detected_turns,
            'aligned_vo': aligned_vo,
        })

        # Print summary for this config
        print(f"\n--- {config_name} Results ---")
        print(f"  Time: {metrics['wall_time_sec']}s ({metrics['ms_per_frame']} ms/frame)")
        print(f"  Smoothness - Jerk: {metrics['smooth_mean_abs_jerk']:.2f}, "
              f"Spikes: {metrics['smooth_spike_count']}")
        print(f"  Tracking - Inlier: {metrics['track_mean_inlier_ratio']:.3f}, "
              f"Features: {metrics['track_mean_feature_count']:.0f}, "
              f"Loss: {metrics['track_tracking_loss_rate']:.3f}")
        print(f"  Turns - P: {metrics['turn_precision']:.2f}, "
              f"R: {metrics['turn_recall']:.2f}, "
              f"F1: {metrics['turn_f1']:.2f}, "
              f"Dir: {metrics['turn_direction_accuracy']:.2f}")
        if metrics.get('gps_procrustes_residual') is not None:
            print(f"  GPS - Residual: {metrics['gps_procrustes_residual']:.4f}m, "
                  f"Path ratio: {metrics['gps_path_length_ratio']:.4f}")

    # Generate summary
    generate_summary(all_results, gps_enu, run_dir)

    print(f"\n{'='*60}")
    print(f"Benchmark complete. Results at: {run_dir}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
