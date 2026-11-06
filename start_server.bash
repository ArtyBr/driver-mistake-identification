#!/bin/bash

# Configuration
SYSTEM_ROOT="/dcs/project/safedrive"
PROJECT_ROOT="$SYSTEM_ROOT/driver-mistake-identification"
LOG_DIR="$PROJECT_ROOT/logs"
FRONTEND_DIR="$PROJECT_ROOT/web_application/frontend"
BACKEND_DIR="$PROJECT_ROOT/web_application/backend"
# Adjust this to your local conda environment path on the Wagtail server
PYTHON_VENV="/dcs/project/safedrive/driver-mistake-identification/web_application/backend/server_env/bin/activate"

BACKEND_PORT=7728
FRONTEND_PORT=7727

# Setup Environment
export PYTHONPATH=$PROJECT_ROOT:$PYTHONPATH

# Load NVM if available
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

echo ">>> Starting Production Server Deployment"
echo "Date: $(date)"

# 1. Stop existing processes (cleanup)
kill_port() {
    local PORT=$1
    if fuser -n tcp $PORT > /dev/null 2>&1; then
        echo "    Killing process on port $PORT..."
        fuser -k -n tcp $PORT > /dev/null 2>&1
        # Wait loop to ensure port is released
        for i in {1..10}; do
            if ! fuser -n tcp $PORT > /dev/null 2>&1; then
                return 0
            fi
            sleep 0.5
        done
        # If still alive, force kill
        fuser -k -9 -n tcp $PORT > /dev/null 2>&1
    fi
}

echo ">>> Cleaning up old processes..."
kill_port $BACKEND_PORT
kill_port $FRONTEND_PORT

rm -f "$LOG_DIR/backend.pid"
rm -f "$LOG_DIR/frontend.pid"

# 2. Start Backend (FastAPI)
echo ">>> Starting Backend on port $BACKEND_PORT..."
source $PYTHON_VENV
cd "$BACKEND_DIR"
nohup uvicorn app.main:app --host 0.0.0.0 --port $BACKEND_PORT --workers 1 --ssl-keyfile "$SYSTEM_ROOT/key.pem" --ssl-certfile "$SYSTEM_ROOT/cert.pem" > "$LOG_DIR/backend.log" 2>&1 &
echo $! > "$LOG_DIR/backend.pid"

# 3. Start Frontend (Serve Build)
echo ">>> Starting Frontend on port $FRONTEND_PORT..."
cd "$FRONTEND_DIR"

# Build frontend to ensure .env.production is picked up
echo "    Building frontend..."
# We use 'npm install' just in case, though on a stable prod server you might skip it.
npm install > /dev/null 2>&1
npm run build > "$LOG_DIR/frontend_build.log" 2>&1

echo "    Serving frontend..."
# Use 'preview' to serve the 'dist' folder on the specific port
nohup npm run preview -- --host 0.0.0.0 --port $FRONTEND_PORT > "$LOG_DIR/frontend.log" 2>&1 &
echo $! > "$LOG_DIR/frontend.pid"

echo ">>> Deployment Complete"
echo "Backend PID: $(cat $LOG_DIR/backend.pid)"
echo "Frontend PID: $(cat $LOG_DIR/frontend.pid)"