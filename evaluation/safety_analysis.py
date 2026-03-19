"""Aggregate safety events across trips, drivers, and conditions."""

import re
import time
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np

from config import (
    OUTPUT_DIR, SAFETY_COLORS, EVENT_COLORS, CONDITION_COLORS, SYSTEM_TO_GT,
)
from data_loader import load_results, extract_trip_gps, load_gps_cache, save_gps_cache
from ground_truth_eval import parse_detection
from plotting_utils import setup_style, save_figure

try:
    import folium
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False


def run_safety_analysis(window_results, labeled_trips):
    """
    Aggregate safety events from windowed results.

    Returns list of output Paths.
    """
    print(f"[Safety Analysis] Processing {len(window_results)} windows ...")
    t0 = time.time()
    setup_style()
    outputs = []

    # Collect all safety events with metadata
    all_events = []

    # Build video→trip lookup
    video_to_trip = {}
    for trip in labeled_trips:
        for road, _ in trip["video_pairs"]:
            video_to_trip[road.stem] = trip

    for wr in window_results:
        if wr.get("road_only"):
            continue  # Skip windows without real face video — safety labels are noise
        try:
            results = load_results(wr["results_path"])
        except Exception:
            continue

        trip = video_to_trip.get(wr["video_id"])
        condition = trip["condition"] if trip else "unknown"
        driver = trip["driver"] if trip else "unknown"

        for te in results.get("timeline_events", []):
            det = parse_detection(te)
            if det is None:
                continue
            det["abs_timestamp"] = det["timestamp"]  # already video-absolute
            det["video_id"] = wr["video_id"]
            det["condition"] = condition
            det["driver"] = driver
            det["trip"] = trip["name"] if trip else "unknown"
            all_events.append(det)

    if not all_events:
        print("[Safety Analysis] No safety events found")
        return outputs, ""

    print(f"  Found {len(all_events)} safety events")

    safe_count = sum(1 for e in all_events if e["is_safe"])
    unsafe_count = len(all_events) - safe_count

    # ── 1. Safe vs unsafe overall ──
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie([safe_count, unsafe_count], labels=["Safe", "Unsafe"],
           autopct="%1.0f%%", colors=[SAFETY_COLORS[True], SAFETY_COLORS[False]],
           startangle=90)
    ax.set_title(f"Safety Events (n={len(all_events)})")
    outputs.append(save_figure(fig, "safety_overall", "safety"))

    # ── 2. Safe vs unsafe rate by condition ──
    cond_safe = Counter()
    cond_total = Counter()
    for e in all_events:
        cond_total[e["condition"]] += 1
        if e["is_safe"]:
            cond_safe[e["condition"]] += 1

    if cond_total:
        fig, ax = plt.subplots(figsize=(8, 5))
        conditions = sorted(cond_total.keys())
        safe_rates = [cond_safe[c] / cond_total[c] for c in conditions]
        unsafe_rates = [1 - r for r in safe_rates]
        x = np.arange(len(conditions))
        ax.bar(x, safe_rates, label="Safe", color=SAFETY_COLORS[True])
        ax.bar(x, unsafe_rates, bottom=safe_rates, label="Unsafe", color=SAFETY_COLORS[False])
        ax.set_xticks(x)
        ax.set_xticklabels([f"{c}\n(n={cond_total[c]})" for c in conditions])
        ax.set_ylabel("Rate")
        ax.set_title("Safety Rate by Condition")
        ax.legend()
        ax.set_ylim(0, 1.05)
        outputs.append(save_figure(fig, "safety_by_condition", "safety"))

    # ── 3. Event type distribution (stacked bar) ──
    type_safe = Counter()
    type_unsafe = Counter()
    for e in all_events:
        gt_type = e.get("maneuver_gt_type", "unknown") or "unknown"
        if e["is_safe"]:
            type_safe[gt_type] += 1
        else:
            type_unsafe[gt_type] += 1

    all_types = sorted(set(list(type_safe.keys()) + list(type_unsafe.keys())))
    if all_types:
        fig, ax = plt.subplots(figsize=(9, 5))
        x = np.arange(len(all_types))
        safe_vals = [type_safe.get(t, 0) for t in all_types]
        unsafe_vals = [type_unsafe.get(t, 0) for t in all_types]
        ax.bar(x, safe_vals, label="Safe", color=SAFETY_COLORS[True])
        ax.bar(x, unsafe_vals, bottom=safe_vals, label="Unsafe", color=SAFETY_COLORS[False])
        ax.set_xticks(x)
        ax.set_xticklabels(all_types, rotation=30, ha="right")
        ax.set_ylabel("Count")
        ax.set_title("Safety Events by Maneuver Type")
        ax.legend()
        outputs.append(save_figure(fig, "safety_by_type", "safety"))

    # ── 4. Safety events on GPS map ──
    if HAS_FOLIUM:
        p = _plot_safety_map(all_events, labeled_trips)
        if p:
            outputs.append(p)

    # ── Summary table ──
    stats_html = "<h3>Safety Event Summary</h3>"
    stats_html += f"<p>Total events: {len(all_events)} (Safe: {safe_count}, Unsafe: {unsafe_count})</p>"
    stats_html += "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>"
    stats_html += "<tr><th>Video</th><th>Time</th><th>Safe?</th><th>Mirror</th><th>Maneuver</th><th>Condition</th></tr>"
    for e in sorted(all_events, key=lambda x: (x["trip"], x["abs_timestamp"])):
        bg = "#e6ffe6" if e["is_safe"] else "#ffe6e6"
        stats_html += (
            f"<tr style='background:{bg};'>"
            f"<td>{e['video_id']}</td>"
            f"<td>{e['abs_timestamp']:.1f}s</td>"
            f"<td>{'SAFE' if e['is_safe'] else 'UNSAFE'}</td>"
            f"<td>{e['mirror_type']}</td>"
            f"<td>{e.get('maneuver_gt_type', e.get('maneuver_label', '?'))}</td>"
            f"<td>{e['condition']}</td></tr>"
        )
    stats_html += "</table>"

    elapsed = time.time() - t0
    print(f"[Safety Analysis] Done ({elapsed:.1f}s) — {len(outputs)} plots")

    return outputs, stats_html


