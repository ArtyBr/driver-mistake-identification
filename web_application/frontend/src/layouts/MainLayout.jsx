import React, { useRef, useEffect } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import CalibrationBanner from '../components/CalibrationBanner';
import VerificationBanner from '../components/VerificationBanner';

const MainLayout = () => {
  const { user, logout } = useAuth();
  const navbarCollapseRef = useRef(null);
  const location = useLocation();

  useEffect(() => {
    const el = navbarCollapseRef.current;
    if (!el) return;
    if (window.bootstrap?.Collapse) {
      window.bootstrap.Collapse.getInstance(el)?.hide();
    } else {
      el.classList.remove('show');
    }
  }, [location.pathname]);

  const handleLogout = () => {
    logout();
    const el = navbarCollapseRef.current;
    if (!el) return;
    if (window.bootstrap?.Collapse) {
      window.bootstrap.Collapse.getInstance(el)?.hide();
    } else {
      el.classList.remove('show');
    }
  };

  return (
    <div className="d-flex flex-column min-vh-100">
      <header>
        <nav className="navbar navbar-expand-lg navbar-dark navbar-cyber">
          <div className="container">
            <Link className="navbar-brand" to="/">SafeDrive AI</Link>
            <button className="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
              <span className="navbar-toggler-icon"></span>
            </button>
            <div className="collapse navbar-collapse" id="navbarNav" ref={navbarCollapseRef}>
              <ul className="navbar-nav me-auto">
                <li className="nav-item">
                  <Link className="nav-link" to="/">HOME</Link>
                </li>
                <li className="nav-item">
                  <Link className="nav-link" to="/analyze">ANALYZE VIDEO</Link>
                </li>
                {user && (
                  <li className="nav-item">
                    <Link className="nav-link" to="/guide">GUIDE</Link>
                  </li>
                )}
                {user?.is_admin && (
                  <li className="nav-item">
                    <Link className="nav-link" to="/dashboard">ADMIN</Link>
                  </li>
                )}
              </ul>

              {/* Mobile-only divider between nav links and user section */}
              <hr className="d-lg-none border-secondary my-1" style={{ opacity: 0.2 }} />

              <ul className="navbar-nav ms-auto align-items-lg-center">
                {user ? (
                  <>
                    {/* Email — nav-link style on mobile, plain text on desktop */}
                    <li className="nav-item d-none d-lg-flex align-items-center me-2">
                      <span className="text-light small" style={{ opacity: 0.65 }}>{user.email}</span>
                    </li>
                    <li className="nav-item d-lg-none">
                      <span className="nav-link small" style={{ cursor: 'default', opacity: 0.5, pointerEvents: 'none' }}>
                        {user.email}
                      </span>
                    </li>

                    {/* Logout — button on desktop, nav-link style on mobile */}
                    <li className="nav-item d-none d-lg-block">
                      <button className="btn btn-cyber btn-sm ms-2" onClick={handleLogout}>
                        LOGOUT
                      </button>
                    </li>
                    <li className="nav-item d-lg-none">
                      <button
                        className="nav-link border-0 bg-transparent text-start w-100"
                        onClick={handleLogout}
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
          <VerificationBanner />
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
