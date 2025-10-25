import numpy as np
import cv2
import math
from scipy.optimize import linear_sum_assignment

class LaneTrack:
    """
    Represents a single tracked lane, using a Kalman Filter to smooth
    the 2nd-order polynomial coefficients (a, b, c) over time.
    """
    def __init__(self, detection_coeffs, track_id):
        self.id = track_id
        self.kf = self.init_kalman_filter(detection_coeffs)
        self.hits = 1
        self.misses = 0
        self.age = 1

    def init_kalman_filter(self, initial_coeffs):
        # State: [a, b, c, da, db, dc], Measurement: [a, b, c]
        kf = cv2.KalmanFilter(6, 3) 
        
        dt = 1.0
        kf.transitionMatrix = np.array([
            [1, 0, 0, dt, 0, 0], [0, 1, 0, 0, dt, 0], [0, 0, 1, 0, 0, dt],
            [0, 0, 0, 1, 0, 0], [0, 0, 0, 0, 1, 0], [0, 0, 0, 0, 0, 1]
        ], dtype=np.float32)

        kf.measurementMatrix = np.array([
            [1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0], [0, 0, 1, 0, 0, 0]
        ], dtype=np.float32)

        q = np.eye(6, dtype=np.float32)
        q[:3, :3] *= 1e-4
        q[3:, 3:] *= 1e-9
        kf.processNoiseCov = q
        
        kf.measurementNoiseCov = np.eye(3, dtype=np.float32) * 1e-1
        
        kf.statePost = np.zeros(6, dtype=np.float32).reshape(6, 1)
        kf.statePost[:3] = initial_coeffs.astype(np.float32).reshape(3, 1)
        
        kf.errorCovPost = np.eye(6, dtype=np.float32) * 1.0 
        
        return kf

    def predict(self):
        """Predicts the next state and increments miss counter."""
        prediction = self.kf.predict()
        self.age += 1
        self.misses += 1
        return prediction[:3].reshape(3)

    def update(self, detection_coeffs):
        """Updates the filter with a new measurement and resets miss counter."""
        self.kf.correct(detection_coeffs.astype(np.float32))
        self.misses = 0
        self.hits += 1

    @property
    def coeffs(self):
        """Returns the current best estimate for the coefficients."""
        state = self.kf.statePost if self.misses == 0 else self.kf.statePre
        return state[:3].ravel()

    @property
    def confidence(self):
        """A simple confidence metric based on track history."""
        if self.age == 0: return 0.0
        return round(max(0.0, min(1.0, (self.hits - self.misses) / self.age)), 2)

class LaneTracker:
    """
    Manages multiple LaneTrack objects, handling detection-to-track
    assignment using the Hungarian algorithm and managing track lifecycle.
    """
    def __init__(self, miss_threshold=30, img_height=590, num_y_samples=20):
        self.tracks = []
        self.next_id = 0
        self.miss_threshold = miss_threshold
        # Y-points to sample for cost calculation
        self.y_eval_points = np.linspace(0, img_height - 1, num_y_samples)

    def _get_x_values(self, coeffs):
        """Evaluates the polynomial at the pre-defined y-sample points."""
        a, b, c = coeffs
        return a * self.y_eval_points**2 + b * self.y_eval_points + c

    def _calculate_cost_matrix(self, predictions, detections):
        """Calculates the cost matrix based on average L1 distance in x."""
        pred_x_vals = [self._get_x_values(p) for p in predictions]
        det_x_vals = [self._get_x_values(d) for d in detections]
        
        cost_matrix = np.zeros((len(predictions), len(detections)))
        for i, pred_x in enumerate(pred_x_vals):
            for j, det_x in enumerate(det_x_vals):
                cost_matrix[i, j] = np.mean(np.abs(pred_x - det_x))
        # print(cost_matrix)
        return cost_matrix

    def _create_new_tracks(self, detections):
        """Creates new LaneTrack objects for a list of detections."""
        for det in detections:
            new_track = LaneTrack(det, self.next_id)
            self.tracks.append(new_track)
            self.next_id += 1

    def _prune_tracks(self):
        """Removes tracks that have been missed for too long."""
        self.tracks = [t for t in self.tracks if t.misses <= self.miss_threshold * math.log(t.age)]

    def update(self, detections):
        """
        Main update loop: predict, associate, update, and manage tracks.
        'detections' is a list of [a, b, c] coefficient arrays.
        """
        # Kalman filter predictions of where tracks are expected to be
        predicted_coeffs = [track.predict() for track in self.tracks]

        # If no detections from model, use/return just previously predicted tracks
        if not detections:
            self._prune_tracks()
            return [(t.coeffs, t.id, t.misses) for t in self.tracks]

        # If no previously predicted tracks, create new ones for all detections
        if not self.tracks:
            self._create_new_tracks(detections)
            return [(t.coeffs, t.id, t.misses) for t in self.tracks]

        # Cost matrix represents the "distance" between predicted tracks and new detections
        # This helps match currently predicted/stored tracks to the detections
        cost_matrix = self._calculate_cost_matrix(predicted_coeffs, detections)
        
        # Assigns detections to tracks using the Hungarian algorithm from the cost matrix
        # row_ind, col_ind = linear_sum_assignment(cost_matrix)

        # Find the first closest match, then next closest, etc., until all possible matches are made
        row_ind, col_ind = [], []
        cost_matrix_copy = cost_matrix.copy()
        while cost_matrix_copy.size > 0:
            r, c = np.unravel_index(np.argmin(cost_matrix_copy), cost_matrix_copy.shape)
            if cost_matrix_copy[r, c] == np.inf or cost_matrix[r, c] > 300:  # Threshold to ignore bad matches
                # print(f"Didn't match track {r} with any detection, min cost {cost_matrix_copy[r, c]:.2f} with detection {c}")
                break
            row_ind.append(r)
            col_ind.append(c)
            cost_matrix_copy[r, :] = np.inf
            cost_matrix_copy[:, c] = np.inf

        # For each matched pair, update the track (kalman filter prediction is updated) 
        # with the detection
        # r corresponds to the track index, c to the detection index
        matched_det_indices = set()
        for r, c in zip(row_ind, col_ind):
            # print("Matched track {} with detection {}, cost {:.2f}".format(
            #     self.tracks[r].id, c, cost_matrix[r, c]))
            self.tracks[r].update(detections[c])
            matched_det_indices.add(c)
        
        # Create new tracks for unmatched detections
        unmatched_det_indices = set(range(len(detections))) - matched_det_indices
        self._create_new_tracks([detections[i] for i in unmatched_det_indices])

        self._prune_tracks()

        return [(t.coeffs, t.id, round(math.log(t.age), 2)) for t in self.tracks]