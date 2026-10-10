import React from 'react';
import {
  Menu,
  Store,
  Sparkles,
} from 'lucide-react';
import { STORES } from '../data/mockData';

export default function Header({
  activeTab,
  onOpenCopilot,
  selectedStore,
  setSelectedStore,
  setMobileOpen,
}) {
  const getTabTitle = () => {
    switch (activeTab) {
      case 'dashboard':
        return {
          title: 'Store Operations Dashboard',
          subtitle: 'Live situational awareness, case triage & inventory health',
        };
      case 'copilot':
        return {
          title: 'AI Operations Copilot',
          subtitle: 'Intelligent triage, SOP compliance & escalation decision engine',
        };
      case 'inventory':
        return {
          title: 'Inventory & Stock Management',
          subtitle: 'Store-level on-hand SKUs, safety thresholds & replenishments',
        };
      case 'support-cases':
        return {
          title: 'Operations Support Cases',
          subtitle: 'Track, escalate, and resolve retail incidents and customer queries',
        };
      case 'vendor-analytics':
        return {
          title: 'Vendor Performance Analytics',
          subtitle: 'Fulfillment fill rates, lead times & SLA compliance tracking',
        };
      case 'reports':
        return {
          title: 'Operational Reports & Audits',
          subtitle: 'Incident history, downtime metrics & store-by-store compliance',
        };
      case 'settings':
        return {
          title: 'System Settings & Guardrails',
          subtitle: 'Configure store parameters, responsible AI safeguards & policies',
        };
      default:
        return {
          title: 'Retail Operations Copilot',
          subtitle: 'Punjab Sports Mart Enterprise System',
        };
    }
  };

  const { title, subtitle } = getTabTitle();

  return (
    <header className="app-header">
      <div className="header-left">
        <button
          className="mobile-menu-btn"
          onClick={() => setMobileOpen(true)}
          aria-label="Open sidebar"
        >
          <Menu size={22} />
        </button>
        <div className="header-titles">
          <h2 className="header-main-title">{title}</h2>
          <p className="header-subtitle">{subtitle}</p>
        </div>
      </div>

      <div className="header-right">
        {/* Store Selector */}
        <div className="store-selector-wrapper">
          <Store size={16} className="store-icon" />
          <select
            className="store-select"
            value={selectedStore}
            onChange={(e) => setSelectedStore(e.target.value)}
            aria-label="Select store"
          >
            {STORES.map((s) => (
              <option key={s.id} value={s.id}>
                {s.id} - {s.name}
              </option>
            ))}
          </select>
        </div>

        {/* Demo Mode Tag */}
        <div className="header-demo-pill" title="Prototype running on client-side demo data">
          <span className="demo-dot"></span>
          <span>Sample Enterprise Data</span>
        </div>

        {/* Quick Copilot Action (if not already on Copilot tab) */}
        {activeTab !== 'copilot' && (
          <button
            className="header-copilot-btn"
            onClick={onOpenCopilot}
            title="Launch AI Operations Copilot"
          >
            <Sparkles size={16} />
            <span>Launch Copilot</span>
          </button>
        )}
      </div>
    </header>
  );
}
