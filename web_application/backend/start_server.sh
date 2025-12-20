#!/bin/bash
export PATH="/home/arty/apps/miniconda3/envs/lane_detection/bin:$PATH"
nohup python main.py > server.log 2>&1 &
echo $! > server.pid