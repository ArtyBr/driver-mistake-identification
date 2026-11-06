# Backend API

FastAPI server that handles video uploads, spawns analysis subprocesses, tracks job progress via SQLite, and serves results. Uses JWT authentication for user accounts.

## Usage

```bash
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or use the convenience script:

```bash
./start_server.sh
```

## Files

```
backend/
  app/
    api/
      routes.py            Upload, status, result, list endpoints
      auth_routes.py       Signup, login, JWT validation
      session_routes.py    Recording session management
      admin_routes.py      Admin utilities
      sync_routes.py       Video synchronisation endpoints
    core/
      config.py            Global settings (JWT secret, upload dir, ports)
    db/
      database.py          SQLite engine setup, session management, admin user creation
    models/
      job.py               SQLModel definition for the jobs table
      schemas.py           Pydantic request/response schemas
    services/
      analysis_service.py  Spawns combined_analysis subprocess, parses stdout for progress
      file_service.py      Multipart upload handling, file organisation
      job_service.py       Job CRUD operations
      auth_service.py      JWT generation/validation, bcrypt password hashing
      batch_service.py     Batch job processing
      video_utils.py       FFmpeg wrapper for video transcoding and metadata
    main.py                App entry point (CORS, static files, DB init)
  requirements.txt
  start_server.sh          Sets PATH and launches uvicorn
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload` | Upload videos, returns `{ job_id }` |
| `GET` | `/api/status/{job_id}` | Returns `{ status, progress }` |
| `GET` | `/api/result/{job_id}` | Returns analysis JSON |
| `GET` | `/api/list_analyses` | List completed jobs on disk |
| `POST` | `/api/run_test` | Create demo job with test videos |

## Dependencies

See `requirements.txt`. Key packages: FastAPI, Uvicorn, SQLModel, python-jose (JWT), passlib (bcrypt), python-multipart.
