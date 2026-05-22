// Settings — appearance prefs (theme/accent/density), API token management.
// Wired to local design prefs in `Topbar` hook plus existing token API.
import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AccentName,
  DensityName,
  ThemeName,
  useDesignPrefs,
} from '../components/hifi/Topbar';
import { Field, Icon, Segmented } from '../components/hifi/primitives';
import {
  clearAutoresearchApiToken,
  getAutoresearchApiToken,
  hasBuildTimeAutoresearchApiToken,
  setAutoresearchApiToken,
} from '../api/client';

const ACCENTS: { id: AccentName; label: string; swatch: string }[] = [
  { id: 'accent-mono', label: 'mono', swatch: 'var(--fg)' },
  { id: 'accent-ember', label: 'ember', swatch: 'oklch(0.78 0.15 70)' },
  { id: 'accent-cobalt', label: 'cobalt', swatch: 'oklch(0.66 0.15 250)' },
  { id: 'accent-lime', label: 'lime', swatch: 'oklch(0.84 0.18 130)' },
];

export default function Settings() {
  const { theme, setTheme, density, setDensity, accent, setAccent } = useDesignPrefs();
  const [tokenDraft, setTokenDraft] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const tokenSet = Boolean(getAutoresearchApiToken());
  const tokenBuildTime = hasBuildTimeAutoresearchApiToken();

  function saveToken(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!tokenDraft.trim()) return;
    setAutoresearchApiToken(tokenDraft.trim());
    setTokenDraft('');
    setSavedAt(new Date().toLocaleTimeString());
  }

  function clearToken() {
    if (!confirm('Clear the stored API token? You will need to re-enter it on next load.')) return;
    clearAutoresearchApiToken();
    setSavedAt(null);
  }

  return (
    <div style={{ display: 'grid', placeItems: 'start center', padding: '32px 24px' }}>
      <div style={{ width: 760, display: 'flex', flexDirection: 'column', gap: 20 }}>
        <div className="col gap-1">
          <div className="crumb">
            <Link to="/">Dashboard</Link>
            <Icon name="chevR" size={12} />
            <span>Settings</span>
          </div>
          <h1 className="h1">Settings</h1>
          <p className="subtle" style={{ fontSize: 12, maxWidth: 540 }}>
            Workspace-scoped preferences for this browser. Theme, density and accent are stored
            locally; token controls workspace-wide API access.
          </p>
        </div>

        {/* Appearance */}
        <section className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 18 }}>
          <div className="col gap-1">
            <span className="label">appearance</span>
            <h2 className="h2">Theme & density</h2>
          </div>
          <Field label="Theme">
            <Segmented
              value={theme}
              onChange={(v) => setTheme(v as ThemeName)}
              options={[
                { value: 'theme-dark', label: 'dark' },
                { value: 'theme-light', label: 'light' },
              ]}
            />
          </Field>
          <Field label="Density">
            <Segmented
              value={density}
              onChange={(v) => setDensity(v as DensityName)}
              options={[
                { value: 'density-comfortable', label: 'comfortable' },
                { value: 'density-compact', label: 'compact' },
              ]}
            />
          </Field>
          <Field label="Accent">
            <div className="row gap-2">
              {ACCENTS.map((a) => {
                const on = accent === a.id;
                return (
                  <button
                    type="button"
                    key={a.id}
                    onClick={() => setAccent(a.id)}
                    className="card"
                    style={{
                      padding: '8px 14px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      cursor: 'pointer',
                      borderColor: on ? 'var(--fg)' : 'var(--line)',
                      background: on ? 'var(--surface-2)' : 'var(--surface)',
                    }}
                  >
                    <span
                      style={{
                        display: 'inline-block',
                        width: 14,
                        height: 14,
                        borderRadius: 999,
                        background: a.swatch,
                        border: '1px solid var(--line)',
                      }}
                    />
                    <span className="mono" style={{ fontSize: 12 }}>{a.label}</span>
                    {on && <Icon name="check" size={12} color="var(--green)" />}
                  </button>
                );
              })}
            </div>
          </Field>
        </section>

        {/* Access */}
        <section className="card" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="col gap-1">
            <span className="label">access</span>
            <h2 className="h2">API token</h2>
          </div>
          <div className="row gap-2">
            <span className={`pill ${tokenSet ? 'pill--green' : 'pill--amber'}`}>
              <span className="dot" />
              {tokenSet ? 'token configured' : 'not set'}
            </span>
            {tokenBuildTime && <span className="pill pill--info">build-time</span>}
          </div>
          {tokenBuildTime ? (
            <p className="subtle" style={{ fontSize: 12 }}>
              The token is supplied at build time via <span className="mono">VITE_AUTORESEARCH_API_TOKEN</span>.
              You don't need to set it manually.
            </p>
          ) : (
            <form onSubmit={saveToken} className="col gap-3">
              <Field label="Update token">
                <div className="row gap-2">
                  <input
                    type={showToken ? 'text' : 'password'}
                    className="input mono"
                    value={tokenDraft}
                    onChange={(e) => setTokenDraft(e.target.value)}
                    placeholder="bearer_token_…"
                  />
                  <button type="button" className="btn btn--ghost" onClick={() => setShowToken(!showToken)}>
                    <Icon name={showToken ? 'eyeOff' : 'eye'} />
                    {showToken ? 'hide' : 'show'}
                  </button>
                </div>
              </Field>
              <div className="row gap-2">
                <button type="submit" className="btn btn--solid" disabled={!tokenDraft.trim()}>
                  <Icon name="check" size={12} />
                  Save
                </button>
                {tokenSet && (
                  <button type="button" className="btn btn--danger" onClick={clearToken}>
                    <Icon name="x" />
                    Clear stored token
                  </button>
                )}
                {savedAt && (
                  <span className="subtle" style={{ fontSize: 11 }}>saved at {savedAt}</span>
                )}
              </div>
            </form>
          )}
        </section>
      </div>
    </div>
  );
}
