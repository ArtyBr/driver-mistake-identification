import numpy as np
import cv2
import argparse
import os

def save_calibration(mtx, dist, output_path):
    """Saves calibration results to a text file in a common format, avoiding overwrites."""
    
    # Handle filename collisions
    base, ext = os.path.splitext(output_path)
    counter = 1
    final_output_path = output_path
    
    while os.path.exists(final_output_path):
        final_output_path = f"{base}_{counter}{ext}"
        counter += 1

    with open(final_output_path, 'w') as f:
        f.write("# Camera Calibration Results\n")
        f.write(f"# Intrinsic Matrix (K):\n")
        f.write(f"{mtx[0,0]} {mtx[0,1]} {mtx[0,2]}\n")
        f.write(f"{mtx[1,0]} {mtx[1,1]} {mtx[1,2]}\n")
        f.write(f"{mtx[2,0]} {mtx[2,1]} {mtx[2,2]}\n\n")
        
        f.write("# Distortion Coefficients (D):\n")
        dist_flat = dist.flatten()
        f.write(" ".join(map(str, dist_flat)) + "\n\n")
        
        f.write("# Parameter Breakdown (for VO/SLAM configs):\n")
        f.write(f"fx: {mtx[0,0]}\n")
        f.write(f"fy: {mtx[1,1]}\n")
        f.write(f"cx: {mtx[0,2]}\n")
        f.write(f"cy: {mtx[1,2]}\n")
        f.write(f"k1: {dist_flat[0]}\n")
        f.write(f"k2: {dist_flat[1]}\n")
        f.write(f"p1: {dist_flat[2]}\n")
        f.write(f"p2: {dist_flat[3]}\n")
        f.write(f"k3: {dist_flat[4]}\n")
    
    print(f"\nCalibration saved to {final_output_path}")

