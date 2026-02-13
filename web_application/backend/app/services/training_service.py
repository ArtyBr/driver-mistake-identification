import json
import numpy as np
import pickle
from pathlib import Path
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
import logging

logger = logging.getLogger(__name__)

class TrainingService:
    @staticmethod
    def train_gaze_model(job_id: str, calibration_data_str: str, output_dir: Path) -> Path:
        """
        Trains a session-specific SVM model using calibration data.
        Generates synthetic data around the calibration points for robustness.
        """
        try:
            calib = json.loads(calibration_data_str)
            # calib format: {'Ahead': {'yaw': 0, 'pitch': 0, ...}, 'Left Mirror': {...}, ...}
            
            X = []
            y = []
            
            # Class mapping (must match config.CLASS_NAMES)
            # {0: 'Left Mirror', 1: 'Right Mirror', 2: 'Looking Ahead', 3: 'Rear Mirror'}
            class_map = {
                'Left Mirror': 0,
                'Right Mirror': 1,
                'Ahead': 2,
                'Rear Mirror': 3
            }

            for label, pose in calib.items():
                if label not in class_map:
                    continue
                
                class_idx = class_map[label]
                # Extract [yaw, pitch, roll]
                centroid = [pose['yaw'], pose['pitch'], pose['roll']]
                
                # Generate synthetic samples (Gaussian noise)
                num_samples = 500
                noise = np.random.normal(0, 3.0, (num_samples, 3)) # 3 degrees std dev
                samples = centroid + noise
                
                X.append(samples)
                y.append(np.full(num_samples, class_idx))

            if not X:
                raise ValueError("No valid calibration data found")

            X = np.vstack(X)
            y = np.concatenate(y)

            # Train SVM
            model = SVC(kernel='rbf', probability=True)
            model.fit(X, y)

            # Save model
            model_path = output_dir / "user_svm.pkl"
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
            
            logger.info(f"Trained user-specific SVM for job {job_id}")
            return model_path

        except Exception as e:
            logger.error(f"Error training SVM for {job_id}: {e}")
            return None
