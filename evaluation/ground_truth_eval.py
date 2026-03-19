"""Ground truth evaluation: precision/recall/F1, confusion matrices, timelines."""

import re
import time
from collections import Counter

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from config import (
    TEMPORAL_TOLERANCE, SYSTEM_TO_GT, GT_TO_CATEGORY,
    GT_EVENT_TYPES, EVENT_COLORS, SAFETY_COLORS, OUTPUT_DIR,
)
from data_loader import load_results
from plotting_utils import setup_style, save_figure


# ── Detection message parsing ──────────────────────────────────────────────

_MSG_RE = re.compile(r"(SAFE|UNSAFE):.*?before (.+?)[.!]")

# Older message formats (pre-maneuver-label)
_OLD_SAFE_RE = re.compile(r"SAFE:\s+(.+?)\s+checked before merging\.")
_OLD_UNSAFE_RE = re.compile(r"UNSAFE:\s+No\s+(.+?)\s+check detected!")


def parse_detection(event):
    """
    Parse a timeline_events entry into a structured detection.

    Returns dict with keys: timestamp, is_safe, mirror_type, maneuver_gt_type, raw_message
    or None if not a safety event.
    """
    msg = event.get("message", "")
    timestamp = event.get("timestamp", 0)

    # Try new format first
    m = _MSG_RE.search(msg)
    if m:
        safety = m.group(1)
        maneuver_label = m.group(2)
        is_safe = safety == "SAFE"

        # Extract mirror from message
        mirror = _extract_mirror(msg, is_safe)

        # Map system maneuver label → GT event type
        gt_type = SYSTEM_TO_GT.get(maneuver_label)

        return {
            "timestamp": timestamp,
            "is_safe": is_safe,
            "mirror_type": mirror,
            "maneuver_gt_type": gt_type,
            "maneuver_label": maneuver_label,
            "raw_message": msg,
        }

    # Try old format: "SAFE: X checked before merging."
    m = _OLD_SAFE_RE.search(msg)
    if m:
        mirror = m.group(1).replace("Rear and ", "")
        return {
            "timestamp": timestamp,
            "is_safe": True,
            "mirror_type": mirror,
            "maneuver_gt_type": None,  # can't determine from old format
            "maneuver_label": "merging",
            "raw_message": msg,
        }

    # Try old format: "UNSAFE: No X check detected!"
    m = _OLD_UNSAFE_RE.search(msg)
    if m:
        mirror = m.group(1)
        return {
            "timestamp": timestamp,
            "is_safe": False,
            "mirror_type": mirror,
            "maneuver_gt_type": None,
            "maneuver_label": "unknown",
            "raw_message": msg,
        }

    return None


def _extract_mirror(msg, is_safe):
    """Extract which mirror was checked (or should have been) from the message."""
    if is_safe:
        # "SAFE: Right Mirror checked..." or "SAFE: Rear and Right Mirror checked..."
        m = re.search(r"SAFE:\s+(?:Rear and )?(.+?)\s+checked", msg)
        return m.group(1) if m else "Unknown"
    else:
        # "UNSAFE: No Right Mirror check before..."
        m = re.search(r"No\s+(.+?)\s+check", msg)
        return m.group(1) if m else "Unknown"


# ── Temporal matching ──────────────────────────────────────────────────────

def match_events(gt_events, detections, tolerance=TEMPORAL_TOLERANCE):
    """
    Greedy temporal matching of GT events to detections.

    Parameters
    ----------
    gt_events : list of (time_seconds, event_type)
    detections : list of detection dicts (from parse_detection)
    tolerance : float
        Max time difference for a match.

    Returns
    -------
    matches : list of (gt_idx, det_idx, time_diff)
    unmatched_gt : list of gt_idx
    unmatched_det : list of det_idx
    """
    used_det = set()
    matches = []

    # Sort GT by time
    gt_indexed = sorted(enumerate(gt_events), key=lambda x: x[1][0])

    for gt_idx, (gt_time, gt_type) in gt_indexed:
        best_det_idx = None
        best_diff = float("inf")
        for det_idx, det in enumerate(detections):
            if det_idx in used_det:
                continue
            diff = abs(det["timestamp"] - gt_time)
            if diff <= tolerance and diff < best_diff:
                best_diff = diff
                best_det_idx = det_idx
        if best_det_idx is not None:
            matches.append((gt_idx, best_det_idx, best_diff))
            used_det.add(best_det_idx)

    unmatched_gt = [i for i in range(len(gt_events)) if i not in {m[0] for m in matches}]
    unmatched_det = [i for i in range(len(detections)) if i not in used_det]

    return matches, unmatched_gt, unmatched_det


