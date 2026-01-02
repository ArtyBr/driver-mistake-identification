import React, { useState } from 'react';
import FileDropZone from '../common/FileDropZone';

const MissingVideosUploader = ({ roadMeta, faceMeta, results, onFilesUploaded }) => {
  const [roadFiles, setRoadFiles] = useState([]);
  const [faceFiles, setFaceFiles] = useState([]);
  const [errors, setErrors] = useState([]);

  // Derive expected info from results if DB meta is missing
  const effectiveRoadMeta = roadMeta || results?.meta?.road_metadata || (results?.meta?.road_file ? {
      filenames: [results.meta.road_file],
      count: 1
  } : null);

  const effectiveFaceMeta = faceMeta || results?.meta?.face_metadata || (results?.meta?.face_file ? {
      filenames: [results.meta.face_file],
      count: 1
  } : null);

  const validateFiles = (files, meta, type) => {
    // If we have metadata, we can do strict validation
    if (meta && meta.count > 0) {
      if (files.length !== meta.count) {
        return { 
          valid: false, 
          errors: [`${type.toUpperCase()}: Expected ${meta.count} video(s), but you selected ${files.length}.`] 
        };
      }

      const currentErrors = [];
      const matchedFiles = [];
      const fileMap = new Map();
      files.forEach(f => fileMap.set(f.name, f));

      meta.filenames.forEach((expectedName, index) => {
        const file = fileMap.get(expectedName);
        if (!file) {
          currentErrors.push(`${type.toUpperCase()}: Missing file "${expectedName}"`);
        } else {
          if (meta.sizes && meta.sizes[index]) {
              const expectedSize = meta.sizes[index];
              if (Math.abs(file.size - expectedSize) > 1024) {
                  currentErrors.push(`${type.toUpperCase()}: File "${expectedName}" size mismatch. Expected ~${(expectedSize/1024/1024).toFixed(2)}MB, got ${(file.size/1024/1024).toFixed(2)}MB.`);
              }
          }
          matchedFiles[index] = file;
        }
      });

      if (currentErrors.length > 0) {
        return { valid: false, errors: currentErrors };
      }
      return { valid: true, files: matchedFiles };
    }

    // If metadata is missing (legacy jobs), just ensure at least one file is picked
    if (files.length === 0) {
      return {
        valid: false,
        errors: [`${type.toUpperCase()}: Please select at least one video file.`]
      };
    }

    return { valid: true, files };
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    console.log("Submit clicked. Road files:", roadFiles.length, "Face files:", faceFiles.length);
    setErrors([]);

    const roadResult = validateFiles(roadFiles, effectiveRoadMeta, 'road');
    const faceResult = validateFiles(faceFiles, effectiveFaceMeta, 'face');

    const allErrors = [];
    if (!roadResult.valid) allErrors.push(...roadResult.errors);
    if (!faceResult.valid) allErrors.push(...faceResult.errors);

    console.log("Validation results. Errors found:", allErrors.length);

    if (allErrors.length > 0) {
      setErrors(allErrors);
      return;
    }

    console.log("Validation successful. Calling onFilesUploaded...");
    onFilesUploaded(roadResult.files, faceResult.files);
  };

  return (
    <div className="card-cyber mb-4">
      <div className="card-header">
        <h4 className="mb-0">Videos Missing from Server</h4>
      </div>
      <div className="card-body">
        <p className="text-muted mb-4">
          The video files for this analysis were deleted from the server to save space. 
          To view the results, please select the original files from your computer.
        </p>

        <form onSubmit={handleSubmit}>
          <div className="row">
            <div className="col-md-6">
              <FileDropZone 
                label={`Road Videos (${effectiveRoadMeta?.count || 'Any'} expected)`}
                files={roadFiles}
                setFiles={setRoadFiles}
                accept="video/*"
                multiple={true}
                helperText={effectiveRoadMeta ? `Expected: ${effectiveRoadMeta.filenames.join(', ')}` : "Select the original road video(s)."}
              />
            </div>
            <div className="col-md-6">
              <FileDropZone 
                label={`Face Videos (${effectiveFaceMeta?.count || 'Any'} expected)`}
                files={faceFiles}
                setFiles={setFaceFiles}
                accept="video/*"
                multiple={true}
                helperText={effectiveFaceMeta ? `Expected: ${effectiveFaceMeta.filenames.join(', ')}` : "Select the original face video(s)."}
              />
            </div>
          </div>

          {errors.length > 0 && (
            <div className="alert alert-cyber alert-cyber-danger mt-2 mb-4">
              <h5 className="alert-heading" style={{ fontSize: '1rem' }}>Selection Errors:</h5>
              <ul className="mb-0 ps-3">
                {errors.map((err, idx) => <li key={idx} style={{ fontSize: '0.9rem' }}>{err}</li>)}
              </ul>
            </div>
          )}

          <button type="submit" className="btn btn-cyber-primary w-100">
            LOAD VIDEOS LOCALLY
          </button>
        </form>
      </div>
    </div>
  );
};

export default MissingVideosUploader;