import pickle
import cv2
import pandas as pd
from pathlib import Path
from insightface.app import FaceAnalysis
import config

class FaceAnalyzer:
    def __init__(self, models_dir: Path):
        self.app = FaceAnalysis(providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
        self.app.prepare(ctx_id=0, det_size=(640, 640))
        
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
            frame: The original frame (untouched).
            analysis_data: Dictionary containing pose and label info, plus raw detection data.
        """
        faces = self.app.get(frame)
        if not faces:
            return frame, None

        face = faces[0]
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

        # Note: We are NO LONGER drawing here.
        return frame, analysis_data