# ── Main evaluation ────────────────────────────────────────────────────────

def run_ground_truth_eval(labeled_trips, all_labels, window_results):
    """
    Run ground truth evaluation across all labeled videos.

    Parameters
    ----------
    labeled_trips : list of trip dicts
    all_labels : dict {trip_name: {video_id: [(time_s, event_type), ...]}}
    window_results : list of dicts with window_start, window_end, results_path, video_id

    Returns
    -------
    list of Path — generated output files
    """
    print(f"[Ground Truth Eval] Evaluating {len(window_results)} analysis windows ...")
    t0 = time.time()
    setup_style()
    outputs = []

    # Group window results by video_id
    results_by_video = {}
    for wr in window_results:
        results_by_video.setdefault(wr["video_id"], []).append(wr)

    # Collect all GT vs detection pairs
    all_gt = []       # list of (time_s, event_type, video_id)
    all_det = []      # list of detection dicts (with abs timestamp and video_id)
    all_matches = []  # list of (gt_global_idx, det_global_idx, time_diff)
    all_unmatched_gt = []
    all_unmatched_det = []

    per_video_data = []

    for trip in labeled_trips:
        labels = all_labels.get(trip["name"], {})
        for video_id, events in labels.items():
            windows = results_by_video.get(video_id, [])

            # Collect detections from all windows, converting to absolute time
            video_detections = []
            has_results = False
            for wr in windows:
                try:
                    results = load_results(wr["results_path"])
                    has_results = True
                except Exception:
                    continue
                for te in results.get("timeline_events", []):
                    det = parse_detection(te)
                    if det is None:
                        continue
                    # Timestamps from video_processor are already video-absolute
                    # (CAP_PROP_POS_MSEC returns absolute position after seek)
                    det["video_id"] = video_id
                    video_detections.append(det)

            # Match GT ↔ detections for this video
            gt_offset = len(all_gt)
            det_offset = len(all_det)

            for t_s, etype in events:
                all_gt.append((t_s, etype, video_id))
            all_det.extend(video_detections)

            matches, ugt, udet = match_events(events, video_detections)

            for gt_local, det_local, diff in matches:
                all_matches.append((gt_offset + gt_local, det_offset + det_local, diff))
            for gi in ugt:
                all_unmatched_gt.append(gt_offset + gi)
            for di in udet:
                all_unmatched_det.append(det_offset + di)

            per_video_data.append({
                "video_id": video_id,
                "trip": trip["name"],
                "gt": events,
                "detections": video_detections,
                "matches": matches,
                "unmatched_gt": ugt,
                "unmatched_det": udet,
                "has_results": has_results,
            })

    # ── Compute metrics ──
    tp = len(all_matches)
    fn = len(all_unmatched_gt)
    fp = len(all_unmatched_det)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    print(f"  Events: {len(all_gt)} GT, {len(all_det)} detections")
    print(f"  TP={tp}, FP={fp}, FN={fn}")
    print(f"  Precision={precision:.2f}, Recall={recall:.2f}, F1={f1:.2f}")

    # ── Per-video console summary ──
    print(f"\n  {'Video':<35} {'GT':>3} {'Det':>4} {'TP':>3} {'FP':>3} {'FN':>3}  Status")
    print(f"  {'─'*35} {'─'*3} {'─'*4} {'─'*3} {'─'*3} {'─'*3}  {'─'*20}")
    for pvd in per_video_data:
        n_gt = len(pvd["gt"])
        n_det = len(pvd["detections"])
        n_tp = len(pvd["matches"])
        n_fp = len(pvd["unmatched_det"])
        n_fn = len(pvd["unmatched_gt"])
        if not pvd["has_results"]:
            status = "NO RESULTS"
        elif n_tp == n_gt and n_fp == 0:
            status = "PERFECT"
        elif n_tp == 0:
            status = "NO MATCHES"
        else:
            status = f"P={n_tp/(n_tp+n_fp):.0%} R={n_tp/(n_tp+n_fn):.0%}"
        print(f"  {pvd['video_id']:<35} {n_gt:>3} {n_det:>4} {n_tp:>3} {n_fp:>3} {n_fn:>3}  {status}")

    # ── P/R/F1 bar chart ──
    fig, ax = plt.subplots(figsize=(6, 5))
    metrics = {"Precision": precision, "Recall": recall, "F1": f1}
    bars = ax.bar(metrics.keys(), metrics.values(), color=["#1f77b4", "#ff7f0e", "#2ca02c"])
    ax.set_ylim(0, 1.05)
    ax.set_title(f"Event Detection — P/R/F1 (tol={TEMPORAL_TOLERANCE}s)")
    for bar, val in zip(bars, metrics.values()):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.02,
                f"{val:.2f}", ha="center", fontweight="bold")
    outputs.append(save_figure(fig, "prf1_bar", "ground_truth"))

    # ── Confusion matrix (all events: TP + FN + FP) ──
    p = _plot_confusion_matrix(all_gt, all_det, all_matches, all_unmatched_gt, all_unmatched_det)
    if p:
        outputs.append(p)

    # ── Timeline comparison + odometry per video ──
    for pvd in per_video_data:
        p = _plot_timeline_comparison(pvd)
        if p:
            outputs.append(p)
        p = _plot_odometry(pvd, results_by_video)
        if p:
            outputs.append(p)

    # ── Per-event detail table (HTML) ──
    detail_html = _build_detail_table(per_video_data, all_gt, all_det, all_matches, all_unmatched_gt, all_unmatched_det)

    # ── Timing error histogram ──
    if all_matches:
        diffs = [d for _, _, d in all_matches]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist(diffs, bins=20, edgecolor="white", alpha=0.8)
        ax.set_title("Temporal Match Error Distribution")
        ax.set_xlabel("Time difference (s)")
        ax.set_ylabel("Count")
        ax.axvline(x=np.mean(diffs), color="red", linestyle="--",
                    label=f"Mean={np.mean(diffs):.1f}s")
        ax.legend()
        outputs.append(save_figure(fig, "timing_errors", "ground_truth"))

    elapsed = time.time() - t0
    print(f"[Ground Truth Eval] Done ({elapsed:.1f}s) — {len(outputs)} plots")

    return outputs, detail_html


