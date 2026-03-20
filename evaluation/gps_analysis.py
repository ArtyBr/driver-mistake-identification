"""GPS route maps, speed profiles, and trip statistics."""

import math
import time

import matplotlib.pyplot as plt
import numpy as np

from config import OUTPUT_DIR, EVENT_COLORS, SAFETY_COLORS
from plotting_utils import setup_style, save_figure
from data_loader import extract_trip_gps, load_gps_cache, save_gps_cache

try:
    import folium
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False


def run_gps_analysis(labeled_trips, all_labels):
    """
    Generate GPS-based analysis for labeled trips.

    Returns list of output Paths.
    """
    print(f"[GPS Analysis] Processing {len(labeled_trips)} trips ...")
    t0 = time.time()
    setup_style()
    outputs = []

    cache = load_gps_cache()
    trip_gps = {}

    for i, trip in enumerate(labeled_trips):
        tt = time.time()
        print(f"  [{i+1}/{len(labeled_trips)}] {trip['name']} ({len(trip['video_pairs'])} clips) ...", end=" ", flush=True)
        gps_df = extract_trip_gps(trip, cache=cache)
        trip_gps[trip["name"]] = gps_df

        if gps_df.empty:
            print("no GPS data")
            continue

        labels = all_labels.get(trip["name"], {})
        elapsed = time.time() - tt
        print(f"{len(gps_df)} points ({elapsed:.1f}s)")

        # Route map
        if HAS_FOLIUM and len(gps_df) > 1:
            p = _plot_route_map(trip, gps_df, labels)
            if p:
                outputs.append(p)

        # Speed profile
        if not gps_df.empty and "speed_kmh" in gps_df.columns:
            p = _plot_speed_profile(trip, gps_df, labels)
            if p:
                outputs.append(p)

    save_gps_cache(cache)

    # All-routes map
    if HAS_FOLIUM and trip_gps:
        p = _plot_all_routes_map(labeled_trips, trip_gps)
        if p:
            outputs.append(p)

    # Speed at events
    p = _plot_speed_at_events(labeled_trips, trip_gps, all_labels)
    if p:
        outputs.append(p)

    # Trip stats table
    stats_html = _compute_trip_stats_table(labeled_trips, trip_gps)

    elapsed = time.time() - t0
    print(f"[GPS Analysis] Done ({elapsed:.1f}s) — {len(outputs)} outputs")

    return outputs, stats_html


