import React from 'react';
import { Outlet, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import CalibrationBanner from '../components/CalibrationBanner';

const MainLayout = () => {
  const { user, logout } = useAuth();

  return (
    <div className="d-flex flex-column min-vh-100">
      <header>
        <nav className="navbar navbar-expand-lg navbar-dark navbar-cyber">
          <div className="container">
            <Link className="navbar-brand" to="/">SafeDrive AI</Link>
            <button className="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
              <span className="navbar-toggler-icon"></span>
            </button>
            <div className="collapse navbar-collapse" id="navbarNav">
              <ul className="navbar-nav me-auto">
                <li className="nav-item">
                  <Link className="nav-link" to="/">HOME</Link>
                </li>
                <li className="nav-item">
                  <Link className="nav-link" to="/analyze">ANALYZE VIDEO</Link>
                </li>
                {user && (
                  <li className="nav-item">
                    <Link className="nav-link" to="/calibrate">CALIBRATE</Link>
                  </li>
                )}
              </ul>
              <ul className="navbar-nav ms-auto">
                {user ? (
                  <>
                    <li className="nav-item d-flex align-items-center me-3">
                      <span className="text-light opacity-75 small">{user.email}</span>
                    </li>
                    <li className="nav-item">
                      <button 
                        className="btn btn-cyber btn-sm ms-2" 
                        onClick={logout}
                      >
                        LOGOUT
                      </button>
                    </li>
                  </>
                ) : (
                  <>
                    <li className="nav-item">
                      <Link className="nav-link" to="/login">LOGIN</Link>
                    </li>
                    <li className="nav-item">
                      <Link className="nav-link" to="/signup">SIGN UP</Link>
                    </li>
                  </>
                )}
              </ul>
            </div>
          </div>
        </nav>
      </header>

      <main className="flex-grow-1 py-4">
        <div className="container app-container">
          <CalibrationBanner />
          <Outlet />
        </div>
      </main>

      <footer className="py-3 mt-auto">
        <div className="container text-center text-muted">
          <small>&copy; {new Date().getFullYear()} Driver Mistake Identification System. All rights reserved.</small>
        </div>
      </footer>
    </div>
  );
};

export default MainLayout;