def _plot_confusion_matrix(all_gt, all_det, matches, unmatched_gt, unmatched_det):
    """Confusion matrix: GT event type vs system-detected event type, including FN/FP."""
    gt_types = sorted(set(GT_EVENT_TYPES))
    # Rows = GT types + "No GT (FP)", Columns = detected types + "Missed (FN)"
    row_labels = gt_types + ["No GT (FP)"]
    col_labels = gt_types + ["Missed (FN)"]
    n_rows = len(row_labels)
    n_cols = len(col_labels)
    type_to_row = {t: i for i, t in enumerate(gt_types)}
    type_to_col = {t: i for i, t in enumerate(gt_types)}
    fn_col = len(gt_types)  # last column
    fp_row = len(gt_types)  # last row

    matrix = np.zeros((n_rows, n_cols), dtype=int)

    # Matched: GT type → detected type
    for gt_idx, det_idx, _ in matches:
        gt_type = all_gt[gt_idx][1]
        det_type = all_det[det_idx].get("maneuver_gt_type")
        ri = type_to_row.get(gt_type)
        ci = type_to_col.get(det_type)
        if ri is not None and ci is not None:
            matrix[ri, ci] += 1
        elif ri is not None:
            # Detected but type unknown — still a TP, count in "Missed" col as type mismatch
            matrix[ri, fn_col] += 1

    # Unmatched GT (FN): GT type → "Missed" column
    for gi in unmatched_gt:
        gt_type = all_gt[gi][1]
        ri = type_to_row.get(gt_type)
        if ri is not None:
            matrix[ri, fn_col] += 1

    # Unmatched detections (FP): "No GT" row → detected type column
    for di in unmatched_det:
        det_type = all_det[di].get("maneuver_gt_type")
        ci = type_to_col.get(det_type)
        if ci is not None:
            matrix[fp_row, ci] += 1
        else:
            matrix[fp_row, fn_col] += 1  # FP with unknown type

    if matrix.sum() == 0:
        return None

    fig, ax = plt.subplots(figsize=(9, 8))

    # Use different colormaps for the main grid vs FN/FP margins
    im = ax.imshow(matrix, cmap="Blues", aspect="auto")
    ax.set_xticks(range(n_cols))
    ax.set_yticks(range(n_rows))
    ax.set_xticklabels(col_labels, rotation=45, ha="right")
    ax.set_yticklabels(row_labels)
    ax.set_xlabel("System Detection")
    ax.set_ylabel("Ground Truth")

    total_gt = len(all_gt)
    total_det = len(all_det)
    tp = len(matches)
    ax.set_title(f"Event Confusion Matrix — {total_gt} GT, {total_det} Det, "
                 f"TP={tp}, FP={len(unmatched_det)}, FN={len(unmatched_gt)}")

    # Draw separator lines before FN col and FP row
    ax.axhline(y=len(gt_types) - 0.5, color="red", linewidth=2)
    ax.axvline(x=len(gt_types) - 0.5, color="red", linewidth=2)

    row_totals = matrix.sum(axis=1)
    for i in range(n_rows):
        for j in range(n_cols):
            val = matrix[i, j]
            if val == 0:
                continue
            pct = 100 * val / max(row_totals[i], 1)
            # Color: FN/FP region gets red text, TP region gets normal
            is_margin = (i == fp_row) or (j == fn_col)
            text_color = "#d62728" if is_margin else ("white" if val > matrix.max() / 2 else "black")
            fontweight = "bold" if is_margin else "normal"
            ax.text(j, i, f"{val}\n({pct:.0f}%)", ha="center", va="center",
                    color=text_color, fontweight=fontweight, fontsize=10)

    fig.colorbar(im, ax=ax, shrink=0.8)
    return save_figure(fig, "confusion_matrix", "ground_truth")


