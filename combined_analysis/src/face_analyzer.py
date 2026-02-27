import pickle
import cv2
import pandas as pd
from pathlib import Path
from insightface.app import FaceAnalysis
import config

class FaceAnalyzer:
    def __init__(self, models_dir):
        # Enable CUDA with CPU fallback
        self.app = FaceAnalysis(providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
        self.app.prepare(ctx_id=0, det_size=(640, 640))
        
        models_dir = Path(models_dir)
        print("Loading Face Analysis Models...")
        self.svm = self._load_model(models_dir / 'svm_head_pose_model.pkl')
        self.pca = self._load_model(models_dir / 'pca_head_pose_model.pkl')

    @staticmethod
    def _load_model(path: Path):
        if path.exists():
            with open(path, 'rb') as f:
                return pickle.load(f)
        print(f"Warning: Model not found at {path}")
        return None

    def process_frame(self, frame):
        """
        Analyzes the frame for face and head pose.
        Returns:
            frame: The blurred frame (driver unblurred, others blurred).
            analysis_data: Dictionary containing pose and label info, plus raw detection data.
        """
        faces = self.app.get(frame)
        if not faces:
            return frame, None

        # 1. Identify driver face
        driver_face = self._identify_driver(faces, frame.shape)
        
        # 2. Apply blurring to other faces
        blurred_frame = self._apply_blurring(frame, faces, driver_face)

        # 3. Analyze driver face
        face = driver_face
        pitch, yaw, roll = face.pose if hasattr(face, 'pose') and face.pose is not None else (0.0, 0.0, 0.0)
        
        # Keypoints processing
        kps = face.kps.astype(int)
        if len(kps) >= 3:
            nose_2d = tuple(kps[2])
        else:
            bbox = face.bbox.astype(int)
            nose_2d = ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)

        # Classification
        svm_label, svm_conf = "N/A", 0.0
        if self.svm and self.pca:
            input_data = pd.DataFrame([[yaw, pitch, roll]], columns=['yaw', 'pitch', 'roll'])
            pca_input = self.pca.transform(input_data)
            svm_pred_idx = self.svm.predict(pca_input)[0]
            svm_probs = self.svm.predict_proba(pca_input)[0]
            svm_conf = svm_probs[svm_pred_idx]
            svm_label = config.CLASS_NAMES.get(svm_pred_idx, "Unknown")

        analysis_data = {
            'yaw': int(yaw), 'pitch': int(pitch), 'roll': int(roll),
            'label': svm_label, 'conf': svm_conf,
            'bbox': face.bbox.astype(int),
            'kps': kps,
            'nose_2d': nose_2d
        }

        # Return the blurred frame and analysis data
        return blurred_frame, analysis_data

    def _identify_driver(self, faces, frame_shape):
        """
        Logic for driver identification:
        - If landscape (width > height):
          - Largest face on the left side of the video.
          - If no face on left, largest overall face.
        - If portrait:
          - Largest face overall.
        """
        if not faces:
            return None

        h, w = frame_shape[:2]
        is_landscape = w > h

        def face_area(f):
            bbox = f.bbox
            return (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])

        if is_landscape:
            # InsightFace bboxes are [x1, y1, x2, y2]
            # Use center of face to determine if it's on the left side
            left_faces = [f for f in faces if (f.bbox[0] + f.bbox[2]) / 2 < w / 2]
            if left_faces:
                return max(left_faces, key=face_area)
            else:
                return max(faces, key=face_area)
        else:
            return max(faces, key=face_area)

    def _apply_blurring(self, frame, faces, driver_face):
        """
        Blurs all faces except the driver_face.
        """
        if not faces:
            return frame

        blurred_frame = frame.copy()
        for face in faces:
            # Compare using object identity
            if face is driver_face:
                continue

            bbox = face.bbox.astype(int)
            x1, y1, x2, y2 = bbox
            
            # Clamp to frame boundaries
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(frame.shape[1], x2)
            y2 = min(frame.shape[0], y2)

            if x2 > x1 and y2 > y1:
                roi = blurred_frame[y1:y2, x1:x2]
                # Apply strong blur proportional to face size
                ksize = int(max(x2-x1, y2-y1) / 3) | 1
                if ksize < 3: ksize = 3
                roi = cv2.GaussianBlur(roi, (ksize, ksize), 30)
                blurred_frame[y1:y2, x1:x2] = roi

        return blurred_frame