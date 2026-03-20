#!/usr/bin/env python3 -u
"""
Evaluation framework CLI — run analysis modules and generate HTML report.

Usage:
    python evaluation/run_evaluation.py --all --video-base /media/arty/3A30-14F9/Videos
    python evaluation/run_evaluation.py --stats --gps --video-base /path/to/videos
    python evaluation/run_evaluation.py --ground-truth --run-pipeline  # run analysis first
"""

import argparse
import builtins
import os
import sys
import time
from pathlib import Path

# Force unbuffered stdout so progress appears immediately in pipes/subprocesses
os.environ["PYTHONUNBUFFERED"] = "1"
_original_print = builtins.print
builtins.print = lambda *args, **kwargs: _original_print(*args, **{**kwargs, "flush": True})

# Ensure evaluation/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import VIDEO_BASE, OUTPUT_DIR, PIPELINE_RESULTS_DIR
from data_loader import discover_trips, load_ground_truth
from plotting_utils import generate_html_report


def main():
    parser = argparse.ArgumentParser(description="Driver Safety Evaluation Framework")
    parser.add_argument("--all", action="store_true", help="Run all analysis modules")
    parser.add_argument("--stats", action="store_true", help="Dataset statistics")
    parser.add_argument("--gps", action="store_true", help="GPS route analysis")
    parser.add_argument("--ground-truth", action="store_true", help="Ground truth evaluation")
    parser.add_argument("--gaze", action="store_true", help="Gaze analysis")
    parser.add_argument("--lanes", action="store_true", help="Lane detection analysis")
    parser.add_argument("--safety", action="store_true", help="Safety event analysis")
    parser.add_argument("--run-pipeline", action="store_true",
                        help="Run analysis pipeline on event windows (slow)")
    parser.add_argument("--force-rerun", action="store_true",
                        help="Force re-run pipeline even if cached results exist")
    parser.add_argument("--video-base", type=str, default=str(VIDEO_BASE),
                        help=f"Path to video folders (default: {VIDEO_BASE})")
    parser.add_argument("--output-dir", type=str, default=str(OUTPUT_DIR),
                        help=f"Output directory (default: {OUTPUT_DIR})")
    args = parser.parse_args()

    # Apply overrides
    import config
    config.VIDEO_BASE = Path(args.video_base)
    config.OUTPUT_DIR = Path(args.output_dir)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Determine which modules to run
    run_all = args.all
    run_stats = run_all or args.stats
    run_gps = run_all or args.gps
    run_gt = run_all or args.ground_truth
    run_gaze = run_all or args.gaze
    run_lanes = run_all or args.lanes
    run_safety = run_all or args.safety

    if not any([run_stats, run_gps, run_gt, run_gaze, run_lanes, run_safety]):
        parser.print_help()
        print("\nError: specify at least one module (--all, --stats, --gps, etc.)")
        sys.exit(1)

    wall_t0 = time.time()

    # ── Discover trips ──
    print(f"[Discovery] Scanning {config.VIDEO_BASE} ...")
    trips = discover_trips(config.VIDEO_BASE)
    print(f"  Found {len(trips)} trips, {sum(len(t['video_pairs']) for t in trips)} video pairs")

    labeled_trips = [t for t in trips if t["has_labels"]]
    print(f"  Labeled trips: {len(labeled_trips)}")

    # ── Load ground truth labels ──
    all_labels = {}
    for trip in labeled_trips:
        label_path = trip["path"] / "event_labels.json"
        if label_path.exists():
            labels = load_ground_truth(label_path)
            all_labels[trip["name"]] = labels
            n_events = sum(len(v) for v in labels.values())
            print(f"    {trip['name']}: {len(labels)} videos, {n_events} events")

    # ── Optionally run pipeline ──
    window_results = []
    if args.run_pipeline:
        from pipeline_runner import run_pipeline_for_trip, compute_windows
        # Count total windows upfront for progress tracking
        total_windows = 0
        for trip in labeled_trips:
            for events in all_labels.get(trip["name"], {}).values():
                total_windows += len(compute_windows(events))
        print(f"\n[Pipeline] Running analysis on {total_windows} windows "
              f"across {len(labeled_trips)} trips ...")
        pt0 = time.time()
        global_progress = {"done": 0, "total": total_windows, "start_time": pt0}
        for ti, trip in enumerate(labeled_trips):
            labels = all_labels.get(trip["name"], {})
            if labels:
                print(f"  [{ti+1}/{len(labeled_trips)}] Trip: {trip['name']} "
                      f"({len(labels)} videos)")
                results = run_pipeline_for_trip(
                    trip, labels, force=args.force_rerun,
                    global_progress=global_progress,
                )
                window_results.extend(results)
        elapsed = time.time() - pt0
        print(f"[Pipeline] Done ({elapsed:.1f}s) — {len(window_results)} windows completed")
    else:
        # Load cached pipeline results
        window_results = _load_cached_results()

    # ── Run modules ──
    report_sections = []

    # Build ordered list of modules to run
    modules = []
    if run_stats:   modules.append("stats")
    if run_gps:     modules.append("gps")
    if run_gt:      modules.append("ground-truth")
    if run_gaze:    modules.append("gaze")
    if run_lanes:   modules.append("lanes")
    if run_safety:  modules.append("safety")

    n_modules = len(modules)
    print(f"\n{'='*60}")
    print(f"Running {n_modules} analysis modules: {', '.join(modules)}")
    print(f"{'='*60}")

    mod_idx = 0

    if run_stats:
        mod_idx += 1
        print(f"\n[{mod_idx}/{n_modules}] ── Dataset Stats ──")
        from dataset_stats import run_dataset_stats
        plots, summary_html = run_dataset_stats(trips, all_labels)
        report_sections.append({
            "heading": "Dataset Overview",
            "items": plots,
            "html_content": summary_html,
        })

    if run_gps:
        mod_idx += 1
        print(f"\n[{mod_idx}/{n_modules}] ── GPS Analysis ──")
        from gps_analysis import run_gps_analysis
        plots, stats_html = run_gps_analysis(labeled_trips, all_labels)
        report_sections.append({
            "heading": "GPS Analysis",
            "items": plots,
            "html_content": stats_html,
        })

    if run_gt:
        mod_idx += 1
        if window_results:
            print(f"\n[{mod_idx}/{n_modules}] ── Ground Truth Evaluation ──")
            from ground_truth_eval import run_ground_truth_eval
            plots, detail_html = run_ground_truth_eval(labeled_trips, all_labels, window_results)
            report_sections.append({
                "heading": "Ground Truth Evaluation",
                "items": plots,
                "html_content": detail_html,
            })
        else:
            print(f"\n[{mod_idx}/{n_modules}] ── Ground Truth Evaluation ── SKIPPED (no pipeline results, use --run-pipeline)")

    if run_gaze:
        mod_idx += 1
        if window_results:
            print(f"\n[{mod_idx}/{n_modules}] ── Gaze Analysis ──")
            from gaze_analysis import run_gaze_analysis
            plots, stats_html = run_gaze_analysis(window_results)
            report_sections.append({
                "heading": "Gaze Analysis",
                "items": plots,
                "html_content": stats_html,
            })
        else:
            print(f"\n[{mod_idx}/{n_modules}] ── Gaze Analysis ── SKIPPED (no pipeline results, use --run-pipeline)")

    if run_lanes:
        mod_idx += 1
        if window_results:
            print(f"\n[{mod_idx}/{n_modules}] ── Lane Detection Analysis ──")
            from lane_analysis import run_lane_analysis
            plots, stats_html = run_lane_analysis(window_results, labeled_trips)
            report_sections.append({
                "heading": "Lane Detection Analysis",
                "items": plots,
                "html_content": stats_html,
            })
        else:
            print(f"\n[{mod_idx}/{n_modules}] ── Lane Detection Analysis ── SKIPPED (no pipeline results, use --run-pipeline)")

    if run_safety:
        mod_idx += 1
        if window_results:
            print(f"\n[{mod_idx}/{n_modules}] ── Safety Analysis ──")
            from safety_analysis import run_safety_analysis
            plots, stats_html = run_safety_analysis(window_results, labeled_trips)
            report_sections.append({
                "heading": "Safety Analysis",
                "items": plots,
                "html_content": stats_html,
            })
        else:
            print(f"\n[{mod_idx}/{n_modules}] ── Safety Analysis ── SKIPPED (no pipeline results, use --run-pipeline)")

    # ── Generate HTML report ──
    if report_sections:
        report_path = generate_html_report(
            "Driver Safety — Evaluation Report", report_sections,
        )
        print(f"\n[Report] Written to {report_path}")

    wall_elapsed = time.time() - wall_t0
    print(f"\n[Total] {wall_elapsed:.1f}s elapsed")


