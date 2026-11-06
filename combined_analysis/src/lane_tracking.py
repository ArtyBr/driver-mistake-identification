import numpy as np
import cv2
from scipy.optimize import linear_sum_assignment

class LaneTrack:
    def __init__(self, detection_coeffs, track_id, img_height, img_width):
        self.id = track_id
        self.kf = self.init_kalman_filter(detection_coeffs)
        self.hits = 1
        self.misses = 0
        self.age = 1
        
        self.img_height = img_height
        self.img_width = img_width
        self.middle_x = img_width / 2.0
        
        self.previous_base_x = None
        
        self.lane_change_events = []

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
        q[3:, 3:] *= 1e-8
        kf.processNoiseCov = q
        
        kf.measurementNoiseCov = np.eye(3, dtype=np.float32) * 1e-1
        
        kf.statePost = np.zeros(6, dtype=np.float32).reshape(6, 1)
        kf.statePost[:3] = initial_coeffs.astype(np.float32).reshape(3, 1)
        
        kf.errorCovPost = np.eye(6, dtype=np.float32) * 1.0 
        
        return kf
    
    def update_lane_change_events(self):
        # Decrease the countdown for each event and remove if it reaches zero
        self.lane_change_events = [(countdown - 1, direction) for countdown, direction in self.lane_change_events if countdown > 1]

    def predict(self):
        prediction = self.kf.predict()
        self.age += 1
        self.misses += 1
        self.update_lane_change_events()
        return prediction[:3].reshape(3)

    def update(self, detection_coeffs):
        self.kf.correct(detection_coeffs.astype(np.float32))
        self.misses = 0
        self.hits += 1
        self.update_lane_change_events()

    @property
    def coeffs(self):
        state = self.kf.statePost if self.misses == 0 else self.kf.statePre
        return state[:3].ravel()

    @property
    def confidence(self):
        if self.age == 0: return 0.0
        return round(max(0.0, min(1.0, (self.hits - self.misses) / self.age)), 2)
        
    @property
    def state_vector(self):
        return (self.kf.statePost if self.misses == 0 else self.kf.statePre).ravel()

    def check_lane_cross(self):
        if self.confidence <= 0.7 or self.age <= 90:
            return None

        state = self.state_vector
        a, b, c = state[:3]
        da, db, dc = state[3:]

        y = self.img_height
        current_base_x = a * y**2 + b * y + c

        base_x_velocity = da * y**2 + db * y + dc

        velocity_threshold = 1.0
        if abs(base_x_velocity) < velocity_threshold:
            return None

        direction = None
        if self.previous_base_x is not None:
            if (self.previous_base_x < self.middle_x) and (current_base_x >= self.middle_x):
                if base_x_velocity > 0:
                    direction = "right-to-left"
                    self.lane_change_events.append((90, direction))
            elif (self.previous_base_x >= self.middle_x) and (current_base_x < self.middle_x):
                if base_x_velocity < 0:
                    direction = "left-to-right"
                    self.lane_change_events.append((90, direction))

        self.previous_base_x = current_base_x

        return direction


class LaneTracker:
    def __init__(self, miss_threshold=180, img_height=590, img_width=1640, num_y_samples=20):
        self.tracks = []
        self.next_id = 0
        self.miss_threshold = miss_threshold
        
        self.img_height = img_height
        self.img_width = img_width
        
        self.y_eval_points = np.linspace(0, img_height - 1, num_y_samples)
        self.cross_events = []

    def _get_x_values(self, coeffs):
        # Evaluate the polynomial at predefined y points
        a, b, c = coeffs
        return a * self.y_eval_points**2 + b * self.y_eval_points + c

    def _calculate_cost_matrix(self, predictions, detections):
        # Compute cost matrix based on mean absolute difference in x-values (distance)
        pred_x_vals = [self._get_x_values(p) for p in predictions]
        det_x_vals = [self._get_x_values(d) for d in detections]
        
        cost_matrix = np.zeros((len(predictions), len(detections)))
        for i, pred_x in enumerate(pred_x_vals):
            for j, det_x in enumerate(det_x_vals):
                cost_matrix[i, j] = np.mean(np.abs(pred_x - det_x))
        return cost_matrix

    def _create_new_tracks(self, detections):
        # Initialise new tracks for unmatched detections
        for det in detections:
            new_track = LaneTrack(det, self.next_id, self.img_height, self.img_width)
            self.tracks.append(new_track)
            self.next_id += 1

    def _prune_tracks(self):
        # Remove tracks that have too many misses relative to their confidence
        self.tracks = [t for t in self.tracks if t.misses <= self.miss_threshold * t.confidence]

    def update(self, detections):
        # Predict the next state for each track
        predicted_coeffs = [track.predict() for track in self.tracks]

        if not detections:
            self._prune_tracks()
            
            self.cross_events = []
            for track in self.tracks:
                direction = track.check_lane_cross()
                if direction:
                    self.cross_events.append({"track_id": track.id, "direction": direction})

            return [(t.coeffs, t.id, t.confidence, t.age, t.lane_change_events) for t in self.tracks]

        if not self.tracks:
            self._create_new_tracks(detections)
            return [(t.coeffs, t.id, t.confidence, t.age, t.lane_change_events) for t in self.tracks]


        # Gate-based matching
        cost_matrix = self._calculate_cost_matrix(predicted_coeffs, detections)
        
        row_ind, col_ind = [], []
        cost_matrix_copy = cost_matrix.copy()
        while cost_matrix_copy.size > 0:
            r, c = np.unravel_index(np.argmin(cost_matrix_copy), cost_matrix_copy.shape)
            if cost_matrix_copy[r, c] == np.inf or cost_matrix[r, c] > 300:
                break
            row_ind.append(r)
            col_ind.append(c)
            cost_matrix_copy[r, :] = np.inf
            cost_matrix_copy[:, c] = np.inf

        # Matched lanes are updated
        matched_det_indices = set()
        for r, c in zip(row_ind, col_ind):
            self.tracks[r].update(detections[c])
            matched_det_indices.add(c)
        
        # Unmatched detections start new tracks
        unmatched_det_indices = set(range(len(detections))) - matched_det_indices
        self._create_new_tracks([detections[i] for i in unmatched_det_indices])

        self._prune_tracks()

        self.cross_events = []
        for track in self.tracks:
            direction = track.check_lane_cross()
            if direction:
                event = {
                    "track_id": track.id,
                    "direction": direction,
                    "age": track.age,
                    "confidence": track.confidence
                }
                self.cross_events.append(event)
        if self.cross_events:
            print("Lane Change Detected:", self.cross_events)

        return [(t.coeffs, t.id, t.confidence, t.age, t.lane_change_events) for t in self.tracks]
