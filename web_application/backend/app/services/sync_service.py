import os
import subprocess
import numpy as np
from pathlib import Path
from scipy.io import wavfile
from scipy import signal
import logging

logger = logging.getLogger(__name__)

class SyncService:
    @staticmethod
    def get_audio_offset(video1_path: Path, video2_path: Path) -> float:
        """
        Calculates the time offset between two videos using audio cross-correlation.
        Returns: Offset in seconds (video1_time - video2_time).
        """
        temp_dir = video1_path.parent / "temp_audio"
        temp_dir.mkdir(exist_ok=True)
        
        wav1 = temp_dir / "audio1.wav"
        wav2 = temp_dir / "audio2.wav"
        
        try:
            # Extract audio using ffmpeg
            # -ac 1 (mono), -ar 16000 (16kHz), -t 60 (first 60 seconds)
            for vid, wav in [(video1_path, wav1), (video2_path, wav2)]:
                cmd = [
                    "ffmpeg", "-i", str(vid),
                    "-vn", "-ac", "1", "-ar", "16000",
                    "-t", "60", "-y", str(wav)
                ]
                # Clean env for ffmpeg
                env = os.environ.copy()
                if "LD_LIBRARY_PATH" in env:
                    del env["LD_LIBRARY_PATH"]
                subprocess.run(cmd, capture_output=True, env=env)

            # Read audio files
            fs1, data1 = wavfile.read(wav1)
            fs2, data2 = wavfile.read(wav2)
            
            # Normalize
            data1 = data1.astype(float)
            data2 = data2.astype(float)
            data1 /= np.max(np.abs(data1))
            data2 /= np.max(np.abs(data2))
            
            # Cross-correlation
            # This can be slow for large arrays, but we only took 60s at 16kHz
            correlation = signal.correlate(data1, data2, mode='full')
            lags = signal.correlation_lags(len(data1), len(data2), mode='full')
            
            lag_idx = np.argmax(np.abs(correlation))
            lag = lags[lag_idx]
            
            offset = lag / fs1
            logger.info(f"Detected audio offset: {offset}s")
            return offset
            
        except Exception as e:
            logger.error(f"Error calculating audio offset: {e}")
            return 0.0
        finally:
            # Cleanup
            if wav1.exists(): wav1.unlink()
            if wav2.exists(): wav2.unlink()
            if temp_dir.exists(): temp_dir.rmdir()
