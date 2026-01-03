import cv2
import numpy as np

class GiveWayDetector:
    def __init__(self, lane_detector_instance=None):
        pass

    def detect(self, frame, lane_coeffs=None):
        """
        Detects horizontal markings (Give Way / Stop lines) that span most of the ego-lane.
        
        Args:
            frame: Input image (H, W, 3).
            lane_coeffs: List of lane coefficients [(coeffs, id, conf, age, events), ...].
                         Coefficients are expected to be in 1640x590 model resolution (default for this project).
            
        Returns:
            lines: List of [x1, y1, x2, y2] representing detected markings.
        """
        if lane_coeffs is None:
            return []

        h_img, w_img = frame.shape[:2]
        
        # 1. Identify Ego Lanes (Left and Right closest to center)
        # Model resolution
        MODEL_W = 1640
        MODEL_H = 590
        
        # Scale factors
        sx = w_img / MODEL_W
        sy = h_img / MODEL_H
        
        ego_left = None
        ego_right = None
        min_dist_left = float('inf')
        min_dist_right = float('inf')
        
        center_x_img = w_img / 2.0
        
        # Evaluate at bottom of image
        for item in lane_coeffs:
            coeffs = item[0]
            a, b, c = coeffs # y = ax^2 + bx + c in model space
            
            # Map model-y to model-x, then scale to image-x
            # Bottom of model image is MODEL_H
            x_model = a * (MODEL_H**2) + b * MODEL_H + c
            x_img = x_model * sx
            
            dist = x_img - center_x_img
            
            if dist < 0: # Left side
                if abs(dist) < min_dist_left:
                    min_dist_left = abs(dist)
                    ego_left = coeffs
            else: # Right side
                if abs(dist) < min_dist_right:
                    min_dist_right = abs(dist)
                    ego_right = coeffs
        
        # If we don't have both lanes, we can't reliably check width coverage
        if ego_left is None or ego_right is None:
            return []

        # 2. Image Processing (Edges)
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
            
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 50, 150)
        
        # 3. Dynamic Masking based on Ego Lanes
        mask = np.zeros_like(edges)
        
        # Generate polygon for the ego lane
        # We'll sample points along the y-axis
        poly_points = []
        
        # We want the mask to cover the area strictly between the lanes
        # Sample 10 points from bottom to 60% up
        y_vals = np.linspace(h_img, h_img * 0.6, 10)
        
        left_pts = []
        right_pts = []
        
        for y_img in y_vals:
            # Convert y_img to y_model
            y_model = y_img / sy
            
            # Calc x_model
            xl_model = ego_left[0]*(y_model**2) + ego_left[1]*y_model + ego_left[2]
            xr_model = ego_right[0]*(y_model**2) + ego_right[1]*y_model + ego_right[2]
            
            # Scale back to x_img
            xl_img = int(xl_model * sx)
            xr_img = int(xr_model * sx)
            
            # Add padding? No, we want strictly between lanes to avoid curb noise
            left_pts.append((xl_img, int(y_img)))
            right_pts.append((xr_img, int(y_img)))
            
        # Create polygon: Left points (bottom-up) + Right points (top-down)
        # Actually y_vals is bottom-to-top (decreasing Y? No, linspace(h, 0.6h) is decreasing)
        # So Left points are Bottom -> Top
        # Right points should be Top -> Bottom for a closed loop
        poly_pts = np.array(left_pts + right_pts[::-1], dtype=np.int32)
        
        cv2.fillPoly(mask, [poly_pts], 255)
        masked_edges = cv2.bitwise_and(edges, mask)
        
        # 4. Hough Lines
        lines = cv2.HoughLinesP(masked_edges, 1, np.pi/180, threshold=30, 
                                minLineLength=30, maxLineGap=20)
        
        if lines is None:
            return []
            
        valid_lines = []
        
        for line in lines:
            x1, y1, x2, y2 = line[0]
            
            # Ensure x1 < x2
            if x1 > x2:
                x1, y1, x2, y2 = x2, y2, x1, y1
                
            # Horizontal Check
            if x2 == x1: continue
            slope = (y2 - y1) / (x2 - x1)
            if abs(slope) > 0.2: continue # Must be roughly horizontal
            
            # Width Coverage Check
            y_center = (y1 + y2) / 2
            
            # Calculate Lane Width at this Y
            y_model = y_center / sy
            xl_model = ego_left[0]*(y_model**2) + ego_left[1]*y_model + ego_left[2]
            xr_model = ego_right[0]*(y_model**2) + ego_right[1]*y_model + ego_right[2]
            
            xl_img = xl_model * sx
            xr_img = xr_model * sx
            
            lane_width = xr_img - xl_img
            if lane_width <= 0: continue
            
            line_width = x2 - x1
            
            # Start/End Checks: The line must be "inside" the lane boundaries
            # Allow some margin (e.g. 20% outside)
            margin = lane_width * 0.2
            if x1 < (xl_img - margin) or x2 > (xr_img + margin):
                continue

            # Coverage Ratio: Must cover at least 40% of the lane width
            # (Give way lines are often dashed or have gaps, so 40-50% is safe)
            if (line_width / lane_width) > 0.4:
                valid_lines.append([int(x1), int(y1), int(x2), int(y2)])
                
        # 5. Merge similar lines (Optional but good for clean output)
        # We can just return valid candidates for now.
        return valid_lines
