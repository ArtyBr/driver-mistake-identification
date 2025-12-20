import cv2
import re
import os
import numpy as np
from config import FONT

def draw_fading_text(img, text, pos, font_scale, color, thickness, alpha):
    x, y = pos
    (w, h), _ = cv2.getTextSize(text, FONT, font_scale, thickness)
    
    # Boundary checks
    if y - h - 5 < 0 or y + 5 > img.shape[0] or x + w > img.shape[1] or x < 0:
        return

    roi = img[y-h-5:y+5, x:x+w]
    overlay = roi.copy()
    cv2.putText(overlay, text, (0, h), FONT, font_scale, color, thickness)
    cv2.addWeighted(overlay, alpha, roi, 1 - alpha, 0, roi)
    img[y-h-5:y+5, x:x+w] = roi

def setup_video_paths(base_path_str):
    """Determines the paths for road (F) and face (I) videos."""
    path_road = base_path_str + "F.mp4"
    
    # Logic to increment trailing number for the face video
    match = re.search(r'(\d+)$', base_path_str)
    if match:
        num_str = match.group(1)
        new_num_str = str(int(num_str) + 1).zfill(len(num_str))
        path_face = base_path_str[:-len(num_str)] + new_num_str + "I.mp4"
    else:
        path_face = base_path_str + "I.mp4"
        
    return path_road, path_face

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
