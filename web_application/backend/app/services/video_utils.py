import subprocess
import logging
import os
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

def _is_browser_playable(video_path: Path) -> bool:
    """Check via ffprobe whether the file is an mp4/mov container that browsers can play natively."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=format_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        env = os.environ.copy()
        env.pop("LD_LIBRARY_PATH", None)
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            return False
        fmt = result.stdout.strip().lower()
        # mp4/mov containers are browser-playable; avi, matroska, etc. are not
        return any(tag in fmt for tag in ("mov", "mp4", "m4a", "m4v"))
    except Exception:
        return False


def _run_ffmpeg_with_progress(cmd: list, duration_seconds: float, on_progress=None) -> subprocess.CompletedProcess:
    """
    Run an ffmpeg command with real-time progress tracking.

    Appends ``-progress pipe:1`` to *cmd* and parses ``out_time_us`` lines to
    compute a percentage.  *on_progress* is called with an int 0-100.
    Falls back to a plain ``subprocess.run`` when *on_progress* is ``None``.
    """
    env = os.environ.copy()
    env.pop("LD_LIBRARY_PATH", None)

    if on_progress is None or duration_seconds <= 0:
        return subprocess.run(cmd, capture_output=True, text=True, env=env)

    full_cmd = cmd + ["-progress", "pipe:1"]
    proc = subprocess.Popen(full_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)

    last_pct = -1
    for line in proc.stdout:
        if line.startswith("out_time_us="):
            try:
                us = int(line.split("=", 1)[1].strip())
                pct = min(100, int(us / (duration_seconds * 1_000_000) * 100))
                if pct != last_pct:
                    last_pct = pct
                    on_progress(pct)
            except (ValueError, ZeroDivisionError):
                pass

    proc.wait()
    stderr = proc.stderr.read() if proc.stderr else ""
    return subprocess.CompletedProcess(full_cmd, proc.returncode, stdout="", stderr=stderr)


def splice_videos(input_paths: List[Path], output_path: Path, on_progress=None) -> bool:
    """
    Concatenates multiple video files into a single video file using ffmpeg.

    Args:
        input_paths: List of paths to the video files to be concatenated.
        output_path: Path where the resulting spliced video should be saved.
        on_progress: Optional callback ``(pct: int) -> None`` called with 0-100
                     during transcoding.  Ignored for fast stream-copy paths.

    Returns:
        True if successful, False otherwise.
    """
    if not input_paths:
        logger.warning("No input paths provided for splicing.")
        return False

    # If there's only one video, we don't need to run ffmpeg concat,
    # but the caller expects the file at output_path.
    # The caller is responsible for renaming/moving if it's a single file
    # and they didn't write it to output_path directly.
    # However, to support the 'part' workflow, if we are given one part,
    # we should move/copy it to output_path.
    if len(input_paths) == 1:
        try:
            src = input_paths[0]
            # If the source and dest are the same, do nothing
            if src.resolve() == output_path.resolve():
                return True

            # Check the actual container format via ffprobe, since the file
            # may have been saved with a .mp4 extension despite being AVI/MOV.
            if not _is_browser_playable(src):
                logger.info(f"Transcoding {src.name} to mp4 for browser compatibility")
                duration = get_video_duration(src)
                cmd = [
                    _get_ffmpeg_exe(), "-i", str(src),
                    "-c:v", "libx264", "-crf", "28", "-preset", "ultrafast",
                    "-movflags", "+faststart",
                    "-c:a", "aac",
                    str(output_path), "-y",
                ]
                result = _run_ffmpeg_with_progress(cmd, duration, on_progress)
                if result.returncode != 0:
                    logger.error(f"FFmpeg transcode error: {result.stderr}")
                    return False
                return True

            # Already browser-playable mp4 — just move it
            import shutil
            shutil.move(str(src), str(output_path))
            return True
        except Exception as e:
            logger.error(f"Error processing single file: {e}")
            return False

    # Create a list file for ffmpeg
    # ffmpeg concat demuxer expects absolute paths
    list_file_path = output_path.parent / f"{output_path.stem}_input_list.txt"
    
    try:
        with open(list_file_path, "w") as f:
            for path in input_paths:
                # helper to escape single quotes in filenames for ffmpeg
                safe_path = str(path.absolute()).replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")
                
        logger.info(f"Splicing {len(input_paths)} videos into {output_path}")

        # Prepare environment: remove LD_LIBRARY_PATH to avoid conflicts
        # between conda libraries and system ffmpeg
        env = os.environ.copy()
        env.pop("LD_LIBRARY_PATH", None)

        # Check if any input is non-mp4 — if so, we must transcode rather
        # than stream-copy, since the codecs may not fit an mp4 container.
        needs_transcode = any(not _is_browser_playable(p) for p in input_paths)

        if needs_transcode:
            logger.info("Non-mp4 inputs detected — transcoding during concat")
            total_duration = sum(get_video_duration(p) for p in input_paths)
            cmd = [
                _get_ffmpeg_exe(), "-f", "concat", "-safe", "0",
                "-i", str(list_file_path),
                "-c:v", "libx264", "-crf", "28", "-preset", "ultrafast",
                "-movflags", "+faststart",
                "-c:a", "aac",
                str(output_path), "-y",
            ]
            result = _run_ffmpeg_with_progress(cmd, total_duration, on_progress)
        else:
            # All inputs are mp4 — fast stream copy
            cmd = [
                "ffmpeg", "-f", "concat", "-safe", "0",
                "-i", str(list_file_path),
                "-c", "copy", str(output_path), "-y",
            ]
            env = os.environ.copy()
            env.pop("LD_LIBRARY_PATH", None)
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Exception during video splicing: {e}")
        return False
        
    finally:
        # Cleanup list file
        if list_file_path.exists():
            try:
                list_file_path.unlink()
            except OSError:
                pass

def trim_video(input_path: Path, output_path: Path,
               start_seconds: float, duration_seconds: float) -> bool:
    """Trim video with frame-accurate FFmpeg seek."""
    cmd = [
        "ffmpeg", "-i", str(input_path),
        "-ss", str(start_seconds),
        "-t", str(duration_seconds),
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        str(output_path), "-y",
    ]
    env = os.environ.copy()
    env.pop("LD_LIBRARY_PATH", None)
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        logger.error("FFmpeg trim error: %s", result.stderr)
        return False
    return True


def get_video_duration(video_path: Path) -> float:
    """
    Returns the duration of the video in seconds using ffprobe.
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]

        # Prepare environment
        env = os.environ.copy()
        if "LD_LIBRARY_PATH" in env:
            del env["LD_LIBRARY_PATH"]

        result = subprocess.run(cmd, capture_output=True, text=True, env=env)

        if result.returncode == 0:
            return float(result.stdout.strip())
        else:
            logger.error(f"ffprobe error: {result.stderr}")
            return 0.0
    except Exception as e:
        logger.error(f"Error getting duration for {video_path}: {e}")
        return 0.0


