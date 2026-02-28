import { Routes, Route } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import Home from './pages/Home';
import UploadPage from './pages/UploadPage';
import StatusPage from './pages/StatusPage';
import ResultPage from './pages/ResultPage';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import VerifyEmailPage from './pages/VerifyEmailPage';
import ProtectedRoute from './components/ProtectedRoute';
import VerifiedRoute from './components/VerifiedRoute';
import AdminRoute from './components/AdminRoute';
import AdminDashboard from './pages/AdminDashboard';
import CalibrationPage from './pages/CalibrationPage';
import GuidePage from './pages/GuidePage';
import './App.css'; // Global styles (VideoPlayer styles etc)

function App() {
  return (
    <Routes>
      <Route path="/" element={<MainLayout />}>
        <Route index element={<Home />} />
        <Route path="analyze" element={
          <VerifiedRoute>
            <UploadPage />
          </VerifiedRoute>
        } />
        <Route path="calibrate" element={
          <VerifiedRoute>
            <CalibrationPage />
          </VerifiedRoute>
        } />
        <Route path="job/:jobId" element={<StatusPage />} />
        <Route path="view/:jobId" element={<ResultPage />} />
        <Route path="dashboard" element={
          <AdminRoute>
            <AdminDashboard />
          </AdminRoute>
        } />
        <Route path="guide" element={<GuidePage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="signup" element={<SignupPage />} />
        <Route path="verify-email" element={<VerifyEmailPage />} />
        {/* Fallback for unknown routes */}
        <Route path="*" element={<Home />} />
      </Route>
    </Routes>
  );
}

export default App;
