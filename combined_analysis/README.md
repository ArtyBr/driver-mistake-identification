# Unified Driver Mistake Identification System

This system represents a comprehensive, multi-modal computer vision pipeline designed to automatically detect potential driving errors. Its primary function is to correlate vehicle maneuvers—specifically lane changes and lateral deviations—with driver attention metrics derived from head pose analysis. By integrating state-of-the-art Lane Detection with robust Face Analysis, the system acts as an automated "driving instructor" or safety monitor, capable of flagging unsafe behaviors such as merging without checking mirrors or drifting out of lanes while distracted.

---

## System Architecture

The system operates as a synchronized, dual-stream processing pipeline. It ingests two concurrent video feeds: the **Road View** (a forward-facing camera capturing the environment) and the **Driver View** (an interior-facing camera capturing the driver). These streams are processed in parallel but synchronized temporally to ensure that events outside the car can be causally linked to actions inside the car.

```mermaid
graph TD
    subgraph Inputs
        RV[Road Video Stream]
        DV[Driver Video Stream]
    end

    subgraph "Core Processing Loop (VideoProcessor)"
        Sync[Frame Synchronization & Time Alignment]
        
        subgraph "Lane Analysis Module"
            LD[LaneAtt Detector (ResNet18)] -->|Raw Polynomial Coeffs| KF[Kalman Filter Tracker]
            KF -->|Smoothed State Vectors| LE[Lane Event Logic]
            LE -->|Event Trigger: Lane Cross| SM
        end

        subgraph "Driver Analysis Module"
            FD[InsightFace Detector] -->|BBox + 5 Landmarks| HP[Head Pose Estimation]
            HP -->|Euler Angles (Yaw/Pitch/Roll)| PCA[PCA Dimensionality Reduction]
            PCA -->|Transformed Features| Gaze[SVM Gaze Classifier]
            Gaze -->|Semantic State: Mirror/Radio| Hist[State History Buffer]
            Hist -->|Contextual Window (5s)| SM
        end

        subgraph "Safety Logic Engine"
            SM[Safety Monitor / Validator] -->|Query Context| Hist
            SM -->|Evaluation: Safe/Unsafe| Alert[Alert System]
        end
    end

    subgraph Outputs
        Vis[Visualizer Overlay (OpenCV)]
        JSON[Structured Analysis Report]
    end

    RV --> Sync
    DV --> Sync
    Sync --> LD
    Sync --> FD
    Alert --> Vis
    Alert --> JSON
```

---

## Component Details

### 1. Video Processing & Synchronization (`video_processor.py`)
**Role:** The Central Controller and Timekeeper.

**Detailed Description:**
The `VideoProcessor` class serves as the backbone of the application. Its primary responsibility is to manage the ingestion of two independent video files which, while recorded simultaneously, may suffer from minor frame rate variances or start-time offsets. The processor iterates through the "Road" video frame-by-frame and retrieves the corresponding "Face" frame by index, enforcing a strict temporal alignment. This is crucial because a discrepancy of even half a second could invalidate the safety logic (e.g., the system might miss that a driver checked their mirror *just before* the lane change if the videos are out of sync). Furthermore, this module handles the "headless" mode logic versus the "visualization" mode, managing distinct pipelines for purely analytical JSON export (optimized for speed) versus graphical overlay generation (optimized for human review). It also manages resource allocation, ensuring that GPU memory is cleared between runs to prevent leaks during batch processing.

### 2. Lane Detection & Tracking (`lane_detector.py`, `lane_tracking.py`)
**Role:** Spatial Awareness and Trajectory Prediction.

**Lane Detection (LaneAtt):**
We utilize **LaneAtt** (Lane Attention), an anchor-based deep learning model with a ResNet18 backbone. Unlike segmentation models that output a pixel-wise probability mask (which requires computationally expensive post-processing like curve fitting or skeletonization), LaneAtt treats lane detection as an object detection problem. It projects thousands of "anchor" lines onto the image and uses the neural network to predict offsets for the anchors that align with the actual lane markings. This approach outputs mathematical lane descriptions (polynomial coefficients) directly from the network head. We chose this architecture because it offers a superior trade-off between inference speed (high FPS) and accuracy, particularly on challenging datasets like CULane where occlusion and lighting variance are common.

