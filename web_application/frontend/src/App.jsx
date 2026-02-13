import { Routes, Route } from 'react-router-dom';
import MainLayout from './layouts/MainLayout';
import Home from './pages/Home';
import UploadPage from './pages/UploadPage';
import StatusPage from './pages/StatusPage';
import ResultPage from './pages/ResultPage';
import RecordPage from './pages/RecordPage';
import './App.css'; // Global styles (VideoPlayer styles etc)

function App() {
  return (
    <Routes>
      <Route path="/" element={<MainLayout />}>
        <Route index element={<Home />} />
        <Route path="record" element={<RecordPage />} />
        <Route path="analyze" element={<UploadPage />} />
        <Route path="status/:jobId" element={<StatusPage />} />
        <Route path="results/:jobId" element={<ResultPage />} />
        {/* Fallback for unknown routes */}
        <Route path="*" element={<Home />} />
      </Route>
    </Routes>
  );
}

export default App;
