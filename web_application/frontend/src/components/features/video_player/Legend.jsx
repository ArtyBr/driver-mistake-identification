import React from 'react';
import './Legend.css';
import { GAZE_STATES, EVENT_SEVERITIES } from '../../../constants/videoConstants';

const Legend = () => {
  return (
    <div className="timeline-legend">
      <div className="legend-row">
	
        <span className="legend-title">Events:</span>
        {[
          { label: 'Unsafe', color: EVENT_SEVERITIES.UNSAFE.color },
          { label: 'Safe', color: EVENT_SEVERITIES.SAFE.color },
        ].map((item, i) => (
          <div key={i} className="legend-item">
            <span className="legend-swatch" style={{ backgroundColor: item.color }}></span>
            <span className="legend-label">{item.label}</span>
          </div>
        ))}
      </div>
      <div className="legend-row">
        <span className="legend-title">Gaze:</span>
        {Object.entries(GAZE_STATES).filter(([key]) => key !== 'N/A' && key !== 'Unknown' && key !== 'Start').map(([key, value]) => (
          <div key={key} className="legend-item">
            <span className="legend-swatch" style={{ backgroundColor: value.color }}></span>
            <span className="legend-label">{key}</span>
          </div>
        ))}
      </div>
      <div className="legend-row">
          <span className="legend-title">Video load:</span>
          {[
            { label: 'Buffered', color: 'rgba(255, 255, 255, 0.2)' },
            { label: 'Unbuffered', color: 'rgba(255, 255, 255, 0.05)' }
          ].map((item, i) => (
            <div key={i} className="legend-item">
              <span className="legend-swatch" style={{ backgroundColor: item.color, border: '1px solid #444' }}></span>
              <span className="legend-label">{item.label}</span>
            </div>
          ))}
        </div>
    </div>
  );
};

export default Legend;
