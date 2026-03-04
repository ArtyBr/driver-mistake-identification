# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Driver Mistake Identification is a full-stack web application for automated driver safety analysis. It processes dual video streams (road-facing + driver-facing) to detect unsafe driving behaviours (e.g., lane changes without checking mirrors).

## Commands

### Frontend (`web_application/frontend/`)
```bash
npm install          # Install dependencies
npm run dev          # Dev server on port 5173 (HMR)
npm run build        # Production bundle → dist/
npm run preview      # Serve production bundle
npm run lint         # ESLint
```

### Backend (`web_application/backend/`)
```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000  # Dev
./start_server.sh    # Production (ports 7728 backend, 7727 frontend)
```

### Backend Tests (`web_application/backend/`)
```bash
pytest tests/                          # All tests
pytest tests/test_batch_service.py     # Single file
pytest tests/ -k "test_name"           # Single test
```

### Core Analysis Engine (`combined_analysis/`)
```bash
python main.py <config_path> \
  --video_base /path/to/videos \
  --load_from /path/to/weights.pth \
  --savedir ./output \
  --show   # optional: display live visualization
```

### Full-stack Production Deployment
```bash
./start_server.bash  # Kills old processes, starts backend+frontend with SSL
```
Production: backend on port 7728, frontend on port 7727. Upload storage at `/dcs/large/safedrive_cs310_2526/uploads`. SSL certs (`key.pem`, `cert.pem`) required in backend directory.

### SLURM Cluster Access
```bash
ssh -J u2204449@remote-49 u2204449@kudu-taught  # Jump via remote-49 to kudu cluster
```
The analysis pipeline runs on the `kudu` cluster. The remote project root is `~/cs310/driver-mistake-identification`.

## Architecture

### Request Flow

```
React SPA (port 5173/7727)
    │  POST /upload (dual videos) → job_id
    │  GET  /status/{job_id}      (poll every 2s)
    │  GET  /result/{job_id}      (fetch JSON)
    ▼
FastAPI Backend (port 8000/7728)
    │  Accepts upload → stores files → returns job_id immediately
    │  Spawns detached subprocess (run_headless.py)
    │  Monitors subprocess stdout for progress updates → writes to SQLite
    ▼
Subprocess: combined_analysis/run_headless.py
    │  VideoProcessor orchestrates dual-stream frame-by-frame analysis
    │  Writes results.json to uploads/{job_id}/
    ▼
SQLite: web_application/backend/jobs.db
    └── Jobs, Users, Sessions
```

**Why subprocess isolation:** Video analysis takes minutes; HTTP timeouts are seconds. The backend returns a `job_id` immediately and the frontend polls `/status/{job_id}`. Subprocess isolation also bypasses the Python GIL for CPU-intensive work.

### Analysis Pipeline (`combined_analysis/src/`)

Each frame passes through:
1. **LaneDetectorWrapper** (`lane_detector.py`) — LaneAtt (ResNet18) infers polynomial lane coefficients
2. **LaneTracker** (`lane_tracking.py`) — Kalman Filter smooths detections; detects lane-change events
3. **FaceAnalyzer** (`face_analyzer.py`) — InsightFace RetinaFace + head pose → PCA+SVM → semantic gaze label (`Forward`, `Left Mirror`, `Right Mirror`, `Rear Mirror`, `Radio`, `Speedometer`)
4. **SafetyMonitor** (`safety_monitor.py`) — On lane-change event, checks 5-second history buffer: "Did driver look at required mirror?" → `SAFE` or `UNSAFE` event
5. **Visualization** (`visualization.py`) — Draws overlays for optional live preview

### Frontend Structure (`web_application/frontend/src/`)

**Pages:** `Home`, `UploadPage`, `StatusPage`, `ResultPage`, `LoginPage`, `SignupPage`

**Custom hooks** encapsulate all complex logic:
- `useJob.js` — Polling with `setInterval`; stops when job completes/fails
- `useVideoPlayback.js` — Frame-accurate synchronization of two `<video>` elements (road + driver)
- `useVideoCanvas.js` — Canvas overlay rendering (lane lines, face boxes, gaze vectors)
- `useVideoAnalysisData.js` — Fetches and caches `results.json`
- `useVideoRecorder.js` — Webcam recording for new uploads
- `useAuth.jsx` — JWT auth state (login/signup/logout)

**ResultPage** is the most complex page: synchronized dual-video player with canvas overlays and an interactive event timeline (red=unsafe, green=safe markers).

### Backend Services (`web_application/backend/app/`)

| Service | Responsibility |
|---|---|
| `analysis_service.py` | Build CLI command, spawn subprocess, parse stdout for progress |
| `file_service.py` | Multipart upload handling, file organization |
| `job_service.py` | Job CRUD on SQLite via SQLModel |
| `auth_service.py` | JWT generation/validation, bcrypt password hashing |
| `batch_service.py` | Batch job processing |

**API routes:**
- `routes.py` — `/upload`, `/status/{job_id}`, `/result/{job_id}`, `/list_analyses`, `/run_test` (demo mode)
- `auth_routes.py` — `/auth/signup`, `/auth/login`, `/auth/me`
- `session_routes.py` — `/session/start`, `/session/{id}`

### Database Models (`app/models/`)
- `Job` — status, progress, results path, owner user_id
- `User` — username, hashed password
- `Session` — recording session metadata

## Key Paths

| Path | Purpose |
|---|---|
| `web_application/backend/app/core/config.py` | Backend config: JWT secret, upload dir, ports |
| `combined_analysis/src/config.py` | Analysis constants: class names, history duration, model dimensions |
| `web_application/backend/jobs.db` | SQLite DB (gitignored, auto-created) |
| `/dcs/large/safedrive_cs310_2526/uploads` | Production upload storage (cluster filesystem) |
| `combined_analysis/weights/` | Model weights (gitignored) |

## Tech Stack

- **Frontend:** React 19, Vite, Bootstrap 5, React Router 7, Axios
- **Backend:** FastAPI, Uvicorn, SQLModel (SQLAlchemy + Pydantic), SQLite, python-jose (JWT), passlib (bcrypt)
- **Analysis:** PyTorch (LaneAtt/ResNet18), OpenCV, InsightFace (RetinaFace), scikit-learn (SVM gaze classifier + PCA)
