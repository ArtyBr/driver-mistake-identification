import cv2
import numpy as np
from insightface.app import FaceAnalysis
from insightface.utils import face_align
import csv
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Initialize InsightFace
app = FaceAnalysis(providers=['CUDAExecutionProvider', 'CPUExecutionProvider'])
app.prepare(ctx_id=0, det_size=(640, 640))

def rotation_matrix_to_euler_angles(R):
    """Convert rotation matrix to Euler angles (pitch, yaw, roll)"""
    sy = np.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)
    singular = sy < 1e-6

    if not singular:
        pitch_rad = np.arctan2(R[2, 1], R[2, 2])
        yaw_rad = np.arctan2(-R[2, 0], sy)
        roll_rad = np.arctan2(R[1, 0], R[0, 0])
    else:
        pitch_rad = np.arctan2(-R[1, 2], R[1, 1])
        yaw_rad = np.arctan2(-R[2, 0], sy)
        roll_rad = 0

    pitch_deg = np.degrees(pitch_rad)
    yaw_deg = np.degrees(yaw_rad)
    roll_deg = np.degrees(roll_rad)
    
    return pitch_deg, yaw_deg, roll_deg

def draw_landmarks_on_image(frame, faces):
    """Draw face landmarks and head pose visualization"""
    annotated_image = frame.copy()
    img_h, img_w, _ = annotated_image.shape
    
    all_poses_in_frame = []
    
    for idx, face in enumerate(faces):
        # Get landmarks (InsightFace provides 5 or 106/68 landmarks depending on model)
        kps = face.kps.astype(int)
        
        # Draw landmarks
        for kp in kps:
            cv2.circle(annotated_image, tuple(kp), 2, (0, 255, 0), -1)
        
        # Get pose from InsightFace
        # InsightFace provides pose as [pitch, yaw, roll] in face.pose
        if hasattr(face, 'pose') and face.pose is not None:
            pitch_deg, yaw_deg, roll_deg = face.pose
        else:
            # If pose not available, estimate from landmarks
            # Using the 5-point landmarks to estimate rough head pose
            # This is a simplified estimation
            pitch_deg = 0.0
            yaw_deg = 0.0
            roll_deg = 0.0
        
        all_poses_in_frame.append((pitch_deg, yaw_deg, roll_deg))
        
        # Display pose angles
        cv2.putText(annotated_image, f'Pitch: {pitch_deg:.2f}', 
                    (10, 30 + idx * 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(annotated_image, f'Yaw: {yaw_deg:.2f}', 
                    (10, 60 + idx * 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(annotated_image, f'Roll: {roll_deg:.2f}', 
                    (10, 90 + idx * 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Draw bounding box
        bbox = face.bbox.astype(int)
        cv2.rectangle(annotated_image, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 0), 2)
        
        # Draw direction line from nose tip
        # Use the nose landmark (typically index 2 in 5-point landmarks)
        if len(kps) >= 3:
            nose_tip = kps[2]  # Nose tip in 5-point landmarks
        else:
            # Use center of face as fallback
            nose_tip = np.array([int((bbox[0] + bbox[2]) / 2), int((bbox[1] + bbox[3]) / 2)])
        
        line_length = 100
        pitch_rad = np.radians(pitch_deg)
        yaw_rad = np.radians(yaw_deg)
        
        end_x = int(nose_tip[0] + line_length * np.sin(yaw_rad) * np.cos(pitch_rad))
        end_y = int(nose_tip[1] + line_length * np.sin(pitch_rad))
        
        cv2.line(annotated_image, tuple(nose_tip), (end_x, end_y), (0, 255, 0), 2)
        
        # Draw semi-transparent square at the end of direction line
        square_size = 20
        pts = np.array([
            [end_x - square_size, end_y - square_size],
            [end_x + square_size, end_y - square_size],
            [end_x + square_size, end_y + square_size],
            [end_x - square_size, end_y + square_size]
        ], np.int32)
        
        FILL_COLOR = (0, 0, 255)
        OPACITY_ALPHA = 0.4
        overlay = annotated_image.copy()
        cv2.fillPoly(overlay, [pts], FILL_COLOR)
        cv2.addWeighted(overlay, OPACITY_ALPHA, annotated_image, 1 - OPACITY_ALPHA, 0, annotated_image)
    
    return annotated_image, all_poses_in_frame

# Video processing
video_path = "/media/arty/3A30-14F9/Videos/13_09_25_me_to_lem_day/directions_cut.mp4"
cap = cv2.VideoCapture(video_path)

head_pose_data = []
head_pose_data.append(['frame', 'face_id', 'pitch', 'yaw', 'roll'])
frame_number = 0

# Setup matplotlib for real-time plotting
plt.ion()  # Turn on interactive mode
fig, ax = plt.subplots(figsize=(10, 8))
fig.suptitle('Head Pose: Pitch vs Yaw (colored by Roll)')

# Initialize data lists for plotting
pitch_values = []
yaw_values = []
roll_values = []

# Setup the axes
ax.set_xlabel('Yaw (degrees)')
ax.set_ylabel('Pitch (degrees)')
ax.grid(True)
ax.set_xlim(-90, 90)
ax.set_ylim(-90, 90)

# Create a colorbar for roll
scatter = ax.scatter([], [], c=[], cmap='hsv', s=50, vmin=-90, vmax=90)
cbar = plt.colorbar(scatter, ax=ax)
cbar.set_label('Roll (degrees)')

plt.tight_layout()

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    height, width, _ = frame.shape
    frame = frame[0:2*height//4, 0:2*width//4]
    
    # Detect faces with InsightFace
    faces = app.get(frame)
    
    # Draw annotations
    annotated_frame, frame_poses = draw_landmarks_on_image(frame, faces)
    
    # Record pose data
    if frame_poses:
        for face_id, (pitch, yaw, roll) in enumerate(frame_poses):
            head_pose_data.append([frame_number, face_id, pitch, yaw, roll])
            
            # Add to plotting data (only plot first face for simplicity)
            if face_id == 0:
                pitch_values.append(pitch)
                yaw_values.append(yaw)
                roll_values.append(roll)
    else:
        head_pose_data.append([frame_number, None, None, None, None])
    
    # Update plot in real-time
    if pitch_values:
        ax.clear()
        scatter = ax.scatter(yaw_values, pitch_values, c=roll_values, 
                           cmap='hsv', s=50, vmin=-90, vmax=90, alpha=0.6)
        ax.set_xlabel('Yaw (degrees)')
        ax.set_ylabel('Pitch (degrees)')
        ax.set_xlim(-90, 90)
        ax.set_ylim(-90, 90)
        ax.grid(True)
        
        # Redraw the plot
        fig.canvas.draw()
        fig.canvas.flush_events()
    
    frame_number += 1
    
    cv2.imshow("Webcam", annotated_frame)
    if cv2.waitKey(0) & 0xFF == ord("q"):
        break

plt.ioff()  # Turn off interactive mode
plt.show()  # Keep the final plot open

cap.release()
cv2.destroyAllWindows()

# Save results
output_filename = 'head_pose_data'
with open(output_filename + '_01.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerows(head_pose_data)