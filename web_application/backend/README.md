# Backend API Architecture

The backend serves as the Command & Control center for the Driver Mistake Identification system. It is built using FastAPI for high performance and easy asynchronous task management.

## Detailed File Structure

```
backend/
├── app/
│   ├── api/
    │   │   └── routes.py           # Endpoint definitions. Maps URLs (/upload, /list_analyses, /run_test, /status/{job_id}, /results/{job_id}) to Service functions.│   │
│   ├── core/
│   │   └── config.py           # Global settings: File paths, Log levels, Project Root resolution.
│   │
│   ├── db/
│   │   └── database.py         # Database engine setup (SQLite) and session management.
│   │
│   ├── models/
│   │   ├── job.py              # SQLModel definition for the 'jobs' table (DB Schema).
│   │   └── schemas.py          # Pydantic models for Request/Response validation (API Schema).
│   │
│   ├── services/
│   │   ├── analysis_service.py # Wraps the external 'combined_analysis' script. Handles subprocess execution.
│   │   ├── file_service.py     # file system operations: creation, deletion, chunk saving.
│   │   ├── job_service.py      # High-level business logic: CRUD for jobs, coordinating files & DB.
│   │   └── video_utils.py      # Low-level video manipulation (FFmpeg wrapper).
│   │
│   └── main.py                 # App Entry point. Configures CORS, Static Files, and DB initialization.
│
├── jobs.db                     # SQLite database file (created on runtime).
├── requirements.txt            # Python dependencies.
└── start_server.sh             # Convenience script to set paths and run Uvicorn.
```

## Technology Justification

We selected our technology stack to maximize developer velocity, type safety, and performance for IO-bound tasks.

### 1. Framework: FastAPI
*   **Choice**: FastAPI was chosen as the core web framework.
*   **Why?** Its native support for Python's `async/await` syntax allows us to handle file uploads and database writes efficiently without blocking the main thread. It also provides automatic Swagger UI documentation, which is invaluable for testing the API independently of the frontend.
*   **Comparison**:
    *   **vs. Flask**: Flask is synchronous by default. Handling large file uploads in Flask blocks the worker thread, requiring a complex WSGI configuration (like Gunicorn/uWSGI with many workers) to handle concurrency.
    *   **vs. Django**: Django is a "batteries-included" framework. For a microservice primarily focused on acting as a wrapper around an ML script, Django's ORM, admin panel, and template engine were unnecessary bloat.

### 2. Database: SQLite with SQLModel
*   **Choice**: We used SQLite for persistence, accessed via SQLModel (SQLAlchemy + Pydantic).
*   **Why?**
    *   **SQLite**: It is serverless and creates a single `.db` file. This ensures the project is portable and easy to run on any machine without installing a database server like MySQL or PostgreSQL.
    *   **SQLModel**: It eliminates the need to duplicate code between database models (SQLAlchemy) and API schemas (Pydantic). We define the `Job` class once and use it for both validation and table creation.
*   **Comparison**: Using a full database server like PostgreSQL would add operational complexity (docker containers, connection credentials) that is unnecessary for a single-user analysis tool.

### 3. Task Management: FastAPI BackgroundTasks
*   **Choice**: We utilized FastAPI's built-in `BackgroundTasks` to trigger the analysis.
*   **Why?** It is simple and requires no external infrastructure.
*   **Comparison**: A robust production system might use **Celery** with Redis. However, introducing Redis would require the user to install and run another service. Given the scope of this project, the "fire-and-forget" nature of `BackgroundTasks` provides the necessary non-blocking behavior with zero configuration.

## Key Components & Design Decisions

### 1. Service-Repository Pattern
We moved logic out of routes.py into services/.
*   **Why?** It allows us to reuse logic (creating a job, managing files, running analysis, processing video) from different contexts (HTTP request vs. CLI tool) and makes unit testing easier.
*   **Flow**: Request -> Route -> JobService -> FileService -> Database.

### 2. FFmpeg Splicing
Dashcams often split video into 1-minute chunks.
*   **Solution**: The video_utils.py module uses ffmpeg to concat these chunks into a single road.mp4 and face.mp4 before analysis begins, ensuring continuity in tracking.
*   **Library Safety**: We explicitly manage environment variables (stripping LD_LIBRARY_PATH) when calling FFmpeg to prevent conflicts with Conda environments.

## API Endpoints Reference

### Job Management
*   POST /upload: Creates a new analysis job.
    *   Payload: Multipart form data (video_road, video_face).
    *   Returns: { "job_id": "uuid..." }
*   GET /status/{job_id}: Polling endpoint.
    *   Returns: { "status": "PROCESSING", "progress": 45, ... }
*   GET /results/{job_id}: Fetch final JSON analysis.

### Utility
*   GET /list_analyses: Returns list of completed jobs stored on disk.
*   POST /run_test: Creates a dummy job using pre-loaded test videos (for dev testing).