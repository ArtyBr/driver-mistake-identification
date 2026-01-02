import React from 'react';
import { Link } from 'react-router-dom';

const Home = () => {
  return (
    <div className="container text-center mt-5">
      <div className="row justify-content-center">
        <div className="col-lg-8">
          <h1 className="display-4 fw-bold mb-4 page-title">Driver Safety Analysis</h1>
          <p className="lead mb-5 page-subtitle">
            Advanced AI-powered system to detect and identify driver mistakes and safety violations from dashcam footage.
            Ensure road safety with our state-of-the-art video analysis.
          </p>
          
          <div className="row g-4 py-4 row-cols-1 row-cols-lg-3">
            <div className="col">
              <div className="card-cyber h-100 shadow-sm">
                <div className="card-body">
                  <h5 className="card-title text-white">Lane Detection</h5>
                  <hr />
                  <p className="card-text text-white">Accurate tracking of lane deviations and unsafe lane changes.</p>
                </div>
              </div>
            </div>
            <div className="col">
              <div className="card-cyber h-100 shadow-sm">
                <div className="card-body">
                  <h5 className="card-title text-white">Face Monitoring</h5>
                  <hr />
                  <p className="card-text text-white">Detects driver distraction, fatigue, and gaze direction.</p>
                </div>
              </div>
            </div>
            <div className="col">
              <div className="card-cyber h-100 shadow-sm">
                <div className="card-body">
                  <h5 className="card-title text-white">Safety Scoring</h5>
                  <hr />
                  <p className="card-text text-white">Comprehensive safety report with actionable insights.</p>
                </div>
              </div>
            </div>
          </div>

          <Link to="/analyze" className="btn btn-cyber-primary btn-lg px-5 mt-4">
            START ANALYSIS
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Home;
