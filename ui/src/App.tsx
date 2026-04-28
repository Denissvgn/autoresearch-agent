import { Routes, Route, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import NewResearch from './pages/NewResearch';
import ResearchDetail from './pages/ResearchDetail';
import History from './pages/History';

export default function App() {
  return (
    <div className="min-h-screen">
      <nav className="border-b border-gray-800 px-6 py-3 flex items-center gap-6">
        <Link to="/" className="text-lg font-bold text-indigo-400">
          Autoresearch Agent
        </Link>
        <Link to="/" className="text-sm text-gray-400 hover:text-gray-200">
          Dashboard
        </Link>
        <Link to="/research/new" className="text-sm text-gray-400 hover:text-gray-200">
          New Research
        </Link>
        <Link to="/history" className="text-sm text-gray-400 hover:text-gray-200">
          History
        </Link>
      </nav>
      <main className="p-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/research/new" element={<NewResearch />} />
          <Route path="/research/:id" element={<ResearchDetail />} />
          <Route path="/history" element={<History />} />
        </Routes>
      </main>
    </div>
  );
}
