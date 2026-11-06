import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const SignupPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { signup } = useAuth();

  // Real-time validation helpers
  const isEmailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const isPasswordLong = password.length >= 8;
  const hasCapital = /[A-Z]/.test(password);
  const isPasswordValid = isPasswordLong && hasCapital;
  const passwordsMatch = password === confirmPassword && password !== '';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!isEmailValid) {
      setError('Please fix the email address.');
      return;
    }
    if (!isPasswordValid) {
      setError('Password does not meet requirements.');
      return;
    }
    if (!passwordsMatch) {
      setError('Passwords do not match.');
      return;
    }

    setIsLoading(true);
    try {
      await signup(email, password);
      setSuccess('Account created! Your registration is pending admin approval. You will be able to log in once an administrator verifies your account.');
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
              <div className="alert py-3 text-center mb-4" style={{ 
                backgroundColor: 'rgba(25, 135, 84, 0.15)', 
                borderColor: '#198754',
                color: '#f8f9fa',
                border: '1px solid #198754'
              }}>
                <i className="bi bi-check-circle-fill me-2" style={{ color: '#20c997' }}></i>
                {success}
              </div>
            )}
            
            <form onSubmit={handleSubmit}>
              <div className="mb-3">
                <label htmlFor="email" className="form-label text-muted d-flex justify-content-between">
                  Email Address
                  {email && !isEmailValid && (
                    <span className="small text-danger">Invalid format</span>
                  )}
                  {email && isEmailValid && (
                    <span className="small text-success"><i className="bi bi-check"></i> Valid</span>
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
              
              <div className="mb-3">
                <label htmlFor="password" name="password" className="form-label text-muted">Password</label>
                <div className="input-group">
                  <span className="input-group-text">
                    <i className="bi bi-lock"></i>
                  </span>
                  <input
                    id="password"
                    type="password"
                    className={`form-control ${password && !isPasswordValid ? 'border-danger' : ''}`}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
                {password && !isPasswordValid && (
                  <div className="small mt-1 text-danger">
                    Must be 8+ chars with at least one capital letter.
                  </div>
                )}
                {password && isPasswordValid && (
                  <div className="small mt-1 text-success">
                    <i className="bi bi-check"></i> Password strength OK.
                  </div>
                )}
              </div>

              <div className="mb-4">
                <label htmlFor="confirmPassword" name="confirmPassword" className="form-label text-muted d-flex justify-content-between">
                  Confirm Password
                  {confirmPassword && !passwordsMatch && (
                    <span className="small text-danger">Doesn't match</span>
                  )}
                </label>
                <div className="input-group">
                  <span className="input-group-text">
                    <i className="bi bi-shield-check"></i>
                  </span>
                  <input
                    id="confirmPassword"
                    type="password"
                    className={`form-control ${confirmPassword && !passwordsMatch ? 'border-danger' : ''}`}
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
                disabled={isLoading || (email && !isEmailValid) || (password && !isPasswordValid) || (confirmPassword && !passwordsMatch)}
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
