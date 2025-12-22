import React from 'react';
import { Link } from 'react-router-dom';

const Home = () => {
  return (
    <div className="container text-center mt-5">
      <div className="row justify-content-center">
        <div className="col-lg-8">
          <h1 className="display-4 fw-bold mb-4">Driver Safety Analysis</h1>
          <p className="lead mb-5 text-secondary">
            Advanced AI-powered system to detect and identify driver mistakes and safety violations from dashcam footage.
            Ensure road safety with our state-of-the-art video analysis.
          </p>
          
          <div className="row g-4 py-4 row-cols-1 row-cols-lg-3">
            <div className="col">
              <div className="card h-100 border-0 shadow-sm">
                <div className="card-body">
                  <h5 className="card-title">Lane Detection</h5>
                  <p className="card-text text-muted">Accurate tracking of lane deviations and unsafe lane changes.</p>
                </div>
              </div>
            </div>
            <div className="col">
              <div className="card h-100 border-0 shadow-sm">
                <div className="card-body">
                  <h5 className="card-title">Face Monitoring</h5>
                  <p className="card-text text-muted">Detects driver distraction, fatigue, and gaze direction.</p>
                </div>
              </div>
            </div>
            <div className="col">
              <div className="card h-100 border-0 shadow-sm">
                <div className="card-body">
                  <h5 className="card-title">Safety Scoring</h5>
                  <p className="card-text text-muted">Comprehensive safety report with actionable insights.</p>
                </div>
              </div>
            </div>
          </div>

          <Link to="/analyze" className="btn btn-primary btn-lg px-5 mt-4">
            Start Analysis
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Home;
