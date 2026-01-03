import cv2
import numpy as np
import config

# --- DRAWING HELPERS ---

def draw_fading_text(img, text, pos, font_scale, color, thickness, alpha):
    x, y = pos
    (w, h), _ = cv2.getTextSize(text, config.FONT, font_scale, thickness)
    
    # Boundary checks
    if y - h - 5 < 0 or y + 5 > img.shape[0] or x + w > img.shape[1] or x < 0:
        return

    roi = img[y-h-5:y+5, x:x+w]
    overlay = roi.copy()
    cv2.putText(overlay, text, (0, h), config.FONT, font_scale, color, thickness)
    cv2.addWeighted(overlay, alpha, roi, 1 - alpha, 0, roi)
    img[y-h-5:y+5, x:x+w] = roi

def draw_hud_panel(img, x, y, w, h, alpha=0.6, color=(0, 0, 0), border_color=(255, 255, 255), border_thickness=1):
    """Draws a semi-transparent panel with a border."""
    # Boundary checks
    if y < 0 or y + h > img.shape[0] or x < 0 or x + w > img.shape[1]:
        return # simplified clipping for safety

    overlay = img.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
    
    # Apply transparency
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    
    # Draw border
    if border_thickness > 0:
        cv2.rectangle(img, (x, y), (x + w, y + h), border_color, border_thickness, cv2.LINE_AA)

def draw_styled_text(img, text, pos, font_scale, color, thickness=1, outline_color=(0, 0, 0)):
    """Draws text with a drop shadow/outline for better visibility."""
    x, y = pos
    # Draw outline/shadow
    cv2.putText(img, text, (x + 1, y + 1), config.FONT, font_scale, outline_color, thickness + 1, cv2.LINE_AA)
    # Draw main text
    cv2.putText(img, text, (x, y), config.FONT, font_scale, color, thickness, cv2.LINE_AA)

# --- VISUALIZER CLASS ---

