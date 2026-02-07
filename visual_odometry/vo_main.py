import cv2
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import sys
import os
import torch
import torchvision
from torchvision import transforms

class VisualOdometry:
    def __init__(self, video_path, start_seconds=0):
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise IOError(f"Cannot open video file: {video_path}")

        # Seek to start time if specified
        if start_seconds > 0:
            print(f"Seeking to {start_seconds} seconds...")
            self.cap.set(cv2.CAP_PROP_POS_MSEC, start_seconds * 1000)

        # Intrinsic Matrix (K) from calibration_3.txt
        self.K_orig = np.array([
            [993.6305137521725, 0.0, 954.7271539229214],
            [0.0, 1144.329008082279, 539.4773780846734],
            [0.0, 0.0, 1.0]
        ])
        
        self.K = self.K_orig.copy()
        self.k_adjusted = False

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
        
        self.traj_x = [0.0]
        self.traj_y = [0.0]
        self.traj_z = [0.0]
        self.frame_count = 0

        # --- Mask R-CNN Setup ---
        print("Initializing Mask R-CNN (ResNet50 FPN V2)...")
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Load the model
        weights = torchvision.models.detection.MaskRCNN_ResNet50_FPN_V2_Weights.DEFAULT
        self.seg_model = torchvision.models.detection.maskrcnn_resnet50_fpn_v2(weights=weights)
        self.seg_model.to(self.device)
        self.seg_model.eval()
        
        # Transform for Mask R-CNN (It expects 0-1 float tensors)
        self.seg_transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.ToTensor(),
        ])
        
        # COCO classes to ignore (dynamic objects)
        # 1: person, 2: bicycle, 3: car, 4: motorcycle, 6: bus, 8: truck
        self.ignore_classes = [1, 2, 3, 4, 6, 8]

    def get_segmentation_mask(self, frame):
        # Prepare input
        input_tensor = self.seg_transform(frame).to(self.device)
        
        with torch.no_grad():
            predictions = self.seg_model([input_tensor])[0]
            
        # Initialize empty mask (0=static)
        h, w = frame.shape[:2]
        combined_mask = np.zeros((h, w), dtype=np.uint8)
        
        # Iterate through detections
        for i in range(len(predictions['scores'])):
            score = predictions['scores'][i].item()
            label = predictions['labels'][i].item()
            
            # Confidence threshold and class check
            if score > 0.5 and label in self.ignore_classes:
                # Extract mask (soft mask > 0.5 becomes binary)
                mask = predictions['masks'][i, 0].cpu().numpy()
                mask_binary = (mask > 0.5).astype(np.uint8) * 255
                
                # Combine with main mask using logical OR
                combined_mask = cv2.bitwise_or(combined_mask, mask_binary)
                
        return combined_mask

    def process_frame(self):
        ret, frame_raw = self.cap.read()
        if not ret:
            return False, None, None, None, None

        # Crop to center 3/4ths
        h, w = frame_raw.shape[:2]
        h_crop = int(h * 0.75)
        w_crop = int(w * 0.75)
        y_start = (h - h_crop) // 2
        x_start = (w - w_crop) // 2
        frame_cropped = frame_raw[y_start:y_start+h_crop, x_start:x_start+w_crop].copy()

        # Adjust K for the crop
        if not self.k_adjusted:
            self.K[0, 2] = self.K_orig[0, 2] - x_start
            self.K[1, 2] = self.K_orig[1, 2] - y_start
            self.k_adjusted = True

        # Generate Mask using Mask R-CNN
        # dynamic_mask: 255 where objects are, 0 where static
        dynamic_mask = self.get_segmentation_mask(frame_cropped)
        
        # Dilate mask slightly to cover edges (safety buffer)
        kernel = np.ones((15, 15), np.uint8) 
        dynamic_mask = cv2.dilate(dynamic_mask, kernel, iterations=1)
        
        # Static mask: 255 where static, 0 where dynamic
        static_mask = cv2.bitwise_not(dynamic_mask)

        # Convert to grayscale
        curr_gray = cv2.cvtColor(frame_cropped, cv2.COLOR_BGR2GRAY)

        if self.prev_image is None:
            # First frame initialization
            self.prev_keypoints = cv2.goodFeaturesToTrack(curr_gray, mask=static_mask, **self.feature_params)
            self.prev_image = curr_gray
            print("Initialized features (Cropped & Masked).", flush=True)
            return True, frame_raw, frame_cropped, None, dynamic_mask

        # Track features
        p1, st, err = cv2.calcOpticalFlowPyrLK(self.prev_image, curr_gray, self.prev_keypoints, None, **self.lk_params)

        # Select good points that are tracked AND in static regions
        good_new = []
        good_old = []
        if p1 is not None:
            for i, (new, old) in enumerate(zip(p1, self.prev_keypoints)):
                if st[i] == 1:
                    x, y = new.ravel()
                    # Check bounds and mask
                    if 0 <= int(y) < h_crop and 0 <= int(x) < w_crop:
                        if static_mask[int(y), int(x)] > 0:
                            good_new.append(new)
                            good_old.append(old)
            
            good_new = np.array(good_new)
            good_old = np.array(good_old)

        # 1. Pose Estimation
        if len(good_new) > 5:
            # Calculate average feature displacement (optical flow magnitude)
            flow_vectors = good_new - good_old
            avg_flow = np.mean(np.linalg.norm(flow_vectors, axis=1))
            
            E, mask = cv2.findEssentialMat(good_new, good_old, self.K, method=cv2.RANSAC, prob=0.999, threshold=1.0)
            if E is not None:
                _, R, t, mask = cv2.recoverPose(E, good_new, good_old, self.K)
                t_mag = np.linalg.norm(t)
                scale = 1.0
                
                # Update trajectory
                self.cur_t = self.cur_t + scale * self.cur_R.dot(t)
                self.cur_R = self.cur_R.dot(R)
                
                self.traj_x.append(self.cur_t[0][0])
                self.traj_y.append(self.cur_t[1][0])
                self.traj_z.append(self.cur_t[2][0])
                
                print(f"Frame {self.frame_count} | Feats: {len(good_new)} | Flow: {avg_flow:.2f}px | Step: {t_mag:.4f} | Pos: ({self.cur_t[0][0]:.2f}, {self.cur_t[1][0]:.2f}, {self.cur_t[2][0]:.2f})", flush=True)
        else:
             print(f"Frame {self.frame_count}: Not enough features ({len(good_new)})", flush=True)

        # 2. Preparation for Next Frame
        if len(good_new) < 1000: 
             new_kps = cv2.goodFeaturesToTrack(curr_gray, mask=static_mask, **self.feature_params)
             self.prev_keypoints = new_kps if new_kps is not None else good_new.reshape(-1, 1, 2)
        else:
             self.prev_keypoints = good_new.reshape(-1, 1, 2)

        self.prev_image = curr_gray
        return True, frame_raw, frame_cropped, None, dynamic_mask

    def on_key(self, event):
        if event.key == 'q':
            self.stop_requested = True

    def run(self):
        plt.ion()
        fig = plt.figure(figsize=(14, 7))
        self.stop_requested = False
        fig.canvas.mpl_connect('key_press_event', self.on_key)
        
        ax_masked = fig.add_subplot(121)
        ax_traj = fig.add_subplot(122, projection='3d')

        ax_masked.set_title("Mask R-CNN Overlay (Red=Dynamic)")
        ax_masked.axis('off')
        
        ax_traj.set_title("3D Trajectory")
        ax_traj.set_xlabel('X')
        ax_traj.set_ylabel('Z')
        ax_traj.set_zlabel('Y')
        ax_traj.view_init(elev=-20, azim=-90)

        line_traj, = ax_traj.plot(self.traj_x, self.traj_z, [-y for y in self.traj_y], color='blue')
        point_curr, = ax_traj.plot([0], [0], [0], 'ro')
        
        img_plot_masked = None

        print("Starting Visual Odometry (Mask R-CNN)...")
        self.frame_count = 0
        while not self.stop_requested:
            ret, frame_raw, frame_crop, _, mask_dyn = self.process_frame()
            if not ret: break
            self.frame_count += 1
            
            # --- Visualization ---
            
            # Blend red overlay on dynamic objects
            vis_masked = frame_crop.copy()
            
            # Prepare red image
            red_img = np.zeros_like(vis_masked)
            red_img[:, :, 2] = 255
            
            # Blend everything
            blended = cv2.addWeighted(vis_masked, 0.6, red_img, 0.4, 0)
            
            # Apply only where mask_dyn is 255
            vis_masked[mask_dyn == 255] = blended[mask_dyn == 255]
            
            # Draw features
            if self.prev_keypoints is not None:
                for new in self.prev_keypoints:
                    a, b = new.ravel()
                    cv2.circle(vis_masked, (int(a), int(b)), 3, (0, 255, 0), -1)
            
            masked_rgb = cv2.cvtColor(vis_masked, cv2.COLOR_BGR2RGB)
            if img_plot_masked is None:
                img_plot_masked = ax_masked.imshow(masked_rgb)
            else:
                img_plot_masked.set_data(masked_rgb)

            # Update Trajectory
            p_x = self.traj_x
            p_y = self.traj_z # Swap axes for plotting
            p_z = [-y for y in self.traj_y]
            
            line_traj.set_data(p_x, p_y)
            line_traj.set_3d_properties(p_z)
            point_curr.set_data([p_x[-1]], [p_y[-1]])
            point_curr.set_3d_properties([p_z[-1]])
            
            # Auto-scale
            if len(p_x) > 1:
                mx, my, mz = (max(p_x)+min(p_x))/2, (max(p_y)+min(p_y))/2, (max(p_z)+min(p_z))/2
                r = np.array([max(p_x)-min(p_x), max(p_y)-min(p_y), max(p_z)-min(p_z)]).max() / 2.0 or 1.0
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
    import argparse
    parser = argparse.ArgumentParser(description="Monocular Visual Odometry")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--start", "-s", type=float, default=0.0, help="Start time in seconds")
    args = parser.parse_args()
    
    if not os.path.exists(args.video):
        print(f"Error: File {args.video} not found.")
        sys.exit(1)
        
    vo = VisualOdometry(args.video, start_seconds=args.start)
    vo.run()