def _plot_route_map(trip, gps_df, labels):
    """Folium polyline colored by speed, with event markers."""
    out_dir = OUTPUT_DIR / "gps"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"route_{trip['name']}.html"

    center = [gps_df["lat"].mean(), gps_df["lon"].mean()]
    m = folium.Map(location=center, zoom_start=14)

    # Color line by speed
    coords = list(zip(gps_df["lat"], gps_df["lon"]))
    speeds = gps_df["speed_kmh"].values
    max_spd = max(speeds.max(), 1)

    # Split into segments colored by speed
    for j in range(len(coords) - 1):
        spd_frac = min(speeds[j] / max_spd, 1.0)
        r = int(255 * spd_frac)
        g = int(255 * (1 - spd_frac))
        color = f"#{r:02x}{g:02x}00"
        folium.PolyLine(
            [coords[j], coords[j + 1]], color=color, weight=4, opacity=0.8,
        ).add_to(m)

    # Start/end markers
    if coords:
        folium.Marker(coords[0], popup="Start",
                       icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(coords[-1], popup="End",
                       icon=folium.Icon(color="red")).add_to(m)

    # Event markers (placed at approximate GPS positions by time fraction)
    _add_event_markers(m, gps_df, labels)

    m.save(str(path))
    return path


def _add_event_markers(m, gps_df, labels):
    """Add GT event markers to a folium map at approximate GPS positions."""
    if gps_df.empty or not labels or "video" not in gps_df.columns:
        return

    for video_id, events in labels.items():
        # Find GPS rows for this specific video (stem without F suffix matches)
        vid_gps = gps_df[gps_df["video"] == video_id]
        if vid_gps.empty:
            # Try matching without the F suffix
            vid_gps = gps_df[gps_df["video"].str.startswith(video_id[:20])]
        if vid_gps.empty:
            continue

        n_vid = len(vid_gps)
        vid_duration = 180.0  # each clip is ~3 min

        for t_sec, etype in events:
            frac = t_sec / vid_duration
            idx = min(int(frac * n_vid), n_vid - 1)
            row = vid_gps.iloc[idx]
            color = EVENT_COLORS.get(etype, "gray")
            folium.CircleMarker(
                [row["lat"], row["lon"]], radius=8,
                color=color, fill=True, fill_opacity=0.8,
                popup=f"{video_id}<br>{_fmt_mmss(t_sec)}: {etype}",
            ).add_to(m)


def _plot_all_routes_map(labeled_trips, trip_gps):
    """All labeled trips on one folium map with layer control."""
    out_dir = OUTPUT_DIR / "gps"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "all_routes.html"

    # Find center
    all_lats, all_lons = [], []
    for df in trip_gps.values():
        if not df.empty:
            all_lats.extend(df["lat"].tolist())
            all_lons.extend(df["lon"].tolist())
    if not all_lats:
        return None
    center = [np.mean(all_lats), np.mean(all_lons)]
    m = folium.Map(location=center, zoom_start=13)

    colors = ["blue", "red", "green", "purple", "orange", "darkred"]
    for i, trip in enumerate(labeled_trips):
        df = trip_gps.get(trip["name"])
        if df is None or df.empty:
            continue
        coords = list(zip(df["lat"], df["lon"]))
        fg = folium.FeatureGroup(name=trip["name"])
        folium.PolyLine(
            coords, color=colors[i % len(colors)], weight=3, opacity=0.7,
        ).add_to(fg)
        fg.add_to(m)

    folium.LayerControl().add_to(m)
    m.save(str(path))
    return path


def _plot_speed_profile(trip, gps_df, labels):
    """Speed vs index with GT event markers."""
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(gps_df["speed_kmh"].values, linewidth=0.8, alpha=0.8)
    ax.set_title(f"Speed Profile — {trip['name']}")
    ax.set_xlabel("GPS Sample Index")
    ax.set_ylabel("Speed (km/h)")
    ax.axhline(y=0, color="gray", linewidth=0.5)

    # Mark events — locate within per-video GPS segments
    if "video" in gps_df.columns:
        # Build cumulative index offset per video
        vid_offsets = {}
        offset = 0
        for vid_name, grp in gps_df.groupby("video", sort=False):
            vid_offsets[vid_name] = offset
            offset += len(grp)

        for video_id, events in labels.items():
            vid_gps = gps_df[gps_df["video"] == video_id]
            if vid_gps.empty:
                continue
            base_idx = vid_offsets.get(video_id, 0)
            n_vid = len(vid_gps)
            for t_sec, etype in events:
                frac = t_sec / 180.0
                local_idx = min(int(frac * n_vid), n_vid - 1)
                idx = base_idx + local_idx
                color = EVENT_COLORS.get(etype, "gray")
                ax.axvline(x=idx, color=color, alpha=0.6, linewidth=1.5, linestyle="--")
                ax.text(idx, ax.get_ylim()[1] * 0.95, f"{etype[:8]} {_fmt_mmss(t_sec)}",
                        rotation=90, fontsize=6, color=color, va="top")

    return save_figure(fig, f"speed_{trip['name']}", "gps")


def _plot_speed_at_events(labeled_trips, trip_gps, all_labels):
    """Box plot of speed at labeled events by event type."""
    speeds_by_type = {}

    for trip in labeled_trips:
        gps_df = trip_gps.get(trip["name"])
        if gps_df is None or gps_df.empty or "video" not in gps_df.columns:
            continue
        labels = all_labels.get(trip["name"], {})

        for video_id, events in labels.items():
            vid_gps = gps_df[gps_df["video"] == video_id]
            if vid_gps.empty:
                continue
            n_vid = len(vid_gps)
            for t_sec, etype in events:
                frac = t_sec / 180.0
                idx = min(int(frac * n_vid), n_vid - 1)
                spd = vid_gps.iloc[idx]["speed_kmh"]
                speeds_by_type.setdefault(etype, []).append(spd)

    if not speeds_by_type:
        return None

    fig, ax = plt.subplots(figsize=(8, 5))
    types = sorted(speeds_by_type.keys())
    data = [speeds_by_type[t] for t in types]
    bp = ax.boxplot(data, labels=types, patch_artist=True)
    for patch, t in zip(bp["boxes"], types):
        patch.set_facecolor(EVENT_COLORS.get(t, "#999"))
        patch.set_alpha(0.7)
    ax.set_title("Speed at Labeled Events by Type")
    ax.set_ylabel("Speed (km/h)")
    return save_figure(fig, "speed_at_events", "gps")


def _fmt_mmss(seconds):
    """Format seconds as M:SS."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


def _haversine(lat1, lon1, lat2, lon2):
    """Haversine distance in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _compute_trip_stats_table(labeled_trips, trip_gps):
    """Generate HTML table with per-trip GPS stats."""
    rows = []
    for trip in labeled_trips:
        df = trip_gps.get(trip["name"])
        if df is None or df.empty:
            rows.append(f"<tr><td>{trip['name']}</td><td colspan='4'>No GPS data</td></tr>")
            continue

        # Distance
        total_dist = 0
        for j in range(len(df) - 1):
            total_dist += _haversine(
                df.iloc[j]["lat"], df.iloc[j]["lon"],
                df.iloc[j + 1]["lat"], df.iloc[j + 1]["lon"],
            )

        avg_speed = df["speed_kmh"].mean()
        max_speed = df["speed_kmh"].max()
        stops = (df["speed_kmh"] < 2).sum()

        rows.append(
            f"<tr><td>{trip['name']}</td>"
            f"<td>{total_dist:.1f} km</td>"
            f"<td>{avg_speed:.1f} km/h</td>"
            f"<td>{max_speed:.1f} km/h</td>"
            f"<td>{stops}</td></tr>"
        )

    html = (
        "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse; margin:16px 0;'>"
        "<tr><th>Trip</th><th>Distance</th><th>Avg Speed</th><th>Max Speed</th><th>Stops (speed&lt;2)</th></tr>"
        + "\n".join(rows) +
        "</table>"
    )
    return html