class VideoVisualizer:
    def __init__(self):
        pass

    def draw_face_overlay(self, vis_road, vis_face, margin=30):
        h_r, w_r = vis_road.shape[:2]
        h_f, w_f = vis_face.shape[:2]
        
        new_w_f = int(w_r * config.OVERLAY_SCALE)
        new_h_f = int(new_w_f * (h_f / w_f))
        vis_face_resized = cv2.resize(vis_face, (new_w_f, new_h_f))
        
        face_x = w_r - new_w_f - margin
        face_y = margin
        
        # Draw Panel Background for Face
        draw_hud_panel(vis_road, face_x - 5, face_y - 30, new_w_f + 10, new_h_f + 40, alpha=0.5)
        draw_styled_text(vis_road, "DRIVER FEED", (face_x, face_y - 10), 0.6, (220, 220, 220), 1)
        
        # Place Face Image
        if face_y + new_h_f < h_r and face_x + new_w_f < w_r:
            vis_road[face_y:face_y+new_h_f, face_x:face_x+new_w_f] = vis_face_resized
            # Add a thin tech-cyan border
            cv2.rectangle(vis_road, (face_x, face_y), (face_x + new_w_f, face_y + new_h_f), (255, 255, 0), 1)

    def draw_status_panel(self, vis_road, face_info, margin=30):
        if not face_info:
            return

        status_w = 380
        status_h = 140
        status_x = margin
        status_y = margin
        
        draw_hud_panel(vis_road, status_x, status_y, status_w, status_h, alpha=0.6)
        draw_styled_text(vis_road, "DRIVER STATUS", (status_x + 15, status_y + 25), 0.6, (200, 200, 200), 1)
        
        # Determine Status Color
        label = face_info['label']
        if "Left" in label or "Right" in label:
            status_color = (0, 165, 255) # Orange for mirrors
        elif "Looking Ahead" in label:
            status_color = (0, 255, 0) # Green
        else:
            status_color = (0, 0, 255) # Red for unknown/other
            
        label_text = label.upper()
        conf_text = f"Confidence: {face_info['conf']:.2f}"
        pose_text = f"Yaw: {face_info['yaw']}  Pitch: {face_info['pitch']}"
        
        draw_styled_text(vis_road, label_text, (status_x + 15, status_y + 70), 1.1, status_color, 2)
        draw_styled_text(vis_road, conf_text, (status_x + 15, status_y + 100), 0.6, (180, 180, 180), 1)
        draw_styled_text(vis_road, pose_text, (status_x + 15, status_y + 125), 0.6, (180, 180, 180), 1)

    def draw_history_panel(self, vis_road, state_history, current_time):
        if not state_history:
            return

        h_r, w_r = vis_road.shape[:2]
        # Filter history to show only last 4 items to keep UI clean
        display_history = state_history[-4:]
        
        hist_w = 400
        hist_h = 30 + (len(display_history) * 25)
        hist_x = (w_r - hist_w) // 2
        # Position at the bottom with 40px margin
        hist_y = h_r - hist_h - 40 
        
        draw_hud_panel(vis_road, hist_x, hist_y, hist_w, hist_h, alpha=0.6, color=(20, 20, 20))
        draw_styled_text(vis_road, "FACE DIRECTION EVENT LOG", (hist_x + 15, hist_y + 20), 0.5, (255, 255, 0), 1)
        
        for i, item in enumerate(display_history):
            age = current_time - item['timestamp']
            txt = f"> {item['state']} ({age:.1f}s ago)"
            y_pos = hist_y + 45 + (i * 25)
            draw_styled_text(vis_road, txt, (hist_x + 20, y_pos), 0.6, (230, 230, 230), 1)

    def draw_safety_alerts(self, vis_road, alerts):
        """
        Draws active safety alerts on the center of the screen.
        """
        if not alerts:
            return

        h, w = vis_road.shape[:2]
        center_x = w // 2
        center_y = h // 3 # Upper middle
        
        # We only display the most recent alert for clarity, or stack them if needed.
        # Let's display the most critical one if multiple exist, otherwise the newest.
        
        # Sort by severity (CRITICAL > WARNING > INFO) then by timestamp
        severity_map = {"CRITICAL": 3, "WARNING": 2, "INFO": 1}
        sorted_alerts = sorted(alerts, key=lambda x: (severity_map.get(x.severity, 0), x.timestamp), reverse=True)
        
        alert = sorted_alerts[0]
        
        # Color Coding
        if alert.is_safe:
            bg_color = (0, 100, 0) # Dark Green
            text_color = (150, 255, 150)
            border_color = (0, 255, 0)
        else:
            bg_color = (0, 0, 150) # Dark Red
            text_color = (150, 150, 255)
            border_color = (0, 0, 255)

        text = alert.message.upper()
        font_scale = 1.2
        thickness = 2
        
        (tw, th), _ = cv2.getTextSize(text, config.FONT, font_scale, thickness)
        
        # Panel Dimensions
        pad = 20
        box_w = tw + (pad * 2)
        box_h = th + (pad * 2)
        box_x = center_x - (box_w // 2)
        box_y = center_y - (box_h // 2)
        
        draw_hud_panel(vis_road, box_x, box_y, box_w, box_h, alpha=0.8, color=bg_color, border_color=border_color, border_thickness=3)
        draw_styled_text(vis_road, text, (box_x + pad, box_y + pad + th), font_scale, text_color, thickness)
        
    def visualize_face_analysis(self, frame, face_info, face_obj=None):
        """
        Draws face bounding box and keypoints. 
        Note: face_obj represents the raw object from InsightFace if available, 
        but here we primarily use face_info if that's what we passed.
        
        Ideally, this should move logic from FaceAnalyzer.process_frame here.
        But for now, I'll assume FaceAnalyzer returns the raw frame and we draw on it here.
        """
        # This will be used if we strip visualization from FaceAnalyzer
        if not face_info:
            return frame

        # Re-implementing drawing logic if we have the data
        # For this refactor, I will modify FaceAnalyzer to return the necessary data 
        # (bbox, kps) instead of drawing itself.
        
        if 'bbox' in face_info:
            bbox = face_info['bbox']
            cv2.rectangle(frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)
            
        if 'kps' in face_info:
            for kp in face_info['kps']:
                cv2.circle(frame, tuple(kp), 2, (0, 255, 0), -1)

        if 'nose_2d' in face_info and 'yaw' in face_info and 'pitch' in face_info:
            nose_2d = face_info['nose_2d']
            yaw = face_info['yaw']
            pitch = face_info['pitch']
            p2 = (int(nose_2d[0] + yaw * 10), int(nose_2d[1] - pitch * 10))
            cv2.line(frame, nose_2d, p2, (255, 0, 0), 3)

        return frame

    def draw_vehicle_distance(self, vis_road, vehicles):
        """
        Draws bounding boxes and distance info for detected vehicles.
        Only shows vehicles within 15 meters.
        """
        if not vehicles:
            return

        for v in vehicles:
            x1, y1, x2, y2 = v['bbox']
            label = v['label']
            dist = v['distance']
            
            # Filter: Only show if within 15m
            if dist >= 15:
                continue

            # Distance-based Color Coding
            if dist < 5:
                color = (0, 0, 255)    # Red (Danger - Too Close)
            else:
                color = (0, 165, 255)  # Orange (Warning)
            
            # Draw Box
            cv2.rectangle(vis_road, (x1, y1), (x2, y2), color, 2)
            
            # Draw Label & Distance
            text = f"{label}: {dist:.1f}m"
            
            # Calculate position above the box
            t_x = x1
            t_y = y1 - 10
            if t_y < 20: t_y = y1 + 20 
            
            draw_styled_text(vis_road, text, (t_x, t_y), 0.6, color, 1)
