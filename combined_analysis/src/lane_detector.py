import cv2
import numpy as np
import config
from utils import scale_lane_coeffs
from lane_tracking import LaneTracker
from lane_detection.lanedet.tools.detect import Detect, visualize_tracked_lanes

class LaneDetectorWrapper:
    def __init__(self, lane_cfg):
        self.detector = Detect(lane_cfg)
        self.tracker = LaneTracker(img_height=config.MODEL_HEIGHT, img_width=config.MODEL_WIDTH)

    def process_frame(self, frame, show_dets=False):
        """
        Processes a frame for lane detection and tracking.
        Returns:
            vis_road: The visualized frame with lanes overlayed (resized to target).
            lane_data: The raw tracking data (coeffs, id, conf, age, events).
            cross_events: A list of immediate lane crossing events from this frame.
        """
        # coeffs are returned in MODEL resolution (1640x590)
        coeffs, ori_road = self.detector.get_lane_detections(frame)
        filtered_coeffs = self.tracker.update(coeffs)
        
        # Retrieve instantaneous cross events from the tracker
        cross_events = self.tracker.cross_events

        # Resize the base video frame to TARGET resolution (1920x1080) before overlaying lanes
        vis_road = cv2.resize(ori_road, (config.TARGET_WIDTH, config.TARGET_HEIGHT), interpolation=cv2.INTER_LINEAR)
        
        if show_dets:
            src_w = config.MODEL_WIDTH
            src_h = config.MODEL_HEIGHT
            dst_w = config.TARGET_WIDTH
            dst_h = config.TARGET_HEIGHT
            
            x_scale = dst_w / src_w
            y_scale = dst_h / src_h
            
            for (a, b, c) in coeffs:
                # Scale
                a_new = a * x_scale / (y_scale ** 2)
                b_new = b * x_scale / y_scale
                c_new = c * x_scale
                
                # Generate points for visualization
                y_points = np.linspace(int(dst_h * 0.55), dst_h - 1, 100)
                x_points = a_new * y_points**2 + b_new * y_points + c_new
                
                points = np.vstack((x_points, y_points)).T
                points = points[(points[:, 0] >= 0) & (points[:, 0] < dst_w)].astype(np.int32)
                
                if len(points) > 1:
                    # Draw dotted line (cyan color for raw detections)
                    for pt in points[::5]: # Draw a dot every 5th point
                         cv2.circle(vis_road, tuple(pt), 2, (0, 255, 255), -1)

        scaled_tracks = scale_lane_coeffs(
            filtered_coeffs, 
            src_w=config.MODEL_WIDTH, src_h=config.MODEL_HEIGHT, 
            dst_w=config.TARGET_WIDTH, dst_h=config.TARGET_HEIGHT
        )
        
        vis_road = visualize_tracked_lanes(vis_road, scaled_tracks, show=False)
        # vis_road = draw_lanes_fancy(vis_road, scaled_tracks)
        
        return vis_road, filtered_coeffs, cross_events
