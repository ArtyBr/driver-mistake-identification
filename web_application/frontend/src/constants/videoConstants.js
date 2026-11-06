/**
 * Constants for the Video Player UI and Analysis Visualization.
 */

export const GAZE_STATES = {
  'Looking Ahead': { color: '#00FF88', icon: '↑' },
  'Left Mirror':   { color: '#FF00FF', icon: '←' },
  'Right Mirror':  { color: '#FFFF00', icon: '→' },
  'Rear Mirror':   { color: '#FFFFFF', icon: '↓' },
  'N/A':           { color: '#B0B0B0', icon: '·' },
  'Unknown':       { color: '#B0B0B0', icon: '·' },
  'Start':         { color: '#adb5bd', icon: '◦' }
};

export const EVENT_SEVERITIES = {
  'CRITICAL': { color: '#dc3545', label: 'Critical' },
  'WARNING': { color: '#ffc107', label: 'Warning' },
  'INFO': { color: '#20c997', label: 'Info' },
  'UNSAFE': { color: '#dc3545', label: 'Unsafe' }, // General fallback
  'SAFE': { color: '#20c997', label: 'Safe' }      // General fallback
};

export const VIDEO_DIMENSIONS = {
  ROAD: { width: 1280, height: 720 },
  FACE: { width: 640, height: 480 }
};

/**
 * Helper to get color for a state with fallback.
 */
export const getColorForState = (state) => {
  return GAZE_STATES[state]?.color || GAZE_STATES['Unknown'].color;
};

/**
 * Helper to get icon for a state with fallback.
 */
export const getIconForState = (state) => {
  return GAZE_STATES[state]?.icon || GAZE_STATES['Unknown'].icon;
};

/**
 * Helper to get color for an event severity.
 */
export const getColorForSeverity = (severity) => {
  return EVENT_SEVERITIES[severity]?.color || '#ccc';
};
