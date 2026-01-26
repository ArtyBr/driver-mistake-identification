import React from 'react';
import './Legend.css';

const Legend = () => {
  return (
    <div className="timeline-legend">
      <div className="legend-row">
        <span className="legend-title">Events:</span>
        {[
          { label: 'Critical', color: '#dc3545' },
          { label: 'Warning', color: '#ffc107' },
          { label: 'Safe', color: '#20c997' },
          { label: 'No event', color: '#6c757d' }
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
          { label: 'Right Mirror', color: '#00d2df' },
          { label: 'Other', color: '#ffc107' }
        ].map((item, i) => (
          <div key={i} className="legend-item">
            <span className="legend-swatch" style={{ backgroundColor: item.color }}></span>
            <span className="legend-label">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Legend;
