import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import LoginView from './components/LoginView';
import DashboardView from './components/DashboardView';
import CopilotView from './components/CopilotView';
import InventoryView from './components/InventoryView';
import SupportCasesView from './components/SupportCasesView';
import VendorAnalyticsView from './components/VendorAnalyticsView';
import ReportsView from './components/ReportsView';
import SettingsView from './components/SettingsView';
import CaseDetailModal from './components/CaseDetailModal';
import { INITIAL_INVENTORY, INITIAL_SUPPORT_CASES } from './data/mockData';
import './App.css';

const SESSION_STORAGE_KEY = 'psm_authenticated_employee';

export default function App() {
  // Authentication State: Employee must log in first before performing further activities
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const saved =
        localStorage.getItem(SESSION_STORAGE_KEY) ||
        sessionStorage.getItem(SESSION_STORAGE_KEY);
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const [activeTab, setActiveTab] = useState('dashboard');
  const [mobileOpen, setMobileOpen] = useState(false);
  const [selectedStore, setSelectedStore] = useState(
    currentUser?.storeId || 'ST002'
  );
  const [inventory, setInventory] = useState(INITIAL_INVENTORY);
  const [supportCases, setSupportCases] = useState(INITIAL_SUPPORT_CASES);
  const [copilotQuery, setCopilotQuery] = useState('');
  const [selectedModalCase, setSelectedModalCase] = useState(null);

  // Handle Employee Login
  const handleLogin = (employee, rememberMe = true) => {
    setCurrentUser(employee);
    if (employee.storeId) {
      setSelectedStore(employee.storeId);
    }
    try {
      if (rememberMe) {
        localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(employee));
        sessionStorage.removeItem(SESSION_STORAGE_KEY);
      } else {
        sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(employee));
        localStorage.removeItem(SESSION_STORAGE_KEY);
      }
    } catch {
      // Ignore storage errors (private mode, etc.)
    }
  };

  // Handle Employee Logout
  const handleLogout = () => {
    setCurrentUser(null);
    setActiveTab('dashboard');
    setCopilotQuery('');
    try {
      localStorage.removeItem(SESSION_STORAGE_KEY);
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
    } catch {
      // Ignore storage errors
    }
  };

  // Navigate to Copilot and populate with specified issue
  const handleTriageWithCopilot = (issueText) => {
    setCopilotQuery(issueText);
    setActiveTab('copilot');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Add new support case from Copilot or user form
  const handleCreateSupportCase = (newCaseData) => {
    const nextId = `CAS-${4092 + supportCases.length}`;
    const newCase = {
      id: nextId,
      issue: newCaseData.issue,
      category: newCaseData.category,
      priority: newCaseData.priority,
      storeId: newCaseData.storeId || selectedStore,
      status: newCaseData.status || 'Open',
      assignedTo: newCaseData.assignedTo || currentUser?.name || 'Store Supervisor',
      createdAt: 'Just now',
      details: newCaseData.details || '',
    };
    setSupportCases((prev) => [newCase, ...prev]);
  };

  // Reset demo data to initial state
  const handleResetDemoData = () => {
    setInventory(INITIAL_INVENTORY);
    setSupportCases(INITIAL_SUPPORT_CASES);
  };

  // Open modal for a case
  const handleViewCase = (caseItem) => {
    setSelectedModalCase(caseItem);
  };

  // If user is not logged in, enforce Employee Login screen first
  if (!currentUser) {
    return <LoginView onLogin={handleLogin} />;
  }

  // Render the selected view once employee is authenticated
  const renderActiveView = () => {
    switch (activeTab) {
      case 'dashboard':
        return (
          <DashboardView
            supportCases={supportCases}
            inventory={inventory}
            onTriageWithCopilot={handleTriageWithCopilot}
            onViewCase={handleViewCase}
            selectedStore={selectedStore}
          />
        );
      case 'copilot':
        return (
          <CopilotView
            key={copilotQuery || 'default'}
            initialQuery={copilotQuery}
            onCreateSupportCase={handleCreateSupportCase}
            selectedStore={selectedStore}
          />
        );
      case 'inventory':
        return (
          <InventoryView
            inventory={inventory}
            setInventory={setInventory}
            onTriageWithCopilot={handleTriageWithCopilot}
            selectedStore={selectedStore}
          />
        );
      case 'support-cases':
        return (
          <SupportCasesView
            supportCases={supportCases}
            setSupportCases={setSupportCases}
            onTriageWithCopilot={handleTriageWithCopilot}
            onViewCase={handleViewCase}
          />
        );
      case 'vendor-analytics':
        return (
          <VendorAnalyticsView onTriageWithCopilot={handleTriageWithCopilot} />
        );
      case 'reports':
        return (
          <ReportsView onTriageWithCopilot={handleTriageWithCopilot} />
        );
      case 'settings':
        return (
          <SettingsView
            selectedStore={selectedStore}
            setSelectedStore={setSelectedStore}
            onResetDemoData={handleResetDemoData}
            currentUser={currentUser}
            onLogout={handleLogout}
          />
        );
      default:
        return (
          <DashboardView
            supportCases={supportCases}
            inventory={inventory}
            onTriageWithCopilot={handleTriageWithCopilot}
            onViewCase={handleViewCase}
            selectedStore={selectedStore}
          />
        );
    }
  };

  const openCasesCount = supportCases.filter((c) => c.status !== 'Resolved').length;
  const lowStockCount = inventory.filter(
    (i) => i.status === 'Out of Stock' || i.status === 'Low Stock'
  ).length;

  return (
    <div className="app-root">
      {/* Dark Navy Sidebar */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={(tab) => {
          // If manually navigating to Copilot without clicking a case, clear prefilled query
          if (tab === 'copilot' && activeTab !== 'copilot') {
            setCopilotQuery('');
          }
          setActiveTab(tab);
        }}
        mobileOpen={mobileOpen}
        setMobileOpen={setMobileOpen}
        openCasesCount={openCasesCount}
        lowStockCount={lowStockCount}
        currentUser={currentUser}
        onLogout={handleLogout}
      />

      {/* Main Workspace */}
      <div className="app-main-layout">
        <Header
          activeTab={activeTab}
          onOpenCopilot={() => {
            setCopilotQuery('');
            setActiveTab('copilot');
          }}
          selectedStore={selectedStore}
          setSelectedStore={setSelectedStore}
          setMobileOpen={setMobileOpen}
          currentUser={currentUser}
          onLogout={handleLogout}
        />

        <main className="app-content-area">{renderActiveView()}</main>
      </div>

      {/* Case Details Dialog */}
      <CaseDetailModal
        selectedCase={selectedModalCase}
        onClose={() => setSelectedModalCase(null)}
        onTriageWithCopilot={handleTriageWithCopilot}
      />
    </div>
  );
}
