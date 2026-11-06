# Web Application

Full-stack web application for the SafeDrive driver safety analysis system. Users upload dual video streams (road + driver), the backend spawns the analysis pipeline as a subprocess, and the frontend displays an interactive results dashboard with synchronised dual-video playback.

**Live deployment:** https://safedrive.dcs.warwick.ac.uk/

## Setup

### Backend (port 8000)

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger docs available at `http://localhost:8000/docs`.

### Frontend (port 5173)

```bash
cd frontend
npm install
npm run dev
```

Application at `http://localhost:5173`.

### Production (DCS cluster)

```bash
./start_server.bash   # Ports 7728 (backend) and 7727 (frontend) with SSL
```

## Project Structure

```
web_application/
  backend/
    app/
      api/          REST endpoint definitions
      core/         Global config (JWT secret, upload dir, ports)
      db/           SQLite database connection and setup
      models/       SQLModel schemas (Job, User, Session)
      services/     Business logic (analysis, files, jobs, auth, video utils)
    main.py         App entry point
    requirements.txt
  frontend/
    src/
      components/   Reusable UI blocks (Uploader, VideoPlayer, Timeline)
      hooks/        Custom logic (useJob, useVideoPlayback, useVideoCanvas)
      pages/        Route views (Home, Upload, Status, Result, Login)
      services/     Axios API wrapper
    package.json
  uploads/          Shared storage ({job_id}/ directories)
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/upload` | Upload road + face videos, returns `job_id` |
| `GET` | `/api/status/{job_id}` | Poll job status and progress percentage |
| `GET` | `/api/result/{job_id}` | Fetch the JSON analysis report |
| `GET` | `/api/list_analyses` | List completed jobs |
| `POST` | `/api/run_test` | Create a demo job with pre-loaded test videos |
| `POST` | `/auth/signup` | Create a new user account |
| `POST` | `/auth/login` | Authenticate and receive JWT |
| `GET` | `/auth/me` | Get current user info |

See [`backend/README.md`](backend/README.md) and [`frontend/README.md`](frontend/README.md) for component-level documentation.
