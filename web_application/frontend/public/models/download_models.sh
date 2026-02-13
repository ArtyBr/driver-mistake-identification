#!/bin/bash
# Download SCRFD 500m
curl -L https://github.com/yakhyo/face-reidentification/releases/download/v1.0/det_500m.onnx -o scrfd_500m.onnx
# Download W600K R50 (ArcFace / Landmarks)
curl -L https://github.com/yakhyo/face-reidentification/releases/download/v1.0/w600k_r50.onnx -o w600k_r50.onnx
