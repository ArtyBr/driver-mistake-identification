import torch
import cv2
import numpy as np
from torchvision.models.detection import fasterrcnn_resnet50_fpn_v2, FasterRCNN_ResNet50_FPN_V2_Weights

class VehicleDetector:
    def __init__(self, confidence_threshold=0.6):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Load Faster R-CNN (ResNet50 FPN V2) - Much better accuracy than SSDLite
        print("Loading Vehicle Detector (Faster R-CNN)...")
        weights = FasterRCNN_ResNet50_FPN_V2_Weights.DEFAULT
        self.model = fasterrcnn_resnet50_fpn_v2(weights=weights).to(self.device)
        self.model.eval()
        
        self.confidence_threshold = confidence_threshold
        
        # COCO class labels for vehicles
        self.vehicle_classes = [3, 4, 6, 8]  # car, motorcycle, bus, truck
        self.class_names = {
            3: 'Car',
            4: 'Moto',
            6: 'Bus',
            8: 'Truck'
        }
        
        # --- Geometric Distance Calibration ---
        # Heuristic: Distance is inversely proportional to the vertical distance 
        # from the horizon to the bottom of the object (where it touches the road).
        # D = K / (y_bottom - y_horizon)
        
        # K depends on camera height and focal length. 
        # approximate K for a standard dashcam at 1080p.
        # Adjusted to 2000 to better balance close vs far range with new horizon.
        self.K_inv_perspective = 2000.0  
        self.horizon_ratio = 0.55 # Horizon at 55% of screen height (lower)
        
        # Camera parameters for lateral distance
        # Assuming f roughly equals K (if H_cam ~ 1.0m)
        self.focal_length = 1000.0 
        self.bumper_offset = 2.0 # Distance from camera to front bumper

    def detect(self, frame):
        """
        Detects vehicles in the frame.
        Args:
            frame: Numpy array (H, W, C), BGR format (standard OpenCV)
        Returns:
            List of dictionaries: {'bbox': [x1, y1, x2, y2], 'label': str, 'score': float, 'distance': float}
        """
        h_img, w_img = frame.shape[:2]
        img_center_x = w_img / 2
        
        # Preprocess
        img_tensor = torch.from_numpy(frame).permute(2, 0, 1).float() / 255.0
        img_tensor = img_tensor.unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            predictions = self.model(img_tensor)[0]
            
        boxes = predictions['boxes'].cpu().numpy()
        labels = predictions['labels'].cpu().numpy()
        scores = predictions['scores'].cpu().numpy()
        
        vehicles = []
        
        horizon_y = h_img * self.horizon_ratio

        for i, score in enumerate(scores):
            if score > self.confidence_threshold:
                label = labels[i]
                if label in self.vehicle_classes:
                    box = boxes[i].astype(int)
                    x1, y1, x2, y2 = box
                    
                    # --- Improved Distance Estimation (Euclidean) ---
                    # 1. Longitudinal Distance (Z)
                    # Using the "flat world" assumption.
                    dy = y2 - horizon_y
                    
                    if dy <= 10: 
                        d_long = 200.0 
                    else:
                        d_long = self.K_inv_perspective / dy
                    
                    # 2. Lateral Distance (X)
                    # X = (u - c_x) * Z / f
                    box_center_x = (x1 + x2) / 2
                    d_lat = (box_center_x - img_center_x) * d_long / self.focal_length
                    
                    # 3. Euclidean Distance
                    d_euclidean = np.sqrt(d_long**2 + d_lat**2)
                    
                    # 4. Bumper Offset
                    # Subtract distance from camera to bumper to get "gap"
                    distance = max(0.0, d_euclidean - self.bumper_offset)
                        
                    # Cap max distance
                    distance = min(distance, 150.0)

                    vehicles.append({
                        'bbox': box.tolist(),
                        'label': self.class_names.get(label, 'Veh'),
                        'score': float(score),
                        'distance': float(distance)
                    })
                    
        return vehicles