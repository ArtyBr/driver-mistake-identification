import { useMemo } from 'react';

export function useVideoAnalysisData(results) {
  // Process frame_data in a single pass to generate both history and faceSegments
  const { history, faceSegments } = useMemo(() => {
    const hist = [];
    const segments = [];
    let lastState = null;
    let currentSegment = null;

    if (results && results.frame_data) {
      results.frame_data.forEach(frame => {
        const state = frame.current_state;
        
        // Handle face segments and history transitions
        if (state && state !== "N/A" && state !== "Unknown") {
          // 1. History (Transitions)
          if (lastState === null) {
            hist.push({ from: "Start", to: state, time: frame.time });
            lastState = state;
          } else if (state !== lastState) {
            hist.push({ from: lastState, to: state, time: frame.time });
            lastState = state;
          }

          // 2. Face Segments (Blocks of same state)
          if (!currentSegment) {
            currentSegment = { state, startTime: frame.time, endTime: frame.time };
          } else if (currentSegment.state !== state) {
            segments.push(currentSegment);
            currentSegment = { state, startTime: frame.time, endTime: frame.time };
          } else {
            currentSegment.endTime = frame.time;
          }
        } else {
          // State is N/A or Unknown
          if (currentSegment) {
            segments.push(currentSegment);
            currentSegment = null;
          }
        }
      });

      // Final cleanup
      if (currentSegment) {
        segments.push(currentSegment);
      }
    }

    return { history: hist, faceSegments: segments };
  }, [results]);

  return { history, faceSegments };
}
