import { useMemo } from 'react';

export function useVideoAnalysisData(results) {
  // Memoize history generation
  const history = useMemo(() => {
    const hist = [];
    let lastState = null;

    if (results && results.frame_data) {
      results.frame_data.forEach(frame => {
        const state = frame.current_state;
        if (state && state !== "N/A" && state !== "Unknown") {
          if (lastState !== null && state !== lastState) {
            hist.push({ from: lastState, to: state, time: frame.time });
          }
          if (lastState === null) {
             hist.push({ from: "Start", to: state, time: frame.time });
             lastState = state;
          } else if (state !== lastState) {
            lastState = state;
          }
        }
      });
    }
    return hist;
  }, [results]);

  // Memoize face segments
  const faceSegments = useMemo(() => {
    const segments = [];
    let currentSegment = null;

    if (results && results.frame_data) {
      results.frame_data.forEach(frame => {
        const state = frame.current_state;
        if (state && state !== "N/A" && state !== "Unknown") {
          if (!currentSegment) {
            currentSegment = { state, startTime: frame.time, endTime: frame.time };
          } else if (currentSegment.state !== state) {
            segments.push(currentSegment);
            currentSegment = { state, startTime: frame.time, endTime: frame.time };
          } else {
            currentSegment.endTime = frame.time;
          }
        } else if (currentSegment) {
            segments.push(currentSegment);
            currentSegment = null;
        }
      });
      if (currentSegment) {
        segments.push(currentSegment);
      }
    }
    return segments;
  }, [results]);

  return { history, faceSegments };
}
