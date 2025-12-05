# Test writing an mp4 video using cv2
import cv2
import numpy as np
def test_write_video(output_path='test_output.mp4', frame_count=100, width=640, height=480, fps=30):
    # Define the codec and create VideoWriter object
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Be sure to use lower case
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    for i in range(frame_count):
        # Create a dummy frame (a simple gradient image)
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.putText(frame, f'Frame {i+1}', (50, height//2), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        # Write the frame
        out.write(frame)

    # Release everything if job is finished
    out.release()
    print(f"Video written to {output_path}")
    return output_path

if __name__ == "__main__":
    test_write_video()