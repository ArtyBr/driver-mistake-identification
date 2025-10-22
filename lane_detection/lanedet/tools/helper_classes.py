import numpy as np
import cv2
from scipy.optimize import linear_sum_assignment

class LaneTrack:
    def __init__(self, detection_coeffs, track_id):
        self.id = track_id
        self.kf = self.init_kalman_filter()
        self.update(detection_coeffs) # Initialize KF with first detection
        self.misses = 0
        self.age = 0

    def init_kalman_filter(self):
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
        kf.processNoiseCov = np.eye(6, dtype=np.float32) * 1e-2

        # Measurement Noise Covariance (R) - tune this
        # Higher values mean we trust the detection less
        kf.measurementNoiseCov = np.eye(3, dtype=np.float32) * 1e-1

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

    @property
    def coeffs(self):
        # Get the current best estimate of the state [a, b, c]
        if self.misses == 0:
            # We were just updated, use the corrected posterior state
            return self.kf.statePost[:3].reshape(3)
        else:
            # We are "coasting", use the predicted prior state
            return self.kf.statePre[:3].reshape(3)

class LaneTracker:
    def __init__(self, miss_threshold=60, iou_threshold=0.5): # Use coeff distance instead
        self.tracks = []
        self.next_id = 0
        self.miss_threshold = miss_threshold

    def update(self, detections):
        # 1. Predict new positions for all existing tracks
        predictions = []
        track_indices = []
        for i, track in enumerate(self.tracks):
            predictions.append(track.predict())
            track_indices.append(i)

        # 2. Associate detections with predictions
        # We need a cost matrix. Let's use simple Euclidean distance of coefficients
        cost_matrix = np.zeros((len(predictions), len(detections)))
        for i, pred_coeffs in enumerate(predictions):
            for j, det_coeffs in enumerate(detections):
                cost_matrix[i, j] = np.linalg.norm(pred_coeffs - det_coeffs)
        
        # Use Hungarian algorithm for optimal assignment
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        # You might want a threshold here to reject bad matches
        # For this example, we'll just use the matches.

        matched_track_indices = set(row_ind)
        matched_det_indices = set(col_ind)

        # 3. Update matched tracks
        for r, c in zip(row_ind, col_ind):
            track_idx = track_indices[r]
            self.tracks[track_idx].update(detections[c])

        # 4. Handle unmatched tracks (missed detections)
        for i, track in enumerate(self.tracks):
            if i not in matched_track_indices:
                if track.misses > self.miss_threshold:
                    self.tracks[i] = None # Mark for removal
        self.tracks = [t for t in self.tracks if t is not None] # Clean up

        # 5. Handle unmatched detections (new tracks)
        for j, det in enumerate(detections):
            if j not in matched_det_indices:
                new_track = LaneTrack(det, self.next_id)
                self.tracks.append(new_track)
                self.next_id += 1

        # Return the current state of all active tracks
        return [(t.coeffs, t.id) for t in self.tracks] # Only return 'live' tracks