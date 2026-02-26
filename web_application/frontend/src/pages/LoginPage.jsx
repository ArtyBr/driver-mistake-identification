import React, { useState } from 'react';
import { useNavigate, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const LoginPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from?.pathname || "/";

  // Real-time validation
  const isEmailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!isEmailValid) {
      setError('Please enter a valid email address.');
      return;
    }

    setIsLoading(true);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="row justify-content-center align-items-center" style={{ minHeight: '70vh' }}>
      <div className="col-md-6 col-lg-5">
        <div className="card card-cyber shadow-lg">
          <div className="card-header text-center">
            <h4>Login to SafeDrive</h4>
            <p className="text-muted small mb-0">Access your personalized driving analysis</p>
          </div>
          <div className="card-body">
            {error && (
              <div className="alert alert-cyber-danger py-2 text-center mb-4">
                <i className="bi bi-exclamation-triangle-fill me-2"></i>
                {error}
              </div>
            )}
            
            <form onSubmit={handleSubmit}>
              <div className="mb-3">
                <label htmlFor="email" className="form-label text-muted d-flex justify-content-between">
                  Email Address
                  {email && !isEmailValid && (
                    <span className="small text-danger">Invalid format</span>
                  )}
                </label>
                <div className="input-group">
                  <span className="input-group-text">
                    <i className="bi bi-envelope"></i>
                  </span>
                  <input
                    id="email"
                    type="email"
                    className={`form-control ${email && !isEmailValid ? 'border-danger' : ''}`}
                    placeholder="name@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
              </div>
              
              <div className="mb-4">
                <label htmlFor="password" name="password" className="form-label text-muted">Password</label>
                <div className="input-group">
                  <span className="input-group-text">
                    <i className="bi bi-lock"></i>
                  </span>
                  <input
                    id="password"
                    type="password"
                    className="form-control"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
              </div>
              
              <button 
                type="submit" 
                className="btn btn-cyber-primary w-100 py-2 fw-bold" 
                disabled={isLoading || (email && !isEmailValid)}
              >
                {isLoading ? (
                  <>
                    <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                    LOGGING IN...
                  </>
                ) : (
                  'LOGIN'
                )}
              </button>
            </form>
          </div>
          <div className="card-footer bg-transparent border-color-muted text-center py-3">
            <p className="text-muted mb-0">
              Don't have an account? <Link to="/signup" className="text-accent-primary fw-bold text-decoration-none">SIGN UP</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
