import time
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .core.config import UPLOAD_DIR, PROJECT_NAME, VERSION
from .db import database
from .models.job import Job
from .api import routes
from .api import calibration_routes
from .api import sync_routes
from .api import admin_routes

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("api_logger")

app = FastAPI(title=PROJECT_NAME, version=VERSION)

# Initialize Database
database.init_db()

# Logging Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    # Allow blob: for media-src to support URL.createObjectURL videos
    response.headers["Content-Security-Policy"] = "default-src 'self' 'unsafe-inline' 'unsafe-eval'; media-src 'self' blob:; img-src 'self' data:; connect-src 'self' https:;"
    return response

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log Request
    logger.info(f"Incoming Request: {request.method} {request.url}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log Response
        logger.info(f"Response: {response.status_code} - Took {process_time:.4f}s")
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"Request Failed: {e} - Took {process_time:.4f}s")
        raise e

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
app.include_router(calibration_routes.router)
app.include_router(sync_routes.router)
app.include_router(admin_routes.router)

# Mount Static Files
app.mount("/static", StaticFiles(directory=str(UPLOAD_DIR)), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
