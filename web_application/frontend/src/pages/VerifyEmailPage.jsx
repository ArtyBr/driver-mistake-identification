import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const VerifyEmailPage = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [status, setStatus] = useState('verifying'); // verifying, success, error
  const [message, setMessage] = useState('');
  const { verifyEmail } = useAuth();

  useEffect(() => {
    const performVerification = async () => {
      if (!token) {
        setStatus('error');
        setMessage('No verification token provided.');
        return;
      }

      try {
        const result = await verifyEmail(token);
        setStatus('success');
        setMessage(result.message || 'Email verified successfully!');
      } catch (err) {
        setStatus('error');
        setMessage(err.message || 'Verification failed. The link may be expired.');
      }
    };

    performVerification();
  }, [token, verifyEmail]);

  return (
    <div className="row justify-content-center align-items-center" style={{ minHeight: '75vh' }}>
      <div className="col-md-6 col-lg-5 text-center">
        <div className="card card-cyber shadow-lg p-4">
          <div className="mb-4">
            {status === 'verifying' && (
              <div className="spinner-border text-primary" role="status">
                <span className="visually-hidden">Loading...</span>
              </div>
            )}
            {status === 'success' && (
              <i className="bi bi-check-circle-fill text-success" style={{ fontSize: '4rem' }}></i>
            )}
            {status === 'error' && (
              <i className="bi bi-x-circle-fill text-danger" style={{ fontSize: '4rem' }}></i>
            )}
          </div>

          <h2 className="mb-3">Email Verification</h2>
          <p className="lead mb-4">{message || (status === 'verifying' ? 'Verifying your email...' : '')}</p>

          <div className="d-grid gap-2">
            {status === 'success' && (
              <Link to="/login" className="btn btn-cyber-primary py-2 fw-bold">
                GO TO LOGIN
              </Link>
            )}
            {status === 'error' && (
              <Link to="/signup" className="btn btn-cyber-primary py-2 fw-bold">
                TRY SIGNING UP AGAIN
              </Link>
            )}
            {status === 'verifying' && (
              <button disabled className="btn btn-cyber-primary py-2 fw-bold">
                PLEASE WAIT...
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default VerifyEmailPage;