**Kalman Filter Tracking:**
Raw neural network detections can be noisy; a single frame of sun glare might cause the detector to lose the lane or output a jittery line. To solve this, we implement a **Kalman Filter** for every detected lane. The filter maintains a state vector `[a, b, c, da, db, dc]`, representing the polynomial coefficients of the lane curve (`a, b, c`) and their rates of change (`da, db, dc`). For every new frame, the filter *predicts* where the lane should be based on its previous velocity, and then *corrects* this prediction using the new measurement from LaneAtt. This allows the system to smooth out jitter and, critically, to "remember" the lane's position for several frames even if the visual detector fails completely (e.g., going under a bridge or during heavy rain), ensuring the safety logic always has valid lane data to work with.

**Event Detection:**
The `LaneTracker` also calculates the lateral position of the "ego-lanes" (the two lines closest to the car) relative to the image center. By monitoring the quadratic component (`c` in `ax^2 + bx + c`) at the bottom of the frame, the system can detect when a lane line crosses the center vertical axis of the image. If the crossing velocity is sufficient, it registers a `Lane Change Event` (either `left-to-right` or `right-to-left`). This event serves as the primary "Trigger" for the Safety Monitor to begin its validation process.

### 3. Face Analysis & Gaze Estimation (`face_analyzer.py`)
**Role:** Driver Attention and Intent Understanding.

