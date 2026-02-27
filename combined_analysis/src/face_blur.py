import cv2
import subprocess
import logging
import shutil
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _identify_driver(faces, frame_w, frame_h):
    """
    Returns the InsightFace Face object most likely to be the driver.
    For landscape frames: largest face in the left half (driver's seat side);
    falls back to largest overall if none found there.
    For portrait frames: largest face overall.
    """
    if not faces:
        return None

    def area(f):
        x1, y1, x2, y2 = f.bbox
        return (x2 - x1) * (y2 - y1)

    def centre_x(f):
        x1, _, x2, _ = f.bbox
        return (x1 + x2) / 2

    if frame_w > frame_h:
        left = [f for f in faces if centre_x(f) < frame_w / 2]
        candidates = left if left else faces
    else:
        candidates = faces

    return max(candidates, key=area)


def blur_passenger_faces(face_path: Path) -> None:
    """
    Blurs all faces except the driver's in face_path in-place.
    Uses InsightFace (RetinaFace) — the same library as the rest of the pipeline.
    Writes blurred frames to a temp file, merges original audio, then renames
    over the original. Non-fatal: logs errors and leaves original unchanged.
    """
    if not face_path.exists():
        logger.warning(f"blur_passenger_faces: {face_path} not found, skipping")
        return

    video_only_tmp = face_path.parent / "face_blur_noaudio.mp4"
    face_tmp = face_path.parent / "face_tmp.mp4"

    try:
        from insightface.app import FaceAnalysis

        cap = cv2.VideoCapture(str(face_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        env = os.environ.copy()
        env.pop('LD_LIBRARY_PATH', None)

        # Step 1: write blurred frames into a video-only temp file via ffmpeg pipe
        pipe_cmd = [
            'ffmpeg', '-y',
            '-f', 'rawvideo', '-vcodec', 'rawvideo',
            '-s', f'{w}x{h}', '-pix_fmt', 'bgr24', '-r', str(fps),
            '-i', 'pipe:0',
            '-an',
            '-c:v', 'libx264', '-crf', '23', '-preset', 'fast',
            str(video_only_tmp),
        ]
        proc = subprocess.Popen(
            pipe_cmd, stdin=subprocess.PIPE, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        detector = FaceAnalysis(providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
        detector.prepare(ctx_id=0, det_size=(640, 640))

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            faces = detector.get(frame)

            if len(faces) > 1:
                driver = _identify_driver(faces, w, h)
                for face in faces:
                    if face is driver:
                        continue
                    x1, y1, x2, y2 = face.bbox.astype(int)
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w, x2), min(h, y2)
                    if x2 > x1 and y2 > y1:
                        roi = frame[y1:y2, x1:x2]
                        ksize = max(51, (min(x2 - x1, y2 - y1) // 3) | 1)
                        frame[y1:y2, x1:x2] = cv2.GaussianBlur(roi, (ksize, ksize), 0)

            proc.stdin.write(frame.tobytes())

        cap.release()
        proc.stdin.close()
        proc.wait()

        if proc.returncode != 0:
            raise RuntimeError("ffmpeg pipe encoding failed")

        # Step 2: merge with original audio
        merge_cmd = [
            'ffmpeg', '-y',
            '-i', str(video_only_tmp),
            '-i', str(face_path),
            '-map', '0:v:0', '-map', '1:a?',
            '-c:v', 'copy', '-c:a', 'copy',
            str(face_tmp),
        ]
        r = subprocess.run(
            merge_cmd, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if r.returncode != 0:
            raise RuntimeError("ffmpeg audio merge failed")

        # Step 3: atomic rename over original
        shutil.move(str(face_tmp), str(face_path))
        logger.info(f"blur_passenger_faces: completed for {face_path.name}")

    except Exception as e:
        logger.error(f"blur_passenger_faces failed: {e}")
    finally:
        for tmp in [video_only_tmp, face_tmp]:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
