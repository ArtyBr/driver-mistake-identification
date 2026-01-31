import cv2
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import sys
import os

class VisualOdometry:
    def __init__(self, video_path):
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise IOError(f"Cannot open video file: {video_path}")

        # Intrinsic Matrix (K) from calibration_3.txt
        self.K_orig = np.array([
            [993.6305137521725, 0.0, 954.7271539229214],
            [0.0, 1144.329008082279, 539.4773780846734],
            [0.0, 0.0, 1.0]
        ])
        
        # We will calculate the adjusted K once we know the crop offsets
        self.K = self.K_orig.copy()
        self.k_adjusted = False

        # Distortion Coefficients (D) - Not used for image undistortion anymore per request
        self.D = np.array([0.09120135029599218, 0.03431960504192815, -0.027375346575880814, -0.017942890066237845, -0.6799011067187613])

        # Feature Detection Parameters
        self.feature_params = dict(maxCorners=2000, qualityLevel=0.01, minDistance=30, blockSize=7)
        self.lk_params = dict(winSize=(21, 21), maxLevel=3,
                              criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))

        # Initialization
        self.cur_R = np.eye(3)
        self.cur_t = np.zeros((3, 1))
        self.prev_image = None
        self.prev_keypoints = None
        
        # Trajectory history
        self.traj_x = [0.0]
        self.traj_y = [0.0]
        self.traj_z = [0.0]
        self.frame_count = 0

    def process_frame(self):
        ret, frame_raw = self.cap.read()
        if not ret:
            return False, None, None

        # Crop to center 3/4ths
        h, w = frame_raw.shape[:2]
        h_crop = int(h * 0.75)
        w_crop = int(w * 0.75)
        y_start = (h - h_crop) // 2
        x_start = (w - w_crop) // 2
        frame_cropped = frame_raw[y_start:y_start+h_crop, x_start:x_start+w_crop].copy()

        # Adjust K for the crop (cx and cy shift)
        if not self.k_adjusted:
            self.K[0, 2] = self.K_orig[0, 2] - x_start
            self.K[1, 2] = self.K_orig[1, 2] - y_start
            self.k_adjusted = True

        # Convert to grayscale
        curr_gray = cv2.cvtColor(frame_cropped, cv2.COLOR_BGR2GRAY)

        if self.prev_image is None:
            # First frame: Initialize features
            self.prev_keypoints = cv2.goodFeaturesToTrack(curr_gray, mask=None, **self.feature_params)
            self.prev_image = curr_gray
            print("Initialized features for the first frame (Cropped).", flush=True)
            return True, frame_raw, frame_cropped

        # Track features
        p1, st, err = cv2.calcOpticalFlowPyrLK(self.prev_image, curr_gray, self.prev_keypoints, None, **self.lk_params)

        # Select good points
        if p1 is not None:
            good_new = p1[st == 1]
            good_old = self.prev_keypoints[st == 1]
        else:
            good_new = []
            good_old = []

        # 1. Pose Estimation
        if len(good_new) > 5:
            # Compute Essential Matrix
            E, mask = cv2.findEssentialMat(good_new, good_old, self.K, method=cv2.RANSAC, prob=0.999, threshold=1.0)
            
            if E is not None:
                # Recover Pose
                _, R, t, mask = cv2.recoverPose(E, good_new, good_old, self.K)
                
                t_mag = np.linalg.norm(t)
                scale = 1.0
                
                # Standard VO Update
                self.cur_t = self.cur_t + scale * self.cur_R.dot(t)
                self.cur_R = self.cur_R.dot(R)

                self.traj_x.append(self.cur_t[0][0])
                self.traj_y.append(self.cur_t[1][0])
                self.traj_z.append(self.cur_t[2][0])
                
                print(f"Frame {self.frame_count} | Feats: {len(good_new)} | Step: {t_mag:.4f} | Pos: ({self.cur_t[0][0]:.2f}, {self.cur_t[1][0]:.2f}, {self.cur_t[2][0]:.2f})", flush=True)
            else:
                print(f"Frame {self.frame_count}: Essential Matrix failed.", flush=True)
        else:
             print(f"Frame {self.frame_count}: Not enough features ({len(good_new)})", flush=True)

        # 2. Preparation for Next Frame
        if len(good_new) < 1000: 
             new_kps = cv2.goodFeaturesToTrack(curr_gray, mask=None, **self.feature_params)
             if new_kps is not None:
                 self.prev_keypoints = new_kps
                 print(f"  -> Re-detected {len(new_kps)} features.", flush=True)
             else:
                 self.prev_keypoints = good_new.reshape(-1, 1, 2)
        else:
             self.prev_keypoints = good_new.reshape(-1, 1, 2)

        self.prev_image = curr_gray
        
        return True, frame_raw, frame_cropped

    def on_key(self, event):
        if event.key == 'q':
            self.stop_requested = True

    def run(self):
        plt.ion()
        fig = plt.figure(figsize=(16, 6))
        
        self.stop_requested = False
        fig.canvas.mpl_connect('key_press_event', self.on_key)
        
        ax_orig = fig.add_subplot(131)
        ax_crop = fig.add_subplot(132)
        ax_traj = fig.add_subplot(133, projection='3d')

        ax_orig.set_title("Original Raw Frame")
        ax_orig.axis('off')

        ax_crop.set_title("Cropped Frame (Processed)")
        ax_crop.axis('off')
        
        ax_traj.set_title("3D Trajectory")
        ax_traj.set_xlabel('X')
        ax_traj.set_ylabel('Z (Forward)')
        ax_traj.set_zlabel('Y (Up)')
        ax_traj.view_init(elev=-20, azim=-90)

        line_traj, = ax_traj.plot(self.traj_x, self.traj_z, [-y for y in self.traj_y], color='blue')
        point_curr, = ax_traj.plot([0], [0], [0], 'ro')
        
        img_plot_orig = None
        img_plot_crop = None

        print("Starting Visual Odometry (No Undistortion)...")
        print("Press 'q' in the plot window to stop.")
        
        self.frame_count = 0
        while not self.stop_requested:
            ret, frame_raw, frame_crop = self.process_frame()
            if not ret:
                break
            self.frame_count += 1
            
            # Update Image Plots
            orig_rgb = cv2.cvtColor(frame_raw, cv2.COLOR_BGR2RGB)
            if img_plot_orig is None:
                img_plot_orig = ax_orig.imshow(orig_rgb)
            else:
                img_plot_orig.set_data(orig_rgb)

            vis_crop = frame_crop.copy()
            if self.prev_keypoints is not None:
                for new in self.prev_keypoints:
                    a, b = new.ravel()
                    cv2.circle(vis_crop, (int(a), int(b)), 3, (0, 255, 0), -1)
            
            crop_rgb = cv2.cvtColor(vis_crop, cv2.COLOR_BGR2RGB)
            if img_plot_crop is None:
                img_plot_crop = ax_crop.imshow(crop_rgb)
            else:
                img_plot_crop.set_data(crop_rgb)

            # Update Trajectory
            p_x, p_y, p_z = self.traj_x, self.traj_z, [-y for y in self.traj_y]
            line_traj.set_data(p_x, p_y)
            line_traj.set_3d_properties(p_z)
            point_curr.set_data([p_x[-1]], [p_y[-1]])
            point_curr.set_3d_properties([p_z[-1]])

            # Dynamic Scaling
            if len(p_x) > 1:
                mx, my, mz = (max(p_x)+min(p_x))/2, (max(p_y)+min(p_y))/2, (max(p_z)+min(p_z))/2
                r = np.array([max(p_x)-min(p_x), max(p_y)-min(p_y), max(p_z)-min(p_z)]).max() / 2.0
                if r < 1.0: r = 1.0 
                ax_traj.set_xlim(mx-r, mx+r)
                ax_traj.set_ylim(my-r, my+r)
                ax_traj.set_zlim(mz-r, mz+r)

            plt.draw()
            plt.pause(0.001)
            
        print("Finished.")
        plt.ioff()
        if not self.stop_requested:
             plt.show(block=True)
        else:
             plt.close()
        self.cap.release()
        cv2.destroyAllWindows()
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python vo_main.py <path_to_video>")
        sys.exit(1)
        
    video_file = sys.argv[1]
    if not os.path.exists(video_file):
        print(f"Error: File {video_file} not found.")
        sys.exit(1)
        
    vo = VisualOdometry(video_file)
    vo.run()
