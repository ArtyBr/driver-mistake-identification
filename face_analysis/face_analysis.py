import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe import solutions
from mediapipe.framework.formats import landmark_pb2

model_path = './models/face_landmarker.task'
BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
VisionRunningMode = mp.tasks.vision.RunningMode
options = FaceLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=model_path),
    output_facial_transformation_matrixes=True,
    running_mode=VisionRunningMode.IMAGE)
detector = vision.FaceLandmarker.create_from_options(options)

def draw_landmarks_on_image(rgb_image, detection_result):
  face_landmarks_list = detection_result.face_landmarks
  annotated_image = np.copy(rgb_image)
  img_h, img_w, _ = annotated_image.shape
  focal_length = img_w
  principal_point = (img_w / 2, img_h / 2)
  dist_coeffs = np.zeros((4, 1), dtype=np.float32)

  K = np.array([
    [focal_length, 0, principal_point[0]],
    [0, focal_length, principal_point[1]],
    [0, 0, 1]
], dtype=np.float32)

  # Loop through the detected faces to visualize.
  for idx in range(len(face_landmarks_list)):
    face_landmarks = face_landmarks_list[idx]

    # Draw the face landmarks.
    face_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
    face_landmarks_proto.landmark.extend([
      landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z) for landmark in face_landmarks
    ])

    solutions.drawing_utils.draw_landmarks(
        image=annotated_image,
        landmark_list=face_landmarks_proto,
        connections=mp.solutions.face_mesh.FACEMESH_TESSELATION,
        landmark_drawing_spec=None,
        connection_drawing_spec=mp.solutions.drawing_styles
        .get_default_face_mesh_tesselation_style())

    if not detection_result.facial_transformation_matrixes:
        continue

    matrix = detection_result.facial_transformation_matrixes[idx]
    R = matrix[0:3, 0:3]
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

    cv2.putText(annotated_image, f'Pitch: {pitch_deg:.2f}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(annotated_image, f'Yaw: {yaw_deg:.2f}', (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(annotated_image, f'Roll: {roll_deg:.2f}', (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
    nose_tip = face_landmarks[1]
    nose_2d = (int(nose_tip.x * img_w), int(nose_tip.y * img_h))
    line_length = 100
    end_x = int(nose_2d[0] + line_length * np.sin(yaw_rad) * np.cos(pitch_rad))
    end_y = int(nose_2d[1] + line_length * np.sin(pitch_rad))

    cv2.line(annotated_image, nose_2d, (end_x, end_y), (0, 255, 0), 2)

    R = matrix[0:3, 0:3]
    t = matrix[0:3, 3]

    rvec, _ = cv2.Rodrigues(R)

    img_h, img_w, _ = annotated_image.shape
    focal_length = img_w
    principal_point = (img_w / 2, img_h / 2)
    K = np.array([[focal_length, 0, principal_point[0]], [0, focal_length, principal_point[1]], [0, 0, 1]], dtype=np.float32)
    dist_coeffs = np.zeros((4, 1), dtype=np.float32)

    square_size_3d = 10.0
    half_size_3d = square_size_3d / 2.0
    
    gaze_vector_R = R[:, 2]
    
    t_new = t - gaze_vector_R
    tvec_new = t_new.reshape((3, 1))

    object_points = np.array([
        [half_size_3d, half_size_3d, 0.0],
        [ -half_size_3d, half_size_3d, 0.0],
        [ -half_size_3d,  -half_size_3d, 0.0],
        [half_size_3d,  -half_size_3d, 0.0], 
    ], dtype=np.float32)

    image_points, _ = cv2.projectPoints(object_points, 
                                        rvec, 
                                        tvec_new, 
                                        K, 
                                        dist_coeffs)
    image_points[:, 0, 0] = img_w - image_points[:, 0, 0]
    image_points[:, 0, 0] += (end_x - np.mean(image_points[:, 0, 0]))
    image_points[:, 0, 1] += (end_y - np.mean(image_points[:, 0, 1]))

    pts = image_points.reshape((-1, 1, 2)).astype(np.int32)
    
    FILL_COLOR = (0, 0, 255)
    OPACITY_ALPHA = 0.4
    overlay = annotated_image.copy()
    cv2.fillPoly(overlay, [pts], FILL_COLOR)
    cv2.addWeighted(overlay, OPACITY_ALPHA, annotated_image, 1 - OPACITY_ALPHA, 0, annotated_image)

  return annotated_image

video_path = "/media/arty/3A30-14F9/Videos/"

# Display webcam footage
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)
    detection_result = detector.detect(image)
    annotated_frame = draw_landmarks_on_image(image.numpy_view(), detection_result)
    cv2.imshow("Webcam", annotated_frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()