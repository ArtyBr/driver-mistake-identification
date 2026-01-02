#!/bin/bash
export PATH="/home/arty/apps/miniconda3/envs/lane_detection/bin:$PATH"
export PYTHONPATH=$PYTHONPATH:.

# Kill existing process if pid file exists
if [ -f server.pid ]; then
    kill $(cat server.pid) 2>/dev/null
    rm server.pid
fi

nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 600 > server.log 2>&1 &
echo $! > server.pid
echo "Server started with PID $(cat server.pid)"
