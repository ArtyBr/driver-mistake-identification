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

    def process_frame(self, frame):
        """
        Processes a frame for lane detection and tracking.
        Returns:
            vis_road: The visualized frame with lanes overlayed (resized to target).
            lane_data: The raw tracking data (coeffs, id, conf, age, events).
        """
        # coeffs are returned in MODEL resolution (1640x590)
        coeffs, ori_road = self.detector.get_lane_detections(frame)
        filtered_coeffs = self.tracker.update(coeffs)

        # Resize the base video frame to TARGET resolution (1920x1080) before overlaying lanes
        vis_road = cv2.resize(ori_road, (config.TARGET_WIDTH, config.TARGET_HEIGHT), interpolation=cv2.INTER_LINEAR)
        
        scaled_tracks = scale_lane_coeffs(
            filtered_coeffs, 
            src_w=config.MODEL_WIDTH, src_h=config.MODEL_HEIGHT, 
            dst_w=config.TARGET_WIDTH, dst_h=config.TARGET_HEIGHT
        )
        
        vis_road = visualize_tracked_lanes(vis_road, scaled_tracks, show=False)
        
        return vis_road, filtered_coeffs
