from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .core.config import UPLOAD_DIR, PROJECT_NAME, VERSION
from .db import database
from .models.job import Job
from .api import routes

app = FastAPI(title=PROJECT_NAME, version=VERSION)

# Initialize Database
database.init_db()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routes
app.include_router(routes.router)

# Mount Static Files
app.mount("/static", StaticFiles(directory=str(UPLOAD_DIR)), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
