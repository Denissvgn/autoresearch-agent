import { FormEvent, useState } from 'react';
import { Routes, Route, Link, NavLink } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import NewResearch from './pages/NewResearch';
import ResearchDetail from './pages/ResearchDetail';
import History from './pages/History';
import {
  clearAutoresearchApiToken,
  getAutoresearchApiToken,
  hasBuildTimeAutoresearchApiToken,
  setAutoresearchApiToken,
} from './api/client';

export default function App() {
  const [hasToken, setHasToken] = useState(() => Boolean(getAutoresearchApiToken()));
  const [tokenDraft, setTokenDraft] = useState('');
  const [showToken, setShowToken] = useState(false);

  function handleTokenSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = tokenDraft.trim();
    if (!token) return;
    setAutoresearchApiToken(token);
    setTokenDraft('');
    setHasToken(true);
  }

  function handleClearToken() {
    clearAutoresearchApiToken();
    setHasToken(false);
  }

  if (!hasToken) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <form
          onSubmit={handleTokenSubmit}
          className="w-full max-w-sm border border-gray-800 bg-gray-950 p-6"
        >
          <h1 className="text-lg font-bold text-indigo-400">Autoresearch Agent</h1>
          <div className="mt-6 flex justify-between items-center">
            <label htmlFor="api-token" className="block text-sm text-gray-300">
              API token
            </label>
            <button
              type="button"
              onClick={() => setShowToken(!showToken)}
              className="text-xs text-indigo-400 hover:text-indigo-300"
            >
              {showToken ? 'Hide' : 'Show'}
            </button>
          </div>
          <input
            id="api-token"
            type={showToken ? 'text' : 'password'}
            value={tokenDraft}
            onChange={(event) => setTokenDraft(event.target.value)}
            autoFocus
            className="mt-2 w-full border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-100 outline-none focus:border-indigo-500 font-mono"
            placeholder="bearer_token_..."
          />
          <p className="mt-2 text-xs text-gray-500 leading-relaxed">
            The API token secures internal agent capabilities. Retrieve it from your workspace orchestrator template file or consult the team settings console.
          </p>
          <button
            type="submit"
            className="mt-4 w-full bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-500"
          >
            Unlock
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <nav className="border-b border-gray-800 px-6 py-3 flex items-center gap-6">
        <Link to="/" className="text-base font-bold text-indigo-400 shrink-0">
          Autoresearch
        </Link>
        <div className="flex items-center gap-1">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `px-3 py-1.5 rounded text-sm transition ${isActive ? 'bg-gray-800 text-gray-100' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'}`
            }
          >
            Dashboard
          </NavLink>
          <NavLink
            to="/research/new"
            className={({ isActive }) =>
              `px-3 py-1.5 rounded text-sm transition ${isActive ? 'bg-gray-800 text-gray-100' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'}`
            }
          >
            New Research
          </NavLink>
          <NavLink
            to="/history"
            className={({ isActive }) =>
              `px-3 py-1.5 rounded text-sm transition ${isActive ? 'bg-gray-800 text-gray-100' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'}`
            }
          >
            History
          </NavLink>
        </div>
        {!hasBuildTimeAutoresearchApiToken() && (
          <button
            type="button"
            onClick={handleClearToken}
            className="ml-auto text-xs text-gray-500 hover:text-gray-300 transition"
          >
            Change token
          </button>
        )}
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
