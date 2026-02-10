import React from 'react';
import './Legend.css';

const Legend = () => {
  return (
    <div className="timeline-legend">
      <div className="legend-row">
	
        <span className="legend-title">Events:</span>
        {[
          { label: 'Unsafe', color: '#dc3545' },
          { label: 'Safe', color: '#20c997' },
        ].map((item, i) => (
          <div key={i} className="legend-item">
            <span className="legend-swatch" style={{ backgroundColor: item.color }}></span>
            <span className="legend-label">{item.label}</span>
          </div>
        ))}
      </div>
      <div className="legend-row">
        <span className="legend-title">Gaze:</span>
        {[
          { label: 'Looking Ahead', color: '#20c997' },
          { label: 'Left Mirror', color: '#6f42c1' },
          { label: 'Right Mirror', color: '#0ffc10' },
          { label: 'Rear Mirror', color: '#ffc107' },
        ].map((item, i) => (
          <div key={i} className="legend-item">
            <span className="legend-swatch" style={{ backgroundColor: item.color }}></span>
            <span className="legend-label">{item.label}</span>
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
