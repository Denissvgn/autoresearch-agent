// Hi-fi top bar with theme/density/accent switching and route-aware nav.
import { useEffect, useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Icon } from './primitives';
import { useStatus } from '../../hooks/useResearch';

export type ThemeName = 'theme-dark' | 'theme-light';
export type DensityName = 'density-comfortable' | 'density-compact';
export type AccentName = 'accent-mono' | 'accent-ember' | 'accent-cobalt' | 'accent-lime';

const THEME_KEY = 'autoresearch.theme';
const DENSITY_KEY = 'autoresearch.density';
const ACCENT_KEY = 'autoresearch.accent';

function readPref<T extends string>(key: string, fallback: T): T {
  if (typeof window === 'undefined') return fallback;
  try {
    return (localStorage.getItem(key) as T) || fallback;
  } catch {
    return fallback;
  }
}

export function useDesignPrefs() {
  const [theme, setTheme] = useState<ThemeName>(() => readPref<ThemeName>(THEME_KEY, 'theme-dark'));
  const [density, setDensity] = useState<DensityName>(() =>
    readPref<DensityName>(DENSITY_KEY, 'density-comfortable'),
  );
  const [accent, setAccent] = useState<AccentName>(() => readPref<AccentName>(ACCENT_KEY, 'accent-mono'));

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('theme-dark', 'theme-light');
    root.classList.add(theme);
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {}
  }, [theme]);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('density-comfortable', 'density-compact');
    root.classList.add(density);
    try {
      localStorage.setItem(DENSITY_KEY, density);
    } catch {}
  }, [density]);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('accent-mono', 'accent-ember', 'accent-cobalt', 'accent-lime');
    root.classList.add(accent);
    try {
      localStorage.setItem(ACCENT_KEY, accent);
    } catch {}
  }, [accent]);

  return { theme, setTheme, density, setDensity, accent, setAccent };
}

export interface TopbarProps {
  onToggleTheme?: () => void;
  theme?: ThemeName;
}

export function Topbar({ onToggleTheme, theme }: TopbarProps) {
  const { pathname } = useLocation();
  const { data: status, isError } = useStatus();
  const connected = !isError && !!status;
  // Treat detail/promote routes as "session" context (no nav highlight)
  const isDashboard = pathname === '/' || pathname.startsWith('/dashboard');
  const isNew = pathname.startsWith('/research/new');
  const isHistory = pathname.startsWith('/history');
  const isSettings = pathname.startsWith('/settings');

  const wsHost = (() => {
    try {
      const url = new URL(window.location.href);
      return `${url.host}/ws`;
    } catch {
      return 'ws://localhost/ws';
    }
  })();

  return (
    <header className="topbar">
      <NavLink to="/" className="topbar__brand">
        <span className="topbar__mark">A</span>
        autoresearch
        <span className="pill" style={{ marginLeft: 6 }}>
          v0.4.1
        </span>
      </NavLink>
      <nav className="topbar__nav">
        <NavLink to="/" end className={() => (isDashboard ? 'on' : undefined)}>
          Dashboard
        </NavLink>
        <NavLink to="/research/new" className={() => (isNew ? 'on' : undefined)}>
          New
        </NavLink>
        <NavLink to="/history" className={() => (isHistory ? 'on' : undefined)}>
          History
        </NavLink>
        <NavLink to="/settings" className={() => (isSettings ? 'on' : undefined)}>
          Settings
        </NavLink>
      </nav>
      <div className="topbar__spacer" />
      <div className="topbar__right">
        <span className={`pill ${connected ? 'pill--green' : 'pill--red'}`}>
          <span className="dot" />
          {connected ? 'srv connected' : 'srv offline'}
        </span>
        <span className="label mono" style={{ color: 'var(--faint)' }}>
          {wsHost}
        </span>
        <button className="btn btn--icon btn--ghost" title="Toggle theme" onClick={onToggleTheme}>
          <Icon name={theme === 'theme-light' ? 'sun' : 'moon'} />
        </button>
        <button className="btn btn--icon btn--ghost" title="Notifications">
          <Icon name="bell" />
        </button>
        <div className="avatar" title="Operator">
          MK
        </div>
      </div>
    </header>
  );
}
