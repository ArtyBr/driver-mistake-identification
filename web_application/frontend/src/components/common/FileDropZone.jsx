import React, { useState, useRef } from 'react';
import './FileDropZone.css';

const FileDropZone = ({ label, files, setFiles, accept, helperText, multiple = false }) => {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      if (multiple) {
        // Convert FileList to Array and sort by name to ensure order if user relies on naming
        const newFiles = Array.from(e.dataTransfer.files).sort((a, b) => a.name.localeCompare(b.name));
        setFiles(newFiles);
      } else {
        setFiles([e.dataTransfer.files[0]]);
      }
    }
  };

  const handleClick = () => {
    inputRef.current.click();
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      if (multiple) {
        const newFiles = Array.from(e.target.files).sort((a, b) => a.name.localeCompare(b.name));
        setFiles(newFiles);
      } else {
        setFiles([e.target.files[0]]);
      }
    }
  };

  return (
    <div className="mb-4">
      <label className="form-label fw-bold" style={{ color: 'var(--text-main)' }}>{label}</label>
      <div
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`dropzone ${isDragging ? 'dragging' : ''}`}
      >
        <input
          type="file"
          ref={inputRef}
          onChange={handleFileChange}
          accept={accept}
          multiple={multiple}
          style={{ display: 'none' }}
        />
        
        {files && files.length > 0 ? (
          <div>
            <div style={{ fontSize: '2em', marginBottom: '10px' }}>📄</div>
            <div style={{ fontWeight: '600' }}>
              {files.length === 1 ? files[0].name : `${files.length} files selected`}
            </div>
            {files.length > 1 && (
                <div className="text-start mt-2 px-3">
                    <ul className="small text-muted mb-0">
                        {files.map((f, i) => <li key={i}>{f.name}</li>)}
                    </ul>
                </div>
            )}
            <div className="text-muted small mt-2">
                (Total: {(files.reduce((acc, f) => acc + f.size, 0) / 1024 / 1024).toFixed(2)} MB)
            </div>
            <div className="text-muted small mt-2">(Click or drag to replace)</div>
          </div>
        ) : (
          <div>
            <div style={{ fontSize: '2em', marginBottom: '10px', color: 'var(--text-muted)' }}>☁️</div>
            <div style={{ fontWeight: '500' }}>Drag & Drop video{multiple ? 's' : ''} here</div>
            <div className="text-muted small mt-1">or click to browse</div>
          </div>
        )}
      </div>
      {helperText && <div className="form-text mt-2">{helperText}</div>}
    </div>
  );
};

export default FileDropZone;
