import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const SignupPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { signup } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setIsLoading(true);

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      setIsLoading(false);
      return;
    }

    try {
      await signup(email, password);
      setSuccess('Signup successful! Redirecting to login...');
      setTimeout(() => navigate('/login'), 2000);
    } catch (err) {
      setError(err.message || 'Signup failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="row justify-content-center align-items-center" style={{ minHeight: '75vh' }}>
      <div className="col-md-6 col-lg-5">
        <div className="card card-cyber shadow-lg">
          <div className="card-header text-center">
            <h4>Create SafeDrive Account</h4>
            <p className="text-muted small mb-0">Join our road safety AI community</p>
          </div>
          <div className="card-body">
            {error && (
              <div className="alert alert-cyber-danger py-2 text-center mb-4">
                <i className="bi bi-exclamation-triangle-fill me-2"></i>
                {error}
              </div>
            )}
            {success && (
              <div className="alert alert-success py-2 text-center mb-4" style={{ backgroundColor: 'rgba(25, 135, 84, 0.15)', borderColor: '#198754' }}>
                <i className="bi bi-check-circle-fill me-2"></i>
                {success}
              </div>
            )}
            
            <form onSubmit={handleSubmit}>
              <div className="mb-3">
                <label htmlFor="email" className="form-label text-muted">Email Address</label>
                <div className="input-group">
                  <span className="input-group-text">
                    <i className="bi bi-envelope"></i>
                  </span>
                  <input
                    id="email"
                    type="email"
                    className="form-control"
                    placeholder="name@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
              </div>
              
              <div className="mb-3">
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

              <div className="mb-4">
                <label htmlFor="confirmPassword" name="confirmPassword" className="form-label text-muted">Confirm Password</label>
                <div className="input-group">
                  <span className="input-group-text">
                    <i className="bi bi-shield-check"></i>
                  </span>
                  <input
                    id="confirmPassword"
                    type="password"
                    className="form-control"
                    placeholder="••••••••"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                  />
                </div>
              </div>
              
              <button 
                type="submit" 
                className="btn btn-cyber-primary w-100 py-2 fw-bold" 
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                    CREATING ACCOUNT...
                  </>
                ) : (
                  'SIGN UP'
                )}
              </button>
            </form>
          </div>
          <div className="card-footer bg-transparent border-color-muted text-center py-3">
            <p className="text-muted mb-0">
              Already have an account? <Link to="/login" className="text-accent-primary fw-bold text-decoration-none">LOGIN</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignupPage;