def calibrate_camera_from_video(video_path, rows=8, cols=8, square_size=1.0, debug=False, sample_interval=30, scale_factor=1.0, crop_center=1.0, output_path="calibration.txt", start_seconds=0.0):
    """
    Calibrates the camera using a video of a checkerboard.

    Args:
        video_path (str): Path to the video file.
        rows (int): Number of internal corners in the checkerboard rows.
        cols (int): Number of internal corners in the checkerboard columns.
        square_size (float): Size of a square side in real-world units (e.g., mm or inches).
        debug (bool): If True, shows images with detected corners.
        sample_interval (int): Process every Nth frame.
        scale_factor (float): Factor to upscale image for detection (helps with small boards).
        crop_center (float): Fraction of frame to keep in center (0.0 < x <= 1.0).
        output_path (str): Output file for calibration results.
        start_seconds (float): Start processing from this timestamp in seconds.
    """
    # Termination criteria for corner refinement
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    # Prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(cols-1,rows-1,0)
    objp = np.zeros((rows * cols, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
    objp = objp * square_size

    # Arrays to store object points and image points from all the images.
    objpoints = [] # 3d point in real world space
    imgpoints = [] # 2d points in image plane.

    # Determine source (file or webcam)
    source = video_path
    if video_path.isdigit():
        source = int(video_path)

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"Error: Could not open video source {video_path}")
        return

    # Skip to start_seconds if applicable
    if start_seconds > 0:
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps > 0:
            start_frame = int(start_seconds * fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            print(f"Skipping to {start_seconds}s (Frame {start_frame})")
        else:
            print("Warning: Could not determine FPS. Starting from beginning.")

    frame_count = 0
    valid_frames = 0
    image_shape = None

    print(f"Processing video...")
    print(f"Looking for checkerboard with {rows} x {cols} INTERNAL corners (intersections).")
    print(f"If your board has {rows+1}x{cols+1} squares, this is correct.")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        if frame_count % sample_interval != 0:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Save shape from original resolution
        if image_shape is None:
            image_shape = gray.shape[::-1]

        # 1. Handle Cropping
        processing_gray = gray
        crop_offset_x = 0
        crop_offset_y = 0

        if crop_center < 1.0:
            h, w = gray.shape
            new_h = int(h * crop_center)
            new_w = int(w * crop_center)
            crop_offset_y = (h - new_h) // 2
            crop_offset_x = (w - new_w) // 2
            processing_gray = gray[crop_offset_y:crop_offset_y+new_h, crop_offset_x:crop_offset_x+new_w]

        # 2. Handle Scaling (on top of optional crop)
        if scale_factor != 1.0:
            # Upscale for better detection of small boards
            width = int(processing_gray.shape[1] * scale_factor)
            height = int(processing_gray.shape[0] * scale_factor)
            processing_gray = cv2.resize(processing_gray, (width, height), interpolation=cv2.INTER_CUBIC)

        # Find the chess board corners
        # Removed FAST_CHECK as it can be too aggressive on webcams
        flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        found, corners = cv2.findChessboardCorners(processing_gray, (cols, rows), flags)

        if found:
            # If we scaled up, we need to scale the corner coordinates back down
            if scale_factor != 1.0:
                corners = corners / scale_factor

            # If we cropped, we need to add the offset to get back to full frame coordinates
            if crop_center < 1.0:
                corners[:, :, 0] += crop_offset_x
                corners[:, :, 1] += crop_offset_y

            objpoints.append(objp)
            
            # Refine corners on the *original* resolution image (gray), not the upscaled/cropped one
            # to ensure maximum accuracy on the actual source pixels.
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            imgpoints.append(corners2)
            valid_frames += 1
            print(f"Corners found in frame {frame_count}")

            if debug:
                cv2.drawChessboardCorners(frame, (cols, rows), corners2, found)
                cv2.imshow('Frame', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("Quitting early...")
                    break
        else:
            if debug:
                # Show what we were actually searching on (for debugging purposes)
                cv2.imshow('Processing View', processing_gray) 
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("Quitting early...")
                    break
            # print(f"Corners NOT found in frame {frame_count}") # Optional: reduce spam

        # Even if not debug, we might want to allow 'q' to quit if a window is somehow open, 
        # or just purely relying on Ctrl+C in terminal.
        # But if we want to support 'q' generally, we need a window to focus. 
        # So 'q' usually only works if a window is shown (debug=True).
        
    cap.release()
    if debug:
        cv2.destroyAllWindows()

    if not objpoints:
        print("No corners detected in the video. Try adjusting --scale_factor, --crop_center or grid size.")
        return

    print(f"\nFound corners in {valid_frames} frames.")
    print("Calculating calibration...")
    
    # Calibrate camera
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, image_shape, None, None)

    print("\nCalibration successful!")
    print(f"Reprojection Error: {ret}")
    print("\nCamera Matrix (Intrinsic parameters):")
    print(mtx)
    print("\nDistortion Coefficients:")
    print(dist)

    if output_path:
        save_calibration(mtx, dist, output_path)

    return mtx, dist

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Calibrate camera using a video of a checkerboard.')
    parser.add_argument('video_path', type=str, help='Path to the video file')
    parser.add_argument('--rows', type=int, default=7, help='Number of internal corners in rows (default: 6)')
    parser.add_argument('--cols', type=int, default=7, help='Number of internal corners in columns (default: 9)')
    parser.add_argument('--square_size', type=float, default=1.0, help='Size of one square in world units (default: 1.0)')
    parser.add_argument('--sample', type=int, default=5, help='Process every Nth frame (default: 5)')
    parser.add_argument('--scale_factor', type=float, default=1.0, help='Upscale factor for detection (e.g. 2.0 for 2x size). Default: 1.0')
    parser.add_argument('--crop_center', type=float, default=1.0, help='Fraction of frame to keep in center (e.g. 0.5 for half size). Default: 1.0')
    parser.add_argument('--output', type=str, default='calibration.txt', help='Output file for calibration results (default: calibration.txt)')
    parser.add_argument('--start_seconds', type=float, default=0.0, help='Start processing from this timestamp in seconds (default: 0.0)')
    parser.add_argument('--debug', action='store_true', help='Show processing frames')

    args = parser.parse_args()

    is_webcam = args.video_path.isdigit()
    if not is_webcam and not os.path.isfile(args.video_path):
        print(f"Error: File '{args.video_path}' does not exist.")
    else:
        calibrate_camera_from_video(args.video_path, args.rows, args.cols, args.square_size, args.debug, args.sample, args.scale_factor, args.crop_center, args.output, args.start_seconds)
