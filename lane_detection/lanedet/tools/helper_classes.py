import numpy as np
import cv2
from scipy.optimize import linear_sum_assignment

class LaneTrack:
    def __init__(self, detection_coeffs, track_id):
        self.id = track_id
        self.kf = self.init_kalman_filter(detection_coeffs)
        self.hits = 1
        # self.update(detection_coeffs) # Initialize KF with first detection
        self.misses = 0
        self.age = 0

    def init_kalman_filter(self, initial_coeffs):
        # We track state [a, b, c] and their velocities [da, db, dc]
        # State vector (6, 1): [a, b, c, da, db, dc]
        # Measurement vector (3, 1): [a, b, c]
        kf = cv2.KalmanFilter(6, 3) 
        
        # State Transition Matrix (F) - constant velocity model
        dt = 1.0
        kf.transitionMatrix = np.array([
            [1, 0, 0, dt, 0, 0],
            [0, 1, 0, 0, dt, 0],
            [0, 0, 1, 0, 0, dt],
            [0, 0, 0, 1, 0, 0],
            [0, 0, 0, 0, 1, 0],
            [0, 0, 0, 0, 0, 1]
        ], dtype=np.float32)

        # Measurement Matrix (H) - we only measure position
        kf.measurementMatrix = np.array([
            [1, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0]
        ], dtype=np.float32)

        # Process Noise Covariance (Q) - tune this
        # Higher values mean we trust the prediction less
        kf.processNoiseCov = np.eye(6, dtype=np.float32) * 1e-3

        # --- AFTER ---
        # We need to tune the diagonal of Q
        q = np.eye(6, dtype=np.float32)
        q[:3, :3] *= 1e-4
        q[3:, 3:] *= 1e-8
        kf.processNoiseCov = q
        kf.measurementNoiseCov = np.eye(3, dtype=np.float32) * 1e-2
        kf.statePost = np.zeros(6, dtype=np.float32).reshape(6, 1)
        kf.statePost[:3] = initial_coeffs.astype(np.float32).reshape(3, 1)
        return kf
    

    def predict(self):
        # Predict the next state
        prediction = self.kf.predict()
        self.age += 1
        self.misses += 1
        # Return predicted position [a, b, c]
        return prediction[:3].reshape(3) 

    def update(self, detection_coeffs):
        # Update the filter with the new measurement
        self.kf.correct(detection_coeffs.astype(np.float32))
        self.misses = 0
        self.hits += 1

    @property
    def coeffs(self):
        return (self.kf.statePost if self.misses == 0 else self.kf.statePre)[:3].ravel()

    @property
    def confidence(self):
        # make the confidence a percentage based on the age of the lane, the hits and the misses
        if self.age == 0:
            return 0.0
        
        return round(max(0.0, min(1.0, (self.hits - self.misses) / self.age)), 2)

class LaneTracker:
    def __init__(self, miss_threshold=60, img_height=590, num_y_samples=20):
        self.tracks = []
        self.next_id = 0
        self.miss_threshold = miss_threshold
        
        self.y_eval_points = np.linspace(0, img_height - 1, num_y_samples)

    def _get_x_values(self, coeffs):
        a, b, c = coeffs
        return a * self.y_eval_points**2 + b * self.y_eval_points + c

    def update(self, detections):
        predictions = []
        track_indices = []
        for i, track in enumerate(self.tracks):
            predictions.append(track.predict())
            track_indices.append(i)

        if not detections:
            for i in range(len(self.tracks)):
                if self.tracks[i].misses > self.miss_threshold:
                    self.tracks[i] = None
            self.tracks = [t for t in self.tracks if t is not None]
            return [(t.coeffs, t.id, t.misses) for t in self.tracks]
            
        if not predictions:
            for det in detections:
                new_track = LaneTrack(det, self.next_id)
                self.tracks.append(new_track)
                self.next_id += 1
            return [(t.coeffs, t.id, t.misses) for t in self.tracks]

        pred_x_vals = [self._get_x_values(p) for p in predictions]
        det_x_vals = [self._get_x_values(d) for d in detections]

        cost_matrix = np.zeros((len(predictions), len(detections)))
        for i, pred_x in enumerate(pred_x_vals):
            for j, det_x in enumerate(det_x_vals):
                avg_dist = np.mean(np.abs(pred_x - det_x))
                cost_matrix[i, j] = avg_dist
        
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        matched_track_indices = set()
        matched_det_indices = set()

        for r, c in zip(row_ind, col_ind):
            track_idx = track_indices[r]
            self.tracks[track_idx].update(detections[c])
            matched_track_indices.add(r)
            matched_det_indices.add(c)
        
        unmatched_track_indices = set(range(len(predictions))) - matched_track_indices
        for r in unmatched_track_indices:
            track_idx = track_indices[r]
            if self.tracks[track_idx].misses > self.miss_threshold:
                self.tracks[track_idx] = None
        self.tracks = [t for t in self.tracks if t is not None]

        unmatched_det_indices = set(range(len(detections))) - matched_det_indices
        for j in unmatched_det_indices:
            det = detections[j]
            new_track = LaneTrack(det, self.next_id)
            self.tracks.append(new_track)
            self.next_id += 1

        return [(t.coeffs, t.id, t.misses) for t in self.tracks]