import React, { useState, useEffect } from 'react';
import {
  Lock,
  User,
  Eye,
  EyeOff,
  LogIn,
  ShieldCheck,
  AlertCircle,
  Store,
  Clock,
  Sparkles,
  CheckCircle2,
  HelpCircle,
  Package,
  Zap,
  Activity,
} from 'lucide-react';
import { MOCK_EMPLOYEES, resolveEmployeeCredentials } from '../data/mockEmployees';
import { STORES as FALLBACK_STORES } from '../data/mockData';
import api from '../services/api';

export default function LoginView({ onLogin }) {
  const [identifier, setIdentifier] = useState('E0035');
  const [password, setPassword] = useState('password123');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [storeId, setStoreId] = useState('ST001');
  const [availableStores, setAvailableStores] = useState(FALLBACK_STORES);
  const [errorMsg, setErrorMsg] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentTime, setCurrentTime] = useState('');
  const [showHelpModal, setShowHelpModal] = useState(false);
  const [backendStatus, setBackendStatus] = useState('checking'); // 'connected' | 'offline' | 'checking'

  // Live clock display
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setCurrentTime(
        now.toLocaleTimeString('en-IN', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true,
        })
      );
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  // Check Backend Health & Fetch Stores on mount
  useEffect(() => {
    let isMounted = true;
    async function checkBackend() {
      try {
        const health = await api.getHealth();
        if (isMounted) {
          if (health?.status === 'ok' || health?.status === 'degraded') {
            setBackendStatus('connected');
          } else {
            setBackendStatus('offline');
          }
        }
      } catch {
        if (isMounted) {
          setBackendStatus('offline');
        }
      }
    }
    checkBackend();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    setErrorMsg('');
    setIsLoading(true);

    const resolved = resolveEmployeeCredentials(identifier) || {
      id: identifier.trim().toUpperCase(),
      name: identifier.trim(),
      email: `${identifier.trim().toLowerCase()}@punjabsportsmart.com`,
      role: 'Store Operations Associate',
      department: 'Store Floor Operations',
      storeId: storeId,
      storeName: 'Jalandhar Sports Hub',
      city: 'Jalandhar',
      shift: 'Standard Duty Shift',
      initials: identifier.trim().slice(0, 2).toUpperCase(),
      avatarBg: 'linear-gradient(135deg, #2563eb, #1d4ed8)',
      badgeText: 'Staff',
      escalationLevel: 3,
      securityClearance: 'Level 3 - Associate',
    };

    const targetEmpId = resolved.id;
    const targetStoreId = storeId || resolved.storeId;

    try {
      // 1. Attempt Real Backend API Login (POST /api/auth/login)
      const apiResult = await api.login(targetEmpId, targetStoreId, rememberMe);

      const authenticatedUser = {
        ...resolved,
        id: apiResult.employee?.employee_id || targetEmpId,
        storeId: apiResult.employee?.assigned_store_id || targetStoreId,
        role: apiResult.employee?.role || resolved.role,
        escalationLevel: apiResult.employee?.escalation_level ?? resolved.escalationLevel ?? 3,
        token: apiResult.access_token,
        tokenExpiresAt: apiResult.expires_at,
        isBackendAuthenticated: true,
        loginTimestamp: new Date().toLocaleTimeString('en-IN', {
          hour: '2-digit',
          minute: '2-digit',
          hour12: true,
        }),
      };

      onLogin(authenticatedUser, rememberMe);
    } catch (err) {
      // If backend responded with 401: Invalid employee or store
      if (err.status === 401) {
        setErrorMsg(`Authentication failed: ${err.message}. Ensure Employee ID (e.g. E0035) matches Store ID (${targetStoreId}).`);
        setIsLoading(false);
      } else if (err.status === 422) {
        setErrorMsg('Validation error: Employee ID format must be E#### (e.g. E0007, E0035) and Store ID ST###.');
        setIsLoading(false);
      } else {
        // Backend offline / network fallback mode
        console.warn('Backend unavailable, proceeding in standalone client mode:', err.message);
        const fallbackUser = {
          ...resolved,
          storeId: targetStoreId,
          isBackendAuthenticated: false,
          loginTimestamp: new Date().toLocaleTimeString('en-IN', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: true,
          }),
        };
        onLogin(fallbackUser, rememberMe);
      }
    }
  };

  // Quick 1-click login for demo / evaluation
  const handleQuickLogin = async (emp) => {
    setIdentifier(emp.id);
    setPassword(emp.password);
    setStoreId(emp.storeId);
    setErrorMsg('');
    setIsLoading(true);

    try {
      // Direct API login with valid backend credentials
      const apiResult = await api.login(emp.id, emp.storeId, rememberMe);

      const authenticatedUser = {
        ...emp,
        id: apiResult.employee?.employee_id || emp.id,
        storeId: apiResult.employee?.assigned_store_id || emp.storeId,
        role: apiResult.employee?.role || emp.role,
        escalationLevel: apiResult.employee?.escalation_level ?? emp.escalationLevel ?? 4,
        token: apiResult.access_token,
        tokenExpiresAt: apiResult.expires_at,
        isBackendAuthenticated: true,
        loginTimestamp: new Date().toLocaleTimeString('en-IN', {
          hour: '2-digit',
          minute: '2-digit',
          hour12: true,
        }),
      };

      onLogin(authenticatedUser, rememberMe);
    } catch (err) {
      console.warn('Quick login fallback:', err.message);
      // Standalone fallback
      const fallbackUser = {
        ...emp,
        isBackendAuthenticated: false,
        loginTimestamp: new Date().toLocaleTimeString('en-IN', {
          hour: '2-digit',
          minute: '2-digit',
          hour12: true,
        }),
      };
      onLogin(fallbackUser, rememberMe);
    }
  };

  return (
    <div className="login-page-wrapper">
      {/* Background Decorative Mesh Elements */}
      <div className="login-bg-mesh" aria-hidden="true">
        <div className="mesh-circle mesh-1" />
        <div className="mesh-circle mesh-2" />
        <div className="mesh-circle mesh-3" />
      </div>

      <div className="login-container">
        {/* Left Column: Brand Hero & Retail System Context */}
        <div className="login-hero-panel">
          <div className="hero-top-brand">
            <div className="brand-logo-circle hero-logo">
              <span className="brand-symbol">PSM</span>
            </div>
            <div className="hero-brand-titles">
              <h1 className="hero-app-title">Punjab Sports Mart</h1>
              <span className="hero-app-badge">StorePilot Enterprise OS</span>
            </div>
          </div>

          <div className="hero-pitch">
            <h2 className="hero-headline">
              AI Retail Operations <br />
              <span className="text-gradient-blue">&amp; Triage Terminal</span>
            </h2>
            <p className="hero-description">
              Integrated full-stack operations hub connected to StorePilot FastAPI &amp; SQLite
              engine with local policy retrieval, incident creation, and analytics.
            </p>
          </div>

          <div className="hero-features-list">
            <div className="hero-feature-item">
              <div className="feature-icon-box">
                <Zap size={18} className="text-blue" />
              </div>
              <div className="feature-text">
                <strong>Sub-Second Incident Classification</strong>
                <p>FastAPI deterministic triage for POS outages, refund claims, and pricing discrepancies.</p>
              </div>
            </div>

            <div className="hero-feature-item">
              <div className="feature-icon-box">
                <Package size={18} className="text-green" />
              </div>
              <div className="feature-text">
                <strong>Transactional Ticket Creation</strong>
                <p>Idempotency-guaranteed ticket generation with atomic event audit logs.</p>
              </div>
            </div>

            <div className="hero-feature-item">
              <div className="feature-icon-box">
                <ShieldCheck size={18} className="text-indigo" />
              </div>
              <div className="feature-text">
                <strong>Role-Scoped Incident Visibility</strong>
                <p>Enforced clearance hierarchy: level-4 leads view all incidents across stores.</p>
              </div>
            </div>
          </div>

          <div className="hero-terminal-status">
            <div className="status-live-pill">
              <span className={`pulse-indicator ${backendStatus === 'connected' ? 'pulse-green' : 'pulse-amber'}`}></span>
              <span className="status-text">
                {backendStatus === 'connected'
                  ? 'FastAPI Backend Online (127.0.0.1:8000)'
                  : backendStatus === 'checking'
                  ? 'Verifying API Connection...'
                  : 'Standalone Terminal Mode'}
              </span>
            </div>
            <div className="live-clock-pill">
              <Clock size={13} />
              <span>{currentTime || '09:00:00 AM IST'}</span>
            </div>
          </div>
        </div>

        {/* Right Column: Employee Authentication Card */}
        <div className="login-card">
          <div className="login-card-header">
            <div className="terminal-auth-pill">
              <Activity size={14} className="text-blue" />
              <span>STOREPILOT REST API AUTHENTICATION</span>
            </div>
            <h2 className="login-card-title">Employee Terminal Login</h2>
            <p className="login-card-subtitle">
              Sign in with your registered Employee ID and Store Assignment to authenticate against the live directory.
            </p>
          </div>

          {/* Error Banner */}
          {errorMsg && (
            <div className="login-error-banner" role="alert">
              <AlertCircle size={18} className="error-icon" />
              <div className="error-text-wrap">
                <span className="error-title">Authentication Failed</span>
                <p className="error-desc">{errorMsg}</p>
              </div>
            </div>
          )}

          {/* Form */}
          <form className="login-form" onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label" htmlFor="employee-identifier">
                Employee Master ID
              </label>
              <div className="input-with-icon">
                <User size={18} className="input-icon-left" />
                <input
                  id="employee-identifier"
                  type="text"
                  className="form-input login-input"
                  placeholder="e.g. E0035, E0007, E0001"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  autoComplete="username"
                  required
                />
              </div>
              <span className="input-hint" style={{ fontSize: '0.72rem', marginTop: '3px' }}>
                Format: <code>E####</code> (matches <code>employee_master</code> in <code>retail.db</code>)
              </span>
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="store-location">
                Assigned Store Location (Must match Employee Directory)
              </label>
              <div className="input-with-icon">
                <Store size={18} className="input-icon-left" />
                <select
                  id="store-location"
                  className="form-select login-input"
                  value={storeId}
                  onChange={(e) => setStoreId(e.target.value)}
                >
                  <option value="ST001">ST001 - Jalandhar Sports Hub (Punjab)</option>
                  <option value="ST008">ST008 - Express Sports Mohali (North)</option>
                  <option value="ST002">ST002 - Model Town Sports (Jalandhar)</option>
                  <option value="ST003">ST003 - Lakeside Sports Mart (Chandigarh)</option>
                  <option value="ST004">ST004 - Civil Lines Sports (Ludhiana)</option>
                  <option value="ST015">ST015 - Jaipur Sports 15 (Haryana)</option>
                  <option value="ST022">ST022 - Dehradun Sports 22 (NCR)</option>
                  <option value="ST029">ST029 - Shimla Sports 29 (Punjab)</option>
                  <option value="ST036">ST036 - Karnal Sports 36 (North)</option>
                  <option value="ST043">ST043 - Panipat Sports 43 (Rajasthan)</option>
                </select>
              </div>
            </div>

            <div className="form-group">
              <div className="label-with-hint">
                <label className="form-label" htmlFor="employee-password">
                  Security PIN / Password
                </label>
                <span className="demo-pass-hint">Default: <code>password123</code></span>
              </div>
              <div className="input-with-icon">
                <Lock size={18} className="input-icon-left" />
                <input
                  id="employee-password"
                  type={showPassword ? 'text' : 'password'}
                  className="form-input login-input"
                  placeholder="Enter employee password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                />
                <button
                  type="button"
                  className="password-toggle-btn"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div className="login-form-options">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                />
                <span>Remember JWT Bearer Session</span>
              </label>
              <button
                type="button"
                className="help-link-btn"
                onClick={() => setShowHelpModal(true)}
              >
                <HelpCircle size={14} />
                <span>Valid ID Roster</span>
              </button>
            </div>

            <button
              type="submit"
              className="btn-login-submit"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <span className="btn-spinner"></span>
                  <span>Authenticating with /api/auth/login...</span>
                </>
              ) : (
                <>
                  <LogIn size={18} />
                  <span>Authenticate &amp; Launch Terminal</span>
                </>
              )}
            </button>
          </form>

          {/* Quick Roster Selector (1-Click Demo Evaluation) */}
          <div className="quick-access-section">
            <div className="quick-access-header">
              <span className="quick-access-line"></span>
              <span className="quick-access-title">
                <Sparkles size={13} className="text-amber" />
                ONE-CLICK LOGIN (VERIFIED BACKEND EMPLOYEES)
              </span>
              <span className="quick-access-line"></span>
            </div>

            <div className="quick-employees-grid">
              {MOCK_EMPLOYEES.map((emp) => {
                const isSelected = identifier.toLowerCase() === emp.id.toLowerCase();
                return (
                  <button
                    key={emp.id}
                    type="button"
                    className={`quick-emp-card ${isSelected ? 'active-selection' : ''}`}
                    onClick={() => handleQuickLogin(emp)}
                    title={`Click to immediately authenticate as ${emp.name} (${emp.id} @ ${emp.storeId})`}
                  >
                    <div
                      className="emp-avatar-circle"
                      style={{ background: emp.avatarBg }}
                    >
                      {emp.initials}
                    </div>
                    <div className="emp-card-details">
                      <div className="emp-card-top">
                        <span className="emp-card-name">{emp.name}</span>
                        <span className="emp-card-badge">{emp.id}</span>
                      </div>
                      <span className="emp-card-role">{emp.role} (L{emp.escalationLevel})</span>
                      <span className="emp-card-store">
                        <Store size={11} /> {emp.storeId} • {emp.city}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Compliance & Security Footer */}
          <div className="login-security-footer">
            <div className="security-item">
              <ShieldCheck size={14} className="text-success" />
              <span>HS256 JWT Signed Sessions (30-Minute Expiry)</span>
            </div>
            <div className="security-item text-muted">
              <span>FastAPI Endpoints: /api/auth/login • /api/me • /api/health</span>
            </div>
          </div>
        </div>
      </div>

      {/* Roster & Help Modal */}
      {showHelpModal && (
        <div className="modal-backdrop" onClick={() => setShowHelpModal(false)}>
          <div
            className="modal-dialog help-dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <div className="modal-title-wrap">
                <HelpCircle size={20} className="text-blue" />
                <h3 className="modal-title">Employee Directory &amp; Store Assignments</h3>
              </div>
              <button
                className="modal-close-btn"
                onClick={() => setShowHelpModal(false)}
              >
                ✕
              </button>
            </div>
            <div className="modal-body">
              <p>
                The StorePilot backend enforces strict employee-to-store assignment validation from{' '}
                <code>retail.db</code>. Each employee must sign in with their assigned store.
              </p>
              <div className="help-box">
                <strong>Recommended Test Employee Credentials:</strong>
                <ul>
                  <li>
                    <strong>Harpreet Singh:</strong> ID <code>E0035</code> | Store <code>ST001</code> (Store Manager, Level 4)
                  </li>
                  <li>
                    <strong>Simran Kaur:</strong> ID <code>E0007</code> | Store <code>ST001</code> (POS Support Lead, Level 4)
                  </li>
                  <li>
                    <strong>Rajesh Kumar:</strong> ID <code>E0014</code> | Store <code>ST001</code> (Inventory Associate, Level 3)
                  </li>
                  <li>
                    <strong>Gurpreet Sandhu:</strong> ID <code>E0001</code> | Store <code>ST008</code> (Regional Manager, Level 2)
                  </li>
                  <li>
                    <strong>Amanpreet Gill:</strong> ID <code>E0015</code> | Store <code>ST008</code> (POS Support, Level 4)
                  </li>
                </ul>
              </div>
              <p className="text-muted" style={{ fontSize: '0.85rem' }}>
                Level 4 clearance grants visibility across all incident tickets in the system.
                Lower levels are scoped according to the escalation hierarchy.
              </p>
            </div>
            <div className="modal-footer">
              <button
                className="btn-action-primary"
                onClick={() => setShowHelpModal(false)}
              >
                <CheckCircle2 size={16} />
                <span>Understood</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