def _load_cached_results():
    """Load previously cached pipeline results from PIPELINE_RESULTS_DIR."""
    import json as _json

    results = []
    skipped = 0
    if not PIPELINE_RESULTS_DIR.exists():
        return results

    for video_dir in sorted(PIPELINE_RESULTS_DIR.iterdir()):
        if not video_dir.is_dir():
            continue
        video_id = video_dir.name
        for window_dir in sorted(video_dir.iterdir()):
            if not window_dir.is_dir():
                continue
            results_file = window_dir / "results.json"
            if not results_file.exists():
                continue
            # Validate JSON
            try:
                with open(results_file) as f:
                    _json.load(f)
            except (_json.JSONDecodeError, OSError):
                print(f"  WARNING: corrupt cache file removed: {results_file}")
                try:
                    results_file.unlink()
                except OSError:
                    pass
                skipped += 1
                continue
            # Parse window_start and window_end from dir name: window_28_88
            parts = window_dir.name.replace("window_", "").split("_")
            try:
                ws = float(parts[0])
                we = float(parts[1])
            except (ValueError, IndexError):
                continue
            road_only = (video_dir / "road_only.marker").exists()
            results.append({
                "window_start": ws,
                "window_end": we,
                "results_path": results_file,
                "video_id": video_id,
                "road_only": road_only,
            })

    if results:
        print(f"  Loaded {len(results)} cached pipeline results"
              + (f" ({skipped} corrupt files removed)" if skipped else ""))
    return results


if __name__ == "__main__":
    main()
