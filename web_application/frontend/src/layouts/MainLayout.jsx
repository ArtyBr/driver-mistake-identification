import React from 'react';
import { Outlet, Link } from 'react-router-dom';

const MainLayout = () => {
  return (
    <div className="d-flex flex-column min-vh-100">
      <header>
        <nav className="navbar navbar-expand-lg navbar-cyber">
          <div className="container">
            <Link className="navbar-brand" to="/">SafeDrive AI</Link>
            <button className="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
              <span className="navbar-toggler-icon" style={{ filter: 'invert(1)' }}></span>
            </button>
            <div className="collapse navbar-collapse" id="navbarNav">
              <ul className="navbar-nav ms-auto">
                <li className="nav-item">
                  <Link className="nav-link" to="/">HOME</Link>
                </li>
                <li className="nav-item">
                  <Link className="nav-link" to="/record">RECORD DRIVE</Link>
                </li>
                <li className="nav-item">
                  <Link className="nav-link" to="/analyze">ANALYZE PREVIOUS</Link>
                </li>
              </ul>
            </div>
          </div>
        </nav>
      </header>

      <main className="flex-grow-1 py-4">
        <div className="container app-container">
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
