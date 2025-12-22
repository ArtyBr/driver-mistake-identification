# Driver Mistake Identification - Web Application

This directory contains the web-based interface for the Driver Mistake Identification system. It is split into a **backend** API (FastAPI) and a **frontend** UI (React).

## Architecture

The application uses a decoupled client-server architecture:

*   **Frontend**: A Single Page Application (SPA) built with React 19 and Vite. It handles video uploads, displays real-time progress, and visualizes the analysis results.
*   **Backend**: A FastAPI server that exposes REST endpoints. It manages video file storage, queues analysis jobs in the background (using `combined_analysis` scripts), and persists state in a SQLite database.

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

*   **Video Upload**: Upload dual video streams (road and face).
*   **Progress Tracking**: Real-time feedback on upload and analysis status.
*   **Result Visualization**: (Planned) Interactive dashboard for reviewing identified mistakes.
*   **Job History**: Persistent record of past analyses.

## Directory Structure

*   `backend/`: Python FastAPI application.
*   `frontend/`: React Vite application.
*   `uploads/`: Storage for uploaded videos and analysis results (generated at runtime).
