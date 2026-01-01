# Driver Mistake Identification - Web Application

This directory contains the full stack web application for the Driver Mistake Identification system. It is designed as a modular Client-Server-Worker system to handle heavy video processing tasks while maintaining a responsive user interface.

## Project Structure Overview

The application is strictly separated into a Backend API and a Frontend UI.

```
web_application/
├── backend/            # FastAPI Server (Python)
│   ├── app/            # Application Logic (Source Code)
│   │   ├── api/        # REST Endpoints (Routes)
│   │   ├── core/       # Global Configuration & Logging
│   │   ├── db/         # Database Connection & Initialization
│   │   ├── models/     # SQLModel Database Schemas
│   │   └── services/   # Business Logic & Orchestration
│   ├── start_server.sh # Launch Script
│   └── jobs.db         # SQLite Database (Auto-generated)
├── frontend/           # React UI (JavaScript/Vite)
│   ├── src/            # Source Code
│   │   ├── components/ # Reusable UI Modules (common/ & features/)
│   │   ├── hooks/      # Custom React Hooks (Logic separation)
│   │   ├── pages/      # Route-level Views
│   │   └── services/   # API Client
│   └── dist/           # Production Build Artifacts
├── uploads/            # Shared Storage for Videos & Results
└── README.md           # This file
```

## Design Rationale

This project was architected to balance the computational intensity of machine learning with the need for a smooth user experience. The following design choices were made to meet these requirements:

### 1. Client-Server-Worker Architecture
*   **Choice**: We adopted an asynchronous Worker pattern. The HTTP API accepts the job, returns a `job_id` immediately, and processes the video in the background.
*   **Justification**: Machine learning inference on video files takes significant time (often longer than HTTP timeout limits). A synchronous "Monolithic" approach where the user waits for the response would lead to browser timeouts and a frozen UI.
*   **Comparison**: A Serverless (Lambda/Cloud Functions) approach was considered but rejected due to the cold-start latency of loading large PyTorch models and the constraints on execution time and memory for video processing.

### 2. Communication Strategy: Short Polling
*   **Choice**: The frontend polls the `/status/{job_id}` endpoint every 2 seconds.
*   **Justification**: Short polling is stateless, robust, and easy to implement/debug. Since our analysis jobs are long-running (minutes), the overhead of checking every few seconds is negligible compared to the complexity of maintaining persistent connections.
*   **Comparison**: WebSockets would offer "real-time" updates but introduce significant state management complexity (handling disconnects, reconnection logic, sticky sessions). Server-Sent Events (SSE) are unidirectional but often blocked by corporate firewalls. Polling proved to be the most reliable solution for this specific use case.

## Architecture

The system follows the Service-Repository Pattern on the backend and a Hook-Based Component Architecture on the frontend.

### Backend (FastAPI)
*   **Role**: Orchestrator. It accepts file uploads, manages job state in a database, and spawns background processes for computer vision analysis.
*   **Key Tech**: FastAPI, SQLModel (ORM), SQLite, FFmpeg, PyTorch (via subprocess).
*   **Design**:
    *   **Thin Controllers (api/)**: Only handle HTTP details (status codes, request parsing).
    *   **Rich Services (services/)**: Contain the actual logic (e.g., "Splicing video parts", "Creating job records").
    *   **Async Workers**: Video analysis runs in a background thread/process to prevent blocking the API.

### Frontend (React)
*   **Role**: User Interface. It handles file selection, upload progress tracking, and complex result visualization.
*   **Key Tech**: React 19, Vite, Bootstrap 5, Axios.
*   **Design**:
    *   **Custom Hooks (hooks/)**: Encapsulate complex logic like "Polling for status" or "Syncing two videos".
    *   **Local-First Playback**: Uses browser Blob URLs to play videos instantly without waiting for server round-trips during the session.

## Quick Start

### 1. Start the Backend
```bash
cd backend
./start_server.sh
```
*   Server runs at: http://localhost:8000
*   API Docs: http://localhost:8000/docs

### 2. Start the Frontend
```bash
cd frontend
npm install
npm run dev
```
*   UI runs at: http://localhost:5173

## Key Features

*   **Multi-Part Uploads**: Automatically detects and splices split video files (common in dashcams) using FFmpeg.
*   **Resilient Analysis**: Runs as a detached process; if the UI closes, the job continues.
*   **Live Synchronization**: The VideoPlayer component synchronizes two video streams (Road & Face) with frame-perfect accuracy.
*   **Interactive Visualization**:
    *   **Lane Overlay**: Draws detected lanes on the HTML5 Canvas over the video.
    *   **Timeline**: Shows color-coded events (blind-spot checks, distractions) on a navigable bar.
*   **Job History**: Persists analysis results in jobs.db so they can be reviewed later.
