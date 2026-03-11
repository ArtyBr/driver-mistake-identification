#!/usr/bin/env python3
"""
Backfill script: generates missing 720p and 480p video variants for existing jobs.

Scans all job directories under UPLOAD_DIR, checks for road.mp4 / face.mp4,
and creates missing quality variants (road_720p.mp4, face_720p.mp4, etc.).
Skips upscaling (won't create a 720p variant from a 480p source).

Usage:
    python backfill_quality_variants.py              # dry-run (default)
    python backfill_quality_variants.py --execute    # actually transcode
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

UPLOAD_DIR = Path("/dcs/large/safedrive_cs310_2526/uploads")
TARGETS = [720, 480]


def get_video_height(path: Path) -> int:
    try:
        env = os.environ.copy()
        env.pop("LD_LIBRARY_PATH", None)
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=height",
             "-of", "default=noprint_wrappers=1:nokey=1",
             str(path)],
            capture_output=True, text=True, env=env,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip())
    except Exception as e:
        print(f"  ERROR probing {path}: {e}")
    return 0


def transcode(input_path: Path, output_path: Path, height: int) -> bool:
    try:
        # Prefer imageio-ffmpeg for libx264 support if available
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            ffmpeg_exe = "ffmpeg"

        cmd = [
            ffmpeg_exe,
            "-i", str(input_path),
            "-vf", f"scale=-2:{height}",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "23",
            "-preset", "fast",
            "-movflags", "+faststart",
            "-c:a", "copy",
            str(output_path),
            "-y",
        ]
        env = os.environ.copy()
        env.pop("LD_LIBRARY_PATH", None)
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            print(f"  FFMPEG ERROR: {result.stderr[:200]}")
            return False
        return True
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Backfill 720p/480p video variants")
    parser.add_argument("--execute", action="store_true", help="Actually perform transcoding (default is dry-run)")
    args = parser.parse_args()

    if not UPLOAD_DIR.exists():
        print(f"Upload directory not found: {UPLOAD_DIR}")
        sys.exit(1)

    job_dirs = sorted([d for d in UPLOAD_DIR.iterdir() if d.is_dir() and d.name != "calibrations"])

    total_to_create = 0
    total_created = 0
    total_skipped = 0

    for job_dir in job_dirs:
        job_id = job_dir.name
        pairs = [
            (job_dir / "road.mp4", "road"),
            (job_dir / "face.mp4", "face"),
        ]

        for source_path, prefix in pairs:
            if not source_path.exists():
                continue

            height = get_video_height(source_path)
            if height == 0:
                print(f"  {job_id}/{prefix}: could not determine height, skipping")
                continue

            for target in TARGETS:
                out_path = job_dir / f"{prefix}_{target}p.mp4"
                if out_path.exists():
                    continue  # already exists
                if height <= target:
                    total_skipped += 1
                    continue  # would upscale

                total_to_create += 1
                if args.execute:
                    print(f"  Transcoding {job_id}/{prefix}.mp4 ({height}p) -> {prefix}_{target}p.mp4")
                    if transcode(source_path, out_path, target):
                        total_created += 1
                        print(f"    OK")
                    else:
                        print(f"    FAILED")
                else:
                    print(f"  [DRY-RUN] Would transcode {job_id}/{prefix}.mp4 ({height}p) -> {prefix}_{target}p.mp4")

    print(f"\nSummary:")
    print(f"  Variants needed:  {total_to_create}")
    print(f"  Skipped (upscale): {total_skipped}")
    if args.execute:
        print(f"  Created: {total_created}")
        print(f"  Failed:  {total_to_create - total_created}")
    else:
        print(f"  (Dry-run mode — use --execute to transcode)")


if __name__ == "__main__":
    main()
