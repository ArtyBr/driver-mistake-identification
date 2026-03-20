"""Lane detection coverage and stability analysis."""

import time

import matplotlib.pyplot as plt
import numpy as np

from config import OUTPUT_DIR, CONDITION_COLORS
from data_loader import load_results
from plotting_utils import setup_style, save_figure


def run_lane_analysis(window_results, labeled_trips):
    """
    Analyse lane detection from windowed pipeline results.

    Returns list of output Paths.
    """
    print(f"[Lane Analysis] Processing {len(window_results)} windows ...")
    t0 = time.time()
    setup_style()
    outputs = []

    per_window_stats = []

    for wr in window_results:
        try:
            results = load_results(wr["results_path"])
        except Exception:
            continue

        frames = results.get("frame_data", [])
        if not frames:
            continue

        lane_counts = [len(f.get("lane_lines", [])) for f in frames]
        n = len(lane_counts)
        if n == 0:
            continue

        has_any = sum(1 for c in lane_counts if c >= 1) / n
        has_two = sum(1 for c in lane_counts if c >= 2) / n

        # Stability: frame-to-frame lane count change
        changes = [abs(lane_counts[i] - lane_counts[i - 1]) for i in range(1, n)]
        stability = 1.0 - (sum(changes) / len(changes)) if changes else 1.0

        # Find trip condition
        condition = "unknown"
        for trip in labeled_trips:
            if wr["video_id"] in [p[0].stem for p in trip["video_pairs"]]:
                condition = trip["condition"]
                break
            # Also check labels
            labels = {}
            if trip["has_labels"]:
                from data_loader import load_ground_truth
                try:
                    labels = load_ground_truth(trip["path"] / "event_labels.json")
                except Exception:
                    pass
            if wr["video_id"] in labels:
                condition = trip["condition"]
                break

        per_window_stats.append({
            "video_id": wr["video_id"],
            "window_start": wr["window_start"],
            "window_end": wr["window_end"],
            "n_frames": n,
            "coverage_any": has_any,
            "coverage_two": has_two,
            "stability": stability,
            "lane_counts": lane_counts,
            "condition": condition,
            "fps": results.get("meta", {}).get("fps", 30),
        })

    if not per_window_stats:
        print("[Lane Analysis] No lane data found")
        return outputs, ""

    # ── 1. Overall coverage bar ──
    avg_any = np.mean([s["coverage_any"] for s in per_window_stats])
    avg_two = np.mean([s["coverage_two"] for s in per_window_stats])
    avg_stab = np.mean([s["stability"] for s in per_window_stats])

    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(["≥1 Lane", "≥2 Lanes", "Stability"], [avg_any, avg_two, avg_stab],
                  color=["#1f77b4", "#ff7f0e", "#2ca02c"])
    ax.set_ylim(0, 1.05)
    ax.set_title("Lane Detection — Average Coverage & Stability")
    for bar, val in zip(bars, [avg_any, avg_two, avg_stab]):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.02,
                f"{val:.1%}", ha="center", fontweight="bold")
    outputs.append(save_figure(fig, "lane_coverage_overall", "lanes"))

    # ── 2. Coverage timeline per window (first 8) ──
    n_show = min(len(per_window_stats), 8)
    if n_show > 0:
        fig, axes = plt.subplots(n_show, 1, figsize=(14, n_show * 1.2 + 1),
                                  squeeze=False)
        for i in range(n_show):
            ws = per_window_stats[i]
            ax = axes[i, 0]
            times = [j / ws["fps"] for j in range(ws["n_frames"])]
            ax.fill_between(times, ws["lane_counts"], alpha=0.5, step="mid")
            ax.set_ylim(-0.2, max(max(ws["lane_counts"]), 4) + 0.5)
            ax.set_ylabel(f"{ws['video_id'][:18]}\n{ws['window_start']:.0f}s",
                          fontsize=7, rotation=0, ha="right", va="center")
            ax.set_yticks([0, 1, 2, 3, 4])
        axes[0, 0].set_title("Lane Count Over Time (per window)")
        axes[-1, 0].set_xlabel("Time (s)")
        fig.tight_layout()
        outputs.append(save_figure(fig, "lane_count_timelines", "lanes"))

    # ── 3. Day vs Night coverage comparison ──
    cond_stats = {}
    for s in per_window_stats:
        cond = s["condition"]
        cond_stats.setdefault(cond, {"any": [], "two": []})
        cond_stats[cond]["any"].append(s["coverage_any"])
        cond_stats[cond]["two"].append(s["coverage_two"])

    if len(cond_stats) > 1:
        fig, ax = plt.subplots(figsize=(8, 5))
        conditions = sorted(cond_stats.keys())
        x = np.arange(len(conditions))
        width = 0.35
        any_means = [np.mean(cond_stats[c]["any"]) for c in conditions]
        two_means = [np.mean(cond_stats[c]["two"]) for c in conditions]
        ax.bar(x - width / 2, any_means, width, label="≥1 Lane",
               color=[CONDITION_COLORS.get(c, "#999") for c in conditions], alpha=0.7)
        ax.bar(x + width / 2, two_means, width, label="≥2 Lanes",
               color=[CONDITION_COLORS.get(c, "#999") for c in conditions], alpha=0.4)
        ax.set_xticks(x)
        ax.set_xticklabels(conditions)
        ax.set_ylabel("Coverage")
        ax.set_title("Lane Detection Coverage by Condition")
        ax.legend()
        ax.set_ylim(0, 1.05)
        outputs.append(save_figure(fig, "lane_coverage_by_condition", "lanes"))

    # ── Stats HTML ──
    stats_html = "<h3>Lane Detection Statistics</h3>"
    stats_html += f"<p>Windows analysed: {len(per_window_stats)}</p>"
    stats_html += "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>"
    stats_html += "<tr><th>Video</th><th>Window</th><th>Frames</th><th>≥1 Lane</th><th>≥2 Lanes</th><th>Stability</th><th>Condition</th></tr>"
    for s in per_window_stats:
        stats_html += (
            f"<tr><td>{s['video_id']}</td>"
            f"<td>{s['window_start']:.0f}–{s['window_end']:.0f}s</td>"
            f"<td>{s['n_frames']}</td>"
            f"<td>{s['coverage_any']:.1%}</td>"
            f"<td>{s['coverage_two']:.1%}</td>"
            f"<td>{s['stability']:.2f}</td>"
            f"<td>{s['condition']}</td></tr>"
        )
    stats_html += "</table>"

    elapsed = time.time() - t0
    print(f"[Lane Analysis] Done ({elapsed:.1f}s) — {len(outputs)} plots")

    return outputs, stats_html
