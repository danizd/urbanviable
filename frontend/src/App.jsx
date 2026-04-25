import { Navigate, Route, Routes } from 'react-router-dom';
import HomePage from './pages/HomePage';
import ScoutingPage from './pages/ScoutingPage';
import HowToUsePage from './pages/HowToUsePage';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/scouting" element={<ScoutingPage />} />
      <Route path="/como-usar" element={<HowToUsePage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}