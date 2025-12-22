# Backend API

The backend is built with **FastAPI** and serves as the orchestrator for the video analysis pipeline.

## Structure

The code is organized in the `app/` package:

*   `app/main.py`: Application entry point and configuration.
*   `app/api/routes.py`: Definition of REST API endpoints.
*   `app/core/config.py`: Global settings (paths, logging).
*   `app/db/database.py`: SQLite database operations.
*   `app/services/analysis_service.py`: Logic for running the analysis subprocess (`combined_analysis/run_headless.py`).
*   `app/models/schemas.py`: Pydantic models for data validation.

## API Endpoints

### `POST /upload`
Uploads road and face videos.
*   **Input**: `multipart/form-data` with `video_road` and `video_face`.
*   **Output**: JSON with `job_id`.
*   **Behavior**: Saves files to `uploads/{job_id}/` and triggers background processing.

### `GET /status/{job_id}`
Checks the status of a job.
*   **Output**: JSON with `status` (PENDING, PROCESSING, COMPLETED, FAILED), `progress` (0-100), and `result` (if completed).

### `GET /list_analyses`
Lists all historically completed analyses available on disk.

### `POST /run_test`
Simulates a job using pre-existing test data (useful for frontend dev without running the heavy ML pipeline).

## Configuration

Settings are defined in `app/core/config.py`.
*   **Database**: Uses `jobs.db` (SQLite) in the backend directory.
*   **Paths**: Automatically resolves project roots to import sibling modules (`combined_analysis`, `lane_detection`).

## Running

```bash
./start_server.sh
```
Or manually:
```bash
uvicorn app.main:app --reload
```
