import { useCallback, useEffect, useState } from 'react';
import * as api from './services/api';
import CopilotWorkspace from './components/CopilotWorkspace';
import OperationsWorkspace from './components/OperationsWorkspace';
import AnalyticsWorkspace from './components/AnalyticsWorkspace';
import './App.css';

export default function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(() => !!api.getAuthToken());
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState('Dashboard');
  const [stores, setStores] = useState([]);
  const [revision, setRevision] = useState(0);
  const expire = useCallback(() => { api.clearAuthToken(); setUser(null); setStores([]); setTab('Dashboard'); }, []);
  const onError = useCallback((err) => { if (err.status === 401) expire(); setError(err.status === 401 ? 'Your session expired. Please sign in again.' : err.message); }, [expire]);
  useEffect(() => {
    let active = true;
    if (!api.getAuthToken()) return;
    api.getMe().then(data => { if (active) setUser(data); }).catch(err => {
      if (active) { if (err.status === 401) api.clearAuthToken(); setError(err.message); }
    }).finally(() => { if (active) setChecking(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!user) return;
    let active = true;
    api.getStores().then(data => { if (active) setStores(data.items); }).catch(err => { if (active) onError(err); });
    return () => { active = false; };
  }, [user, onError]);
  async function signIn(event) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    try { const result = await api.login(form.get('employee').trim().toUpperCase(), form.get('store').trim().toUpperCase(), form.has('remember')); setUser(result.employee); }
    catch (err) { onError(err); } finally { setBusy(false); }
  }
  async function signOut() {
    setBusy(true);
    try { await api.logout(); } catch (err) { setError(err.message); }
    finally { expire(); setBusy(false); }
  }
  if (checking) return <main className="login-shell"><p role="status">Checking your session…</p></main>;
  if (!user) return <main className="login-shell"><form className="panel login-panel" onSubmit={signIn}>
    <span className="brand">StorePilot</span><h1>Sign in</h1><p>Use your assigned employee and store IDs.</p>
    {error && <p className="error" role="alert">{error}</p>}
    <label>Employee ID<input name="employee" required placeholder="E0007" pattern="[Ee][0-9]{4}" autoComplete="username" /></label>
    <label>Store ID<input name="store" required placeholder="ST001" pattern="([Ss][Tt]|[Ww][Hh])[0-9]{3}" /></label>
    <label className="check"><input name="remember" type="checkbox" /> Remember me</label>
    <button className="primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
  </form></main>;
  return <div className="workspace">
    <header className="topbar"><span className="brand">StorePilot</span><span className="identity">{user.employee_id} · {user.role} · {user.assigned_store_id}</span><button disabled={busy} onClick={signOut}>Sign out</button></header>
    <nav className="tabs" aria-label="Main navigation">{['Dashboard', 'Copilot', 'Analytics/Query'].map(name => <button key={name} aria-current={tab === name ? 'page' : undefined} onClick={() => { setTab(name); setError(''); }}>{name}</button>)}</nav>
    <main className="content"><h1>{tab}</h1>{error && <p className="error" role="alert">{error}</p>}
      {tab === 'Dashboard' && <OperationsWorkspace user={user} stores={stores} revision={revision} onError={onError} onCopilot={() => setTab('Copilot')} />}
      {tab === 'Analytics/Query' && <AnalyticsWorkspace stores={stores} onError={onError} />}
      <div hidden={tab !== 'Copilot'}><CopilotWorkspace user={user} stores={stores} onError={onError} onSaved={() => setRevision(value => value + 1)} /></div>
    </main>
  </div>;
}