def get_video_height(video_path: Path) -> int:
    """Returns the height of the first video stream using ffprobe. Returns 0 on failure."""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=height",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path)
        ]
        env = os.environ.copy()
        env.pop("LD_LIBRARY_PATH", None)
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip())
        logger.error(f"ffprobe height error: {result.stderr}")
        return 0
    except Exception as e:
        logger.error(f"Error getting height for {video_path}: {e}")
        return 0


def _get_ffmpeg_exe() -> str:
    """Returns the path to an ffmpeg binary with libx264 support (via imageio-ffmpeg if available)."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def transcode_to_quality(input_path: Path, output_path: Path, height: int) -> bool:
    """
    Transcodes a video to the specified height using libx264.
    Returns True on success, False on failure.
    """
    try:
        cmd = [
            _get_ffmpeg_exe(),
            "-i", str(input_path),
            "-vf", f"scale=-2:{height}",
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "fast",
            "-movflags", "+faststart",
            "-c:a", "copy",
            str(output_path),
            "-y"
        ]
        env = os.environ.copy()
        env.pop("LD_LIBRARY_PATH", None)
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            logger.error(f"FFmpeg transcode error: {result.stderr}")
            return False
        return True
    except Exception as e:
        logger.error(f"Exception during transcoding {input_path} to {height}p: {e}")
        return False