def _plot_timeline_comparison(pvd):
    """Timeline plot for one video: GT triangles + detection circles with match lines."""
    video_id = pvd["video_id"]
    gt = pvd["gt"]
    dets = pvd["detections"]
    matches = pvd["matches"]

    if not gt and not dets:
        return None

    n_tp = len(matches)
    n_fp = len(pvd["unmatched_det"])
    n_fn = len(pvd["unmatched_gt"])

    fig, ax = plt.subplots(figsize=(14, 3.5))

    # GT events as triangles at y=1
    for i, (t_s, etype) in enumerate(gt):
        color = EVENT_COLORS.get(etype, "gray")
        is_matched = i in {m[0] for m in matches}
        ax.scatter(t_s, 1.0, marker="^", s=120, color=color, zorder=5,
                   edgecolors="black", linewidth=0.5)
        ax.annotate(etype, (t_s, 1.0), textcoords="offset points",
                    xytext=(0, 12), fontsize=7, ha="center", rotation=30)

    # Detections as circles at y=0
    for i, det in enumerate(dets):
        safe_color = SAFETY_COLORS[det["is_safe"]]
        ax.scatter(det["timestamp"], 0.0, marker="o", s=100, color=safe_color,
                   zorder=5, edgecolors="black", linewidth=0.5)
        # Annotate detection type
        det_label = det.get("maneuver_gt_type") or det.get("maneuver_label", "?")
        ax.annotate(det_label, (det["timestamp"], 0.0), textcoords="offset points",
                    xytext=(0, -14), fontsize=6, ha="center", rotation=30, color="gray")

    # Match lines (green dashed)
    matched_gt = set()
    matched_det = set()
    for gt_idx, det_idx, diff in matches:
        matched_gt.add(gt_idx)
        matched_det.add(det_idx)
        gt_time = gt[gt_idx][0]
        det_time = dets[det_idx]["timestamp"]
        ax.plot([gt_time, det_time], [1.0, 0.0], color="#2ca02c", linestyle="--",
                alpha=0.6, linewidth=1.2)

    # Highlight unmatched GT (FN) — red ring + red "FN" label
    for gi in pvd["unmatched_gt"]:
        ax.scatter(gt[gi][0], 1.0, marker="^", s=200, facecolors="none",
                   edgecolors="red", linewidth=2, zorder=6)
        ax.annotate("FN", (gt[gi][0], 1.0), textcoords="offset points",
                    xytext=(8, -8), fontsize=7, color="red", fontweight="bold")

    # Highlight unmatched detections (FP) — red ring + red "FP" label
    for di in pvd["unmatched_det"]:
        ax.scatter(dets[di]["timestamp"], 0.0, marker="o", s=160, facecolors="none",
                   edgecolors="red", linewidth=2, zorder=6)
        ax.annotate("FP", (dets[di]["timestamp"], 0.0), textcoords="offset points",
                    xytext=(8, 8), fontsize=7, color="red", fontweight="bold")

    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Detections", "Ground Truth"])
    ax.set_xlabel("Time (s)")

    # Title includes TP/FP/FN counts
    has_results = pvd.get("has_results", True)
    if not has_results:
        status_str = "— NO PIPELINE RESULTS (all FN)"
    else:
        status_str = f"— TP={n_tp}  FP={n_fp}  FN={n_fn}"
    ax.set_title(f"Timeline — {video_id}  {status_str}")
    ax.set_xlim(-5, 185)
    ax.set_ylim(-0.5, 2.0)

    # Legend
    legend_elements = [
        mpatches.Patch(color=SAFETY_COLORS[True], label="Safe detection"),
        mpatches.Patch(color=SAFETY_COLORS[False], label="Unsafe detection"),
        plt.scatter([], [], marker="^", s=60, c="gray", label="GT event"),
        plt.Line2D([0], [0], color="#2ca02c", linestyle="--", label="TP match"),
        plt.scatter([], [], marker="^", s=60, facecolors="none",
                    edgecolors="red", linewidth=2, label="FN (missed)"),
        plt.scatter([], [], marker="o", s=60, facecolors="none",
                    edgecolors="red", linewidth=2, label="FP (false alarm)"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=7, ncol=2)

    return save_figure(fig, f"timeline_{video_id}", "ground_truth")


def _plot_odometry(pvd, results_by_video):
    """Plot X-Z odometry trajectory for a video with GT and detection event markers."""
    video_id = pvd["video_id"]
    windows = results_by_video.get(video_id, [])
    if not windows:
        return None

    # Collect per-frame VO data from all windows, chaining coordinate systems
    # Each window starts VO at (0,0), so offset each window to continue from
    # where the previous one ended.
    all_vo_x = []
    all_vo_z = []
    all_times = []
    event_vo = []
    offset_x, offset_z = 0.0, 0.0

    sorted_windows = sorted(windows, key=lambda w: w["window_start"])
    for wr in sorted_windows:
        try:
            results = load_results(wr["results_path"])
        except Exception:
            continue

        # Collect per-frame VO for this window
        win_xs, win_zs, win_ts = [], [], []
        for f in results.get("frame_data", []):
            if "vo_x" in f and "vo_z" in f:
                win_xs.append(f["vo_x"])
                win_zs.append(f["vo_z"])
                win_ts.append(f["time"])

        if win_xs:
            # Apply offset so this window chains from the previous one's end
            all_vo_x.extend([x + offset_x for x in win_xs])
            all_vo_z.extend([z + offset_z for z in win_zs])
            all_times.extend(win_ts)
            # Update offset: next window starts from this window's endpoint
            offset_x += win_xs[-1]
            offset_z += win_zs[-1]

        # Collect event-level VO (also offset)
        # Events share the same coordinate system as this window's per-frame data,
        # so use the offset *before* it was updated by this window's endpoint.
        win_offset_x = offset_x - (win_xs[-1] if win_xs else 0)
        win_offset_z = offset_z - (win_zs[-1] if win_xs else 0)
        for e in results.get("timeline_events", []):
            if e.get("vo_x") is not None and e.get("vo_z") is not None:
                event_vo.append({
                    **e,
                    "vo_x": e["vo_x"] + win_offset_x,
                    "vo_z": e["vo_z"] + win_offset_z,
                })

    if not all_vo_x and not event_vo:
        return None

    fig, ax = plt.subplots(figsize=(8, 8))

    # Plot trajectory if per-frame data available
    if all_vo_x:
        ax.plot(all_vo_x, all_vo_z, color="#1f77b4", linewidth=0.8, alpha=0.6, label="VO trajectory")
        ax.scatter(all_vo_x[0], all_vo_z[0], color="green", s=80, zorder=5,
                   marker="s", edgecolors="black", label="Start")

    # Plot GT events — find nearest VO position by timestamp
    gt = pvd["gt"]
    for i, (t_sec, etype) in enumerate(gt):
        vo_x, vo_z = _find_vo_at_time(t_sec, all_times, all_vo_x, all_vo_z, event_vo)
        if vo_x is not None:
            color = EVENT_COLORS.get(etype, "gray")
            is_fn = i in pvd["unmatched_gt"]
            ax.scatter(vo_x, vo_z, marker="^", s=120, color=color, zorder=6,
                       edgecolors="red" if is_fn else "black", linewidth=2 if is_fn else 0.5)
            label = f"{_fmt_time_short(t_sec)} {etype}"
            if is_fn:
                label += " (FN)"
            ax.annotate(label, (vo_x, vo_z), textcoords="offset points",
                        xytext=(8, 8), fontsize=7, color=color)

    # Plot detection events
    dets = pvd["detections"]
    for i, det in enumerate(dets):
        is_fp = i in pvd["unmatched_det"]
        # Use VO from the event itself
        vo_x = det.get("_vo_x")
        vo_z = det.get("_vo_z")
        if vo_x is None:
            # Find from event_vo or interpolate
            vo_x, vo_z = _find_vo_at_time(det["timestamp"], all_times, all_vo_x, all_vo_z, event_vo)
        if vo_x is not None:
            safe_color = SAFETY_COLORS[det["is_safe"]]
            ax.scatter(vo_x, vo_z, marker="o", s=80, color=safe_color, zorder=6,
                       edgecolors="red" if is_fp else "black", linewidth=2 if is_fp else 0.5)
            if is_fp:
                ax.annotate("FP", (vo_x, vo_z), textcoords="offset points",
                            xytext=(8, -10), fontsize=7, color="red", fontweight="bold")

    ax.set_xlabel("X (Visual Odometry)")
    ax.set_ylabel("Z (Visual Odometry)")
    ax.set_title(f"Odometry — {video_id}")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.3)

    # Legend
    legend_elements = [
        plt.Line2D([0], [0], marker="^", color="w", markerfacecolor="gray",
                   markeredgecolor="black", markersize=8, label="GT event"),
        plt.Line2D([0], [0], marker="^", color="w", markerfacecolor="gray",
                   markeredgecolor="red", markeredgewidth=2, markersize=8, label="GT missed (FN)"),
        mpatches.Patch(color=SAFETY_COLORS[True], label="Safe detection"),
        mpatches.Patch(color=SAFETY_COLORS[False], label="Unsafe detection"),
    ]
    if all_vo_x:
        legend_elements.insert(0, plt.Line2D([0], [0], color="#1f77b4", label="VO trajectory"))
    ax.legend(handles=legend_elements, loc="best", fontsize=7)

    return save_figure(fig, f"odometry_{video_id}", "ground_truth")


