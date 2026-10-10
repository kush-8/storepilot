import React, { useState } from 'react';
import {
  ShieldCheck,
  Store,
  RefreshCw,
  CheckCircle2,
  Database,
  Save,
  User,
  LogOut,
  BadgeCheck,
} from 'lucide-react';
import { STORES } from '../data/mockData';

export default function SettingsView({
  selectedStore,
  setSelectedStore,
  onResetDemoData,
  currentUser,
  onLogout,
}) {
  const [pciGuardrail, setPciGuardrail] = useState(true);
  const [managerApprovalRule, setManagerApprovalRule] = useState(true);
  const [autoP1Escalation, setAutoP1Escalation] = useState(true);
  const [savedMsg, setSavedMsg] = useState('');

  const handleSavePreferences = (e) => {
    e?.preventDefault();
    setSavedMsg('Responsible AI guardrail rules updated successfully.');
    setTimeout(() => setSavedMsg(''), 3000);
  };

  return (
    <div className="settings-container">
      {savedMsg && (
        <div className="inventory-toast-banner">
          <CheckCircle2 size={18} className="text-success" />
          <span>{savedMsg}</span>
          <button className="toast-close" onClick={() => setSavedMsg('')}>
            ✕
          </button>
        </div>
      )}

      {/* Main Settings Card */}
      <div className="settings-grid">
        {/* Responsible AI Safeguards Section */}
        <div className="settings-card">
          <div className="settings-card-header">
            <div className="settings-header-icon bg-red-subtle">
              <ShieldCheck size={20} className="text-danger" />
            </div>
            <div>
              <h3 className="settings-title">Responsible AI & Security Safeguards</h3>
              <p className="settings-subtitle">Enterprise safety guardrails & credential filtering</p>
            </div>
          </div>

          <div className="settings-body">
            <div className="setting-toggle-item">
              <div className="toggle-text">
                <span className="toggle-title">PCI-DSS Credential & Payment Data Refusal</span>
                <p className="toggle-desc">
                  Strictly blocks employees or prompts from querying unmasked credit card numbers,
                  CVVs, PINs, or admin credentials. Flags security violations.
                </p>
              </div>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={pciGuardrail}
                  onChange={(e) => setPciGuardrail(e.target.checked)}
                />
                <span className="slider round"></span>
              </label>
            </div>

            <div className="setting-toggle-item">
              <div className="toggle-text">
                <span className="toggle-title">Mandatory Manager Approval for High-Value Returns</span>
                <p className="toggle-desc">
                  Prohibits Copilot from auto-approving returns &gt; ₹5,000 without verified receipt
                  and requires Store Manager manual authorization.
                </p>
              </div>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={managerApprovalRule}
                  onChange={(e) => setManagerApprovalRule(e.target.checked)}
                />
                <span className="slider round"></span>
              </label>
            </div>

            <div className="setting-toggle-item">
              <div className="toggle-text">
                <span className="toggle-title">Immediate P1 Storewide Outage Escalation</span>
                <p className="toggle-desc">
                  Automatically pages Regional IT On-Call when all register payment gateways fail,
                  enforcing the 15-minute SLA.
                </p>
              </div>
              <label className="switch">
                <input
                  type="checkbox"
                  checked={autoP1Escalation}
                  onChange={(e) => setAutoP1Escalation(e.target.checked)}
                />
                <span className="slider round"></span>
              </label>
            </div>

            <div style={{ marginTop: '8px' }}>
              <button className="btn-action-primary" onClick={handleSavePreferences}>
                <Save size={16} />
                <span>Save Guardrail Rules</span>
              </button>
            </div>
          </div>
        </div>

        {/* Store Profile Section */}
        <div className="settings-card">
          <div className="settings-card-header">
            <div className="settings-header-icon bg-blue-subtle">
              <Store size={20} className="text-blue" />
            </div>
            <div>
              <h3 className="settings-title">Active Store Station Configuration</h3>
              <p className="settings-subtitle">Manage terminal location context for incident triage</p>
            </div>
          </div>

          <div className="settings-body">
            <div className="form-group">
              <label className="form-label">Primary Operating Store</label>
              <select
                className="form-select"
                value={selectedStore}
                onChange={(e) => setSelectedStore(e.target.value)}
              >
                {STORES.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.id} - {s.name} ({s.city})
                  </option>
                ))}
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Active Duty Operations Manager</label>
              <input
                type="text"
                className="form-input"
                value={currentUser ? `${currentUser.name} (${currentUser.role})` : 'Harpreet Singh (Ops Lead)'}
                readOnly
              />
            </div>

            <div className="form-group">
              <label className="form-label">Policy Evidence Knowledge Base</label>
              <input
                type="text"
                className="form-input"
                defaultValue="Simulated SOP Repository [Placeholder Mode]"
                readOnly
              />
              <span className="input-hint">
                Real implementation connects to central enterprise Confluence & ERP via REST API.
              </span>
            </div>
          </div>
        </div>

        {/* Authenticated Employee Terminal Session Card */}
        {currentUser && (
          <div className="settings-card">
            <div className="settings-card-header">
              <div className="settings-header-icon bg-indigo-subtle">
                <User size={20} className="text-indigo" />
              </div>
              <div>
                <h3 className="settings-title">Active Employee Terminal Session</h3>
                <p className="settings-subtitle">Authenticated staff identity and store access credentials</p>
              </div>
            </div>

            <div className="settings-body">
              <div className="emp-session-profile-card">
                <div
                  className="emp-session-avatar"
                  style={currentUser.avatarBg ? { background: currentUser.avatarBg } : undefined}
                >
                  {currentUser.initials}
                </div>
                <div className="emp-session-details">
                  <div className="emp-session-name-row">
                    <h4 className="emp-session-name">{currentUser.name}</h4>
                    <span className="badge-accent">{currentUser.id}</span>
                  </div>
                  <p className="emp-session-role">{currentUser.role} • {currentUser.department}</p>
                  <p className="emp-session-sub">
                    <span>Email: <strong>{currentUser.email}</strong></span> • 
                    <span> Shift: <strong>{currentUser.shift}</strong></span>
                  </p>
                </div>
              </div>

              <div className="sys-info-box" style={{ marginTop: '16px' }}>
                <div className="sys-info-item">
                  <span className="sys-key">Security Clearance:</span>
                  <span className="sys-val" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <BadgeCheck size={14} className="text-success" />
                    {currentUser.securityClearance}
                  </span>
                </div>
                <div className="sys-info-item">
                  <span className="sys-key">Assigned Home Store:</span>
                  <span className="sys-val">{currentUser.storeName} ({currentUser.storeId})</span>
                </div>
                <div className="sys-info-item">
                  <span className="sys-key">Terminal Sign-In Time:</span>
                  <span className="sys-val">{currentUser.loginTimestamp || 'Active Session'}</span>
                </div>
              </div>

              {onLogout && (
                <div style={{ marginTop: '16px' }}>
                  <button className="btn-signout-card" onClick={onLogout}>
                    <LogOut size={16} />
                    <span>Sign Out / Switch Employee Account</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Prototype Reset Card */}
        <div className="settings-card">
          <div className="settings-card-header">
            <div className="settings-header-icon bg-amber-subtle">
              <Database size={20} className="text-amber" />
            </div>
            <div>
              <h3 className="settings-title">Prototype Sandbox Management</h3>
              <p className="settings-subtitle">Reset demo inventory and incident logs</p>
            </div>
          </div>

          <div className="settings-body">
            <p className="settings-text text-muted">
              You can restore the initial hackathon demo dataset (including the out-of-stock SG
              cricket bats, card payment outage tickets, and sample vendor records) at any time.
            </p>

            <div className="settings-action-row">
              <button className="btn-reset-data" onClick={onResetDemoData}>
                <RefreshCw size={16} />
                <span>Reset Demo Data to Initial State</span>
              </button>
            </div>

            <div className="sys-info-box">
              <div className="sys-info-item">
                <span className="sys-key">Application:</span>
                <span className="sys-val">Punjab Sports Mart Retail Copilot</span>
              </div>
              <div className="sys-info-item">
                <span className="sys-key">Architecture:</span>
                <span className="sys-val">React 19 + Vite + Recharts + Lucide</span>
              </div>
              <div className="sys-info-item">
                <span className="sys-key">Inference:</span>
                <span className="sys-val">Local Deterministic Rule Engine (Simulated Demo AI)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
