import * as ort from 'onnxruntime-web';

// Tell ONNX Runtime where to find the .wasm files
ort.env.wasm.wasmPaths = '/wasm/';
ort.env.webgl.pack = false; // Important for Resize op

class FaceAnalysisService {
  constructor() {
    this.session = null;
    this.isLoaded = false;
    this.inputSize = 640;
    this.strides = [8, 16, 32];
    this.numAnchors = 2;
    this.anchors = this.generateAnchors();
    
    this.offscreenCanvas = document.createElement('canvas');
    this.offscreenCanvas.width = this.inputSize;
    this.offscreenCanvas.height = this.inputSize;
    this.offscreenCtx = this.offscreenCanvas.getContext('2d', { willReadFrequently: true });
  }

  generateAnchors() {
    const anchors = [];
    this.strides.forEach(stride => {
      const gridHeight = this.inputSize / stride;
      const gridWidth = this.inputSize / stride;
      for (let y = 0; y < gridHeight; y++) {
        for (let x = 0; x < gridWidth; x++) {
          for (let k = 0; k < 2; k++) {
            anchors.push({ x, y, stride });
          }
        }
      }
    });
    return anchors;
  }

  async loadModels() {
    if (this.isLoaded) return;
    console.log('[FaceAnalysisService] Loading models (WebGPU > WASM)...');

    try {
      const options = {
        executionProviders: ['webgpu', 'wasm'],
        graphOptimizationLevel: 'all',
      };

      this.session = await ort.InferenceSession.create('/models/scrfd_500m.onnx', options);
      this.isLoaded = true;
      console.log('[FaceAnalysisService] Models loaded. Backend:', this.session.handler?.backend || 'unknown');
    } catch (error) {
      console.error('[FaceAnalysisService] Load failed:', error);
      throw error;
    }
  }

  // Helper: Intersection Over Union
  calculateIOU(box1, box2) {
    const x1 = Math.max(box1[0], box2[0]);
    const y1 = Math.max(box1[1], box2[1]);
    const x2 = Math.min(box1[2], box2[2]);
    const y2 = Math.min(box1[3], box2[3]);
    const intersectionArea = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
    const box1Area = (box1[2] - box1[0]) * (box1[3] - box1[1]);
    const box2Area = (box2[2] - box2[0]) * (box2[3] - box2[1]);
    return intersectionArea / (box1Area + box2Area - intersectionArea);
  }

  nms(boxes, scores, iouThreshold) {
    const detections = boxes.map((box, index) => ({ box, score: scores[index], index }));
    detections.sort((a, b) => b.score - a.score);
    const selected = [];
    while (detections.length > 0) {
      const best = detections.shift();
      selected.push(best);
      for (let i = detections.length - 1; i >= 0; i--) {
        if (this.calculateIOU(best.box, detections[i].box) > iouThreshold) {
          detections.splice(i, 1);
        }
      }
    }
    return selected;
  }

  estimatePose(kps) {
    const leftEye = kps[0];
    const rightEye = kps[1];
    const nose = kps[2];
    const dx = rightEye.x - leftEye.x;
    const dy = rightEye.y - leftEye.y;
    const eyeDist = Math.sqrt(dx * dx + dy * dy);
    const eyeCenter = { x: (leftEye.x + rightEye.x) / 2, y: (leftEye.y + rightEye.y) / 2 };
    const yaw = ((nose.x - eyeCenter.x) / eyeDist) * 100;
    const pitch = ((nose.y - eyeCenter.y) / eyeDist - 0.4) * 100;
    const roll = Math.atan2(dy, dx) * 180 / Math.PI;
    return { yaw, pitch, roll };
  }

  async analyze(videoElement) {
    if (!this.isLoaded) return null;

    const videoWidth = videoElement.videoWidth;
    const videoHeight = videoElement.videoHeight;

    this.offscreenCtx.drawImage(videoElement, 0, 0, this.inputSize, this.inputSize);
    const imageData = this.offscreenCtx.getImageData(0, 0, this.inputSize, this.inputSize).data;

    const input = new Float32Array(this.inputSize * this.inputSize * 3);
    const area = this.inputSize * this.inputSize;
    for (let i = 0; i < area; i++) {
      const i4 = i << 2;
      input[i] = (imageData[i4 + 2] - 127.5) * 0.0078125;
      input[i + area] = (imageData[i4 + 1] - 127.5) * 0.0078125;
      input[i + 2 * area] = (imageData[i4] - 127.5) * 0.0078125;
    }

    const inputTensor = new ort.Tensor('float32', input, [1, 3, this.inputSize, this.inputSize]);

    try {
      const results = await this.session.run({ [this.session.inputNames[0]]: inputTensor });
      
      const allDetections = [];
      let anchorIdx = 0;

      for (let s = 0; s < this.strides.length; s++) {
        const stride = this.strides[s];
        const scoreData = results[`score_${stride}`].data;
        const bboxData = results[`bbox_${stride}`].data;
        const kpsData = results[`kps_${stride}`].data;

        for (let i = 0; i < scoreData.length; i++) {
          const score = scoreData[i];
          if (score > 0.5) {
            const anchor = this.anchors[anchorIdx + i];
            const scaleX = videoWidth / this.inputSize;
            const scaleY = videoHeight / this.inputSize;

            const x1 = (anchor.x * stride - bboxData[i * 4] * stride) * scaleX;
            const y1 = (anchor.y * stride - bboxData[i * 4 + 1] * stride) * scaleY;
            const x2 = (anchor.x * stride + bboxData[i * 4 + 2] * stride) * scaleX;
            const y2 = (anchor.y * stride + bboxData[i * 4 + 3] * stride) * scaleY;

            const landmarks = [];
            for (let k = 0; k < 5; k++) {
              landmarks.push({
                x: (anchor.x * stride + kpsData[i * 10 + k * 2] * stride) * scaleX,
                y: (anchor.y * stride + kpsData[i * 10 + k * 2 + 1] * stride) * scaleY
              });
            }
            allDetections.push({ bbox: [x1, y1, x2, y2], score, landmarks });
          }
        }
        anchorIdx += scoreData.length;
      }

      const selected = this.nms(allDetections.map(d => d.bbox), allDetections.map(d => d.score), 0.45);
      const faces = selected.map(sel => {
        const face = allDetections[sel.index];
        return { ...face, pose: this.estimatePose(face.landmarks) };
      });

      return { faces };
    } catch (err) {
      console.error('[FaceAnalysisService] Analysis failed:', err);
      return null;
    }
  }
}

export const faceAnalysisService = new FaceAnalysisService();