**Face Detection & Landmarks:**
The system employs the **InsightFace** library, specifically using the RetinaFace detector for bounding box localization and coordinate regression. We extract 5 key facial landmarks (two eyes, nose tip, two mouth corners). InsightFace was selected because it is an industry-standard, lightweight model robust to the extreme lighting conditions found in vehicles (e.g., pitch black nights illuminated only by dashboard lights, or direct sunlight hitting the driver's face).

**Head Pose & Gaze Classification:**
While "Eye Tracking" is often discussed in driver monitoring, it requires high-resolution imagery and precise calibration that is rarely available in standard dashcam setups. Instead, we use **Head Pose** (Pitch, Yaw, Roll) as a robust proxy for attention. We extract these Euler angles from the facial landmarks. However, raw angles (e.g., "Yaw: 25.4 degrees") are noisy and difficult to write hard-coded logic for. To bridge this gap, we trained a **Support Vector Machine (SVM)** classifier. We feed the raw Euler angles into a PCA (Principal Component Analysis) transformer to normalize the features, and then into the SVM. This classifier outputs discrete semantic labels: `Forward`, `Left Mirror`, `Right Mirror`, `Rear Mirror`, `Radio`, and `Speedometer`. This converts a continuous, noisy signal into a clean, actionable state stream.

### 4. Safety Monitor (`safety_monitor.py`)
**Role:** The Rule Engine and Decision Maker.

**Contextual Memory:**
The monitor maintains a rolling buffer called `state_history`, which stores the timestamped classification of the driver's gaze for the last 5 seconds (configurable). This "short-term memory" is essential because safe driving behaviors are temporal sequences, not instantaneous states. A driver checks their mirror *before* moving, not necessarily *while* moving.

**Validation Logic:**
The validation process follows a strict "Trigger-Query" pattern. 
1.  **Trigger:** The Lane Tracker reports a `Lane Change Event` (e.g., moving Left).
2.  **Query:** The Safety Monitor looks back into the `state_history`. It filters for the specific safety action required for that maneuver (e.g., "Did we see the `Left Mirror` state in the last 5 seconds?").
3.  **Decision:**
    *   **SAFE (INFO):** If the required state exists in the history window, the maneuver is validated. The system logs this as a safe lane change.
    *   **UNSAFE (CRITICAL):** If the required state is absent (i.e., the driver looked only `Forward` or at the `Radio` before merging), the system flags this as a critical safety violation ("Blind Merge").

---

## Design Decisions & Rationale

### Why Head Pose instead of Eye Gaze?
We deliberately chose Head Pose estimation over direct Eye Gaze tracking. Eye tracking is incredibly sensitive to image quality; it fails when the driver wears sunglasses, glasses with thick rims, or when the camera resolution is low (common in dashcams). Furthermore, the geometry of a car cabin means drivers *must* rotate their heads to check side mirrors effectively (the "shoulder check" or simply turning to see the mirror). Head pose provides a macro-signal that is far more robust to noise, occlusion, and lighting changes, providing high reliability without requiring expensive hardware or per-driver calibration.

### Why Anchor-Based Lane Detection (LaneAtt) over Segmentation?
Many lane detection tutorials use Semantic Segmentation (e.g., U-Net) to generate a binary mask of the lanes. While visually intuitive, segmentation is computationally expensive and mathematically indirect. The output is just a "blob" of pixels that requires heavy CPU post-processing (hough transforms, sliding windows, polyfitting) to turn into a usable line equation. **LaneAtt**, conversely, outputs the line equations directly from the GPU. This reduces the latency of the system significantly, freeing up CPU cycles for the heavy logic of the Kalman Filter and Safety Monitor, and ensuring the system can run in real-time on modest hardware.

### Why a Modular "Pipeline" instead of End-to-End Deep Learning?
We could have trained a single large Neural Network to take video as input and output "Safe" or "Unsafe" directly (e.g., a Video Transformer). However, we chose a modular architecture for **Explainability** and **Debuggability**. 
*   **Explainability:** If the system says a driver is unsafe, we can point exactly to *why*: "The Lane Detector saw a merge at T=4s, but the Face Analyzer saw no mirror check between T=0s and T=4s." A black-box model cannot provide this granular reasoning.
*   **Debuggability:** If the system fails, we can isolate the fault. Is the lane detector missing the lines? Is the face detector missing the face? Or is the logic threshold too strict? This modularity allows us to upgrade individual components (e.g., swapping LaneAtt for a newer model) without retraining the entire safety logic.

---

## Usage Guide

### Prerequisites
*   **Python 3.9+**: Required for compatibility with modern PyTorch and InsightFace versions.
*   **Hardware**: A CUDA-enabled NVIDIA GPU is highly recommended for real-time performance. The system *can* run on CPU, but frame rates will be significantly lower (approx 1-5 FPS vs 30+ FPS on GPU).
*   **Dependencies**: Key libraries include `torch` (neural network inference), `opencv-python` (video manipulation), `insightface` (face analysis), and `scikit-learn` (SVM classification).

### Execution Command
The system is executed via `main.py`. It requires a pointer to the specific LaneAtt configuration file (defining the model architecture) and the base path to the video pair.

```bash
# Standard Execution
python3 main.py ./lane_detection/lanedet/configs/laneatt/resnet18_culane.py \
    --video_base /home/user/data/drive_session_01/2025_0901_recording \
    --load_from ./lane_detection/weights/laneatt_r18_culane.pth \
    --savedir ./combined_analysis/output/ \
    --show
```

**Argument Breakdown:**
*   `config_path`: The first argument. Points to the Python config file that defines the LaneAtt model structure (backbone, anchors, etc.).
*   `--video_base`: The absolute path to the video files, **excluding** the suffix. The system automatically appends `_F.mp4` (Front/Face) and `_I.mp4` (Infrastructure/Road) to this path to find the source files.
*   `--load_from`: Path to the pre-trained `.pth` weights for the LaneAtt model.
*   `--savedir`: Directory where the output video (with visualization overlay) and JSON report will be saved.
*   `--show`: Optional flag. If present, it opens an OpenCV window to display the processing in real-time. Remove this for faster, headless processing on a server.

```