# Technology Stack

## Core Technologies
- **Programming Language:** Python 3.9+, JavaScript
- **Backend Framework:** FastAPI (Python)
- **Frontend Framework:** React (Vite)
- **Database:** SQLite (via SQLModel)
- **Computer Vision:** OpenCV, PyTorch, InsightFace
- **Styling:** Bootstrap

## Infrastructure & Deployment
- **Web Server Host:** `wagtail.dcs.warwick.ac.uk` (User: `safedrive`)
- **Public URL:** `safedrive.dcs.warwick.ac.uk`
- **Compute Server:** `kudu-taught` (Accessed via jump host `remote-49`)
- **Large Storage:** `/dcs/large/safedrive_cs310_2526/`
- **Orchestration:** `start_server.bash` (Auto-runs on server restart)

## Port Configuration
- **7727:** Frontend (Webpage)
- **7728:** Backend Server
- **7729:** Available

## Workflows
- **Batch Processing (Goal):** Future implementation will utilize `sbatch` scripts on `kudu-taught` for heavy headless analysis, offloading work from the web server.
