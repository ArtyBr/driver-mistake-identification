import subprocess
import logging
import librosa
import numpy as np
import scipy.signal
from pathlib import Path
from .video_utils import get_video_duration

logger = logging.getLogger(__name__)

class AudioSyncService:
    @staticmethod
    def extract_audio(video_path: Path, output_audio_path: Path):
        """Extracts audio from video using ffmpeg."""
        cmd = [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            str(output_audio_path)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    @staticmethod
    def compute_offset(audio1_path: Path, audio2_path: Path, max_duration: int = 60) -> float:
        """
        Computes the time offset (lag) of audio2 relative to audio1.
        Returns offset in seconds. Positive means audio2 starts AFTER audio1.
        """
        # Load only the first 60 seconds (sufficient for sync clap/beep)
        y1, sr = librosa.load(audio1_path, sr=16000, duration=max_duration)
        y2, _ = librosa.load(audio2_path, sr=16000, duration=max_duration)

        # Cross-correlation
        correlation = scipy.signal.correlate(y1, y2, mode="full")
        lags = scipy.signal.correlation_lags(y1.size, y2.size, mode="full")
        
        lag = lags[np.argmax(correlation)]
        offset = lag / sr
        return offset

    @staticmethod
    def sync_videos(phone_video_path: Path, dashcam_video_path: Path, output_dir: Path) -> tuple[Path, Path]:
        """
         aligns dashcam video to phone video.
        """
        # 1. Extract Audio
        phone_audio = output_dir / "phone_audio.wav"
        dashcam_audio = output_dir / "dashcam_audio.wav"
        
        AudioSyncService.extract_audio(phone_video_path, phone_audio)
        AudioSyncService.extract_audio(dashcam_video_path, dashcam_audio)
        
        # 2. Compute Offset
        # We want to know when dashcam starts relative to phone
        # Offset > 0: Dashcam starts later. Offset < 0: Dashcam starts earlier.
        offset = AudioSyncService.compute_offset(phone_audio, dashcam_audio)
        logger.info(f"Computed Sync Offset: {offset:.4f}s")
        
        # 3. Align
        # We will trim the one that starts earlier.
        
        synced_phone = output_dir / "synced_phone.mp4"
        synced_dashcam = output_dir / "synced_road.mp4"
        
        if offset > 0:
            # Dashcam starts later (or phone starts earlier). 
            # Trim Phone to match Dashcam start.
            # Start Phone at 'offset' seconds.
            cmd_phone = [
                "ffmpeg", "-y", "-i", str(phone_video_path),
                "-ss", str(abs(offset)), "-c", "copy", str(synced_phone)
            ]
            # Copy Dashcam as is
            cmd_dash = [
                "ffmpeg", "-y", "-i", str(dashcam_video_path),
                "-c", "copy", str(synced_dashcam)
            ]
        else:
            # Dashcam starts earlier. Trim Dashcam.
            # Start Dashcam at 'abs(offset)' seconds.
            cmd_dash = [
                "ffmpeg", "-y", "-i", str(dashcam_video_path),
                "-ss", str(abs(offset)), "-c", "copy", str(synced_dashcam)
            ]
            # Copy Phone as is
            cmd_phone = [
                "ffmpeg", "-y", "-i", str(phone_video_path),
                "-c", "copy", str(synced_phone)
            ]

        subprocess.run(cmd_phone, check=True)
        subprocess.run(cmd_dash, check=True)
        
        # Cleanup
        phone_audio.unlink(missing_ok=True)
        dashcam_audio.unlink(missing_ok=True)
        
        return synced_phone, synced_dashcam
