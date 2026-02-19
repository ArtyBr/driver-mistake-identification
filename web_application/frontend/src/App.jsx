import { Routes, Route } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import Home from './pages/Home';
import UploadPage from './pages/UploadPage';
import StatusPage from './pages/StatusPage';
import ResultPage from './pages/ResultPage';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import ProtectedRoute from './components/ProtectedRoute';
import './App.css'; // Global styles (VideoPlayer styles etc)

function App() {
  return (
    <Routes>
      <Route path="/" element={<MainLayout />}>
        <Route index element={<Home />} />
        <Route path="analyze" element={
          <ProtectedRoute>
            <UploadPage />
          </ProtectedRoute>
        } />
        <Route path="status/:jobId" element={<StatusPage />} />
        <Route path="results/:jobId" element={<ResultPage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="signup" element={<SignupPage />} />
        {/* Fallback for unknown routes */}
        <Route path="*" element={<Home />} />
      </Route>
    </Routes>
  );
}

export default App;
