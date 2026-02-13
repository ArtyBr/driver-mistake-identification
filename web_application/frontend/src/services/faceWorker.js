import * as ort from 'onnxruntime-web';

ort.env.wasm.wasmPaths = '/wasm/';
ort.env.wasm.numThreads = 1; // Disabled multi-threading to avoid COOP/COEP issues
ort.env.wasm.simd = true;
ort.env.webgl.pack = false; 

let session = null;
let inputSize = 640;
let anchors = [];

const generateAnchors = (size) => {
  const strides = [8, 16, 32];
  const anchors = [];
  strides.forEach(stride => {
    const gridHeight = size / stride;
    const gridWidth = size / stride;
    for (let y = 0; y < gridHeight; y++) {
      for (let x = 0; x < gridWidth; x++) {
        for (let k = 0; k < 2; k++) {
          anchors.push({ x, y, stride });
        }
      }
    }
  });
  return anchors;
};

const calculateIOU = (box1, box2) => {
  const x1 = Math.max(box1[0], box2[0]);
  const y1 = Math.max(box1[1], box2[1]);
  const x2 = Math.min(box1[2], box2[2]);
  const y2 = Math.min(box1[3], box2[3]);
  const intersection = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
  const area1 = (box1[2] - box1[0]) * (box1[3] - box1[1]);
  const area2 = (box2[2] - box2[0]) * (box2[3] - box2[1]);
  return intersection / (area1 + area2 - intersection);
};

const nms = (boxes, scores, iouThreshold) => {
  const detections = boxes.map((box, index) => ({ box, score: scores[index], index }));
  detections.sort((a, b) => b.score - a.score);
  const selected = [];
  while (detections.length > 0) {
    const best = detections.shift();
    selected.push(best);
    for (let i = detections.length - 1; i >= 0; i--) {
      if (calculateIOU(best.box, detections[i].box) > iouThreshold) {
        detections.splice(i, 1);
      }
    }
  }
  return selected;
};

const estimatePose = (kps) => {
  const leftEye = kps[0];
  const rightEye = kps[1];
  const nose = kps[2];
  const dx = rightEye.x - leftEye.x;
  const dy = rightEye.y - leftEye.y;
  const dist = Math.sqrt(dx * dx + dy * dy);
  const yaw = ((nose.x - (leftEye.x + rightEye.x) / 2) / dist) * 45;
  const pitch = ((nose.y - (leftEye.y + rightEye.y) / 2) / dist) * 45;
  const roll = Math.atan2(dy, dx) * 180 / Math.PI;
  return { yaw, pitch, roll };
};

self.onmessage = async (e) => {
  const { type, data } = e.data;

  if (type === 'load') {
    try {
      console.log('[Worker] Starting model load from:', data.modelPath);
      const startTime = performance.now();
      
      const options = {
        executionProviders: ['webgpu', 'wasm'],
        graphOptimizationLevel: 'all',
      };
      
      session = await ort.InferenceSession.create(data.modelPath, options);
      
      const loadTime = performance.now() - startTime;
      console.log(`[Worker] Model loaded in ${Math.round(loadTime)}ms. Backend used:`, session.handler?.backend || 'unknown');
      
      anchors = generateAnchors(inputSize);
      self.postMessage({ type: 'loaded' });
    } catch (err) {
      console.error('[Worker] Load Failed:', err);
      self.postMessage({ type: 'error', error: err.message });
    }
  }

  if (type === 'analyze') {
    if (!session) return;
    
    const { imageData, videoWidth, videoHeight } = data;
    const input = new Float32Array(inputSize * inputSize * 3);
    const area = inputSize * inputSize;
    
    // BGR normalization
    for (let i = 0; i < area; i++) {
      const i4 = i << 2;
      input[i] = (imageData[i4 + 2] - 127.5) * 0.0078125;
      input[i + area] = (imageData[i4 + 1] - 127.5) * 0.0078125;
      input[i + 2 * area] = (imageData[i4] - 127.5) * 0.0078125;
    }

    const inputTensor = new ort.Tensor('float32', input, [1, 3, inputSize, inputSize]);

    try {
      const results = await session.run({ [session.inputNames[0]]: inputTensor });
      
      const allDetections = [];
      const strides = [8, 16, 32];
      let anchorIdx = 0;

      for (let s = 0; s < strides.length; s++) {
        const stride = strides[s];
        const scoreData = results[`score_${stride}`].data;
        const bboxData = results[`bbox_${stride}`].data;
        const kpsData = results[`kps_${stride}`].data;

        for (let i = 0; i < scoreData.length; i++) {
          const score = scoreData[i];
          if (score > 0.5) {
            const anchor = anchors[anchorIdx + i];
            const scaleX = videoWidth / inputSize;
            const scaleY = videoHeight / inputSize;

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

      const selected = nms(allDetections.map(d => d.bbox), allDetections.map(d => d.score), 0.45);
      const faces = selected.map(sel => {
        const face = allDetections[sel.index];
        return { ...face, pose: estimatePose(face.landmarks) };
      });

      self.postMessage({ type: 'result', faces });
    } catch (err) {
      self.postMessage({ type: 'error', error: err.message });
    }
  }
};