def _plot_safety_map(all_events, labeled_trips):
    """Plot safety events on a GPS map (green=safe, red=unsafe)."""
    cache = load_gps_cache()

    # Build video→trip GPS
    trip_gps = {}
    for trip in labeled_trips:
        gps_df = extract_trip_gps(trip, cache=cache)
        if not gps_df.empty:
            trip_gps[trip["name"]] = gps_df

    save_gps_cache(cache)

    if not trip_gps:
        return None

    # Find center
    all_lats = []
    all_lons = []
    for df in trip_gps.values():
        all_lats.extend(df["lat"].tolist())
        all_lons.extend(df["lon"].tolist())

    m = folium.Map(location=[np.mean(all_lats), np.mean(all_lons)], zoom_start=13)

    # Draw routes faintly
    for trip_name, df in trip_gps.items():
        coords = list(zip(df["lat"], df["lon"]))
        folium.PolyLine(coords, color="gray", weight=2, opacity=0.4).add_to(m)

    # Place event markers
    for e in all_events:
        gps_df = trip_gps.get(e["trip"])
        if gps_df is None or gps_df.empty or "video" not in gps_df.columns:
            continue

        # Find GPS segment for this specific video
        vid_gps = gps_df[gps_df["video"] == e["video_id"]]
        if vid_gps.empty:
            continue
        n_vid = len(vid_gps)
        frac = e["abs_timestamp"] / 180.0  # timestamp is video-absolute within the clip
        idx = min(int(frac * n_vid), n_vid - 1)
        row = vid_gps.iloc[idx]

        color = "green" if e["is_safe"] else "red"
        folium.CircleMarker(
            [row["lat"], row["lon"]], radius=8,
            color=color, fill=True, fill_opacity=0.8,
            popup=f"{'SAFE' if e['is_safe'] else 'UNSAFE'}<br>{e['mirror_type']}<br>{e.get('maneuver_label','?')}<br>{e['video_id']} @ {e['abs_timestamp']:.0f}s",
        ).add_to(m)

    out_dir = OUTPUT_DIR / "safety"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "safety_events_map.html"
    m.save(str(path))
    return path
