import cv2
import os

def classify_video_frames(video_path):
    """
    Iterates through video frames, allowing user to classify and save them.

    Keys:
    '1': Save to 'right_mirror'
    '2': Save to 'looking_ahead'
    '3': Save to 'left_mirror'
    'q': Quit
    Any other key: Skip frame
    """

    # --- 1. Setup Paths and Directories ---
    if not os.path.exists(video_path):
        print(f"Error: Video file not found at {video_path}")
        return

    video_filename = os.path.splitext(os.path.basename(video_path))[0]
    base_data_dir = os.path.join('.', 'data', video_filename)

    class_map = {
        '1': 'right_mirror',
        '2': 'looking_ahead',
        '3': 'left_mirror',
    }

    dir_paths = {}
    for key, class_name in class_map.items():
        path = os.path.join(base_data_dir, class_name)
        os.makedirs(path, exist_ok=True)
        dir_paths[class_name] = path

    print(f"Data will be saved in: {base_data_dir}")
    print("Press '1' for 'right_mirror'")
    print("Press '2' for 'looking_ahead'")
    print("Press '3' for 'left_mirror'")
    print("Press 'q' to quit")
    print("Press any other key to skip a frame.")

    # --- 2. Open Video and Loop ---
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: Could not open video file {video_path}")
        return

    frame_index = 0
    window_name = "Classify Frame | 1: Right | 2: Ahead | 3: Left | q: Quit"

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("End of video.")
            break

        # --- 3. Display Frame and Get Input ---
        cv2.imshow(window_name, frame)
        
        # Wait indefinitely for a key press (0)
        key = cv2.waitKey(0) & 0xFF

        save_path = None
        class_name = None

        if chr(key) in class_map:
            class_name = class_map[chr(key)]
            save_path = dir_paths[class_name]
        elif chr(key) == 'q':
            print("Quitting...")
            break
        else:
            print("Frame skipped.")
            frame_index += 1
            continue

        # --- 4. Save Frame if Classified ---
        if save_path:
            filename = f"frame_{frame_index:06d}.png"
            full_save_path = os.path.join(save_path, filename)
            cv2.imwrite(full_save_path, frame)
            print(f"Saved frame {frame_index} to {class_name}")

        frame_index += 1

    # --- 5. Cleanup ---
    cap.release()
    cv2.destroyAllWindows()
    print("Classification complete.")

if __name__ == "__main__":
    # Get video path from user
    video_path_input = "/media/arty/3A30-14F9/Videos/13_09_25_me_to_lem_day/directions_cut.mp4"

    
    # Remove surrounding quotes if user dragged and dropped file
    if video_path_input.startswith('"') and video_path_input.endswith('"'):
        video_path_input = video_path_input[1:-1]
    if video_path_input.startswith("'") and video_path_input.endswith("'"):
        video_path_input = video_path_input[1:-1]
        
    classify_video_frames(video_path_input)