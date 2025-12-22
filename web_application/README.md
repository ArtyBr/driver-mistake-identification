# Driver Mistake Identification - Web Application

This directory contains the web-based interface for the Driver Mistake Identification system. It is split into a **backend** API (FastAPI) and a **frontend** UI (React).

## Architecture

The application uses a decoupled client-server architecture:

*   **Frontend**: A Single Page Application (SPA) built with React 19 and Vite.
    *   **Modular Design**: Logic is separated into custom hooks (`useVideoPlayback`, `useVideoCanvas`, `useVideoAnalysisData`) for cleaner code and better maintainability.
    *   **Local-First Playback**: Optimized to play uploaded files directly from the user's browser (Blob URLs) when available, reducing server bandwidth and providing instant feedback.
*   **Backend**: A FastAPI server that exposes REST endpoints. It manages video file storage, uses **FFmpeg** to splice multi-part uploads into continuous streams for analysis, and persists state in a SQLite database.

## Prerequisites

*   **Python 3.9+** (Conda environment recommended)
*   **Node.js 18+** & **npm**

## Quick Start

### 1. Start the Backend

Navigate to the backend directory and run the server script:

```bash
cd backend
./start_server.sh
```
This starts the API server at `http://localhost:8000`.

### 2. Start the Frontend

Navigate to the frontend directory, install dependencies, and start the development server:

```bash
cd frontend
npm install
npm run dev
```
The UI will be available at `http://localhost:5173`.

## Features

*   **Spliced Video Support**: Upload multiple video parts for both road and face cameras; the backend automatically merges them using FFmpeg.
*   **Intelligent Timeline**: Interactive seeker that spans multiple video segments seamlessly.
*   **Rich Visualizations**: Real-time overlay of detected lane lines (road) and head pose pointers (face).
*   **Flicker-Free Playback**: Optimized React rendering that reuses video elements during segment transitions.
*   **Progress Tracking**: Real-time feedback on upload and analysis status.
*   **Job History**: Persistent record of past analyses with collision-resistant job ID generation.

## Directory Structure

*   `backend/`: Python FastAPI application.
*   `frontend/`: React Vite application.
*   `uploads/`: Storage for uploaded videos and analysis results (generated at runtime).
