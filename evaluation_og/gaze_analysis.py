"""Gaze distribution, transitions, head pose plots."""

import time
from collections import Counter

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from config import GAZE_LABELS, GAZE_COLORS, OUTPUT_DIR
from data_loader import load_results
from plotting_utils import setup_style, save_figure


def run_gaze_analysis(window_results):
    """
    Analyse gaze data from windowed pipeline results.

    Returns list of output Paths.
    """
    print(f"[Gaze Analysis] Processing {len(window_results)} windows ...")
    t0 = time.time()
    setup_style()
    outputs = []

    # Collect all frame-level gaze data
    all_labels = []           # flat list of gaze labels
    all_transitions = []      # list of (from_label, to_label)
    all_poses = []            # list of (yaw, pitch, roll, label)
    per_window_data = []      # per-window timeline data

    for wr in window_results:
        if wr.get("road_only"):
            continue  # Skip windows without real face video
        try:
            results = load_results(wr["results_path"])
        except Exception:
            continue

        frames = results.get("frame_data", [])
        if not frames:
            continue

        labels_seq = []
        poses_seq = []
        for f in frames:
            fi = f.get("face_info")
            label = f.get("current_state") or "Unknown"
            if fi:
                label = fi.get("label") or label
                poses_seq.append((
                    fi.get("yaw", 0), fi.get("pitch", 0), fi.get("roll", 0), label
                ))
            labels_seq.append(label)

        all_labels.extend(labels_seq)
        all_poses.extend(poses_seq)

        # Transitions
        for i in range(1, len(labels_seq)):
            if labels_seq[i] != labels_seq[i - 1]:
                all_transitions.append((labels_seq[i - 1], labels_seq[i]))

        per_window_data.append({
            "video_id": wr["video_id"],
            "window_start": wr["window_start"],
            "window_end": wr["window_end"],
            "labels": labels_seq,
            "poses": poses_seq,
            "fps": results.get("meta", {}).get("fps", 30),
        })

    if not all_labels:
        print("[Gaze Analysis] No gaze data found")
        return outputs, ""

    # ── 1. Gaze distribution pie chart ──
    label_counts = Counter(all_labels)
    fig, ax = plt.subplots(figsize=(7, 7))
    labels_sorted = sorted(label_counts.keys(), key=lambda x: -label_counts[x])
    sizes = [label_counts[l] for l in labels_sorted]
    colors = [GAZE_COLORS.get(l, "#999") for l in labels_sorted]
    ax.pie(sizes, labels=labels_sorted, autopct="%1.1f%%", colors=colors, startangle=90)
    ax.set_title("Gaze Distribution (all windows)")
    outputs.append(save_figure(fig, "gaze_distribution", "gaze"))

    # ── 2. Gaze timeline strips (up to 12 windows) ──
    n_windows = min(len(per_window_data), 12)
    if n_windows > 0:
        fig, axes = plt.subplots(n_windows, 1, figsize=(14, n_windows * 0.8 + 1),
                                  squeeze=False)
        for i in range(n_windows):
            wd = per_window_data[i]
            ax = axes[i, 0]
            _draw_gaze_strip(ax, wd["labels"], wd["fps"], wd["window_start"])
            ax.set_ylabel(f"{wd['video_id'][:20]}\n{wd['window_start']:.0f}s",
                          fontsize=7, rotation=0, ha="right", va="center")
        axes[0, 0].set_title("Gaze Timeline Strips")
        axes[-1, 0].set_xlabel("Time (s)")

        # Legend
        handles = [mpatches.Patch(color=GAZE_COLORS.get(l, "#999"), label=l)
                    for l in GAZE_LABELS if l in label_counts]
        fig.legend(handles=handles, loc="lower center", ncol=len(handles), fontsize=8)
        fig.tight_layout(rect=[0, 0.04, 1, 1])
        outputs.append(save_figure(fig, "gaze_timelines", "gaze"))

    # ── 3. Transition matrix heatmap ──
    if all_transitions:
        unique = sorted(set(l for pair in all_transitions for l in pair))
        n = len(unique)
        idx_map = {l: i for i, l in enumerate(unique)}
        matrix = np.zeros((n, n), dtype=int)
        for fr, to in all_transitions:
            matrix[idx_map[fr], idx_map[to]] += 1

        fig, ax = plt.subplots(figsize=(8, 7))
        im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto")
        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(unique, rotation=45, ha="right")
        ax.set_yticklabels(unique)
        ax.set_xlabel("To")
        ax.set_ylabel("From")
        ax.set_title("Gaze Transition Matrix")
        for i in range(n):
            for j in range(n):
                ax.text(j, i, str(matrix[i, j]), ha="center", va="center",
                        fontsize=8, color="white" if matrix[i, j] > matrix.max() / 2 else "black")
        fig.colorbar(im, ax=ax)
        outputs.append(save_figure(fig, "gaze_transitions", "gaze"))

    # ── 4. Mirror check stats ──
    mirror_labels = {"Left Mirror", "Right Mirror", "Rear Mirror"}
    mirror_counts = {l: label_counts.get(l, 0) for l in mirror_labels}
    total_frames = len(all_labels)
    total_seconds = total_frames / 30.0  # approximate

    stats_html = "<h3>Mirror Check Statistics</h3>"
    stats_html += f"<p>Total frames analysed: {total_frames} (~{total_seconds:.0f}s)</p>"
    stats_html += "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>"
    stats_html += "<tr><th>Mirror</th><th>Frames</th><th>% of Time</th><th>Per Minute</th></tr>"
    for label in sorted(mirror_labels):
        cnt = mirror_counts[label]
        pct = cnt / total_frames * 100 if total_frames > 0 else 0
        # Count transitions into this state as "checks"
        checks = sum(1 for _, to in all_transitions if to == label)
        per_min = checks / (total_seconds / 60) if total_seconds > 0 else 0
        stats_html += f"<tr><td>{label}</td><td>{cnt}</td><td>{pct:.1f}%</td><td>{per_min:.1f}</td></tr>"
    stats_html += "</table>"

    # ── 5. Head pose scatter (yaw vs pitch, colored by label) ──
    if all_poses:
        fig, ax = plt.subplots(figsize=(9, 7))
        for label in GAZE_LABELS:
            pts = [(y, p) for y, p, r, l in all_poses if l == label]
            if pts:
                ys, ps = zip(*pts)
                ax.scatter(ys, ps, alpha=0.15, s=8, label=label,
                           color=GAZE_COLORS.get(label, "#999"))
        ax.set_xlabel("Yaw (degrees)")
        ax.set_ylabel("Pitch (degrees)")
        ax.set_title("Head Pose Distribution by Gaze Label")
        ax.legend(markerscale=4)
        outputs.append(save_figure(fig, "head_pose_scatter", "gaze"))

    # ── 6. Head pose over time (first few windows) ──
    for wd in per_window_data[:4]:
        if not wd["poses"]:
            continue
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 5), sharex=True)
        fps = wd["fps"]
        n_frames = len(wd["poses"])
        times = [i / fps for i in range(n_frames)]
        yaws = [p[0] for p in wd["poses"]]
        pitches = [p[1] for p in wd["poses"]]
        rolls = [p[2] for p in wd["poses"]]

        ax1.plot(times, yaws, linewidth=0.6, label="Yaw", alpha=0.8)
        ax1.plot(times, pitches, linewidth=0.6, label="Pitch", alpha=0.8)
        ax1.plot(times, rolls, linewidth=0.6, label="Roll", alpha=0.8)
        ax1.set_ylabel("Degrees")
        ax1.legend(fontsize=8)
        ax1.set_title(f"Head Pose — {wd['video_id']} ({wd['window_start']:.0f}s–{wd['window_end']:.0f}s)")

        # Gaze label background on lower axis
        _draw_gaze_strip(ax2, wd["labels"][:n_frames], fps, 0)
        ax2.set_xlabel("Time (s)")
        ax2.set_ylabel("Gaze")

        fig.tight_layout()
        name = f"head_pose_{wd['video_id']}_{wd['window_start']:.0f}"
        outputs.append(save_figure(fig, name, "gaze"))

    elapsed = time.time() - t0
    print(f"[Gaze Analysis] Done ({elapsed:.1f}s) — {len(outputs)} plots")

    return outputs, stats_html


def _draw_gaze_strip(ax, labels, fps, time_offset):
    """Draw a colored horizontal strip of gaze states on an axis."""
    if not labels:
        return
    n = len(labels)
    # Build run-length encoding
    runs = []
    start = 0
    for i in range(1, n):
        if labels[i] != labels[start]:
            runs.append((start, i, labels[start]))
            start = i
    runs.append((start, n, labels[start]))

    for s, e, label in runs:
        t_start = s / fps
        t_end = e / fps
        color = GAZE_COLORS.get(label, "#999")
        ax.axvspan(t_start, t_end, alpha=0.6, color=color)

    ax.set_xlim(0, n / fps)
    ax.set_yticks([])
