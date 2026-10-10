import React from 'react';
import {
  LayoutDashboard,
  Bot,
  Package,
  LifeBuoy,
  TrendingUp,
  FileText,
  Settings,
  ShieldCheck,
  X,
} from 'lucide-react';

export default function Sidebar({
  activeTab,
  setActiveTab,
  mobileOpen,
  setMobileOpen,
  openCasesCount = 4,
  lowStockCount = 5,
}) {
  const navItems = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: LayoutDashboard,
      badge: null,
    },
    {
      id: 'copilot',
      label: 'AI Operations Copilot',
      icon: Bot,
      badge: 'AI',
      badgeColor: 'badge-accent',
    },
    {
      id: 'inventory',
      label: 'Inventory',
      icon: Package,
      badge: lowStockCount > 0 ? `${lowStockCount} alerts` : null,
      badgeColor: 'badge-warning',
    },
    {
      id: 'support-cases',
      label: 'Support Cases',
      icon: LifeBuoy,
      badge: `${openCasesCount} open`,
      badgeColor: 'badge-danger',
    },
    {
      id: 'vendor-analytics',
      label: 'Vendor Analytics',
      icon: TrendingUp,
      badge: null,
    },
    {
      id: 'reports',
      label: 'Reports',
      icon: FileText,
      badge: null,
    },
    {
      id: 'settings',
      label: 'Settings',
      icon: Settings,
      badge: null,
    },
  ];

  const handleNavClick = (id) => {
    setActiveTab(id);
    if (mobileOpen) {
      setMobileOpen(false);
    }
  };

  return (
    <>
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      <aside className={`app-sidebar ${mobileOpen ? 'mobile-open' : ''}`}>
        {/* Brand Header */}
        <div className="sidebar-brand">
          <div className="brand-logo-container">
            <div className="brand-logo-circle">
              <span className="brand-symbol">PSM</span>
            </div>
            <div className="brand-text">
              <h1 className="brand-title">Punjab Sports Mart</h1>
              <span className="brand-subtitle">Retail Operations Copilot</span>
            </div>
          </div>
          {mobileOpen && (
            <button
              className="sidebar-close-btn"
              onClick={() => setMobileOpen(false)}
              aria-label="Close menu"
            >
              <X size={20} />
            </button>
          )}
        </div>

        {/* Demo Environment Tag */}
        <div className="sidebar-env-badge">
          <span className="env-dot"></span>
          <span>ST002 Jalandhar Flagship • Demo Sandbox</span>
        </div>

        {/* Navigation Items */}
        <nav className="sidebar-nav">
          <div className="nav-group-title">MAIN OPERATIONS</div>
          <ul className="nav-list">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <li key={item.id} className="nav-item">
                  <button
                    className={`nav-link ${isActive ? 'active' : ''}`}
                    onClick={() => handleNavClick(item.id)}
                  >
                    <Icon className="nav-icon" size={18} />
                    <span className="nav-label">{item.label}</span>
                    {item.badge && (
                      <span className={`nav-badge ${item.badgeColor || ''}`}>
                        {item.badge}
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Sidebar Footer / User Profile */}
        <div className="sidebar-footer">
          <div className="user-profile-card">
            <div className="user-avatar">
              <span>HS</span>
            </div>
            <div className="user-info">
              <span className="user-name">Harpreet Singh</span>
              <span className="user-role">Operations Lead • ST002</span>
            </div>
          </div>

          <div className="responsible-ai-pill">
            <ShieldCheck size={14} className="shield-icon" />
            <span>AI Guardrails Active (PCI-DSS)</span>
          </div>
        </div>
      </aside>
    </>
  );
}
