"""Dataset overview: counts, durations, breakdowns."""

import time
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np

from config import OUTPUT_DIR, EVENT_COLORS, CONDITION_COLORS, VIDEO_MAX_DURATION
from plotting_utils import setup_style, save_figure


def run_dataset_stats(trips, all_labels):
    """
    Generate dataset statistics plots and summary.

    Parameters
    ----------
    trips : list of trip dicts
    all_labels : dict  {trip_name: {video_id: [(time_s, event_type), ...]}}

    Returns
    -------
    list of Path — generated files
    """
    print("[Dataset Stats] Generating overview ...")
    t0 = time.time()
    setup_style()
    outputs = []

    total_clips = sum(len(t["video_pairs"]) for t in trips)
    total_duration_min = total_clips * VIDEO_MAX_DURATION / 60
    labeled_trips = [t for t in trips if t["has_labels"]]
    labeled_clips = sum(
        len(all_labels.get(t["name"], {})) for t in labeled_trips
    )
    total_events = sum(
        len(evts) for labels in all_labels.values() for evts in labels.values()
    )

    # ── Pie chart: clips by driver ──
    driver_counts = Counter(t["driver"] for t in trips for _ in t["video_pairs"])
    if driver_counts:
        fig, ax = plt.subplots(figsize=(7, 7))
        ax.pie(
            driver_counts.values(), labels=driver_counts.keys(),
            autopct="%1.0f%%", startangle=90,
        )
        ax.set_title("Video Clips by Driver")
        outputs.append(save_figure(fig, "clips_by_driver", "stats"))

    # ── Bar chart: clips by condition ──
    cond_counts = Counter(t["condition"] for t in trips for _ in t["video_pairs"])
    if cond_counts:
        fig, ax = plt.subplots(figsize=(8, 5))
        conditions = list(cond_counts.keys())
        counts = [cond_counts[c] for c in conditions]
        colors = [CONDITION_COLORS.get(c, "#999") for c in conditions]
        ax.bar(conditions, counts, color=colors)
        ax.set_title("Video Clips by Condition")
        ax.set_ylabel("Number of Clips")
        outputs.append(save_figure(fig, "clips_by_condition", "stats"))

    # ── Horizontal bar: clips per trip ──
    fig, ax = plt.subplots(figsize=(10, max(6, len(trips) * 0.35)))
    trip_names = [t["name"] for t in trips]
    trip_clip_counts = [len(t["video_pairs"]) for t in trips]
    colors = ["#2ca02c" if t["has_labels"] else "#aaa" for t in trips]
    ax.barh(trip_names, trip_clip_counts, color=colors)
    ax.set_xlabel("Number of Video Pairs")
    ax.set_title("Clips per Trip (green = has labels)")
    ax.invert_yaxis()
    outputs.append(save_figure(fig, "clips_per_trip", "stats"))

    # ── Labeled vs unlabeled split ──
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie(
        [labeled_clips, total_clips - labeled_clips],
        labels=["Labeled", "Unlabeled"],
        autopct="%1.0f%%", colors=["#2ca02c", "#ddd"], startangle=90,
    )
    ax.set_title("Labeled vs Unlabeled Clips")
    outputs.append(save_figure(fig, "labeled_split", "stats"))

    # ── Event type distribution ──
    event_type_counts = Counter()
    for labels in all_labels.values():
        for evts in labels.values():
            for _, et in evts:
                event_type_counts[et] += 1

    if event_type_counts:
        fig, ax = plt.subplots(figsize=(8, 5))
        types = list(event_type_counts.keys())
        counts = [event_type_counts[t] for t in types]
        colors = [EVENT_COLORS.get(t, "#999") for t in types]
        ax.bar(types, counts, color=colors)
        ax.set_title("Ground Truth Event Distribution")
        ax.set_ylabel("Count")
        for i, c in enumerate(counts):
            ax.text(i, c + 0.3, str(c), ha="center", fontweight="bold")
        outputs.append(save_figure(fig, "event_distribution", "stats"))

    # ── Events per video ──
    events_per_video = []
    for labels in all_labels.values():
        for evts in labels.values():
            events_per_video.append(len(evts))
    if events_per_video:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(events_per_video, bins=range(0, max(events_per_video) + 2),
                edgecolor="white", alpha=0.8)
        ax.set_title("Events per Labeled Video")
        ax.set_xlabel("Number of Events")
        ax.set_ylabel("Number of Videos")
        outputs.append(save_figure(fig, "events_per_video", "stats"))

    # ── Summary HTML table ──
    summary_html = f"""
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; margin:16px 0;">
    <tr><th>Metric</th><th>Value</th></tr>
    <tr><td>Total trips</td><td>{len(trips)}</td></tr>
    <tr><td>Total video pairs</td><td>{total_clips}</td></tr>
    <tr><td>Estimated total duration</td><td>{total_duration_min:.0f} min</td></tr>
    <tr><td>Labeled trips</td><td>{len(labeled_trips)}</td></tr>
    <tr><td>Labeled video clips</td><td>{labeled_clips}</td></tr>
    <tr><td>Total labeled events</td><td>{total_events}</td></tr>
    <tr><td>Unique drivers</td><td>{len(set(t['driver'] for t in trips))}</td></tr>
    <tr><td>Conditions</td><td>{', '.join(sorted(set(t['condition'] for t in trips)))}</td></tr>
    </table>
    """

    elapsed = time.time() - t0
    print(f"[Dataset Stats] Done ({elapsed:.1f}s) — {len(outputs)} plots")

    return outputs, summary_html
