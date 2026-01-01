import subprocess
import logging
import os
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

def splice_videos(input_paths: List[Path], output_path: Path) -> bool:
    """
    Concatenates multiple video files into a single video file using ffmpeg.
    
    Args:
        input_paths: List of paths to the video files to be concatenated.
        output_path: Path where the resulting spliced video should be saved.
        
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
            # If the source and dest are the same, do nothing
            if input_paths[0].resolve() == output_path.resolve():
                return True
                
            # Move the single file to the output path
            # using shutil.move would be safer across filesystems but pathlib rename is fine here
            # assuming same temp dir.
            import shutil
            shutil.move(str(input_paths[0]), str(output_path))
            return True
        except Exception as e:
            logger.error(f"Error moving single file: {e}")
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
        
        # Run ffmpeg
        # -safe 0 is required for absolute paths
        # -c copy does a stream copy (fast, no re-encoding)
        cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0", 
            "-i", str(list_file_path), 
            "-c", "copy", str(output_path), "-y"
        ]
        
        # Prepare environment: remove LD_LIBRARY_PATH to avoid conflicts 
        # between conda libraries and system ffmpeg
        env = os.environ.copy()
        if "LD_LIBRARY_PATH" in env:
            del env["LD_LIBRARY_PATH"]

        # Capture output for debugging
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
