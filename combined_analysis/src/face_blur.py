import sys
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


def _run_blur(face_path: Path) -> None:
    """
    Core blur logic. Runs inside an isolated subprocess so that OpenCV/ONNX
    cleanup cannot corrupt the main analysis process's heap.
    """
    from insightface.app import FaceAnalysis

    video_only_tmp = face_path.parent / "face_blur_noaudio.mp4"
    face_tmp = face_path.parent / "face_tmp.mp4"

    try:
        cap = cv2.VideoCapture(str(face_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(str(video_only_tmp), fourcc, fps, (w, h))
        if not writer.isOpened():
            raise RuntimeError("cv2.VideoWriter failed to open")

        # Detection-only: we only need bounding boxes, not landmarks/pose/recognition.
        detector = FaceAnalysis(
            providers=['CUDAExecutionProvider', 'CPUExecutionProvider'],
            allowed_modules=['detection'],
        )
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

            writer.write(frame)

        cap.release()
        writer.release()

        # Merge with original audio via ffmpeg (best-effort — face videos may have no audio)
        env = os.environ.copy()
        env.pop('LD_LIBRARY_PATH', None)
        merge_cmd = [
            'ffmpeg', '-y',
            '-i', str(video_only_tmp),
            '-i', str(face_path),
            '-map', '0:v:0', '-map', '1:a?',
            '-c:v', 'copy', '-c:a', 'copy',
            str(face_tmp),
        ]
        r = subprocess.run(merge_cmd, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode != 0:
            logger.warning("blur: audio merge failed, using video-only output")
            shutil.move(str(video_only_tmp), str(face_path))
        else:
            shutil.move(str(face_tmp), str(face_path))

        print(f"blur_passenger_faces: completed for {face_path.name}", flush=True)

    except Exception as e:
        print(f"blur_passenger_faces failed: {e}", flush=True)
    finally:
        for tmp in [video_only_tmp, face_tmp]:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass


def blur_passenger_faces(face_path: Path) -> None:
    """
    Spawns an isolated subprocess to blur passenger faces in face_path.
    Running in a subprocess ensures OpenCV/ONNX destructor crashes cannot
    corrupt the main analysis process's heap.
    Non-fatal: if the subprocess fails the original file is left unchanged.
    """
    try:
        result = subprocess.run(
            [sys.executable, __file__, str(face_path)],
            timeout=600,
        )
        if result.returncode != 0:
            print(f"blur subprocess exited with code {result.returncode} — continuing with original video", flush=True)
    except subprocess.TimeoutExpired:
        print("blur subprocess timed out — continuing with original video", flush=True)
    except Exception as e:
        print(f"blur subprocess error: {e} — continuing with original video", flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: face_blur.py <face_path>")
        sys.exit(1)
    logging.basicConfig(level=logging.INFO)
    _run_blur(Path(sys.argv[1]))