def _find_vo_at_time(target_time, times, vo_xs, vo_zs, event_vo):
    """Find the VO position closest to target_time."""
    # Try per-frame data first
    if times:
        best_idx = min(range(len(times)), key=lambda i: abs(times[i] - target_time))
        if abs(times[best_idx] - target_time) < 1.0:
            return vo_xs[best_idx], vo_zs[best_idx]

    # Fall back to event VO
    if event_vo:
        best = min(event_vo, key=lambda e: abs(e["timestamp"] - target_time))
        if abs(best["timestamp"] - target_time) < 10.0:
            return best["vo_x"], best["vo_z"]

    return None, None


def _fmt_time_short(seconds):
    """Format seconds as M:SS."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


def _build_detail_table(per_video_data, all_gt, all_det, matches_global,
                        unmatched_gt_global, unmatched_det_global):
    """Build an HTML detail table grouped by video with per-video subtotals."""
    rows = []

    for pvd in per_video_data:
        video_id = pvd["video_id"]
        gt = pvd["gt"]
        dets = pvd["detections"]
        matches = pvd["matches"]
        ugt = pvd["unmatched_gt"]
        udet = pvd["unmatched_det"]
        has_results = pvd.get("has_results", True)

        n_tp = len(matches)
        n_fp = len(udet)
        n_fn = len(ugt)

        # Video header row
        if not has_results:
            header_bg = "#f0f0f0"
            status = "NO PIPELINE RESULTS"
        elif n_tp == len(gt) and n_fp == 0:
            header_bg = "#d4edda"
            status = "PERFECT"
        elif n_tp == 0 and n_fp == 0:
            header_bg = "#f8d7da"
            status = f"ALL MISSED ({n_fn} FN)"
        else:
            header_bg = "#fff3cd"
            p = n_tp / (n_tp + n_fp) if (n_tp + n_fp) > 0 else 0
            r = n_tp / (n_tp + n_fn) if (n_tp + n_fn) > 0 else 0
            status = f"TP={n_tp} FP={n_fp} FN={n_fn} (P={p:.0%} R={r:.0%})"

        rows.append(
            f"<tr style='background:{header_bg}; font-weight:bold;'>"
            f"<td colspan='3'>{video_id}</td>"
            f"<td colspan='3'>{pvd['trip']}</td>"
            f"<td colspan='2'>{status}</td></tr>"
        )

        # Build per-event rows sorted by time
        event_rows = []

        # Matched events
        for gt_idx, det_idx, diff in matches:
            gt_time = gt[gt_idx][0]
            gt_type = gt[gt_idx][1]
            det = dets[det_idx]
            event_rows.append((gt_time, (
                f"<tr style='background:#e6ffe6;'>"
                f"<td></td>"
                f"<td>{_fmt_time(gt_time)}</td><td>{gt_type}</td>"
                f"<td>{_fmt_time(det['timestamp'])}</td>"
                f"<td>{det.get('maneuver_gt_type') or det.get('maneuver_label', '?')}</td>"
                f"<td>{'SAFE' if det['is_safe'] else 'UNSAFE'}</td>"
                f"<td>{diff:.1f}s</td>"
                f"<td style='color:#2ca02c; font-weight:bold;'>TP</td></tr>"
            )))

        # Unmatched GT (FN)
        for gi in ugt:
            gt_time = gt[gi][0]
            gt_type = gt[gi][1]
            event_rows.append((gt_time, (
                f"<tr style='background:#f8d7da;'>"
                f"<td></td>"
                f"<td>{_fmt_time(gt_time)}</td><td>{gt_type}</td>"
                f"<td>—</td><td>—</td><td>—</td>"
                f"<td>—</td>"
                f"<td style='color:#d62728; font-weight:bold;'>FN</td></tr>"
            )))

        # Unmatched detections (FP)
        for di in udet:
            det = dets[di]
            event_rows.append((det["timestamp"], (
                f"<tr style='background:#fff3e0;'>"
                f"<td></td>"
                f"<td>—</td><td>—</td>"
                f"<td>{_fmt_time(det['timestamp'])}</td>"
                f"<td>{det.get('maneuver_gt_type') or det.get('maneuver_label', '?')}</td>"
                f"<td>{'SAFE' if det['is_safe'] else 'UNSAFE'}</td>"
                f"<td>—</td>"
                f"<td style='color:#e67e22; font-weight:bold;'>FP</td></tr>"
            )))

        # Sort by time and append
        event_rows.sort(key=lambda x: x[0])
        for _, row_html in event_rows:
            rows.append(row_html)

    # Totals footer
    tp = len(matches_global)
    fp = len(unmatched_det_global)
    fn = len(unmatched_gt_global)
    p = tp / (tp + fp) if (tp + fp) > 0 else 0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
    rows.append(
        f"<tr style='background:#333; color:white; font-weight:bold;'>"
        f"<td colspan='3'>TOTAL: {len(all_gt)} GT events, {len(all_det)} detections</td>"
        f"<td colspan='2'>TP={tp}  FP={fp}  FN={fn}</td>"
        f"<td colspan='3'>Precision={p:.2f}  Recall={r:.2f}  F1={f1:.2f}</td></tr>"
    )

    html = (
        "<table border='1' cellpadding='6' cellspacing='0' "
        "style='border-collapse:collapse; margin:16px 0; width:100%;'>"
        "<tr style='background:#444; color:white;'>"
        "<th>Video</th><th>GT Time</th><th>GT Type</th>"
        "<th>Det Time</th><th>Det Type</th><th>Safe?</th>"
        "<th>Δt</th><th>Result</th></tr>\n"
        + "\n".join(rows) +
        "\n</table>"
    )
    return html


def _fmt_time(seconds):
    """Format seconds as M:SS (e.g. 85 → 1:25)."""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d} ({seconds:.0f}s)"
