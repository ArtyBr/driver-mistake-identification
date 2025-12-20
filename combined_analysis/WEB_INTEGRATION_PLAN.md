# Web Application Integration Plan: Driver Analysis System

This document outlines the architectural and implementation strategy for converting the CLI-based Driver Analysis System into a full-stack web application.

## 1. High-Level Architecture

The system will follow a **Client-Server-Worker** architecture to handle the computationally intensive video processing without blocking the user interface.

*   **Frontend (Client):** A Single Page Application (SPA) (Recommended: **React** or **Vue.js**) to handle file uploads, synchronize video playback, and render the interactive timeline/overlays.
*   **Backend (API):** A Python-based web server (Recommended: **FastAPI**) to manage uploads, serve static files, and dispatch processing jobs.
*   **Task Queue (Worker):** An asynchronous worker (Recommended: **Celery** with **Redis**) to execute the `VideoProcessor` logic in the background.
*   **Storage:** A local file system or Object Storage (S3) for videos, and a lightweight database (SQLite/PostgreSQL) for job status and metadata.

---

## 2. Backend Implementation Strategy

### A. Refactoring for "Headless" Execution
Currently, the system is designed to visualize using OpenCV windows or write to a video file. To support the web app, the `VideoProcessor` in `src/` needs a **Data Extraction Mode**.

1.  **Modify `VideoProcessor.run()`**:
    *   Add a flag (e.g., `export_json=True`).
    *   Instead of writing to `cv2.VideoWriter`, collect frame-by-frame data and event logs into a Python dictionary.
    *   **Data to collect:**
        *   Lane Polynomials (for drawing lines on the client canvas).
        *   Face Bounding Box & Gaze Vector (yaw, pitch).
        *   Safety Events (timestamp, severity, message).
2.  **Output Format**: Save the collected data as a `.json` file alongside the uploaded videos.

### B. The API Layer (FastAPI)
You need three main endpoints:

1.  **`POST /upload`**:
    *   Accepts `Multipart/form-data` containing two files: `video_road` and `video_face`.
    *   Saves files to a unique temporary directory (e.g., `uploads/{job_uuid}/`).
    *   Creates a generic "Job" entry in the database with status `PENDING`.
    *   Triggers the background worker task.
    *   **Returns:** `job_id`.

2.  **`GET /status/{job_id}`**:
    *   Checks the database/Redis for the progress of the analysis.
    *   **Returns:** `{"status": "PROCESSING", "progress": 45}` or `{"status": "COMPLETED"}`.

3.  **`GET /results/{job_id}`**:
    *   **Returns:** The generated JSON analysis data.
    *   Also serves the raw video files (via static file serving) so the frontend can stream them.

### C. The Background Worker
The web server cannot run the analysis directly or it will time out.
1.  **Job Trigger**: When `POST /upload` is hit, add a task to the Queue.
2.  **Execution**: The Worker imports your existing `src` modules.
    *   It initializes `LaneDetectorWrapper` and `FaceAnalyzer`.
    *   It runs the processing loop.
    *   **Crucially**, it does *not* need to generate a new MP4. It only needs to generate the JSON. This saves significant processing time.
3.  **Completion**: Updates the Job status to `COMPLETED` and saves the JSON result.

---

## 3. Data Structure (JSON Protocol)

To allow the frontend to visualize data, the backend should return a JSON object structured like this:

```json
{
  "meta": {
    "duration": 124.5,
    "fps": 30
  },
  "timeline_events": [
    {
      "id": 1,
      "timestamp": 12.5,
      "type": "lane_change",
      "severity": "CRITICAL", 
      "message": "UNSAFE: No Left Mirror check",
      "duration": 2.0
    },
    {
      "id": 2,
      "timestamp": 45.2,
      "type": "distraction",
      "severity": "INFO",
      "message": "Driver checking mirrors",
      "duration": 1.5
    }
  ],
  "frame_data": [
    {
      "time": 0.033,
      "lane_lines": [[x1, y1], [x2, y2], ...], 
      "face_bbox": [x, y, w, h],
      "gaze": {"yaw": 10, "pitch": -5},
      "current_state": "Looking Ahead"
    },
    ... (repeated for every frame or every Nth frame) ...
  ]
}
```

---

## 4. Frontend Implementation Strategy

### A. Dual Video Sync
You need to play the "Road" and "Face" videos in perfect unison.
*   **Technique**: Use a single "Master" time control.
*   Load both videos into HTML5 `<video>` elements.
*   Hide the default controls for the individual videos.
*   Create a custom "Play/Pause" button and "Scrubber" bar.
*   **Logic**: When the Master scrubber moves to timestamp `T`, programmatically set `roadVideo.currentTime = T` and `faceVideo.currentTime = T`.

### B. Canvas Overlay (The Visualization)
Instead of watching a pre-processed video, you will render the analysis live in the browser.
*   Place an HTML5 `<canvas>` transparently on top of the `<video>` elements.
*   **Render Loop**: use `requestAnimationFrame`.
    *   Get current video time.
    *   Look up the corresponding entry in the `frame_data` JSON array.
    *   Draw the lane lines and face bounding box using JavaScript Canvas API.
    *   *Benefit:* This allows the user to toggle visualizations on/off instantly without reloading videos.

### C. The Timeline Bar
This is a custom component positioned below the videos.
1.  **Base Layer**: A standard progress bar representing 0 to `video_duration`.
2.  **Event Layer**: Iterate through the `timeline_events` JSON array.
    *   For each event, calculate its position: `left = (event.timestamp / total_duration) * 100%`.
    *   Render a colored marker/pill at that position.
    *   **Color Logic**: 
        *   `CRITICAL` (Unsafe Lane Change) -> Red.
        *   `WARNING` -> Orange.
        *   `INFO` (Safe Lane Change) -> Green.
3.  **Interaction**:
    *   **Hover**: Show a tooltip with `event.message`.
    *   **Click**: Set the Master video time to `event.timestamp - 2.0` (rewind slightly for context).

### D. Dashboard Layout
*   **Top**: Dual Video Player (Side-by-side) with Canvas Overlays.
*   **Middle**: Master Playback Controls + The "Event Timeline".
*   **Bottom**: A detailed list/table of events (Logs) that can also be clicked to jump to that timestamp.

---

## 5. Deployment Considerations

*   **GPU Access**: The backend (Python/PyTorch) requires GPU access for speed. If hosting on AWS/GCP, use a generic GPU instance (e.g., g4dn.xlarge).
*   **Containerization**: Use **Docker**.
    *   *Container 1 (Frontend):* Nginx serving React static files.
    *   *Container 2 (API):* FastAPI + Uvicorn.
    *   *Container 3 (Worker):* Celery Worker (with access to CUDA).
    *   *Container 4 (Broker):* Redis.
