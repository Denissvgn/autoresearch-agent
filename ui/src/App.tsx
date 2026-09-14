// App shell: token gate, hi-fi topbar with theme/density/accent prefs, routes.
import { FormEvent, useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import NewResearch from './pages/NewResearch';
import ResearchDetail from './pages/ResearchDetail';
import History from './pages/History';
import Promote from './pages/Promote';
import Settings from './pages/Settings';
import Leaderboard from './pages/Leaderboard';
import Skills from './pages/Skills';
import { Topbar, useDesignPrefs } from './components/hifi/Topbar';
import { ResearchRealtimeBridge } from './hooks/useResearch';
import { WebSocketProvider } from './hooks/useWebSocket';
import { Icon } from './components/hifi/primitives';
import {
  getAutoresearchApiToken,
  hasBuildTimeAutoresearchApiToken,
  setAutoresearchApiToken,
} from './api/client';

export default function App() {
  const [hasToken, setHasToken] = useState(() => Boolean(getAutoresearchApiToken()));
  const [tokenDraft, setTokenDraft] = useState('');
  const [showToken, setShowToken] = useState(false);
  const { theme, setTheme } = useDesignPrefs();

  function handleTokenSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = tokenDraft.trim();
    if (!token) return;
    setAutoresearchApiToken(token);
    setTokenDraft('');
    setHasToken(true);
  }

  if (!hasToken) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'grid',
          placeItems: 'center',
          padding: 24,
          background: 'var(--bg)',
        }}
      >
        <form onSubmit={handleTokenSubmit} className="card" style={{ width: 360, padding: 24 }}>
          <div className="col gap-1" style={{ marginBottom: 16 }}>
            <span className="label">access</span>
            <h1 className="h2">autoresearch agent</h1>
            <p className="subtle" style={{ marginTop: 4, fontSize: 12 }}>
              Authenticate to unlock the research console.
            </p>
          </div>
          <div className="field" style={{ marginBottom: 12 }}>
            <div className="field__lbl">
              API token
              <span className="grow" />
              <button
                type="button"
                onClick={() => setShowToken(!showToken)}
                className="btn btn--ghost btn--sm"
              >
                <Icon name={showToken ? 'eyeOff' : 'eye'} size={12} />
                {showToken ? 'hide' : 'show'}
              </button>
            </div>
            <input
              className="input mono"
              type={showToken ? 'text' : 'password'}
              value={tokenDraft}
              onChange={(e) => setTokenDraft(e.target.value)}
              autoFocus
              placeholder="bearer_token_…"
            />
            <div className="field__help">
              Retrieved from your workspace orchestrator template or the team settings console.
            </div>
          </div>
          <button type="submit" className="btn btn--solid" style={{ width: '100%', height: 36 }}>
            Unlock
          </button>
          {hasBuildTimeAutoresearchApiToken() && (
            <p className="faint" style={{ fontSize: 11, marginTop: 12 }}>
              A build-time token is configured. Submit any value to proceed.
            </p>
          )}
        </form>
      </div>
    );
  }

  return (
    <WebSocketProvider>
      <ResearchRealtimeBridge />
      <div className="app">
        <Topbar
          theme={theme}
          onToggleTheme={() => setTheme(theme === 'theme-dark' ? 'theme-light' : 'theme-dark')}
        />
        <main className="app__main">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/research/new" element={<NewResearch />} />
            <Route path="/research/:id" element={<ResearchDetail />} />
            <Route path="/research/:id/promote" element={<Promote />} />
            <Route path="/history" element={<History />} />
            <Route path="/leaderboard" element={<Leaderboard />} />
            <Route path="/skills" element={<Skills />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </WebSocketProvider>
  );
}
