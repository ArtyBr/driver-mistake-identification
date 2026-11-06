import cv2
import os
import numpy as np
from config import FONT

def fix_anchor_path(heads_cfg, lanedet_dir):
    """Corrects relative paths in the lane detection config."""
    if hasattr(heads_cfg, 'anchors_freq_path') and heads_cfg.anchors_freq_path:
        if not os.path.isabs(heads_cfg.anchors_freq_path):
            potential = os.path.join(lanedet_dir, heads_cfg.anchors_freq_path)
            if os.path.exists(potential):
                heads_cfg.anchors_freq_path = potential

def scale_lane_coeffs(tracks, src_w, src_h, dst_w, dst_h):
    """
    Scales polynomial coefficients from source resolution to destination resolution.
    Equation: x = ay^2 + by + c
    """
    sx = dst_w / src_w
    sy = dst_h / src_h
    
    scaled_tracks = []
    
    for track in tracks:
        coeffs, t_id, conf, age, events = track
        a, b, c = coeffs

        new_a = a * sx / (sy ** 2)
        new_b = b * sx / sy
        new_c = c * sx
        
        scaled_coeffs = np.array([new_a, new_b, new_c])
        scaled_tracks.append((scaled_coeffs, t_id, conf, age, events))
        
    return scaled_tracks
